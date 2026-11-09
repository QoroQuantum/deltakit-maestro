# SPDX-FileCopyrightText: 2026 Qoro Quantum
# SPDX-License-Identifier: GPL-3.0-or-later

"""
Coherent Noise vs Its Pauli Twirl — Simulating What Stim Cannot
==============================================================

Physical quantum hardware suffers from coherent errors, such as systematic gate
over-rotations and calibration drift. Unlike Pauli channels (X, Y, Z flips),
coherent errors preserve quantum phases and allow error amplitudes to interfere
constructively across rounds of error correction.

Because coherent errors are non-Clifford operations, Clifford tableau simulators
like Stim cannot simulate them directly. Standard practice replaces coherent
rotations with their "Pauli twirl" — an average Pauli depolarizing channel with
the same average gate infidelity.

With Maestro's Matrix Product State (MPS) simulator, we can simulate the genuine
coherent rotations and directly measure the "coherence penalty" against the twirl,
which Maestro's stabilizer samples on Pauli frames.

This script demonstrates:
    1. Constructing a repetition code circuit with parameterized gate noise.
    2. Simulating genuine coherent over-rotations using Maestro MPS.
    3. Simulating the corresponding Pauli twirl on Maestro's stabilizer.
    4. Decoding both with the exact same twirl-matched Detector Error Model (DEM).
    5. Quantifying the logical error rate gap and detection event ratio.

Usage:
    pip install -e ".[examples]"    # from project root (deltakit-maestro/)
    python examples/example_coherent_noise.py
"""

import time

import numpy as np
import pymatching
import stim

from deltakit_maestro import MaestroBackend

# =============================================================================
# EXPERIMENT CONFIGURATION
# =============================================================================

DISTANCE = 3  # d=3 repetition code
ROUNDS = [3, 9]  # Memory rounds (short vs long duration)
NOISE_STRENGTHS = [0.01, 0.03]  # Physical gate infidelity levels
COHERENT_SHOTS = 8000  # Shots for Maestro MPS simulation (~seconds)
TWIRL_SHOTS = 200_000  # Shots for the Pauli twirl (Pauli frames, fast)
SEED = 1


# =============================================================================
# CIRCUIT GENERATION & DECODING
# =============================================================================


def repetition_code(p: float, rounds: int) -> stim.Circuit:
    """Generate a distance-3 repetition code memory circuit with gate noise only.

    Restricting noise to gate depolarization ensures that switching to
    noise_type='coherent' replaces all circuit noise with coherent over-rotations.
    """
    return stim.Circuit.generated(
        "repetition_code:memory",
        distance=DISTANCE,
        rounds=rounds,
        after_clifford_depolarization=p,
    )


def compute_logical_error_rate(
    matcher: pymatching.Matching,
    detection_events: np.ndarray,
    observable_flips: np.ndarray,
) -> tuple[float, float]:
    """Decode detection events with PyMatching and return (error_rate, standard_error)."""
    predicted_observables = matcher.decode_batch(detection_events)
    failures = np.any(predicted_observables != observable_flips, axis=1)
    logical_error_rate = float(failures.mean())
    standard_error = float(np.sqrt(logical_error_rate * (1 - logical_error_rate) / len(failures)))
    return logical_error_rate, standard_error


# =============================================================================
# MAIN BENCHMARK
# =============================================================================


def main():
    backend = MaestroBackend()
    coherent_type = backend.config_for("coherent").simulation_type.name
    twirl_type = backend.config_for("pauli").simulation_type.name

    print("=" * 78)
    print("  Coherent noise vs its Pauli twirl — d=3 repetition code")
    print("=" * 78)
    print(f"  Coherent:   {COHERENT_SHOTS} shots per point, Maestro {coherent_type}")
    print(f"  Twirl:      {TWIRL_SHOTS} shots per point, Maestro {twirl_type} (Pauli frames)")
    print("  Decoder:    PyMatching using the twirl's Detector Error Model")
    print("\n  Physical Context:")
    print("    - Coherent noise applies an isotropic rotation after each gate.")
    print("    - The Pauli twirl replaces this rotation with DEPOLARIZE1(p).")
    print("    - When amplitudes add coherently, errors accumulate faster than")
    print("      the twirled random walk predicts.")

    print(
        f"\n  {'p':>5} {'rounds':>6} │ {'coherent LEP':>16} │ {'twirl LEP':>16} │ "
        f"{'LEP ratio':>9} │ {'det. ratio':>10} │ {'time':>5}"
    )
    print(f"  {'─' * 80}")

    for p in NOISE_STRENGTHS:
        for rounds in ROUNDS:
            circuit = repetition_code(p, rounds)

            # -----------------------------------------------------------------
            # 1. Simulate Coherent Over-Rotations via Maestro MPS
            # -----------------------------------------------------------------
            start_time = time.time()
            coherent_sampler = backend.compile_sampler(circuit, noise_type="coherent", seed=SEED)
            coherent_dets, coherent_obs = coherent_sampler.sample_detection_events(COHERENT_SHOTS)
            elapsed_time = time.time() - start_time

            # -----------------------------------------------------------------
            # 2. Build Twirled Baseline Circuit & Simulate on Maestro's Stabilizer
            # -----------------------------------------------------------------
            # Both runs are decoded using the same detector error model (the twirl's DEM).
            matcher = pymatching.Matching.from_detector_error_model(
                coherent_sampler.task.detector_error_model
            )
            twirled_circuit = backend.twirled_circuit(circuit, noise_type="coherent")
            twirl_sampler = backend.compile_sampler(twirled_circuit, seed=SEED)
            twirl_dets, twirl_obs = twirl_sampler.sample_detection_events(TWIRL_SHOTS)

            # -----------------------------------------------------------------
            # 3. Decode & Calculate Statistics
            # -----------------------------------------------------------------
            coherent_lep, coherent_err = compute_logical_error_rate(
                matcher, coherent_dets, coherent_obs
            )
            twirl_lep, twirl_err = compute_logical_error_rate(matcher, twirl_dets, twirl_obs)

            lep_ratio = coherent_lep / twirl_lep if twirl_lep > 0 else float("nan")
            det_ratio = (
                coherent_dets.mean() / twirl_dets.mean() if twirl_dets.mean() > 0 else float("nan")
            )

            print(
                f"  {p:>5.2f} {rounds:>6} │ "
                f"{coherent_lep:.4f} ± {coherent_err:.4f} │ "
                f"{twirl_lep:.4f} ± {twirl_err:.4f} │ "
                f"{lep_ratio:>9.2f} │ "
                f"{det_ratio:>10.2f} │ "
                f"{elapsed_time:>4.0f}s"
            )

    print(f"\n{'=' * 78}")
    print("  Key Takeaways:")
    print("    - Coherence Penalty: Ratios above 1.0 reveal that coherent rotations")
    print("      produce significantly higher logical error rates than their twirls.")
    print("    - Detection Ratio: The mean detection-event rate is a low-variance proxy")
    print("      for syndrome activity. Coherent amplitudes trigger noticeably more detections.")
    print("    - Decoder Mismatch: Standard decoders assume independent Pauli faults.")
    print("      Physical coherent errors violate this assumption, degrading threshold fidelity.")
    print("=" * 78)


if __name__ == "__main__":
    main()
