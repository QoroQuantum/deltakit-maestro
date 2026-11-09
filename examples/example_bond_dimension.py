# SPDX-FileCopyrightText: 2026 Qoro Quantum
# SPDX-License-Identifier: GPL-3.0-or-later

"""
Bond Dimension — choosing χ for coherent runs and checking it
==============================================================

Coherent noise is not Clifford, so Maestro simulates it with a matrix product state
(MPS) of bond dimension χ. Too small a χ truncates the state, and truncation shows up
as extra detection events: the same direction as the coherent-noise effect a study is
looking for. So χ has to be checked, not assumed.

Demonstrates:
    1. Setting χ, and forcing MPS for a run that would otherwise run on Maestro's
       stabilizer simulator.
    2. The noiseless check: with no noise every detector is silent, so a detection
       event in a noiseless MPS run is truncation error. It needs no reference and
       few shots. A rotated d=3 code passes at χ=8; an unrotated d=3 code fails at
       every χ shown.
    3. That the noiseless check is necessary but not sufficient: coherent noise
       needs a larger χ, found by raising χ until the result stops changing. Too
       small a χ inflates the very coherent effect being measured.

Usage:
    pip install -e ".[examples]"    # from the project root (deltakit-maestro/)
    python examples/example_bond_dimension.py
"""

import time

import maestro
import numpy as np
import stim

# Deltakit must be imported before pymatching: with pymatching 2.4 loaded
# first, Deltakit's circuit builders fail with "Caught an unknown exception!".
from deltakit.circuit.gates import PauliBasis
from deltakit.explorer.codes import RotatedPlanarCode, UnrotatedPlanarCode, css_code_memory_circuit
from deltakit.explorer.qpu import QPU, SI1000Noise

from deltakit_maestro import MaestroBackend, to_stim

MPS = maestro.SimulationType.MatrixProductState


# =============================================================================
# CONFIGURATION
# =============================================================================

P = 0.01
ROUNDS = 3
NOISELESS_CHIS = [4, 8, 16, 32]
NOISELESS_SHOTS = 50  # One spurious detection event is enough to fail
COHERENT_CHIS = [8, 16, 32, 64]
COHERENT_SHOTS = 400
SEED = 1


# =============================================================================
# HELPERS
# =============================================================================


def memory_circuit(code) -> stim.Circuit:
    circuit = css_code_memory_circuit(code, num_rounds=ROUNDS, logical_basis=PauliBasis.Z)
    return to_stim(
        QPU(circuit.qubits, noise_model=SI1000Noise(p=P)).compile_and_add_noise_to_circuit(circuit)
    )


def detection_rate(dets: np.ndarray) -> tuple[float, float]:
    """Mean detection-event rate, with its error from the spread between shots."""
    per_shot = dets.mean(axis=1)
    return per_shot.mean(), per_shot.std(ddof=1) / np.sqrt(len(per_shot))


# =============================================================================
# MAIN
# =============================================================================


def main():
    codes = {
        "Rotated planar d=3": memory_circuit(RotatedPlanarCode(3, 3)),
        "Unrotated planar d=3": memory_circuit(UnrotatedPlanarCode(3, 3)),
    }

    print("=" * 74)
    print("  Bond dimension — choosing χ for coherent runs and checking it")
    print("=" * 74)

    # -------------------------------------------------------------------------
    # 1. Setting χ
    # -------------------------------------------------------------------------
    print(f"\n{'─' * 74}")
    print("  1. Setting χ")
    print(f"{'─' * 74}")
    backend = MaestroBackend(max_bond_dimension=64)
    config = backend.config_for("coherent")
    print("  MaestroBackend(max_bond_dimension=64).config_for('coherent'):")
    print(f"      {str(config.simulation_type).split('.')[-1]}, χ={config.max_bond_dimension}")
    print("  MaestroBackend(simulation_type=MPS, max_bond_dimension=8).config_for('pauli'):")
    forced = MaestroBackend(simulation_type=MPS, max_bond_dimension=8).config_for("pauli")
    print(f"      {str(forced.simulation_type).split('.')[-1]}, χ={forced.max_bond_dimension}")
    print("  Coherent runs pick MPS by themselves; χ defaults to 32. Pauli and noiseless")
    print("  runs use the stabilizer unless simulation_type picks MPS, as section 2 does.")

    # -------------------------------------------------------------------------
    # 2. The noiseless check
    # -------------------------------------------------------------------------
    print(f"\n{'─' * 74}")
    print("  2. Noiseless check: any detection event is truncation error")
    print(f"{'─' * 74}")
    print(
        f"  {'code':<21} │ {'qubits':>6} │ {'χ':>3} │ {'shots with a detection event':>28} │ {'ms/shot':>7}"
    )
    print(f"  {'─' * 72}")
    for name, circuit in codes.items():
        for chi in NOISELESS_CHIS:
            backend = MaestroBackend(simulation_type=MPS, max_bond_dimension=chi)
            t0 = time.time()
            dets = backend.simulate(circuit, NOISELESS_SHOTS, "none", seed=SEED).detection_events
            ms_per_shot = (time.time() - t0) / NOISELESS_SHOTS * 1e3
            failed = dets.any(axis=1).mean()
            verdict = "exact" if failed == 0 else "TRUNCATED"
            print(
                f"  {name:<21} │ {circuit.num_qubits:>6} │ {chi:>3} │ "
                f"{failed:>17.0%} {verdict:>10} │ {ms_per_shot:>7.1f}"
            )
    print("  The unrotated code is not exact at χ=32, where it already costs ~0.3 s a")
    print("  shot; at χ=64 (~1 s a shot, not run here) most noiseless shots are still")
    print("  wrong. The toric code and rotated d=5 fail the same way, so coherent studies")
    print("  of them need a far larger χ than is practical on a laptop.")

    # -------------------------------------------------------------------------
    # 3. Coherent noise: raise χ until the result stops changing
    # -------------------------------------------------------------------------
    circuit = codes["Rotated planar d=3"]
    print(f"\n{'─' * 74}")
    print(f"  3. Coherent noise on the rotated d=3 code, {COHERENT_SHOTS} shots per χ")
    print(f"{'─' * 74}")
    twirl = MaestroBackend().twirled_circuit(circuit, "coherent")
    twirl_rate = MaestroBackend().simulate(twirl, 100_000, seed=SEED).detection_events.mean()
    print(f"  Pauli twirl of the same noise (stabilizer): {twirl_rate:.4f}. The coherent effect")
    print("  is the excess over it.\n")
    print(f"  {'χ':>3} │ {'detection-event rate':>20} │ {'excess over twirl':>17} │ {'ms/shot':>7}")
    print(f"  {'─' * 58}")
    for chi in COHERENT_CHIS:
        backend = MaestroBackend(max_bond_dimension=chi)
        t0 = time.time()
        dets = backend.simulate(circuit, COHERENT_SHOTS, "coherent", seed=SEED).detection_events
        ms_per_shot = (time.time() - t0) / COHERENT_SHOTS * 1e3
        rate, err = detection_rate(dets)
        print(
            f"  {chi:>3} │ {rate:>11.4f} ± {err:.4f} │ {rate - twirl_rate:>+17.4f} │ {ms_per_shot:>7.1f}"
        )

    print(f"\n{'=' * 74}")
    print("  Notes:")
    print("    - The noiseless code is exact at χ=8, but coherent noise needs more:")
    print("      χ=8 is several error bars high, χ=16 still a little high, and χ=32 and")
    print("      64 agree. At χ=8 the truncation adds about as much as the coherent")
    print("      effect itself, so too small a χ can double the effect being measured.")
    print("    - Recipe: pass the noiseless check, then double χ until the coherent")
    print("      result is unchanged within its error bars.")
    print("=" * 74)


if __name__ == "__main__":
    main()
