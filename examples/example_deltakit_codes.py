# SPDX-FileCopyrightText: 2026 Qoro Quantum
# SPDX-License-Identifier: GPL-3.0-or-later

"""
Deltakit Codes — every code family through MaestroBackend
==========================================================

Deltakit builds memory experiments for several code families. Each runs through
MaestroBackend unchanged, and its logical error probability (LEP) is decoded against
the task's detector error model. SI1000 noise is all Pauli, so Maestro's stabilizer
samples these runs exactly on Pauli frames; coherent noise moves a run to a matrix
product state, and T1 decay to the stabilizer shot by shot.

Demonstrates:
    1. Repetition, rotated and unrotated planar, and toric codes, decoded with
       PyMatching against the task's detector error model.
    2. A bivariate bicycle qLDPC code, [[72,12,6]]. Its errors are not graphlike, so
       matching does not apply; it is decoded with BP-OSD from ``ldpc``, which
       Deltakit installs.

Stability experiments and ``use_iswap_gates=True`` need a Deltakit cloud ``client``,
so they are not shown. Coherent noise needs MPS, whose cost depends strongly on the
code; see ``example_bond_dimension.py``.

Usage:
    pip install -e ".[examples]"    # from the project root (deltakit-maestro/)
    python examples/example_deltakit_codes.py
"""

# Deltakit must be imported before pymatching: with pymatching 2.4 loaded
# first, Deltakit's circuit builders fail with "Caught an unknown exception!".
from deltakit.circuit.gates import PauliBasis
from deltakit.explorer.codes import (
    BivariateBicycleCode,
    RepetitionCode,
    RotatedPlanarCode,
    UnrotatedPlanarCode,
    UnrotatedToricCode,
    css_code_memory_circuit,
)
from deltakit.explorer.qpu import QPU, SI1000Noise

# isort: split
import time

import numpy as np
import pymatching
import scipy.sparse
import stim
from ldpc import BpOsdDecoder

from deltakit_maestro import MaestroBackend, to_stim

# =============================================================================
# CONFIGURATION
# =============================================================================

P = 0.003  # SI1000 noise strength
ROUNDS = 3
SHOTS = 20_000  # Shots per matching-decoded code; Pauli frames and PyMatching are fast
BB_SHOTS = 1000  # BP-OSD takes ~12 ms a shot here, so fewer
SEED = 1

CODES = {
    "Repetition d=5": RepetitionCode(5),
    "Rotated planar d=3": RotatedPlanarCode(3, 3),
    "Rotated planar d=5": RotatedPlanarCode(5, 5),
    "Unrotated planar d=3": UnrotatedPlanarCode(3, 3),
    "Toric d=3": UnrotatedToricCode(3, 3),
}
# x^3 + y + y^2 and y^3 + x + x^2 on a 6x6 torus, from arXiv:2308.07915.
BB_CODE = BivariateBicycleCode(param_l=6, param_m=6, m_A_powers=[3, 1, 2], m_B_powers=[3, 1, 2])


# =============================================================================
# HELPERS
# =============================================================================


def memory_circuit(code) -> stim.Circuit:
    """Z-basis memory experiment on ``code`` with SI1000(P) noise, as Stim."""
    circuit = css_code_memory_circuit(code, num_rounds=ROUNDS, logical_basis=PauliBasis.Z)
    return to_stim(
        QPU(circuit.qubits, noise_model=SI1000Noise(p=P)).compile_and_add_noise_to_circuit(circuit)
    )


def lep(fails: np.ndarray) -> tuple[float, float]:
    rate = fails.mean()
    return rate, np.sqrt(rate * (1 - rate) / len(fails))


def matching_fails(dem, dets: np.ndarray, obs: np.ndarray) -> np.ndarray:
    predicted = pymatching.Matching.from_detector_error_model(dem).decode_batch(dets)
    return np.any(predicted != obs, axis=1)


class BpOsd:
    """BP-OSD on a detector error model: one column per error, one row per detector."""

    def __init__(self, dem: stim.DetectorErrorModel):
        checks, observables, priors = [], [], []
        for inst in dem.flattened():
            if inst.type != "error":
                continue
            column = len(priors)
            priors.append(inst.args_copy()[0])
            for t in inst.targets_copy():
                if t.is_relative_detector_id():
                    checks.append((t.val, column))
                elif t.is_logical_observable_id():
                    observables.append((t.val, column))
        self.checks = _matrix(checks, (dem.num_detectors, len(priors)))
        self.observables = _matrix(observables, (dem.num_observables, len(priors)))
        self.decoder = BpOsdDecoder(
            self.checks,
            error_channel=priors,
            max_iter=30,
            bp_method="product_sum",
            osd_method="osd0",
        )

    def fails(self, dets: np.ndarray, obs: np.ndarray) -> np.ndarray:
        errors = np.array([self.decoder.decode(d.astype(np.uint8)) for d in dets])
        predicted = (errors @ self.observables.T) % 2
        return np.any(predicted != obs, axis=1)


def _matrix(entries, shape) -> scipy.sparse.csc_matrix:
    rows, cols = zip(*entries) if entries else ((), ())
    return scipy.sparse.csc_matrix((np.ones(len(rows), dtype=np.uint8), (rows, cols)), shape=shape)


def cell(rate_err: tuple[float, float]) -> str:
    return f"{rate_err[0]:.4f} ± {rate_err[1]:.4f}"


def row(name, circuit, simulator, decoder, lep_err, seconds_per_shot) -> str:
    return (
        f"  {name:<21} │ {circuit.num_qubits:>3} │ {circuit.num_detectors:>4} │ {simulator:<10} │ "
        f"{decoder:<10} │ {cell(lep_err):>15} │ {seconds_per_shot * 1e6:>7.1f}"
    )


def simulator_of(sampler) -> str:
    return sampler.config.simulation_type.name


# =============================================================================
# MAIN
# =============================================================================


def main():
    backend = MaestroBackend()

    print("=" * 94)
    print(
        f"  Deltakit codes through MaestroBackend — SI1000(p={P}), {ROUNDS} rounds, Z-basis memory"
    )
    print("=" * 94)
    print(f"  {SHOTS} shots per code ({BB_SHOTS} for the qLDPC code), decoded with the task's DEM")
    print(
        f"\n  {'code':<21} │ {'qb':>3} │ {'dets':>4} │ {'simulator':<10} │ {'decoder':<10} │ "
        f"{'LEP':>15} │ µs/shot"
    )
    print(f"  {'─' * 90}")

    # -------------------------------------------------------------------------
    # 1. Matching-decoded codes
    # -------------------------------------------------------------------------
    for name, code in CODES.items():
        circuit = memory_circuit(code)
        t0 = time.time()
        sampler = backend.compile_sampler(circuit, seed=SEED)
        dets, obs = sampler.sample_detection_events(SHOTS)
        seconds_per_shot = (time.time() - t0) / SHOTS
        fails = matching_fails(sampler.task.detector_error_model, dets, obs)
        print(row(name, circuit, simulator_of(sampler), "PyMatching", lep(fails), seconds_per_shot))

    # -------------------------------------------------------------------------
    # 2. A qLDPC code: its DEM is not graphlike, so BP-OSD instead of matching
    # -------------------------------------------------------------------------
    circuit = memory_circuit(BB_CODE)
    t0 = time.time()
    sampler = backend.compile_sampler(circuit, decoder=None, seed=SEED)
    dets, obs = sampler.sample_detection_events(BB_SHOTS)
    seconds_per_shot = (time.time() - t0) / BB_SHOTS
    bposd = BpOsd(sampler.task.detector_error_model)
    name = f"BB [[{BB_CODE.n},{BB_CODE.k},6]]"
    print(
        row(
            name,
            circuit,
            simulator_of(sampler),
            "BP-OSD",
            lep(bposd.fails(dets, obs)),
            seconds_per_shot,
        )
    )
    print(f"  {'':<21}   {BB_CODE.k} logical qubits: a shot fails if any observable is wrong.")

    print(f"\n{'=' * 94}")
    print("  Notes:")
    print("    - µs/shot is sampling only; decoding is extra. These runs have Pauli noise")
    print("      only, which the stabilizer samples on Pauli frames.")
    print("    - The DEM is decomposed into graphlike errors for matching where possible and")
    print("      left whole otherwise; that is what lets the qLDPC code run at all.")
    print("    - The same calls take coherent rotations (MPS) and T1 decay (stabilizer, shot")
    print("      by shot), e.g. backend.compile_sampler(circuit, t1=1e-3).")
    print("=" * 94)


if __name__ == "__main__":
    main()
