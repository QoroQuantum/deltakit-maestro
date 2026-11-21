# SPDX-FileCopyrightText: 2026 Qoro Quantum
# SPDX-License-Identifier: GPL-3.0-or-later

"""Small coherent errors past a statevector: Maestro's extended stabilizer.

The extended stabilizer holds a state as a Clifford acting on a sparse list of
components. Clifford gates and Pauli noise add none; a coherent over-rotation
can add some, and a measurement removes them. With
``extended_stabilizer_amplitude_tolerance`` it drops the components below a
fraction of the state's norm, so a branch with k coherent errors since the last
syndrome measurement, of amplitude about sin(θ/2)^k, is kept only while it
matters. Hardware noise is mostly stochastic with a smaller coherent part, and
there the list stays short on codes no statevector can hold.

Every circuit is a Deltakit Z-basis memory experiment under SI1000(p=0.002),
whose Pauli noise Maestro samples, plus an isotropic coherent over-rotation of
infidelity ``COHERENT`` after every gate (``noise_type='full'``), its sign drawn
once per qubit per shot. Each is decoded with the Pauli twirl's detector error
model, as ``benchmarks/coherent.py`` does.

``exact``
    The rotated d=3 surface code (17 qubits) on the extended stabilizer at
    several tolerances, against Maestro's exact statevector: the case above,
    and the hardest one, coherent over-rotations of the full strength p in
    place of the gates' Pauli noise (``noise_type='coherent'``).
``surface``
    The rotated surface code at d=3, 5 and 7 (17, 49 and 97 qubits): coherent
    against its twirl on Stim at tolerance ``TOLERANCE``, each code checked at
    ``CHECK_TOLERANCE``.
``qldpc``
    The [[72,12,6]] bivariate bicycle code (144 qubits, 6 rounds), BP-OSD:
    coherent against its twirl, checked the same way.

    OMP_NUM_THREADS=1 WORKERS=32 python benchmarks/extended.py          # every part
    OMP_NUM_THREADS=1 WORKERS=32 python benchmarks/extended.py surface  # one

Needs a Maestro with the extended-stabilizer pruning settings (after 0.3.16,
QoroQuantum/maestro#60). Writes benchmarks/results/extended_<part>.json.
"""

from coherent import merged, ratios
from common import BpOsd, bivariate_bicycle, memory_circuit, save, surface_code, z_score

# isort: split
import argparse
import concurrent.futures as cf
import functools
import multiprocessing
import os
import time

import maestro
import numpy as np
import pymatching
import stim

from deltakit_maestro import MaestroBackend

EXTENDED = maestro.SimulationType.ExtendedStabilizer
STATEVECTOR = maestro.SimulationType.Statevector
SEED = 2026
P = 0.002
COHERENT = 5e-4
TOLERANCE = 3e-4
CHECK_TOLERANCE = 1e-4
WORKERS = int(os.environ.get("WORKERS", os.cpu_count() or 8))
TWIRL_CHUNK = 1_000_000

REALISTIC = {"noise_type": "full", "coherent": COHERENT}
COHERENT_ONLY = {"noise_type": "coherent"}

# The decoder qldpc.py uses for the bivariate bicycle codes.
BP_OSD = dict(max_iter=100, bp_method="minimum_sum", ms_scaling_factor=0.625, osd_method="osd0", osd_order=0)


# -----------------------------------------------------------------------------
# Chunks of shots, run in worker processes
# -----------------------------------------------------------------------------


def failures(dets: np.ndarray, obs: np.ndarray, dem: stim.DetectorErrorModel, qldpc: bool) -> np.ndarray:
    """Which shots the decoder gets wrong."""
    if not qldpc:
        predicted = pymatching.Matching.from_detector_error_model(dem).decode_batch(dets)
        return np.any(predicted != obs, axis=1)
    decoder = BpOsd(**BP_OSD).compile_decoder_for_dem(dem=dem)
    packed = np.packbits(dets, axis=1, bitorder="little")
    predicted = decoder.decode_shots_bit_packed(bit_packed_detection_event_data=packed)
    predicted = np.unpackbits(predicted, axis=1, bitorder="little")[:, : obs.shape[1]]
    return np.any(predicted != obs, axis=1)


def counts(dets: np.ndarray, obs: np.ndarray, dem_text: str, qldpc: bool) -> dict:
    """What a chunk of shots adds to a summary: sums that merge across chunks."""
    per_shot = dets.mean(axis=1)
    return {
        "shots": len(dets),
        "rate_sum": float(per_shot.sum()),
        "rate_sq_sum": float((per_shot**2).sum()),
        "per_detector": dets.sum(axis=0).astype(np.int64),
        "errors": int(failures(dets, obs, stim.DetectorErrorModel(dem_text), qldpc).sum()),
    }


def maestro_chunk(circuit_text: str, dem_text: str, noise: dict, method: str, tolerance: float | None,
                  qldpc: bool, shots: int, seed: int) -> dict:
    """``shots`` shots on the extended stabilizer (pruned at ``tolerance``) or the statevector, counted."""
    config = {} if tolerance is None else {"extended_stabilizer_amplitude_tolerance": tolerance}
    backend = MaestroBackend(simulation_type=EXTENDED if method == "extended" else STATEVECTOR, **config)
    sampler = backend.compile_sampler(stim.Circuit(circuit_text), decoder=None, seed=seed, **noise)
    t0 = time.perf_counter()
    dets, obs = sampler.sample_detection_events(shots)
    seconds = time.perf_counter() - t0
    return counts(dets, obs, dem_text, qldpc) | {"seconds": seconds}


def twirl_chunk(twirl_text: str, dem_text: str, qldpc: bool, shots: int, seed: int) -> dict:
    """``shots`` shots of the Pauli twirl on Stim, counted."""
    sampler = stim.Circuit(twirl_text).compile_detector_sampler(seed=seed)
    dets, obs = sampler.sample(shots, separate_observables=True)
    return counts(dets, obs, dem_text, qldpc)


def run(pool, job, total: int, chunk: int, seed: int) -> dict:
    """``total`` shots of ``job(shots, seed)`` in chunks of ``chunk``, each with its own seed."""
    sizes = [chunk] * (total // chunk) + ([total % chunk] if total % chunk else [])
    t0 = time.perf_counter()
    futures = [pool.submit(job, n, seed + i) for i, n in enumerate(sizes)]
    result = merged([f.result() for f in futures])
    result["wall_seconds"] = time.perf_counter() - t0
    result["seconds_per_shot"] = result["seconds"] / result["shots"] if result["seconds"] else None
    return result


def prepare(circuit: stim.Circuit, noise: dict) -> tuple[str, str, str]:
    """The circuit, its twirl and the twirl's DEM, as text for the workers."""
    backend = MaestroBackend(simulation_type=EXTENDED)
    twirl = backend.twirled_circuit(circuit, **noise)
    dem = backend.compile_sampler(circuit, decoder=None, **noise).task.detector_error_model
    return str(circuit), str(twirl), str(dem)


def agreement(a: dict, b: dict) -> dict:
    """z-scores of two summaries, detection rate and LEP."""
    return {
        "z_detection_rate": z_score((a["detection_rate"], a["detection_rate_err"]),
                                    (b["detection_rate"], b["detection_rate_err"])),
        "z_lep": z_score((a["lep"], a["lep_err"]), (b["lep"], b["lep_err"])),
    }


def short(r: dict) -> str:
    t = f" {r['seconds_per_shot']:.3f} s/shot" if r.get("seconds_per_shot") else ""
    return (f"rate {r['detection_rate']:.5f}±{r['detection_rate_err']:.5f} "
            f"LEP {r['lep']:.5f}±{r['lep_err']:.5f} ({r['errors']} in {r['shots']:,}){t}")


def compare_to_twirl(pool, label: str, circuit: stim.Circuit, qldpc: bool, shots: int, chunk: int,
                     check_shots: int, twirl_shots: int, seed: int) -> dict:
    """Coherent at TOLERANCE against its twirl, and against itself at CHECK_TOLERANCE."""
    text, twirl, dem = prepare(circuit, REALISTIC)
    coherent = run(pool, functools.partial(maestro_chunk, text, dem, REALISTIC, "extended", TOLERANCE, qldpc),
                   shots, chunk, seed)
    print(f"{label} tolerance {TOLERANCE:g}: {short(coherent)}", flush=True)
    # The check is slower a shot: spread its fewer shots over every worker.
    check_chunk = max(1, min(chunk, check_shots // WORKERS))
    check = run(pool, functools.partial(maestro_chunk, text, dem, REALISTIC, "extended", CHECK_TOLERANCE, qldpc),
                check_shots, check_chunk, seed + 500_000)
    z = agreement(coherent, check)
    print(f"{label} tolerance {CHECK_TOLERANCE:g}: {short(check)} │ z rate {z['z_detection_rate']:+.2f} "
          f"LEP {z['z_lep']:+.2f}", flush=True)
    pauli = run(pool, functools.partial(twirl_chunk, twirl, dem, qldpc), twirl_shots,
                min(TWIRL_CHUNK, max(1, twirl_shots // WORKERS)), seed + 900_000)
    r = ratios(coherent, pauli)
    print(f"{label} twirl: {short(pauli)} │ coherent/twirl rate {r['detection_rate_ratio']:.4f}"
          f"±{r['detection_rate_ratio_err']:.4f} LEP {r['lep_ratio']:.3f}±{r['lep_ratio_err']:.3f}", flush=True)
    return {"qubits": circuit.num_qubits, "detectors": circuit.num_detectors, "coherent": coherent,
            "check": check, "check_agreement": z, "twirl": pauli, **r}


# -----------------------------------------------------------------------------
# exact: against the statevector on the rotated d=3 surface code
# -----------------------------------------------------------------------------

EXACT_TOLERANCES = [1e-2, 1e-3, 3e-4, 1e-4]
EXACT_SHOTS = 100_000
EXACT_CHUNK = 2_000
EXACT_CASES = {"pauli + coherent": REALISTIC, "coherent only": COHERENT_ONLY}


def part_exact(pool):
    records = []
    meta = {"code": "rotated d=3, 3 rounds", "base_noise": "SI1000", "p": P}
    circuit = surface_code(3, "SI1000", P)
    for c, (case, noise) in enumerate(EXACT_CASES.items()):
        text, _, dem = prepare(circuit, noise)
        seed = SEED + 10_000_000 * (c + 1)  # Chunks count up from here: no two runs share a seed.
        exact = run(pool, functools.partial(maestro_chunk, text, dem, noise, "statevector", None, False),
                    EXACT_SHOTS, EXACT_CHUNK, seed)
        print(f"{case}: statevector {short(exact)}", flush=True)
        for t, tolerance in enumerate(EXACT_TOLERANCES):
            r = run(pool, functools.partial(maestro_chunk, text, dem, noise, "extended", tolerance, False),
                    EXACT_SHOTS, EXACT_CHUNK, seed + 100_000 * (t + 1))
            records.append({"case": case, **noise, "tolerance": tolerance, "extended": r, "statevector": exact,
                            **agreement(r, exact)})
            print(f"{case}: tolerance {tolerance:g} {short(r)} │ z rate {records[-1]['z_detection_rate']:+.2f} "
                  f"LEP {records[-1]['z_lep']:+.2f}", flush=True)
        save("extended_exact", records, **meta, complete=False)  # Keep what's done.
    save("extended_exact", records, **meta, complete=True)


# -----------------------------------------------------------------------------
# surface: coherent against its twirl, past the statevector
# -----------------------------------------------------------------------------

SURFACE_D = [3, 5, 7]
# The LEP where shots are affordable; at d=7 the detection rate only.
SURFACE_SHOTS = {3: 400_000, 5: 100_000, 7: 1_280}
SURFACE_CHUNK = {3: 4_000, 5: 250, 7: 10}
SURFACE_CHECK_SHOTS = {3: 40_000, 5: 3_200, 7: 320}
SURFACE_TWIRL_SHOTS = 20_000_000


def part_surface(pool):
    records = []
    meta = {"base_noise": "SI1000", "p": P, **REALISTIC, "tolerance": TOLERANCE,
            "check_tolerance": CHECK_TOLERANCE}
    for i, d in enumerate(SURFACE_D):
        circuit = surface_code(d, "SI1000", P)
        r = compare_to_twirl(pool, f"rotated d={d}", circuit, False, SURFACE_SHOTS[d], SURFACE_CHUNK[d],
                             SURFACE_CHECK_SHOTS[d], SURFACE_TWIRL_SHOTS, SEED + 30_000_000 + 1_000_000 * i)
        records.append({"code": "rotated", "d": d, "rounds": d, **r})
        save("extended_surface", records, **meta, complete=False)  # Keep what's done.
    save("extended_surface", records, **meta, complete=True)


# -----------------------------------------------------------------------------
# qldpc: coherent errors on a bivariate bicycle code
# -----------------------------------------------------------------------------

QLDPC_SHOTS = 320
QLDPC_CHUNK = 5
QLDPC_CHECK_SHOTS = 64
# BP-OSD decodes a [[72,12,6]] shot in about a millisecond: the twirl's detection rate is what's compared.
QLDPC_TWIRL_SHOTS = 200_000


def part_qldpc(pool):
    circuit = memory_circuit(bivariate_bicycle(72), "SI1000", P, 6)
    r = compare_to_twirl(pool, "[[72,12,6]]", circuit, True, QLDPC_SHOTS, QLDPC_CHUNK, QLDPC_CHECK_SHOTS,
                         QLDPC_TWIRL_SHOTS, SEED + 60_000_000)
    save("extended_qldpc", [{"code": "[[72,12,6]]", "d": 6, "rounds": 6, **r}], base_noise="SI1000", p=P,
         **REALISTIC, tolerance=TOLERANCE, check_tolerance=CHECK_TOLERANCE,
         decoder={"name": "BP-OSD (ldpc), OSD-0", **BP_OSD}, complete=True)


PARTS = {"exact": part_exact, "surface": part_surface, "qldpc": part_qldpc}


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
