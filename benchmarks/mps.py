# SPDX-FileCopyrightText: 2026 Qoro Quantum
# SPDX-License-Identifier: GPL-3.0-or-later

"""How accurately Maestro's matrix product state (MPS) samples QEC circuits.

Five parts, each checked against a reference that has no truncation:

``pauli``
    MPS (χ=32, pinned) against Stim on the rotated d=3 surface code under three
    Deltakit Pauli noise models. Stim is an independent simulator, so this
    checks the MPS sampler end to end.
``exact``
    MPS against Maestro's exact ``Statevector`` under noise no Clifford
    simulator can run: coherent over-rotations, ``T1`` amplitude damping, and
    both on top of the circuit's Pauli noise, on the rotated d=3 surface code
    and repetition codes up to 21 qubits.
``chi``
    The detection-event rate and LEP against χ, with the exact ``Statevector``
    value as the reference: coherent noise alone, and with ``T1`` decay and the
    circuit's Pauli noise, which needs a larger χ.
``confirm``
    The run that needs more than χ=32, at χ=64 with 40,000 shots each, against
    ``Statevector``: a sharper test of the converged result.
``scaling``
    Time a shot against code size for MPS and ``Statevector`` on repetition
    codes with coherent noise, past the size a statevector can hold.

Every run decodes with PyMatching against the task's detector error model (the
Pauli twirl of what is simulated), and uses every core: one sampler spreads its
shots over all of them.

    python benchmarks/mps.py                    # every part, about an hour and a half
    python benchmarks/mps.py exact chi          # some of them

Writes benchmarks/results/mps_<part>.json.
"""

from common import compare, detection_summary, repetition_code, save, surface_code

# isort: split
import argparse
import os
import time

import maestro

from deltakit_maestro import MaestroBackend

MPS = maestro.SimulationType.MatrixProductState
SV = maestro.SimulationType.Statevector
SEED = 2026


def run(backend: MaestroBackend, circuit, shots: int, seed: int, **noise) -> dict:
    """Sample ``shots`` and summarise them, with the wall time a shot took."""
    sampler = backend.compile_sampler(circuit, decoder=None, seed=seed, **noise)
    t0 = time.perf_counter()
    dets, obs = sampler.sample_detection_events(shots)
    seconds = time.perf_counter() - t0
    out = detection_summary(dets, obs, sampler.task.detector_error_model)
    out["seconds_per_shot"] = seconds / shots
    return out


def stim_run(circuit, shots: int, seed: int) -> dict:
    sampler = circuit.compile_detector_sampler(seed=seed)
    t0 = time.perf_counter()
    dets, obs = sampler.sample(shots, separate_observables=True)
    seconds = time.perf_counter() - t0
    out = detection_summary(dets, obs, circuit.detector_error_model(decompose_errors=True))
    out["seconds_per_shot"] = seconds / shots
    return out


def line(label: str, a: dict, b: dict, cmp: dict, names=("MPS", "ref")) -> str:
    return (
        f"{label:<34} {names[0]} {a['detection_rate']:.4f}±{a['detection_rate_err']:.4f} "
        f"LEP {a['lep']:.4f}±{a['lep_err']:.4f} │ {names[1]} {b['detection_rate']:.4f}±"
        f"{b['detection_rate_err']:.4f} LEP {b['lep']:.4f}±{b['lep_err']:.4f} │ "
        f"z {cmp['z_detection_rate']:+.2f} {cmp['z_lep']:+.2f} max|z| {cmp['max_abs_z_detector']:.2f}"
    )


# -----------------------------------------------------------------------------
# pauli: MPS against Stim
# -----------------------------------------------------------------------------

PAULI_NOISES = ["SI1000", "SD6", "Toy"]
PAULI_P = [0.002, 0.005, 0.01]
PAULI_MPS_SHOTS = 20_000
PAULI_STIM_SHOTS = 2_000_000


def part_pauli():
    mps = MaestroBackend(simulation_type=MPS, max_bond_dimension=32)
    records = []
    for noise in PAULI_NOISES:
        for p in PAULI_P:
            circuit = surface_code(3, noise, p, rounds=3)
            a = run(mps, circuit, PAULI_MPS_SHOTS, SEED)
            b = stim_run(circuit, PAULI_STIM_SHOTS, SEED)
            cmp = compare(a, b)
            records.append({"noise": noise, "p": p, "mps": a, "stim": b, **cmp})
            print(line(f"rotated d=3 {noise}({p})", a, b, cmp, ("MPS", "Stim")), flush=True)
    save(
        "mps_pauli",
        records,
        code="rotated d=3, 3 rounds",
        max_bond_dimension=32,
    )


# -----------------------------------------------------------------------------
# exact: MPS against Statevector
# -----------------------------------------------------------------------------

# (label, SI1000 strength p, noise_type, noise keywords) on the rotated d=3 code
EXACT_SURFACE = [
    ("coherent", 0.002, "coherent", {}),
    ("coherent", 0.005, "coherent", {}),
    ("coherent", 0.01, "coherent", {}),
    ("T1", 0.005, "pauli", {"t1": 0.005}),
    ("full", 0.005, "full", {"t1": 0.005}),
]
EXACT_SURFACE_SHOTS = 10_000
EXACT_REPETITION = [5, 9, 11]
EXACT_REPETITION_P = 0.01
EXACT_REPETITION_SHOTS = {5: 10_000, 9: 10_000, 11: 4_000}


def part_exact():
    mps = MaestroBackend(simulation_type=MPS, max_bond_dimension=32)
    sv = MaestroBackend(simulation_type=SV)
    records = []

    def one(code: str, d: int, label: str, p: float, circuit, shots: int, noise_type, kw):
        a = run(mps, circuit, shots, SEED, noise_type=noise_type, **kw)
        b = run(sv, circuit, shots, SEED + 1, noise_type=noise_type, **kw)
        cmp = compare(a, b)
        records.append(
            {
                "code": code,
                "d": d,
                "qubits": circuit.num_qubits,
                "label": label,
                "p": p,
                "noise_type": noise_type,
                "noise": kw,
                "mps": a,
                "statevector": b,
                **cmp,
            }
        )
        print(line(f"{code} d={d} {label} p={p}", a, b, cmp, ("MPS", "SV")), flush=True)

    for label, p, noise_type, kw in EXACT_SURFACE:
        circuit = surface_code(3, "SI1000", p, rounds=3)
        one("rotated", 3, label, p, circuit, EXACT_SURFACE_SHOTS, noise_type, kw)
    for d in EXACT_REPETITION:
        circuit = repetition_code(d, "SI1000", EXACT_REPETITION_P)
        for label, noise_type, kw in (
            ("coherent", "coherent", {}),
            ("full", "full", {"t1": 0.005}),
        ):
            one(
                "repetition",
                d,
                label,
                EXACT_REPETITION_P,
                circuit,
                EXACT_REPETITION_SHOTS[d],
                noise_type,
                kw,
            )
    save("mps_exact", records, max_bond_dimension=32, base_noise="SI1000")


# -----------------------------------------------------------------------------
# chi: convergence in the bond dimension, against Statevector
# -----------------------------------------------------------------------------

# Coherent noise alone, and with T1 decay and the circuit's Pauli noise, which
# needs a larger χ: at χ=32 that run has too many detection events.
CHI_CASES = [
    {
        "name": "coherent",
        "p": 0.01,
        "noise_type": "coherent",
        "noise": {},
        "chi": [4, 8, 12, 16, 24, 32, 48, 64],
    },
    {
        "name": "full",
        "p": 0.005,
        "noise_type": "full",
        "noise": {"t1": 0.005},
        "chi": [16, 32, 48, 64, 96, 128],
    },
]
CHI_SHOTS = 5_000
CHI_SV_SHOTS = 20_000


def part_chi():
    cases = []
    for case in CHI_CASES:
        circuit = surface_code(3, "SI1000", case["p"], rounds=3)
        noise = {"noise_type": case["noise_type"], **case["noise"]}
        sv = run(MaestroBackend(simulation_type=SV), circuit, CHI_SV_SHOTS, SEED, **noise)
        print(
            f"{case['name']} p={case['p']}: Statevector rate "
            f"{sv['detection_rate']:.4f}±{sv['detection_rate_err']:.4f}",
            flush=True,
        )
        records = []
        for chi in case["chi"]:
            backend = MaestroBackend(simulation_type=MPS, max_bond_dimension=chi)
            a = run(backend, circuit, CHI_SHOTS, SEED + chi, **noise)
            cmp = compare(a, sv)
            records.append({"chi": chi, "mps": a, **cmp})
            print(line(f"  chi={chi}", a, sv, cmp, ("MPS", "SV")), flush=True)
        cases.append(
            {k: v for k, v in case.items() if k != "chi"} | {"statevector": sv, "results": records}
        )
    save("mps_chi", cases, code="rotated d=3, 3 rounds", base_noise="SI1000")


# -----------------------------------------------------------------------------
# scaling: time a shot against code size
# -----------------------------------------------------------------------------

SCALING_D = [3, 5, 7, 9, 11, 13, 15, 21, 25, 31, 41, 51]
SCALING_SV_MAX_QUBITS = 25
SCALING_P = 0.01
# MPS shots by distance; fewer on the largest codes, whose shots take seconds.
# Each count is rounded up to a multiple of the cores (whole_rounds), so every
# core runs the same number.
SCALING_SHOTS = {d: 1_200 if d <= 15 else 480 if d <= 31 else 120 for d in SCALING_D}
SCALING_SV_SHOTS = {21: 240, 25: 12}  # By qubits: a statevector shot gets slow.
SURFACE_SHOTS = 480


def whole_rounds(shots: int) -> int:
    """``shots`` rounded up to a multiple of the cores the sampler spreads them over."""
    cores = os.cpu_count() or 1
    return -(-shots // cores) * cores


def part_scaling():
    records = []
    for d in SCALING_D:
        circuit = repetition_code(d, "SI1000", SCALING_P)
        n = circuit.num_qubits
        row = {"d": d, "qubits": n, "rounds": d}
        # χ=32, the default, against χ=64 from an independent seed: if doubling χ
        # changes nothing, χ=32 is converged, where no statevector can check it.
        for chi in (32, 64):
            backend = MaestroBackend(simulation_type=MPS, max_bond_dimension=chi)
            row[f"mps{chi}"] = run(
                backend, circuit, whole_rounds(SCALING_SHOTS[d]), SEED + chi, noise_type="coherent"
            )
        row["mps32_vs_mps64"] = compare(row["mps32"], row["mps64"])
        if n <= SCALING_SV_MAX_QUBITS:
            shots = whole_rounds(SCALING_SV_SHOTS.get(n, SCALING_SHOTS[d]))
            sv = MaestroBackend(simulation_type=SV)
            row["statevector"] = run(sv, circuit, shots, SEED, noise_type="coherent")
            row["mps32_vs_statevector"] = compare(row["mps32"], row["statevector"])
        records.append(row)
        sv_text = ""
        if "statevector" in row:
            sv_text = (
                f"SV {row['statevector']['seconds_per_shot'] * 1e3:9.2f} ms "
                f"(z χ=32 vs SV {row['mps32_vs_statevector']['z_detection_rate']:+.2f})"
            )
        print(
            f"d={d:>2} qubits={n:>3} MPS χ=32 {row['mps32']['seconds_per_shot'] * 1e3:8.2f} ms "
            f"χ=64 {row['mps64']['seconds_per_shot'] * 1e3:8.2f} ms "
            f"rate {row['mps32']['detection_rate']:.4f} "
            f"(z χ=32 vs 64 {row['mps32_vs_mps64']['z_detection_rate']:+.2f}) " + sv_text,
            flush=True,
        )

    # The rotated d=3 surface code, for comparison: 17 qubits but a 2D layout.
    surface = surface_code(3, "SI1000", SCALING_P, rounds=3)
    surface_row = {"code": "rotated d=3, 3 rounds", "qubits": surface.num_qubits}
    for name, backend in (
        ("mps32", MaestroBackend(simulation_type=MPS, max_bond_dimension=32)),
        ("sv", MaestroBackend(simulation_type=SV)),
    ):
        sampler = backend.compile_sampler(surface, decoder=None, seed=SEED, noise_type="coherent")
        t0 = time.perf_counter()
        sampler.sample_detection_events(SURFACE_SHOTS)
        surface_row[f"{name}_seconds_per_shot"] = (time.perf_counter() - t0) / SURFACE_SHOTS
    print(
        f"rotated d=3: MPS χ=32 {surface_row['mps32_seconds_per_shot'] * 1e3:.2f} ms, "
        f"SV {surface_row['sv_seconds_per_shot'] * 1e3:.2f} ms",
        flush=True,
    )
    save(
        "mps_scaling",
        records,
        code="repetition, d rounds",
        noise="coherent, SI1000(0.01)",
        surface=surface_row,
        load_average=os.getloadavg()[0],
    )


# -----------------------------------------------------------------------------
# confirm: one converged run with more shots
# -----------------------------------------------------------------------------

CONFIRM_CHI = 64
CONFIRM_SHOTS = 40_000


def part_confirm():
    """Pauli + coherent + T1 at a converged χ, 40,000 shots each, against Statevector."""
    case = next(c for c in CHI_CASES if c["name"] == "full")
    circuit = surface_code(3, "SI1000", case["p"], rounds=3)
    noise = {"noise_type": case["noise_type"], **case["noise"]}
    sv = run(MaestroBackend(simulation_type=SV), circuit, CONFIRM_SHOTS, 11, **noise)
    mps = MaestroBackend(simulation_type=MPS, max_bond_dimension=CONFIRM_CHI)
    a = run(mps, circuit, CONFIRM_SHOTS, 12, **noise)
    cmp = compare(a, sv)
    print(line(f"full p={case['p']} chi={CONFIRM_CHI}", a, sv, cmp, ("MPS", "SV")), flush=True)
    save(
        "mps_confirm",
        {"mps": a, "statevector": sv, **cmp},
        code="rotated d=3, 3 rounds",
        noise=f"SI1000({case['p']}), noise_type='full', t1={case['noise']['t1']}",
        max_bond_dimension=CONFIRM_CHI,
    )


PARTS = {
    "pauli": part_pauli,
    "exact": part_exact,
    "chi": part_chi,
    "confirm": part_confirm,
    "scaling": part_scaling,
}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("parts", nargs="*", help=f"any of {', '.join(PARTS)} (default: all)")
    parts = parser.parse_args().parts or list(PARTS)
    unknown = set(parts) - set(PARTS)
    if unknown:
        parser.error(f"unknown parts {sorted(unknown)}; choose from {', '.join(PARTS)}")
    for part in parts:
        print(f"\n=== {part} ===", flush=True)
        PARTS[part]()


if __name__ == "__main__":
    main()
