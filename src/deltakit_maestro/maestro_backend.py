# SPDX-FileCopyrightText: 2026 Qoro Quantum
# SPDX-License-Identifier: GPL-3.0-or-later

"""
Maestro Backend
================

Runs Deltakit QEC circuits on Qoro's Maestro simulator via ``maestro.sinter``.

Maestro executes Stim's in-circuit Pauli channels and measurement flips
directly, while ``maestro.NoiseModel`` supplies hardware noise layers
(isotropic coherent over-rotations, ``T1`` decay) or rate overrides. The
decoder gets the detector error model of the Pauli twirl of whatever is
simulated. A run without coherent noise is Clifford and runs on Maestro's
stabilizer simulator, which samples Pauli noise on Pauli frames; coherent
noise runs on a matrix product state:

    deltakit Circuit ──as_stim_circuit()──▶ noisy stim.Circuit
        ├─ noisy (or strip_gate_noise()) → executed by Maestro
        ├─ noise_params_from_stim()   → rates for maestro.NoiseModel layers
        └─ pauli_twirl_circuit()      → DEM for the decoder

Example::

    from deltakit_maestro import MaestroBackend

    backend = MaestroBackend(max_bond_dimension=32)
    result = backend.simulate(noisy_circuit, shots=1000, noise_type='coherent')
    result.detection_events     # (1000, n_detectors) bool

    sampler = backend.compile_sampler(noisy_circuit)
    dets, obs = sampler.sample_detection_events(1000)

    stats = sinter.collect(
        tasks=[backend.as_sinter_task(noisy_circuit)],
        custom_decoders=backend.sinter_decoders(),
        num_workers=4, max_shots=10_000,
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import maestro
import numpy as np
import sinter
import stim
from maestro.sinter import MaestroCompiledSampler

from .noise import (
    NOISE_KEYS,
    NOISE_TYPES,
    build_noise_model,
    noise_params_from_stim,
    pauli_twirl_circuit,
    strip_gate_noise,
)

# Decoder name that ``as_sinter_task`` tasks carry; ``sinter_decoders()``
# maps it to the Maestro sampler.
SINTER_DECODER = "maestro"

_PAULI_KEYS = {"p_1q", "p_2q", "readout_error"}

# Simulation types that run T1 as amplitude damping; the rest reset the qubit.
_AMPLITUDE_DAMPING_TYPES = (
    maestro.SimulationType.DensityMatrix,
    maestro.SimulationType.MatrixProductOperator,
)

# Noise keywords that a noise_type never reads.
_UNUSED_KEYS = {
    "pauli": {"coherent"},
    "coherent": {"p_1q"},
    "full": set(),
    "none": set(NOISE_KEYS),
}


@dataclass
class SimulationResult:
    """Output of ``MaestroBackend.simulate``.

    Attributes:
        measurements: ``(shots, num_measurements)`` uint8, Stim record order.
        detection_events: ``(shots, num_detectors)`` bool.
        observable_flips: ``(shots, num_observables)`` bool.
        metadata: Backend, shot count and the noise parameters used.
    """

    measurements: np.ndarray
    detection_events: np.ndarray
    observable_flips: np.ndarray
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def num_measurements(self) -> int:
        """Measurements in each shot's record."""
        return self.measurements.shape[1]


def to_stim(circuit: Any) -> stim.Circuit:
    """Deltakit ``Circuit`` (or anything Stim-like) → native ``stim.Circuit``."""
    if hasattr(circuit, "as_stim_circuit"):
        circuit = circuit.as_stim_circuit()
    # Deltakit hands back its own Stim polyfill; round-trip through text.
    return circuit if isinstance(circuit, stim.Circuit) else stim.Circuit(str(circuit))


class MaestroBackend:
    """Maestro simulator backend for Deltakit circuits.

    Args:
        simulator_type: Maestro engine; ``SimulatorType.Gpu`` for GPU.
        simulation_type: ``Stabilizer``, ``MatrixProductState``,
            ``Statevector``, ``TensorNetwork``, ... ``None`` (default) picks
            per run: ``Stabilizer`` unless the run has coherent noise, then
            ``MatrixProductState``. ``Stabilizer`` samples Pauli noise on
            Pauli frames; ``T1`` decay, which is not a Pauli channel, it runs
            shot by shot. Any other value runs everything with that type.
        max_bond_dimension: MPS/TTN bond dimension χ.
        **config: Further ``maestro.SimulatorConfig`` fields, except ``seed``:
            pass that to ``simulate`` or ``compile_sampler``, since under
            ``sinter.collect`` every worker would draw the same shots.
            ``fixed_backend`` defaults to ``True``, so the simulation type
            above is the one that runs; ``False`` lets Maestro replace it,
            e.g. sample a Clifford circuit on Pauli frames instead of an MPS.

    Noise keyword arguments (``p_1q``, ``p_2q``, ``readout_error``, ``t1``,
    ``coherent``) on the methods below override or extend the rates read
    from the circuit; see ``build_noise_model``.
    """

    def __init__(
        self,
        simulator_type: maestro.SimulatorType = maestro.SimulatorType.QCSim,
        simulation_type: maestro.SimulationType | None = None,
        max_bond_dimension: int = 32,
        **config,
    ):
        if "seed" in config:
            raise ValueError(
                "Pass seed= to simulate() or compile_sampler(), not to "
                "MaestroBackend: every sinter.collect worker would share it"
            )
        self.simulator_type = simulator_type
        self.simulation_type = simulation_type
        self.max_bond_dimension = max_bond_dimension
        self.extra_config = config
        self.config_for("pauli")  # Reject bad SimulatorConfig fields now.

    def config_for(self, noise_type: str = "pauli", **noise) -> maestro.SimulatorConfig:
        """The ``maestro.SimulatorConfig`` a run with this noise uses.

        A run is Clifford, so ``Stabilizer``, unless it has coherent noise. For
        ``'coherent'`` and ``'full'`` the strength is ``coherent``, else the
        circuit's ``p_2q``. Without either keyword that rate is unknown here,
        so it is taken to be nonzero and the answer is ``MatrixProductState``;
        the sampler itself knows the circuit and decides exactly.

        The type is pinned (``fixed_backend=True``) unless ``fixed_backend``
        was passed to the backend: unpinned, Maestro runs any Clifford circuit
        on Pauli frames whatever the type, so a noiseless MPS check of χ would
        never see truncation. A pinned ``Stabilizer`` still uses frames.
        """
        simulation_type = self.simulation_type
        if simulation_type is None:
            strength = noise.get("coherent", noise.get("p_2q"))
            clifford = noise_type not in ("coherent", "full") or strength == 0
            simulation_type = (
                maestro.SimulationType.Stabilizer
                if clifford
                else maestro.SimulationType.MatrixProductState
            )
        return maestro.SimulatorConfig(
            simulator_type=self.simulator_type,
            simulation_type=simulation_type,
            max_bond_dimension=self.max_bond_dimension,
            **{"fixed_backend": True, **self.extra_config},
        )

    def as_sinter_task(
        self,
        circuit: Any,
        noise_type: str = "pauli",
        json_metadata: dict | None = None,
        **noise,
    ) -> sinter.Task:
        """Circuit + matching DEM as a ``sinter.Task``.

        For ``'pauli'`` and ``'full'`` without explicit Pauli overrides
        (``p_1q``, ``p_2q``, ``readout_error``), the noisy Stim circuit is kept
        intact so Maestro executes its in-circuit Pauli channels and measurement
        flips directly. Otherwise the gate noise is stripped (``strip_gate_noise``)
        and the ``NoiseModel`` replaces it; idle, reset and measurement noise
        stay in the circuit. The
        ``NoiseModel`` layers travel in ``json_metadata['noise']`` so the
        sampler can rebuild them in each worker.

        The DEM is that of ``twirled_circuit``, so the decoder knows the noise
        that is simulated. For ``'none'`` there is no such noise and the input
        circuit's own DEM is used. The DEM is decomposed into graphlike errors
        for matching decoders where it can be; where it can't, as for
        bivariate bicycle codes, it is left whole for decoders such as BP-OSD.
        """
        noisy = to_stim(circuit)
        task_circuit, params = _plan(noisy, noise_type, noise)
        dem_circuit = noisy if noise_type == "none" else self._twirl(task_circuit, params)
        try:
            dem = dem_circuit.detector_error_model(decompose_errors=True)
        except ValueError:
            dem = dem_circuit.detector_error_model()
        return sinter.Task(
            circuit=task_circuit,
            detector_error_model=dem if len(dem) else None,
            decoder=SINTER_DECODER,
            json_metadata={**(json_metadata or {}), "noise": params},
        )

    def twirled_circuit(
        self,
        circuit: Any,
        noise_type: str = "pauli",
        **noise,
    ) -> stim.Circuit:
        """Stim circuit carrying the Pauli twirl of the noise that is simulated.

        Its DEM is the one ``as_sinter_task`` gives the decoder. Sampling it
        (``simulate`` or ``compile_sampler`` with the default ``'pauli'``, which
        runs a circuit's own noise as it is) gives the Pauli-twirled baseline to
        compare a coherent run against. For ``'pauli'`` without overrides it is
        the input circuit.
        """
        task_circuit, params = _plan(to_stim(circuit), noise_type, noise)
        return self._twirl(task_circuit, params)

    def compile_sampler(
        self,
        circuit: Any,
        noise_type: str = "pauli",
        decoder: str | sinter.Decoder | None = "pymatching",
        seed: int | None = None,
        **noise,
    ) -> MaestroCompiledSampler:
        """``MaestroCompiledSampler`` for measurement or detection-event sampling.

        ``decoder`` is compiled against the task's DEM and used by
        ``.sample()``; ``.sample_detection_events()`` and
        ``.sample_measurements()`` ignore it. Pass ``decoder='vacuous'`` (or
        ``None``) for undecoded logical error statistics. Shots come back in
        random order, so any slice of them is a fair sample.
        """
        task = self.as_sinter_task(circuit, noise_type, **noise)
        return self._sampler(task, decoder, seed)

    def simulate(
        self,
        circuit: Any,
        shots: int,
        noise_type: str = "pauli",
        seed: int | None = None,
        **noise,
    ) -> SimulationResult:
        """Run ``shots`` and return raw measurements plus detection events."""
        task = self.as_sinter_task(circuit, noise_type, **noise)
        measurements = self._sampler(task, None, seed).sample_measurements(shots)
        dets, obs = task.circuit.compile_m2d_converter().convert(
            measurements=measurements, separate_observables=True
        )
        return SimulationResult(
            measurements=measurements.astype(np.uint8),
            detection_events=dets,
            observable_flips=obs,
            metadata={
                "backend": type(self).__name__,
                "shots": shots,
                "noise": task.json_metadata["noise"],
            },
        )

    def sinter_decoders(
        self,
        decoder: str | sinter.Decoder | None = "pymatching",
    ) -> dict[str, sinter.Sampler]:
        """``custom_decoders=`` for ``sinter.collect`` over ``as_sinter_task`` tasks."""
        return {SINTER_DECODER: _SinterSampler(self, decoder)}

    def _sampler(
        self,
        task: sinter.Task,
        decoder: str | sinter.Decoder | None,
        seed: int | None,
    ) -> MaestroCompiledSampler:
        meta = task.json_metadata
        params = meta.get("noise", {}) if isinstance(meta, dict) else {}
        return MaestroCompiledSampler(
            task,
            noise_model=_noise_model_for_task(task),
            config=self.config_for(**_layers(params)),
            decoder="vacuous" if decoder is None else decoder,
            seed=seed,
        )

    def _twirl(self, task_circuit: stim.Circuit, params: dict[str, Any]) -> stim.Circuit:
        amplitude_damping = self.simulation_type in _AMPLITUDE_DAMPING_TYPES
        return pauli_twirl_circuit(
            task_circuit, **_layers(params), amplitude_damping=amplitude_damping
        )

    def __repr__(self) -> str:
        simulation_type = "auto" if self.simulation_type is None else repr(self.simulation_type)
        return (
            f"MaestroBackend(simulator_type={self.simulator_type!r}, "
            f"simulation_type={simulation_type}, "
            f"max_bond_dimension={self.max_bond_dimension})"
        )


class _SinterSampler(sinter.Sampler):
    """Builds each task's sampler the way ``compile_sampler`` does, per worker."""

    def __init__(self, backend: MaestroBackend, decoder: str | sinter.Decoder | None):
        self.backend = backend
        self.decoder = decoder

    def compiled_sampler_for_task(self, task: sinter.Task) -> sinter.CompiledSampler:
        # Seeded sinter.collect is unsupported: workers can't split seed streams.
        return self.backend._sampler(task, self.decoder, None)


def _plan(
    noisy: stim.Circuit,
    noise_type: str,
    noise: dict[str, float],
) -> tuple[stim.Circuit, dict[str, Any]]:
    """The circuit Maestro runs and the ``NoiseModel`` layers added to it.

    ``params['stim_noise']`` says whether the circuit keeps all of its own
    Stim noise; the other entries are ``build_noise_model`` arguments. When it
    doesn't, only the gate noise (and an overridden readout error) is removed
    and the ``NoiseModel`` supplies its replacement; idle, reset and
    measurement noise stay in the circuit.
    """
    if noise_type not in NOISE_TYPES:
        raise ValueError(f"noise_type must be one of {NOISE_TYPES}, got {noise_type!r}")
    unknown = noise.keys() - set(NOISE_KEYS)
    if unknown:
        raise TypeError(f"Unknown noise keywords {sorted(unknown)}; expected {NOISE_KEYS}")
    unused = noise.keys() & _UNUSED_KEYS[noise_type]
    if unused:
        raise ValueError(f"{sorted(unused)} have no effect with noise_type={noise_type!r}")

    keep = noise_type in ("pauli", "full") and not (_PAULI_KEYS & noise.keys())
    if noise_type == "none":
        layers, task_circuit = {}, noisy.without_noise()
    elif keep:
        # The circuit's Stim noise is the Pauli layer; the NoiseModel only adds
        # coherent and T1 noise on top, the coherent strength defaulting to p_2q.
        layers, task_circuit = dict(noise), noisy
        if noise_type == "full" and "coherent" not in noise:
            layers["coherent"] = noise_params_from_stim(noisy)["p_2q"]
    else:
        # The NoiseModel replaces the gate noise, and the readout error only if
        # overridden; the circuit's M(p) already carries it otherwise.
        rates = noise_params_from_stim(noisy)
        layers = {"p_1q": rates["p_1q"], "p_2q": rates["p_2q"], **noise}
        task_circuit = strip_gate_noise(noisy, readout="readout_error" in noise)
    return task_circuit, {"noise_type": noise_type, "stim_noise": keep, **layers}


def _layers(params: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in params.items() if k != "stim_noise"}


def _noise_model_for_task(task: sinter.Task) -> maestro.NoiseModel | None:
    """Build the supplementary ``maestro.NoiseModel`` for a ``sinter.Task``."""
    meta = task.json_metadata
    if not isinstance(meta, dict) or "noise" not in meta:
        return None
    nm = build_noise_model(task.circuit, **_layers(meta["noise"]))
    return nm if nm.has_any() else None
