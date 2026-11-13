# SPDX-FileCopyrightText: 2026 Qoro Quantum
# SPDX-License-Identifier: GPL-3.0-or-later

"""
Custom Maestro NoiseModel — Per-Qubit Calibration, Crosstalk & Sinter
=====================================================================

`MaestroBackend` extracts uniform gate and readout error rates from a Stim or
Deltakit circuit so you do not have to construct a `maestro.NoiseModel` for
standard Pauli, T1, or uniform coherent-noise studies.

When modelling device-specific calibration data—such as a degraded "hot" qubit,
a noisy two-qubit coupler, asymmetric readout errors, directed coherent
over-rotations, or ZZ crosstalk—you can build a custom `maestro.NoiseModel`
and pass it directly to `maestro.sinter.MaestroCompiledSampler` or
`maestro.sinter.MaestroSinterSampler`.

Demonstrates:
    1. Seeding a `maestro.NoiseModel` from a Deltakit SI1000 surface-code
       circuit with `noise_params_from_stim()`, `strip_gate_noise()`, and
       `build_noise_model()`, then customizing individual qubits and couplers.
    2. Direct sampling and PyMatching decoding with `MaestroCompiledSampler`
       comparing uniform SI1000 against a hot qubit/coupler (Stabilizer) and
       adding directed coherent rotations + ZZ crosstalk (MPS).
    3. Multi-worker `sinter.collect` sweeps over custom `maestro.NoiseModel`
       configurations using `MaestroSinterSampler`.

Usage:
    pip install -e ".[examples]"    # from project root (deltakit-maestro/)
    python examples/example_custom_noise_model.py
"""

# Deltakit must be imported before pymatching: with pymatching 2.4 loaded
# first, Deltakit's circuit builders fail with "Caught an unknown exception!".
from deltakit.circuit.gates import PauliBasis
from deltakit.explorer.codes import RotatedPlanarCode, css_code_memory_circuit
from deltakit.explorer.qpu import QPU, SI1000Noise

# isort: split
import maestro
import numpy as np
import pymatching
import sinter
import stim
from maestro.sinter import MaestroCompiledSampler, MaestroSinterSampler

from deltakit_maestro import (
    MaestroBackend,
    build_noise_model,
    noise_params_from_stim,
    strip_gate_noise,
    to_stim,
)

# =============================================================================
# EXPERIMENT CONFIGURATION
# =============================================================================

BASE_P = 0.005  # Baseline SI1000 noise parameter
ROUNDS = 3
HOT_DATA_QUBIT = 0  # Degraded data qubit index
HOT_ANCILLA_QUBIT = 2  # Measure qubit coupled to HOT_DATA_QUBIT
HOT_COUPLER = (0, 2)  # Degraded two-qubit gate pair
PAULI_SHOTS = 4000
MPS_SHOTS = 300
SWEEP_SHOTS = 2000
HOT_SCALES = [1.0, 8.0, 20.0]
SEED = 7


# =============================================================================
# CIRCUIT & CUSTOM NOISE MODEL BUILDERS
# =============================================================================


def build_surface_code_base(p: float = BASE_P) -> tuple[stim.Circuit, stim.Circuit, dict]:
    """Build a d=3 rotated surface code and split its gate/readout noise out.

    Returns (original_noisy_circuit, stripped_circuit, extracted_rates).
    """
    code = RotatedPlanarCode(width=3, height=3)
    circuit = css_code_memory_circuit(code, num_rounds=ROUNDS, logical_basis=PauliBasis.Z)
    noisy = to_stim(
        QPU(circuit.qubits, noise_model=SI1000Noise(p=p)).compile_and_add_noise_to_circuit(circuit)
    )
    rates = noise_params_from_stim(noisy)
    # Strip gate depolarizing and measurement flips so the custom NoiseModel
    # supplies them without double-counting; idle and reset noise stay in `stripped`.
    stripped = strip_gate_noise(noisy, readout=True)
    return noisy, stripped, rates


def build_hot_qubit_model(
    stripped: stim.Circuit,
    rates: dict[str, float],
    hot_scale: float = 10.0,
    include_coherent_and_crosstalk: bool = False,
) -> maestro.NoiseModel:
    """Start from uniform SI1000 rates and override a degraded qubit and coupler."""
    nm = build_noise_model(stripped, "pauli", **rates)

    # Per-qubit and per-coupler Pauli + T1 + asymmetric readout overrides
    nm.set_1q_gate_depolarizing(HOT_DATA_QUBIT, rates["p_1q"] * hot_scale)
    nm.set_2q_depolarizing(*HOT_COUPLER, rates["p_2q"] * hot_scale)
    nm.set_t1(HOT_DATA_QUBIT, rates["p_2q"] * 0.5 * hot_scale)
    nm.set_readout_error(
        HOT_ANCILLA_QUBIT,
        p_meas1_prep0=rates["readout_error"] * 0.8,
        p_meas0_prep1=min(0.45, rates["readout_error"] * (1.0 + 0.15 * hot_scale)),
    )

    if include_coherent_and_crosstalk:
        # Non-Clifford hardware channels (require MatrixProductState simulation)
        nm.set_coherent_rotation(HOT_DATA_QUBIT, rx=0.08, ry=0.0, rz=0.16)
        nm.set_crosstalk(*HOT_COUPLER, strength=0.06)

    return nm


def decode_logical_error_rate(
    dem: stim.DetectorErrorModel,
    dets: np.ndarray,
    obs: np.ndarray,
) -> tuple[float, float]:
    """Decode detection events with PyMatching and return (lep, std_error)."""
    matcher = pymatching.Matching.from_detector_error_model(dem)
    predicted = matcher.decode_batch(dets)
    fails = np.any(predicted != obs, axis=1)
    rate = float(fails.mean())
    err = float(np.sqrt(rate * (1 - rate) / len(fails)))
    return rate, err


# =============================================================================
# STEP DEMONSTRATIONS
# =============================================================================


def step_1_inspect_custom_model(stripped: stim.Circuit, rates: dict[str, float]):
    """Build and inspect custom maestro.NoiseModel instances."""
    print(f"\n{'─' * 76}")
    print("  1. Building a custom maestro.NoiseModel on top of SI1000 base rates")
    print(f"{'─' * 76}")
    print("  strip_gate_noise(noisy, readout=True) removes gate depolarizing and M(p)")
    print("  flips so a custom maestro.NoiseModel can assign per-qubit and per-coupler")
    print("  channels while keeping SI1000's idle and reset noise inside the circuit.\n")

    pauli_hot = build_hot_qubit_model(stripped, rates, hot_scale=10.0)
    coherent_hot = build_hot_qubit_model(
        stripped, rates, hot_scale=10.0, include_coherent_and_crosstalk=True
    )

    print(f"  Base SI1000 rates:       {rates}")
    print(
        f"  Hot qubit / coupler:     q{HOT_DATA_QUBIT}, q{HOT_ANCILLA_QUBIT}, coupler {HOT_COUPLER}"
    )
    print(
        f"  Hot Pauli + T1 model:    has_1q={pauli_hot.has_1q_gate_noise()}, "
        f"has_2q={pauli_hot.has_any_2q_depolarizing()}, "
        f"has_t1={pauli_hot.has_t1()}, "
        f"has_readout={pauli_hot.has_readout_error()}"
    )
    print(
        f"  + Coherent & crosstalk:  has_coherent={coherent_hot.has_coherent()}, "
        f"has_crosstalk={coherent_hot.has_crosstalk()}"
    )


def step_2_direct_sampling(
    noisy: stim.Circuit,
    stripped: stim.Circuit,
    rates: dict[str, float],
):
    """Sample and decode custom NoiseModel runs via MaestroCompiledSampler."""
    print(f"\n{'─' * 76}")
    print("  2. Direct sampling and decoding with MaestroCompiledSampler")
    print(f"{'─' * 76}")
    print("  A standard decoder uses the baseline Detector Error Model (DEM) from the")
    print("  uniform circuit, while MaestroCompiledSampler executes the custom hardware")
    print("  NoiseModel on Stabilizer (Clifford + T1) or MatrixProductState (coherent).\n")

    dem = noisy.detector_error_model(decompose_errors=True)
    task = sinter.Task(circuit=stripped, detector_error_model=dem)
    backend = MaestroBackend(max_bond_dimension=32)

    runs = [
        (
            "Uniform SI1000 baseline",
            build_noise_model(stripped, "pauli", **rates),
            backend.config_for("pauli"),
            PAULI_SHOTS,
        ),
        (
            "Hot qubit + T1 + asym readout",
            build_hot_qubit_model(stripped, rates, hot_scale=10.0),
            backend.config_for("pauli", t1=rates["p_2q"]),
            PAULI_SHOTS,
        ),
        (
            "+ Coherent rot & ZZ crosstalk",
            build_hot_qubit_model(
                stripped, rates, hot_scale=10.0, include_coherent_and_crosstalk=True
            ),
            backend.config_for("coherent"),
            MPS_SHOTS,
        ),
    ]

    print(f"  {'model configuration':<31} │ {'simulator':<18} │ {'det. rate':>9} │ {'LEP':>15}")
    print(f"  {'─' * 74}")

    for label, noise_model, config, shots in runs:
        sampler = MaestroCompiledSampler(
            task,
            noise_model=noise_model,
            config=config,
            decoder="pymatching",
            seed=SEED,
        )
        dets, obs = sampler.sample_detection_events(shots)
        lep, err = decode_logical_error_rate(dem, dets, obs)
        sim_name = config.simulation_type.name
        print(f"  {label:<31} │ {sim_name:<18} │ {dets.mean():>9.4f} │ {lep:.4f} ± {err:.4f}")


def step_3_sinter_sweep(
    noisy: stim.Circuit,
    stripped: stim.Circuit,
    rates: dict[str, float],
):
    """Run a multi-worker Sinter sweep across custom NoiseModel instances."""
    print(f"\n{'─' * 76}")
    print("  3. Multi-worker sinter.collect with MaestroSinterSampler")
    print(f"{'─' * 76}")
    print("  MaestroSinterSampler wraps a custom NoiseModel as a Sinter Sampler so")
    print("  sinter.collect can distribute shots across worker processes.\n")

    dem = noisy.detector_error_model(decompose_errors=True)
    config = MaestroBackend().config_for("pauli", t1=rates["p_2q"])

    tasks = []
    custom_decoders = {}
    for scale in HOT_SCALES:
        decoder_key = f"maestro_hot_{scale:g}x"
        tasks.append(
            sinter.Task(
                circuit=stripped,
                detector_error_model=dem,
                decoder=decoder_key,
                json_metadata={"hot_scale": scale},
            )
        )
        custom_decoders[decoder_key] = MaestroSinterSampler(
            noise_model=build_hot_qubit_model(stripped, rates, hot_scale=scale),
            config=config,
            decoder="pymatching",
        )

    stats = sinter.collect(
        num_workers=2,
        tasks=tasks,
        custom_decoders=custom_decoders,
        max_shots=SWEEP_SHOTS,
        max_batch_size=500,
    )

    print(f"  {'hot_scale':>9} │ {'shots':>6} │ {'errors':>6} │ {'LER':>15}")
    print(f"  {'─' * 45}")
    for stat in sorted(stats, key=lambda s: s.json_metadata["hot_scale"]):
        scale = stat.json_metadata["hot_scale"]
        ler = stat.errors / stat.shots
        err = float(np.sqrt(ler * (1 - ler) / stat.shots))
        print(f"  {scale:>8.1f}x │ {stat.shots:>6} │ {stat.errors:>6} │ {ler:.4f} ± {err:.4f}")


# =============================================================================
# MAIN ENTRYPOINT
# =============================================================================


def main():
    noisy, stripped, rates = build_surface_code_base()

    print("=" * 76)
    print("  Custom maestro.NoiseModel — per-qubit calibration, crosstalk & Sinter")
    print("=" * 76)
    print(f"  Circuit:    d=3 rotated surface code ({stripped.num_qubits} qubits, {ROUNDS} rounds)")

    # 1. Build and inspect custom NoiseModel layers
    step_1_inspect_custom_model(stripped, rates)

    # 2. Direct sampling and decoding on Stabilizer and MPS
    step_2_direct_sampling(noisy, stripped, rates)

    # 3. Multi-worker Sinter sweep
    step_3_sinter_sweep(noisy, stripped, rates)

    print("=" * 76)


if __name__ == "__main__":
    main()
