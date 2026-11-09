# SPDX-FileCopyrightText: 2026 Qoro Quantum
# SPDX-License-Identifier: GPL-3.0-or-later

"""
Noise Translation
==================

Deltakit noise → ``maestro.NoiseModel``, and back to Stim for the decoder.

Maestro executes Stim's in-circuit Pauli noise (``DEPOLARIZE1/2``,
``X/Y/Z_ERROR``, ``PAULI_CHANNEL_1/2``) and measurement flips (``M(p)``)
natively. A ``maestro.NoiseModel`` supplies hardware noise layers (coherent
over-rotations, ``T1`` decay) or replaces the circuit's *gate* noise: the
depolarizing after gates, which ``strip_gate_noise`` takes out of the circuit.
Idle, reset and measurement noise stay in the circuit. The rates it finds map
onto the model:

    DEPOLARIZE2(p) after 2-qubit gates → ``set_2q_depolarizing`` per pair
    DEPOLARIZE1(p) after 1-qubit gates → ``set_all_1q_gate_depolarizing``
    M(p) measurement flips             → ``set_all_readout_error`` (overrides only)

``pauli_twirl_circuit`` goes the other way: it writes the Pauli twirl of
those layers back into the Stim circuit, so the decoder's detector error
model describes the noise Maestro actually simulates.
"""

from __future__ import annotations

import math
import warnings
from collections import Counter

import maestro
import stim

NOISE_TYPES = ("pauli", "coherent", "full", "none")
NOISE_KEYS = ("p_1q", "p_2q", "readout_error", "t1", "coherent")

_MEASUREMENTS = {"M", "MZ", "MX", "MY", "MR", "MRZ", "MRX", "MRY"}


def noise_params_from_stim(noisy: stim.Circuit) -> dict[str, float]:
    """Read the gate and readout error rates out of a noisy Stim circuit.

    The gate rates are those of the depolarizing that ``strip_gate_noise``
    removes. Warns if the circuit has several rates for one of them, since a
    single rate replaces them all.

    Returns:
        ``{'p_1q', 'p_2q', 'readout_error'}``, ready to splat into
        ``build_noise_model``.
    """
    _, gate_rates = _split_gate_noise(noisy)
    readout = {
        inst.gate_args_copy()[0]
        for inst in noisy.flattened()
        if inst.name in _MEASUREMENTS and inst.gate_args_copy()
    }
    params = {
        "p_1q": _dominant(gate_rates[1]),
        "p_2q": _dominant(gate_rates[2]),
        "readout_error": max(readout, default=0.0),
    }
    for name, key, rates in (
        ("single-qubit gate", "p_1q", set(gate_rates[1])),
        ("two-qubit gate", "p_2q", set(gate_rates[2])),
        ("measurement flip", "readout_error", readout),
    ):
        if len(rates) > 1:
            warnings.warn(
                f"Circuit has several {name} rates {sorted(rates)}; using {params[key]} everywhere",
                stacklevel=2,
            )
    return params


def _dominant(rates: Counter) -> float:
    """The rate that follows the most gates, the larger on a tie, 0 if none."""
    return max(rates, key=lambda p: (rates[p], p), default=0.0)


def strip_gate_noise(noisy: stim.Circuit, readout: bool = False) -> stim.Circuit:
    """``noisy`` without the depolarizing that follows its gates.

    A ``DEPOLARIZE1`` or ``DEPOLARIZE2`` target is gate noise if its qubit's
    latest operation was a gate of the same arity that no noise has followed
    yet. Deltakit puts it after the next ``TICK``, merged with the idle noise
    of the other qubits, so the targets of one instruction are split: gate
    noise goes, idle noise stays. Resets, measurements and every other noise
    channel stay too. Returns a flattened circuit.

    Args:
        noisy: The Stim circuit.
        readout: Also remove measurement flips ``M(p)``, for when a
            ``NoiseModel`` supplies the readout error instead.
    """
    return _split_gate_noise(noisy, readout)[0]


def _split_gate_noise(
    noisy: stim.Circuit,
    readout: bool = False,
) -> tuple[stim.Circuit, dict[int, Counter]]:
    """``strip_gate_noise``'s circuit, and the rates it stripped by arity."""
    out = stim.Circuit()
    rates: dict[int, Counter] = {1: Counter(), 2: Counter()}
    # qubit -> partner of its latest unfollowed gate (-1 for a 1-qubit gate)
    pending: dict[int, int] = {}
    for inst in noisy.flattened():
        name, targets = inst.name, inst.targets_copy()
        args = inst.gate_args_copy()
        gate = stim.gate_data(name)

        if name in ("DEPOLARIZE1", "DEPOLARIZE2"):
            arity = 1 if name == "DEPOLARIZE1" else 2
            kept = []
            for i in range(0, len(targets), arity):
                group = targets[i : i + arity]
                qubits = [t.value for t in group]
                partners = qubits[::-1] if arity == 2 else [-1]
                if all(pending.get(q) == partner for q, partner in zip(qubits, partners)):
                    for q in qubits:
                        del pending[q]
                    rates[arity][args[0]] += 1
                else:
                    kept += group
            if kept:
                out.append(name, kept, args)
            continue

        if name in _MEASUREMENTS and args and readout:
            out.append(name, targets)
        else:
            out.append(inst)

        if gate.is_unitary and name != "I":
            arity = 2 if gate.is_two_qubit_gate else 1
            for i in range(0, len(targets), arity):
                qubits = [t.value for t in targets[i : i + arity]]
                partners = qubits[::-1] if arity == 2 else [-1]
                pending.update(zip(qubits, partners))
        elif gate.is_unitary or gate.is_reset or gate.produces_measurements:
            for t in targets:
                if t.is_qubit_target:
                    pending.pop(t.value, None)
    return out, rates


def build_noise_model(
    circuit: stim.Circuit,
    noise_type: str = "pauli",
    *,
    p_1q: float = 0.0,
    p_2q: float = 0.0,
    readout_error: float = 0.0,
    t1: float = 0.0,
    coherent: float | None = None,
) -> maestro.NoiseModel:
    """Build a ``maestro.NoiseModel`` for ``circuit``.

    Args:
        circuit: Stim circuit; supplies the qubit count and the two-qubit
            gate pairs that carry two-qubit depolarizing.
        noise_type: How gate errors are realised. ``'pauli'``: stochastic
            depolarizing. ``'coherent'``: isotropic coherent over-rotations
            (ε = 2·arcsin√p about a body diagonal after every gate).
            ``'full'``: both. ``'none'``: no noise at all.
        p_1q: Depolarizing probability after single-qubit gates.
        p_2q: Two-qubit depolarizing probability after two-qubit gates.
        readout_error: Symmetric measurement flip probability.
        t1: Per-gate ``T1`` decay probability γ. ``DensityMatrix`` and
            ``MatrixProductOperator`` apply amplitude damping γ; every other
            simulation type resets the qubit to |0⟩ with probability γ.
        coherent: Infidelity of the coherent over-rotation, applied per qubit
            after every gate, one- or two-qubit. Defaults to ``p_2q``.
    """
    if noise_type not in NOISE_TYPES:
        raise ValueError(f"noise_type must be one of {NOISE_TYPES}, got {noise_type!r}")
    nm = maestro.NoiseModel()
    if noise_type == "none":
        return nm

    n = circuit.num_qubits
    if noise_type in ("pauli", "full"):
        if p_1q:
            nm.set_all_1q_gate_depolarizing(n, p_1q)
        if p_2q:
            for a, b in _two_qubit_pairs(circuit):
                nm.set_2q_depolarizing(a, b, p_2q)
    p_coh = _coherent_rate(noise_type, p_2q, coherent)
    if p_coh:
        nm.set_all_coherent_depolarizing(n, p_coh)
    if readout_error:
        nm.set_all_readout_error(n, readout_error)
    if t1:
        nm.set_all_t1(n, t1)
    return nm


def pauli_twirl_circuit(
    circuit: stim.Circuit,
    noise_type: str = "pauli",
    *,
    p_1q: float = 0.0,
    p_2q: float = 0.0,
    readout_error: float = 0.0,
    t1: float = 0.0,
    coherent: float | None = None,
    amplitude_damping: bool = False,
) -> stim.Circuit:
    """``circuit`` plus the Pauli twirl of ``build_noise_model``'s layers.

    Takes the same arguments as ``build_noise_model`` and places each channel
    where Maestro injects it: after every gate except ``I``, which Maestro
    runs as an idle. The circuit's own Stim noise is kept. The twirl is exact
    for the Pauli layers; the coherent over-rotation twirls to
    ``DEPOLARIZE1(coherent)``. ``T1`` decay γ twirls to
    ``PAULI_CHANNEL_1(γ/4, γ/4, γ/4)``, the reset to |0⟩ with probability γ
    that Maestro's pure-state simulation types run.

    Args:
        amplitude_damping: Twirl ``T1`` as amplitude damping γ instead, to
            ``PAULI_CHANNEL_1(γ/4, γ/4, (1-√(1-γ))²/4)``, as ``DensityMatrix``
            and ``MatrixProductOperator`` simulate it.
    """
    if noise_type not in NOISE_TYPES:
        raise ValueError(f"noise_type must be one of {NOISE_TYPES}, got {noise_type!r}")
    pauli = noise_type in ("pauli", "full")
    p_coh = _coherent_rate(noise_type, p_2q, coherent)
    if noise_type == "none" or not (pauli and (p_1q or p_2q) or p_coh or readout_error or t1):
        return circuit.copy()
    if amplitude_damping:
        t1_channel = [t1 / 4, t1 / 4, (1 - math.sqrt(1 - t1)) ** 2 / 4]
    else:
        t1_channel = [t1 / 4] * 3

    out = stim.Circuit()
    for inst in circuit.flattened():
        name, targets, args = inst.name, inst.targets_copy(), inst.gate_args_copy()
        if name in _MEASUREMENTS and readout_error:
            # Maestro composes its readout flip after the measurement's own.
            own = args[0] if args else 0.0
            out.append(name, targets, own + readout_error - 2 * own * readout_error)
            continue
        gate = stim.gate_data(name)
        if not gate.is_unitary or name == "I":
            out.append(inst)
            continue
        # Maestro injects noise after each gate, so split the instruction.
        arity = 2 if gate.is_two_qubit_gate else 1
        for i in range(0, len(targets), arity):
            group = targets[i : i + arity]
            out.append(name, group, args)
            if pauli and arity == 1 and p_1q:
                out.append("DEPOLARIZE1", group, p_1q)
            if pauli and arity == 2 and p_2q:
                out.append("DEPOLARIZE2", group, p_2q)
            if p_coh:
                out.append("DEPOLARIZE1", group, p_coh)
            if t1:
                out.append("PAULI_CHANNEL_1", group, t1_channel)
    return out


def _coherent_rate(noise_type: str, p_2q: float, coherent: float | None) -> float:
    if noise_type not in ("coherent", "full"):
        return 0.0
    return p_2q if coherent is None else coherent


def _two_qubit_pairs(circuit: stim.Circuit) -> set[tuple[int, int]]:
    pairs = set()
    for inst in circuit.flattened():
        gate = stim.gate_data(inst.name)
        if gate.is_unitary and gate.is_two_qubit_gate:
            qubits = [t.value for t in inst.targets_copy()]
            pairs.update(zip(qubits[::2], qubits[1::2]))
    return pairs
