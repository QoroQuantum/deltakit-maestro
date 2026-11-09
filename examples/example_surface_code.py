# SPDX-FileCopyrightText: 2026 Qoro Quantum
# SPDX-License-Identifier: GPL-3.0-or-later

"""
Surface Code QEC Benchmark — Riverlane Deltakit & Qoro MaestroBackend
=====================================================================

This benchmark combines Riverlane's Deltakit framework for designing topological
error correction codes with Qoro's MaestroBackend simulation engine.

We simulate a distance-3 rotated surface code memory experiment (17 physical qubits,
3 syndrome extraction rounds) under realistic superconducting QPU noise.

Demonstrates:
    1. Circuit Generation with SI1000 Noise:
       Using Deltakit's `RotatedPlanarCode` and `QPU` to build a surface code
       memory experiment compiled with superconducting hardware noise (SI1000).
    2. Direct Detection-Event Sampling & Decoding:
       Sampling detection events directly using `MaestroBackend.compile_sampler()`
       and decoding them with PyMatching (Minimum Weight Perfect Matching).
       SI1000 noise is all Pauli, so Maestro's stabilizer samples it on Pauli
       frames; results are checked against Stim's own sampler as a reference.
    3. Multi-Worker Sinter Sweeps:
       Distributing Monte Carlo sampling across multiple worker processes
       using `sinter.collect()` with backend tasks.
    4. Coherent Noise vs Pauli Twirl Comparison:
       Simulating genuine non-Clifford coherent over-rotations on the 17-qubit
       surface code lattice using Maestro's Matrix Product State (MPS) tensor
       network engine (bond dimension chi=32), compared to its Pauli twirl, which
       Maestro's stabilizer samples.

Usage:
    pip install -e ".[examples]"    # from project root (deltakit-maestro/)
    python examples/example_surface_code.py
"""

# Deltakit must be imported before pymatching: with pymatching 2.4 loaded
# first, Deltakit's circuit builders fail with "Caught an unknown exception!".
from deltakit.circuit.gates import PauliBasis
from deltakit.explorer.codes import RotatedPlanarCode, css_code_memory_circuit
from deltakit.explorer.qpu import QPU, SI1000Noise

# isort: split
import time
from typing import Any

import numpy as np
import pymatching
import sinter

from deltakit_maestro import MaestroBackend, to_stim

# =============================================================================
# EXPERIMENT CONFIGURATION
# =============================================================================

DISTANCE = 3  # Code distance (d=3 rotated surface code: 17 physical qubits)
NUM_ROUNDS = 3  # Number of syndrome extraction rounds
MPS_BOND_DIM = 32  # Maximum MPS bond dimension (chi) for coherent simulation
NOISE_STRENGTHS = [0.002, 0.005, 0.01]  # Physical noise parameter (p)
SHOTS = 20_000  # Shots per data point for Pauli runs (Pauli frames, fast)
COHERENT_SHOTS = 300  # Shots for MPS simulation (~60 ms/shot per core on 17 qubits)
SEED = 1234


# =============================================================================
# CIRCUIT BUILDER & DECODER UTILITIES
# =============================================================================


def build_noisy_surface_code(p: float):
    """Build a Deltakit distance-d rotated surface code memory circuit with SI1000(p) noise.

    SI1000 models a superconducting architecture with 1-qubit depolarizing,
    2-qubit depolarizing, measurement bit-flip error, and data qubit idle noise.
    """
    code = RotatedPlanarCode(width=DISTANCE, height=DISTANCE)
    circuit = css_code_memory_circuit(code, num_rounds=NUM_ROUNDS, logical_basis=PauliBasis.Z)
    qpu = QPU(circuit.qubits, noise_model=SI1000Noise(p=p))
    return qpu.compile_and_add_noise_to_circuit(circuit)


def decode_with_pymatching(
    dem: Any,
    detection_events: np.ndarray,
    observable_flips: np.ndarray,
) -> tuple[float, float]:
    """Decode detection events using Minimum Weight Perfect Matching (MWPM).

    Returns (logical_error_rate, standard_error).
    """
    matcher = pymatching.Matching.from_detector_error_model(dem)
    predicted_flips = matcher.decode_batch(detection_events)
    failures = np.any(predicted_flips != observable_flips, axis=1)
    logical_error_rate = float(failures.mean())
    std_error = float(np.sqrt(logical_error_rate * (1 - logical_error_rate) / len(failures)))
    return logical_error_rate, std_error


def format_error_rate(rate_err: tuple[float, float]) -> str:
    """Format an error rate and its standard error as '0.XXXX ± 0.XXXX'."""
    return f"{rate_err[0]:.4f} ± {rate_err[1]:.4f}"


# =============================================================================
# BENCHMARK PHASES
# =============================================================================


def phase_1_direct_sampling(backend: MaestroBackend, circuits: dict[float, Any]):
    """Demonstrate direct detection-event sampling and PyMatching decoding, checked against Stim."""
    print(f"\n{'─' * 70}")
    print("  1. Direct sampling + PyMatching: Logical Error Probability (LEP)")
    print(f"{'─' * 70}")
    print("  SI1000 noise is all Pauli, so Maestro's stabilizer samples it on Pauli frames.")
    print("  It is checked against Stim's own sampler on the same circuit, decoded with the")
    print("  same DEM; the two agree to within sampling error.\n")

    print(f"  {'p':>6} │ {'Maestro':>15} │ {'Stim SI1000 (ref)':>17} │ {'Maestro time':>12}")
    print(f"  {'─' * 60}")

    for p, noisy_circuit in circuits.items():
        start_time = time.time()
        sampler = backend.compile_sampler(noisy_circuit, noise_type="pauli", seed=SEED)
        maestro_dets, maestro_obs = sampler.sample_detection_events(SHOTS)
        elapsed = time.time() - start_time

        dem = sampler.task.detector_error_model
        maestro_lep = decode_with_pymatching(dem, maestro_dets, maestro_obs)

        # Independent reference: Stim's sampler on the exact same circuit
        stim_circuit = to_stim(noisy_circuit)
        stim_dets, stim_obs = stim_circuit.compile_detector_sampler(seed=SEED).sample(
            SHOTS, separate_observables=True
        )
        stim_lep = decode_with_pymatching(dem, stim_dets, stim_obs)

        print(
            f"  {p:>6.3f} │ "
            f"{format_error_rate(maestro_lep):>15} │ "
            f"{format_error_rate(stim_lep):>17} │ "
            f"{elapsed:>11.1f}s"
        )


def phase_2_sinter_sweep(backend: MaestroBackend, circuits: dict[float, Any]):
    """Demonstrate parallel Monte Carlo sampling over a noise sweep using Sinter."""
    print(f"\n{'─' * 70}")
    print("  2. sinter.collect (Pauli noise on Maestro's Pauli frames, PyMatching)")
    print(f"{'─' * 70}")
    print("  Distributing tasks across 4 worker processes via Sinter.")
    print("  Each worker compiles and samples tasks independently.\n")

    tasks = [
        backend.as_sinter_task(noisy_circuit, json_metadata={"p": p})
        for p, noisy_circuit in circuits.items()
    ]

    start_time = time.time()
    collected_stats = sinter.collect(
        num_workers=4,
        tasks=tasks,
        custom_decoders=backend.sinter_decoders(decoder="pymatching"),
        max_shots=SHOTS,
        max_batch_size=500,
    )
    total_elapsed = time.time() - start_time

    print(f"  {'p':>6} │ {'shots':>6} │ {'errors':>6} │ {'LER':>15}")
    print(f"  {'─' * 42}")
    for stat in sorted(collected_stats, key=lambda s: s.json_metadata["p"]):
        ler = stat.errors / stat.shots
        err = np.sqrt(ler * (1 - ler) / stat.shots)
        print(
            f"  {stat.json_metadata['p']:>6.3f} │ {stat.shots:>6} │ {stat.errors:>6} │ {ler:.4f} ± {err:.4f}"
        )
    print(f"  ({total_elapsed:.1f}s on 4 workers)")


def phase_3_coherent_vs_twirl(backend: MaestroBackend, circuits: dict[float, Any]):
    """Simulate coherent unitary over-rotations on the surface code lattice using MPS."""
    print(f"\n{'─' * 70}")
    print("  3. Coherent noise (Maestro MPS) vs its Pauli twirl (Maestro stabilizer), same DEM")
    print(f"{'─' * 70}")
    print("  Coherent mode replaces gate depolarization with unitary over-rotations.")
    print(f"  Simulated via Matrix Product States (MPS) with bond dimension chi={MPS_BOND_DIM}.")
    print("  Both coherent runs and twirled runs are decoded using the twirl's DEM.\n")

    print(f"  {'p':>6} │ {'Maestro coherent':>16} │ {'Pauli twirl':>16} │ {'coherent time':>13}")
    print(f"  {'─' * 60}")

    for p, noisy_circuit in circuits.items():
        start_time = time.time()
        coherent_sampler = backend.compile_sampler(noisy_circuit, noise_type="coherent", seed=SEED)
        coherent_dets, coherent_obs = coherent_sampler.sample_detection_events(COHERENT_SHOTS)
        elapsed = time.time() - start_time

        dem = coherent_sampler.task.detector_error_model
        coherent_lep = decode_with_pymatching(dem, coherent_dets, coherent_obs)

        # Build the twirled circuit and sample it on Maestro's stabilizer
        twirled_circuit = backend.twirled_circuit(noisy_circuit, noise_type="coherent")
        twirl_sampler = backend.compile_sampler(twirled_circuit, seed=SEED)
        twirl_dets, twirl_obs = twirl_sampler.sample_detection_events(SHOTS)
        twirl_lep = decode_with_pymatching(dem, twirl_dets, twirl_obs)

        print(
            f"  {p:>6.3f} │ "
            f"{format_error_rate(coherent_lep):>16} │ "
            f"{format_error_rate(twirl_lep):>16} │ "
            f"{elapsed:>12.1f}s"
        )


# =============================================================================
# MAIN ENTRYPOINT
# =============================================================================


def main():
    n_qubits = 2 * DISTANCE**2 - 1

    print("=" * 70)
    print("  Surface Code QEC Benchmark — MaestroBackend & Deltakit")
    print("=" * 70)
    print(f"  Code:          d={DISTANCE} rotated surface code ({n_qubits} physical qubits)")
    print(f"  Rounds:        {NUM_ROUNDS} syndrome extraction rounds")
    print(f"  Simulator:     Maestro Stabilizer (Pauli), Maestro MPS chi={MPS_BOND_DIM} (coherent)")
    print(f"  Shots:         {SHOTS} per Pauli point, {COHERENT_SHOTS} per coherent point")

    backend = MaestroBackend(max_bond_dimension=MPS_BOND_DIM)
    circuits = {p: build_noisy_surface_code(p) for p in NOISE_STRENGTHS}

    # 1. Direct sampling & decoding compared to Stim
    phase_1_direct_sampling(backend, circuits)

    # 2. Parallel Sinter sweep
    phase_2_sinter_sweep(backend, circuits)

    # 3. Coherent over-rotations vs Pauli twirling
    phase_3_coherent_vs_twirl(backend, circuits)

    print(f"\n{'=' * 70}")
    print("  Notes:")
    print("    - Pauli runs: SI1000's noise is all Pauli, so Maestro's stabilizer samples")
    print("      it exactly on Pauli frames. Coherent runs need its MPS simulator, since")
    print("      no Clifford simulator can run a coherent over-rotation.")
    print("    - Coherence Gap: Coherent mode replaces gate noise with unitary")
    print("      over-rotations while retaining idle, reset, and readout noise.")
    print("      Any divergence from the twirl column reveals coherent interference.")
    print("=" * 70)


if __name__ == "__main__":
    main()
