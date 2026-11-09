# SPDX-FileCopyrightText: 2026 Qoro Quantum
# SPDX-License-Identifier: GPL-3.0-or-later

"""
Raw Sampling with MaestroBackend on Arbitrary Stim Circuits
===========================================================

MaestroBackend is designed to accept either Deltakit `Circuit` objects or
standard `stim.Circuit` objects. This script uses only Stim, demonstrating how
to sample, decode, and run distributed Sinter sweeps directly on any existing
Stim circuit without requiring Deltakit dependencies.

We use a distance-5 repetition code memory experiment as our testbed. Its noise
is all Pauli, so every run here is on Maestro's Stabilizer, which samples Pauli
noise exactly on Pauli frames. The same calls run coherent noise on a matrix
product state; see example_coherent_noise.py. Stim's own sampler is used only as
an independent reference.

Demonstrates:
    1. Bit-for-bit noiseless comparison against Stim.
    2. Inspecting structured output from `simulate()` (measurements, detection
       events, observable flips, and metadata).
    3. Deterministic, seeded sampling reproducibility.
    4. Manual batch decoding using PyMatching with the task's auto-generated
       Detector Error Model (DEM).
    5. Parallel parameter sweeping across noise rates using `sinter.collect()`.

Usage:
    pip install -e ".[examples]"    # from project root (deltakit-maestro/)
    python examples/example_stim_circuit.py
"""

import numpy as np
import pymatching
import sinter
import stim

from deltakit_maestro import MaestroBackend

# =============================================================================
# EXPERIMENT CONFIGURATION
# =============================================================================

DISTANCE = 5
ROUNDS = 5
SHOTS = 4000
SEED = 7
BASE_NOISE = 0.04  # High enough that logical errors occur within 4000 shots
NOISE_SWEEP = [0.01, 0.02, 0.04, 0.06]


# =============================================================================
# CIRCUIT BUILDER & DECODING HELPERS
# =============================================================================


def build_repetition_code(p: float) -> stim.Circuit:
    """Build a standard distance-5 repetition code memory circuit in Stim."""
    return stim.Circuit.generated(
        "repetition_code:memory",
        distance=DISTANCE,
        rounds=ROUNDS,
        after_clifford_depolarization=p,
        before_measure_flip_probability=p,
        after_reset_flip_probability=p,
    )


def compute_logical_error_rate(
    detector_error_model: stim.DetectorErrorModel,
    detection_events: np.ndarray,
    observable_flips: np.ndarray,
) -> tuple[float, float]:
    """Decode detection events using PyMatching and return (error_rate, standard_error)."""
    matcher = pymatching.Matching.from_detector_error_model(detector_error_model)
    predicted_observables = matcher.decode_batch(detection_events)
    failures = np.any(predicted_observables != observable_flips, axis=1)
    rate = float(failures.mean())
    std_err = float(np.sqrt(rate * (1 - rate) / len(failures)))
    return rate, std_err


# =============================================================================
# INDIVIDUAL STEP DEMONSTRATIONS
# =============================================================================


def step_1_noiseless_validation(backend: MaestroBackend, circuit: stim.Circuit):
    """Verify that the backend matches Stim measurement-by-measurement on a noiseless circuit."""
    print(f"\n{'─' * 70}")
    print("  1. Noiseless run against Stim's measurement record")
    print(f"{'─' * 70}")
    print("  When running with noise_type='none', all errors are stripped.")
    print(
        "  The measurement record must match Stim's noiseless execution bit-for-bit,\n"
        "  and zero detectors or observables should trigger.\n"
    )

    clean_result = backend.simulate(circuit, shots=5, noise_type="none", seed=SEED)
    stim_reference = circuit.without_noise().compile_sampler(seed=SEED).sample(5)

    is_identical = np.array_equal(clean_result.measurements.astype(bool), stim_reference)
    print(f"  measurement record identical to Stim's: {is_identical}")
    print(
        f"  detection events fired: {int(clean_result.detection_events.sum())}   "
        f"observable flips: {int(clean_result.observable_flips.sum())}"
    )


def step_2_simulate_api(backend: MaestroBackend, circuit: stim.Circuit):
    """Demonstrate the structured return values of backend.simulate()."""
    print(f"\n{'─' * 70}")
    print("  2. simulate(): measurements, detection events, observable flips")
    print(f"{'─' * 70}")
    print("  simulate() returns a SimulationResult containing three synchronized NumPy arrays:")
    print("    - measurements: raw physical measurement outcomes (shots x num_measurements)")
    print("    - detection_events: calculated detector triggers (shots x num_detectors)")
    print("    - observable_flips: logical observable outcomes (shots x num_observables)\n")

    result = backend.simulate(circuit, shots=SHOTS, seed=SEED)
    print(f"  measurements      {result.measurements.shape}  {result.measurements.dtype}")
    print(f"  detection_events  {result.detection_events.shape}  {result.detection_events.dtype}")
    print(f"  observable_flips  {result.observable_flips.shape}  {result.observable_flips.dtype}")
    print(f"  metadata          {result.metadata}")

    stim_detectors = circuit.compile_detector_sampler(seed=SEED).sample(100_000)
    print(
        f"  mean detection rate: Maestro {result.detection_events.mean():.4f}, "
        f"Stim (reference) {stim_detectors.mean():.4f}"
    )


def step_3_deterministic_seeding(backend: MaestroBackend, circuit: stim.Circuit):
    """Demonstrate reproducible sampling using random seeds."""
    print(f"\n{'─' * 70}")
    print("  3. Seeded sampling is reproducible")
    print(f"{'─' * 70}")
    print("  Specifying an integer seed guarantees identical pseudo-random sequences,")
    print("  essential for reproducible debugging and comparative benchmarks.\n")

    run_a = backend.simulate(circuit, shots=SHOTS, seed=SEED)
    run_b = backend.simulate(circuit, shots=SHOTS, seed=SEED)
    run_c = backend.simulate(circuit, shots=SHOTS, seed=SEED + 1)

    print(
        f"  same seed, same record:       {np.array_equal(run_a.measurements, run_b.measurements)}"
    )
    print(
        f"  different seed, same record:  {np.array_equal(run_a.measurements, run_c.measurements)}"
    )


def step_4_manual_decoding(backend: MaestroBackend, circuit: stim.Circuit):
    """Demonstrate decoding detection events using PyMatching against the DEM."""
    print(f"\n{'─' * 70}")
    print("  4. Decoding with PyMatching on the task's detector error model")
    print(f"{'─' * 70}")
    print("  backend.compile_sampler() packages the circuit and builds a matching")
    print("  Detector Error Model (DEM). We pass this DEM to PyMatching to decode batches.\n")

    sampler = backend.compile_sampler(circuit, seed=SEED)
    backend_dets, backend_obs = sampler.sample_detection_events(SHOTS)
    dem = sampler.task.detector_error_model

    stim_dets, stim_obs = circuit.compile_detector_sampler(seed=SEED).sample(
        SHOTS, separate_observables=True
    )

    for name, (dets, obs) in {
        "Maestro": (backend_dets, backend_obs),
        "Stim": (stim_dets, stim_obs),
    }.items():
        rate, err = compute_logical_error_rate(dem, dets, obs)
        print(f"  {name:<8} logical error rate {rate:.4f} ± {err:.4f}")

    print("\n  The DEM is the sampler task's own, so it matches the noise that is simulated.")


def step_5_sinter_parameter_sweep(backend: MaestroBackend):
    """Demonstrate distributed parameter sweeps across physical noise rates using Sinter."""
    print(f"\n{'─' * 70}")
    print("  5. sinter.collect over a noise sweep")
    print(f"{'─' * 70}")
    print("  Using backend.as_sinter_task() and backend.sinter_decoders(), Sinter can")
    print("  distribute sampling and decoding across multiple worker processes.\n")

    tasks = [
        backend.as_sinter_task(build_repetition_code(p), json_metadata={"p": p})
        for p in NOISE_SWEEP
    ]

    collected_stats = sinter.collect(
        num_workers=2,
        tasks=tasks,
        custom_decoders=backend.sinter_decoders(decoder="pymatching"),
        max_shots=SHOTS,
        max_batch_size=1000,
    )

    print(f"  {'p':>6} │ {'shots':>6} │ {'errors':>6} │ {'LER':>15}")
    print(f"  {'─' * 42}")
    for stat in sorted(collected_stats, key=lambda s: s.json_metadata["p"]):
        ler = stat.errors / stat.shots
        std_err = float(np.sqrt(ler * (1 - ler) / stat.shots))
        print(
            f"  {stat.json_metadata['p']:>6.3f} │ {stat.shots:>6} │ {stat.errors:>6} │ "
            f"{ler:.4f} ± {std_err:.4f}"
        )


# =============================================================================
# MAIN ENTRYPOINT
# =============================================================================


def main():
    backend = MaestroBackend()
    circuit = build_repetition_code(BASE_NOISE)

    print("=" * 70)
    print("  Any Stim circuit — MaestroBackend raw sampling")
    print("=" * 70)
    print(
        f"  Circuit:    d={DISTANCE} repetition code, {ROUNDS} rounds, {circuit.num_qubits} qubits"
    )
    print(
        f"  Record:     {circuit.num_measurements} measurements, "
        f"{circuit.num_detectors} detectors, {circuit.num_observables} observable"
    )
    print(f"  Backend:    {backend}")
    print(
        f"  Simulator:  Maestro {backend.config_for().simulation_type.name}"
        " (Pauli noise only, sampled on Pauli frames)"
    )

    # 1. Noiseless verification
    step_1_noiseless_validation(backend, circuit)

    # 2. simulate() outputs
    step_2_simulate_api(backend, circuit)

    # 3. Random seeds
    step_3_deterministic_seeding(backend, circuit)

    # 4. Standalone batch decoding
    step_4_manual_decoding(backend, circuit)

    # 5. Distributed noise sweep with Sinter
    step_5_sinter_parameter_sweep(backend)

    print("=" * 70)


if __name__ == "__main__":
    main()
