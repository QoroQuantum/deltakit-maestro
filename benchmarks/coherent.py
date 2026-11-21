# SPDX-FileCopyrightText: 2026 Qoro Quantum
# SPDX-License-Identifier: GPL-3.0-or-later

"""Coherent noise against its Pauli twirl: what MPS adds where Stim can't run.

A coherent over-rotation and its Pauli twirl have the same infidelity per gate,
but only the over-rotation's amplitudes add up across gates. Decoder studies
usually simulate the twirl. Here both run on the same circuit and decoder: the
over-rotations on Maestro's matrix product state (MPS), the twirl on Stim, both
decoded by PyMatching with the twirl's detector error model.

``repetition``
    Repetition codes of growing distance (d rounds) at two noise strengths: does
    the coherent excess shrink as the distance grows?
``surface``
    The rotated d=3 surface code (3 rounds) against noise strength, with
    thousands of logical errors a point.

Each point samples until it has ``TARGET_ERRORS`` logical errors or reaches its
shot cap. A sampler spreads its shots over only part of a large machine, so
the MPS shots run in ``WORKERS`` processes at once (default: cores / 8).
The strongest point of each part also runs at χ=64, to check χ=32.

    python benchmarks/coherent.py                 # both parts
    python benchmarks/coherent.py surface         # one

Writes benchmarks/results/coherent_<part>.json.
"""

from common import repetition_code, save, surface_code, z_score

# isort: split
import argparse
import concurrent.futures as cf
import multiprocessing
import os
import time

import maestro
import numpy as np
import pymatching
import stim

from deltakit_maestro import MaestroBackend

MPS = maestro.SimulationType.MatrixProductState
SEED = 2026
CHI = 32
CHI_CHECK = 64
WORKERS = int(os.environ.get("WORKERS", max(1, (os.cpu_count() or 8) // 8)))
TWIRL_CHUNK = 1_000_000


# -----------------------------------------------------------------------------
# Sampling in chunks, and merging what the chunks counted
# -----------------------------------------------------------------------------


def counts(dets: np.ndarray, obs: np.ndarray, dem: stim.DetectorErrorModel) -> dict:
    """What a chunk of shots adds to a summary: sums that merge across chunks."""
    per_shot = dets.mean(axis=1)
    matcher = pymatching.Matching.from_detector_error_model(dem)
    failures = np.any(matcher.decode_batch(dets) != obs, axis=1)
    return {
        "shots": len(dets),
        "rate_sum": float(per_shot.sum()),
        "rate_sq_sum": float((per_shot**2).sum()),
        "per_detector": dets.sum(axis=0).astype(np.int64),
        "errors": int(failures.sum()),
    }


def merged(chunks: list[dict]) -> dict:
    """The summary of all the chunks' shots, as ``common.detection_summary`` gives it."""
    n = sum(c["shots"] for c in chunks)
    s1 = sum(c["rate_sum"] for c in chunks)
    s2 = sum(c["rate_sq_sum"] for c in chunks)
    k = sum(c["errors"] for c in chunks)
    variance = max(s2 - s1 * s1 / n, 0.0) / (n - 1)
    lep = k / n
    return {
        "shots": n,
        "detection_rate": s1 / n,
        "detection_rate_err": float(np.sqrt(variance / n)),
        "per_detector": (sum(c["per_detector"] for c in chunks) / n).tolist(),
        "lep": lep,
        "lep_err": float(np.sqrt(max(lep * (1 - lep), 1 / n**2) / n)),
        "errors": k,
        "seconds": sum(c.get("seconds", 0.0) for c in chunks),
    }


def mps_chunk(circuit_text: str, dem_text: str, chi: int, shots: int, seed: int) -> dict:
    """``shots`` coherent-noise shots on the MPS, counted."""
    backend = MaestroBackend(simulation_type=MPS, max_bond_dimension=chi)
    sampler = backend.compile_sampler(
        stim.Circuit(circuit_text), decoder=None, seed=seed, noise_type="coherent"
    )
    t0 = time.perf_counter()
    dets, obs = sampler.sample_detection_events(shots)
    seconds = time.perf_counter() - t0
    return counts(dets, obs, stim.DetectorErrorModel(dem_text)) | {"seconds": seconds}


def twirl_chunk(twirl_text: str, dem_text: str, shots: int, seed: int) -> dict:
    """``shots`` shots of the Pauli twirl on Stim, counted."""
    sampler = stim.Circuit(twirl_text).compile_detector_sampler(seed=seed)
    dets, obs = sampler.sample(shots, separate_observables=True)
    return counts(dets, obs, stim.DetectorErrorModel(dem_text))


def until_errors(pool, submit, chunk: int, target: int, cap: int) -> dict:
    """Submit chunks in waves of one per worker until ``target`` errors or ``cap`` shots."""
    chunks, index = [], 0
    while True:
        shots = sum(c["shots"] for c in chunks)
        errors = sum(c["errors"] for c in chunks)
        if errors >= target or shots >= cap:
            return merged(chunks)
        wave = []
        for _ in range(WORKERS):
            size = min(chunk, cap - shots - sum(s for _, s in wave))
            if size <= 0:
                break
            wave.append((submit(pool, size, index), size))
            index += 1
        chunks += [f.result() for f, _ in wave]


def point(
    pool, circuit: stim.Circuit, chi: int, chunk: int, target: int, cap: int, seed: int
) -> dict:
    """One noise strength and code: coherent on the MPS against its twirl on Stim."""
    backend = MaestroBackend(simulation_type=MPS, max_bond_dimension=chi)
    twirl = backend.twirled_circuit(circuit, noise_type="coherent")
    # Both runs decode with the DEM a coherent run's decoder gets: the twirl's.
    dem = backend.compile_sampler(
        circuit, decoder=None, noise_type="coherent"
    ).task.detector_error_model
    same_dem = dem == twirl.detector_error_model(decompose_errors=True)
    circuit_text, twirl_text, dem_text = str(circuit), str(twirl), str(dem)
    coherent = until_errors(
        pool,
        lambda p, n, i: p.submit(mps_chunk, circuit_text, dem_text, chi, n, seed + i),
        chunk,
        target,
        cap,
    )
    pauli = until_errors(
        pool,
        lambda p, n, i: p.submit(twirl_chunk, twirl_text, dem_text, n, seed + 100_000 + i),
        TWIRL_CHUNK,
        4 * target,
        200_000_000,
    )
    return {
        "coherent": coherent,
        "twirl": pauli,
        "twirl_dem_matches": same_dem,
        **ratios(coherent, pauli),
    }


def ratios(a: dict, b: dict) -> dict:
    """Coherent over twirl, for the detection-event rate and the LEP, with errors."""
    out = {}
    for key in ("detection_rate", "lep"):
        x, ex, y, ey = a[key], a[f"{key}_err"], b[key], b[f"{key}_err"]
        r = x / y if y else float("nan")
        out[f"{key}_ratio"] = r
        out[f"{key}_ratio_err"] = abs(r) * float(np.hypot(ex / x if x else 0, ey / y if y else 0))
        out[f"z_{key}"] = z_score((x, ex), (y, ey))
    return out


def line(label: str, r: dict) -> str:
    c, t = r["coherent"], r["twirl"]
    return (
        f"{label:<26} coherent rate {c['detection_rate']:.4f} LEP {c['lep']:.5f} "
        f"({c['errors']} in {c['shots']:,}) │ twirl rate {t['detection_rate']:.4f} "
        f"LEP {t['lep']:.5f} │ ratio rate {r['detection_rate_ratio']:.3f}±{r['detection_rate_ratio_err']:.3f} "
        f"LEP {r['lep_ratio']:.3f}±{r['lep_ratio_err']:.3f}"
    )


def chi_check(pool, circuit, chunk, shots, seed) -> dict:
    """χ=32 against χ=64 on the same circuit, independent seeds, same number of shots."""
    backend = MaestroBackend(simulation_type=MPS, max_bond_dimension=CHI)
    dem_text = str(
        backend.compile_sampler(
            circuit, decoder=None, noise_type="coherent"
        ).task.detector_error_model
    )
    runs = {}
    for chi in (CHI, CHI_CHECK):
        runs[chi] = until_errors(
            pool,
            lambda p, n, i, chi=chi: p.submit(
                mps_chunk, str(circuit), dem_text, chi, n, seed + 7 * chi + i
            ),
            chunk,
            10**12,
            shots,
        )
    a, b = runs[CHI], runs[CHI_CHECK]
    return {
        f"chi{CHI}": a,
        f"chi{CHI_CHECK}": b,
        "z_detection_rate": z_score(
            (a["detection_rate"], a["detection_rate_err"]),
            (b["detection_rate"], b["detection_rate_err"]),
        ),
        "z_lep": z_score((a["lep"], a["lep_err"]), (b["lep"], b["lep_err"])),
    }


# -----------------------------------------------------------------------------
# repetition: the coherent excess against distance
# -----------------------------------------------------------------------------

REPETITION_D = [3, 5, 7, 9, 11, 13, 15]
REPETITION_P = [0.005, 0.01]
REPETITION_TARGET = 400
REPETITION_CAP = 400_000
# Shots a chunk, so a chunk takes about a minute: an MPS shot's cost grows with d.
REPETITION_CHUNK = {3: 20_000, 5: 8_000, 7: 2_000, 9: 800, 11: 400, 13: 200, 15: 120}


def part_repetition(pool):
    records = []
    meta = {
        "base_noise": "SI1000",
        "max_bond_dimension": CHI,
        "target_errors": REPETITION_TARGET,
        "shot_cap": REPETITION_CAP,
    }
    for i, (p, d) in enumerate((p, d) for p in REPETITION_P for d in REPETITION_D):
        circuit = repetition_code(d, "SI1000", p)
        seed = SEED + 1_000_000 * (i + 1)  # Chunks count up from here: no two points share one.
        r = point(pool, circuit, CHI, REPETITION_CHUNK[d], REPETITION_TARGET, REPETITION_CAP, seed)
        records.append({"d": d, "p": p, "qubits": circuit.num_qubits, "rounds": d, **r})
        print(line(f"repetition d={d} p={p}", r), flush=True)
        save("coherent_repetition", records, **meta, complete=False)  # Keep what's done.
    d, p = REPETITION_D[-1], max(REPETITION_P)
    shots = 2 * REPETITION_CHUNK[d] * WORKERS  # Two waves of chunks.
    check = chi_check(pool, repetition_code(d, "SI1000", p), REPETITION_CHUNK[d], shots, SEED + 5)
    print(
        f"χ check, repetition d={d} p={p}: z rate {check['z_detection_rate']:+.2f} LEP {check['z_lep']:+.2f}",
        flush=True,
    )
    save("coherent_repetition", records, **meta, chi_check={"d": d, "p": p, **check}, complete=True)


# -----------------------------------------------------------------------------
# surface: the rotated d=3 code against noise strength
# -----------------------------------------------------------------------------

SURFACE_P = [0.002, 0.003, 0.005, 0.007, 0.01]
SURFACE_TARGET = 4_000
SURFACE_CAP = 1_000_000
SURFACE_CHUNK = 5_000


def part_surface(pool):
    records = []
    meta = {
        "code": "rotated d=3, 3 rounds",
        "base_noise": "SI1000",
        "max_bond_dimension": CHI,
        "target_errors": SURFACE_TARGET,
        "shot_cap": SURFACE_CAP,
    }
    for i, p in enumerate(SURFACE_P):
        circuit = surface_code(3, "SI1000", p, rounds=3)
        seed = SEED + 50_000_000 + 1_000_000 * i
        r = point(pool, circuit, CHI, SURFACE_CHUNK, SURFACE_TARGET, SURFACE_CAP, seed)
        records.append({"d": 3, "p": p, "qubits": circuit.num_qubits, "rounds": 3, **r})
        print(line(f"rotated d=3 p={p}", r), flush=True)
        save("coherent_surface", records, **meta, complete=False)  # Keep what's done.
    p = max(SURFACE_P)
    check = chi_check(
        pool, surface_code(3, "SI1000", p, rounds=3), SURFACE_CHUNK, 200_000, SEED + 6
    )
    print(
        f"χ check, rotated d=3 p={p}: z rate {check['z_detection_rate']:+.2f} LEP {check['z_lep']:+.2f}",
        flush=True,
    )
    save("coherent_surface", records, **meta, chi_check={"p": p, **check}, complete=True)


PARTS = {"repetition": part_repetition, "surface": part_surface}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("parts", nargs="*", help=f"any of {', '.join(PARTS)} (default: all)")
    parts = parser.parse_args().parts or list(PARTS)
    unknown = set(parts) - set(PARTS)
    if unknown:
        parser.error(f"unknown parts {sorted(unknown)}; choose from {', '.join(PARTS)}")
    context = multiprocessing.get_context("spawn")  # Maestro runs threads: don't fork them.
    with cf.ProcessPoolExecutor(WORKERS, mp_context=context) as pool:
        for part in parts:
            print(f"\n=== {part} ({WORKERS} workers) ===", flush=True)
            PARTS[part](pool)


if __name__ == "__main__":
    main()
