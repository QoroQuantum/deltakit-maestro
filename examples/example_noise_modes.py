# SPDX-FileCopyrightText: 2026 Qoro Quantum
# SPDX-License-Identifier: GPL-3.0-or-later

"""
Noise Modes — Understanding How MaestroBackend Handles Circuit Noise
====================================================================

In quantum error correction (QEC) workflows, noise is typically embedded
directly inside a Stim circuit (e.g. as DEPOLARIZE1, DEPOLARIZE2, or X_ERROR).

With Deltakit-Maestro, you do not need to manually build a `maestro.NoiseModel`.
Instead, `MaestroBackend` inspects the circuit, identifies gate and readout error
rates, and picks Maestro's simulation type: Stabilizer for runs without coherent
noise (Pauli noise is sampled on Pauli frames, T1 decay shot by shot), and Matrix
Product State for coherent noise.

This script demonstrates:
    1. Noise Extraction & Stripping:
       How MaestroBackend identifies gate noise and separates it from idle,
       reset, and readout noise remaining in the circuit.
    2. Available Noise Modes & Simulation Types:
       What each `noise_type` ('pauli', 'coherent', 'full', 'none') and keyword
       override does, and which Maestro simulation type runs it.
    3. Round-Trip Verification:
       Demonstrating that stripping gate noise and replacing it with Maestro's
       NoiseModel reproduces the exact detection event rates of the original circuit,
       checked against Stim's own sampler.
    4. Fast-Fail Validation:
       Confirming that invalid noise parameters fail immediately before launching
       expensive sampling tasks.

Usage:
    pip install -e ".[examples]"    # from project root (deltakit-maestro/)
    python examples/example_noise_modes.py
"""

# Deltakit must be imported before pymatching: with pymatching 2.4 loaded
# first, Deltakit's circuit builders fail with "Caught an unknown exception!".
from collections import Counter
from dataclasses import dataclass
from typing import Any

import stim
from deltakit.circuit.gates import PauliBasis
from deltakit.explorer.codes import RotatedPlanarCode, css_code_memory_circuit
from deltakit.explorer.qpu import QPU, SI1000Noise

from deltakit_maestro import MaestroBackend, noise_params_from_stim, strip_gate_noise, to_stim

# =============================================================================
# CIRCUITS UNDER TEST
# =============================================================================


def si1000_circuit(p: float = 0.01) -> stim.Circuit:
    """Build a Deltakit distance-3 rotated surface code memory circuit with SI1000 noise.

    SI1000 represents a superconducting architecture noise model with 1-qubit gate
    depolarization, 2-qubit gate depolarization, readout errors, and idle noise.
    """
    code = RotatedPlanarCode(width=3, height=3)
    circuit = css_code_memory_circuit(code, num_rounds=3, logical_basis=PauliBasis.Z)
    noisy_qpu = QPU(circuit.qubits, noise_model=SI1000Noise(p=p))
    compiled_circuit = noisy_qpu.compile_and_add_noise_to_circuit(circuit)
    return to_stim(compiled_circuit)


def stim_circuit() -> stim.Circuit:
    """Build a standard Stim distance-3 rotated surface code circuit.

    Uses distinct, explicit error probabilities for each noise source:
    gate noise, before-round idle noise, reset flip probability, and measurement flip.
    """
    return stim.Circuit.generated(
        "surface_code:rotated_memory_z",
        distance=3,
        rounds=3,
        after_clifford_depolarization=0.01,
        before_round_data_depolarization=0.02,
        after_reset_flip_probability=0.03,
        before_measure_flip_probability=0.04,
    )


def noise_summary(circuit: stim.Circuit) -> str:
    """Summarize noise channels present in a Stim circuit along with target counts."""
    counts: Counter = Counter()
    for inst in circuit.flattened():
        args = inst.gate_args_copy()
        is_noise_instruction = (
            inst.name.startswith(("DEPOLARIZE", "PAULI_CHANNEL"))
            or inst.name.endswith("_ERROR")
            or (inst.name in ("M", "MR") and args)
        )
        if is_noise_instruction:
            formatted_args = ",".join(f"{a:g}" for a in args)
            channel_name = f"{inst.name}({formatted_args})"
            counts[channel_name] += len(inst.targets_copy())

    summary = "  ".join(f"{name}×{n}" for name, n in sorted(counts.items()))
    return summary or "(none)"


def mean_detection_rate(circuit: stim.Circuit, shots: int, seed: int, **noise: Any) -> float:
    """Simulate a circuit on Maestro and return the average fraction of triggered detectors."""
    result = MaestroBackend().simulate(circuit, shots=shots, seed=seed, **noise)
    return float(result.detection_events.mean())


# =============================================================================
# DEMONSTRATION HELPERS
# =============================================================================


@dataclass
class NoiseScenario:
    """A test configuration representing a simulation mode and parameter set."""

    noise_type: str
    noise_kwargs: dict[str, Any]
    purpose: str


def run_section_1_noise_extraction(circuits: dict[str, stim.Circuit]):
    """Demonstrate how MaestroBackend separates gate noise from circuit noise."""
    print(f"\n{'─' * 78}")
    print("  1. Gate noise is split from idle, reset and readout noise")
    print(f"{'─' * 78}")
    print("  Stim circuits embed noise directly inside instructions. When Maestro")
    print("  replaces or modifies gate noise (e.g. for parameter sweeps or coherent")
    print("  errors), it strips the gate noise from the circuit and handles it via")
    print("  Maestro's NoiseModel. Idle, reset, and readout errors stay in the circuit.\n")

    for name, circuit in circuits.items():
        extracted_rates = noise_params_from_stim(circuit)
        original_noise = noise_summary(circuit)
        stripped_circuit = strip_gate_noise(circuit)
        stripped_noise = noise_summary(stripped_circuit)

        print(f"  {name}")
        print(f"    rates:     {extracted_rates}")
        print(f"    circuit:   {original_noise}")
        print(f"    stripped:  {stripped_noise}\n")

    print("  Stripped keeps everything the NoiseModel does not replace. Gate noise is the")
    print("  depolarizing after a gate; Deltakit merges it with idle noise, so those are")
    print("  split per qubit. The Stim circuit's 'before round' noise follows a CX, so it stays.")


def run_section_2_noise_modes(si1000_circuit_instance: stim.Circuit):
    """Demonstrate each noise_type, parameter overrides, and the simulation type used."""
    backend = MaestroBackend()

    print(f"\n{'─' * 78}")
    print("  2. What each mode runs (SI1000 circuit)")
    print(f"{'─' * 78}")
    print("  MaestroBackend supports four primary noise modes:")
    print("    - 'pauli': Standard Pauli errors, sampled exactly on Maestro's Pauli frames.")
    print("    - 'coherent': Unitary rotation errors, requiring Maestro's Matrix Product States.")
    print("    - 'full': Combined Pauli and coherent errors, simulated via MPS.")
    print("    - 'none': Strips all noise for noiseless baseline verification.\n")

    scenarios = [
        NoiseScenario(
            noise_type="pauli",
            noise_kwargs={},
            purpose="Default baseline: Maestro runs the circuit as-is with its original noise.",
        ),
        NoiseScenario(
            noise_type="pauli",
            noise_kwargs={"p_2q": 0.02},
            purpose="Override 2-qubit gate error to 0.02: existing gate noise stripped, a NoiseModel supplies the new rate.",
        ),
        NoiseScenario(
            noise_type="pauli",
            noise_kwargs={"readout_error": 0.1},
            purpose="Override measurement error to 0.1: the circuit's readout flips replaced by the new rate.",
        ),
        NoiseScenario(
            noise_type="pauli",
            noise_kwargs={"t1": 0.002},
            purpose="Add T1 decay, a sampled reset: not a Pauli channel, so the Stabilizer runs it shot by shot.",
        ),
        NoiseScenario(
            noise_type="coherent",
            noise_kwargs={},
            purpose="Unitary over-rotations: automatically switches to Maestro's MatrixProductState.",
        ),
        NoiseScenario(
            noise_type="coherent",
            noise_kwargs={"coherent": 0.005},
            purpose="Coherent noise with custom rotation angle override.",
        ),
        NoiseScenario(
            noise_type="full",
            noise_kwargs={},
            purpose="Combined Pauli and coherent noise channels simulated under MatrixProductState.",
        ),
        NoiseScenario(
            noise_type="none",
            noise_kwargs={},
            purpose="Noiseless execution: all noise stripped, used for baseline checks and syndrome validation.",
        ),
    ]

    for scenario in scenarios:
        task = backend.as_sinter_task(
            si1000_circuit_instance, scenario.noise_type, **scenario.noise_kwargs
        )
        noise_layers = {
            k: v
            for k, v in task.json_metadata["noise"].items()
            if k not in ("noise_type", "stim_noise")
        }
        simulation_type = backend.config_for(
            scenario.noise_type, **scenario.noise_kwargs
        ).simulation_type
        simulator = f"Maestro {simulation_type.name}"
        dem_errors = task.detector_error_model.num_errors if task.detector_error_model else 0

        label = (
            f"{scenario.noise_type}, {scenario.noise_kwargs}"
            if scenario.noise_kwargs
            else scenario.noise_type
        )

        print(f"\n  {label}")
        print(f"    circuit simulated:     {noise_summary(task.circuit)}")
        print(f"    NoiseModel layers:     {noise_layers or '(none)'}")
        print(f"    simulator:             {simulator}")
        print(f"    decoder DEM errors:    {dem_errors}")


def run_section_3_fidelity_verification(circuits: dict[str, stim.Circuit]):
    """Verify that stripping and re-injecting noise reproduces original circuit results."""
    print(f"\n{'─' * 78}")
    print("  3. Overriding with a circuit's own gate rates reproduces the circuit")
    print(f"{'─' * 78}")
    print("  This comparison verifies round-trip fidelity across three execution paths:")
    print("    1. Stim reference: direct sampling from the native Stim circuit.")
    print("    2. Maestro as-is: Maestro running the circuit without modifying gate noise.")
    print("    3. Maestro own rates: Maestro strips gate noise from the circuit and delegates")
    print("       it to Maestro's NoiseModel. Close agreement confirms exact translation.")
    print("  Stim's own sampler is the independent reference.\n")

    print(f"  {'circuit':<26} │ {'Stim':>7} │ {'Maestro as-is':>13} │ {'Maestro, own rates':>18}")
    print(f"  {'─' * 72}")

    for name, circuit in circuits.items():
        rates = noise_params_from_stim(circuit)
        # 1. Native Stim reference rate
        stim_rate = circuit.compile_detector_sampler(seed=1).sample(50_000).mean()
        # 2. Maestro without stripping gate noise
        as_is_rate = mean_detection_rate(circuit, shots=3000, seed=1)
        # 3. Maestro stripping gate noise and re-applying via NoiseModel
        own_rates = mean_detection_rate(
            circuit,
            shots=3000,
            seed=1,
            p_1q=rates["p_1q"],
            p_2q=rates["p_2q"],
        )
        print(f"  {name:<26} │ {stim_rate:>7.4f} │ {as_is_rate:>13.4f} │ {own_rates:>18.4f}")

    print("\n  Mean detection-event rate. In the last column the gate noise runs through a")
    print("  NoiseModel while idle, reset and readout noise stay in the circuit.")


def run_section_4_bad_arguments(si1000_circuit_instance: stim.Circuit):
    """Demonstrate immediate upfront validation of invalid noise options."""
    backend = MaestroBackend()

    print(f"\n{'─' * 78}")
    print("  4. Bad noise arguments fail before sampling")
    print(f"{'─' * 78}")
    print("  In large QEC experiments with Sinter, invalid configurations must fail")
    print("  immediately before allocating worker processes or running shots.\n")

    invalid_configurations = [
        ("pauli", {"p2q": 0.01}, "Typo in keyword argument ('p2q' instead of 'p_2q')"),
        (
            "pauli",
            {"coherent": 0.01},
            "Incompatible noise parameter (coherent noise cannot run under Pauli)",
        ),
        (
            "none",
            {"t1": 0.01},
            "Contradictory options (requested noiseless 'none' but provided t1 noise)",
        ),
        ("depolarizing", {}, "Unrecognized noise_type name"),
    ]

    for noise_type, noise_kwargs, reason in invalid_configurations:
        try:
            backend.as_sinter_task(si1000_circuit_instance, noise_type, **noise_kwargs)
        except (TypeError, ValueError) as error:
            print(f"  {noise_type!r}, {noise_kwargs}  # {reason}")
            print(f"    {type(error).__name__}: {error}")


# =============================================================================
# MAIN ENTRYPOINT
# =============================================================================


def main():
    circuits = {
        "Deltakit SI1000(p=0.01)": si1000_circuit(),
        "Stim-generated": stim_circuit(),
    }
    si1000 = circuits["Deltakit SI1000(p=0.01)"]

    print("=" * 78)
    print("  Noise modes — MaestroBackend reads the noise from the Stim circuit")
    print("=" * 78)

    # 1. Noise extraction and gate noise separation
    run_section_1_noise_extraction(circuits)

    # 2. Noise modes and the simulation type each uses
    run_section_2_noise_modes(si1000)

    # 3. Round-trip fidelity validation
    run_section_3_fidelity_verification(circuits)

    # 4. Input validation and error handling
    run_section_4_bad_arguments(si1000)

    print(f"\n{'=' * 78}")
    print("  A custom maestro.NoiseModel is not accepted by MaestroBackend; use")
    print("  maestro.sinter.MaestroCompiledSampler directly for that.")
    print("=" * 78)


if __name__ == "__main__":
    main()
