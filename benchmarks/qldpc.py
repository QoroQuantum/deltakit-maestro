# SPDX-FileCopyrightText: 2026 Qoro Quantum
# SPDX-License-Identifier: GPL-3.0-or-later

"""T1 decay on bivariate bicycle codes, against its Pauli twirl.

T1 decay is not a Pauli channel, so a Clifford simulator can only run its
twirl. Maestro's stabilizer simulator runs the decay itself, shot by shot, as a
reset to |0⟩ with probability γ after every gate, so qLDPC codes far past what a
statevector or an MPS can hold run with it. Here the [[72,12,6]] and
[[144,12,12]] bivariate bicycle codes (Z-basis memory, d rounds) run under
Deltakit's SI1000(p) with T1 decay γ = p, both arms on Maestro: the decay on its
stabilizer, shot by shot, and its twirl on Pauli frames. Both are decoded alike,
with the twirl's detector error model, as ``as_sinter_task`` gives it.

``rates``
    Detection events of each arm, overall and in the first round (where the
    data qubits are still in |0⟩), at every strength on both codes, and how
    fast each samples per CPU second. No decoding.
``logical``
    Logical error rates under ``sinter.collect`` (any of the 12 logical
    qubits wrong counts as an error): [[72,12,6]] at every strength,
    [[144,12,12]] from p=0.001. Decoding takes nearly all the time, so the
    decoder is a fast one, checked against a slow, more accurate one (see
    ``DECODER``).

    OMP_NUM_THREADS=1 python benchmarks/qldpc.py          # both parts
    OMP_NUM_THREADS=1 python benchmarks/qldpc.py logical  # one

Writes benchmarks/results/qldpc_<part>.json (and qldpc_logical.csv, sinter's
own format, not committed; rerunning resumes from it).
"""

from common import RESULTS, BpLsd, bivariate_bicycle, memory_circuit, proportion, save, z_score

# isort: split
import argparse
import os
import time

import numpy as np
import sinter

from deltakit_maestro import MaestroBackend

# n -> distance, which is also the number of rounds
CODES = {n: d for n, d in {72: 6, 144: 12}.items() if str(n) in os.environ.get("CODES", "72,144")}
_P = os.environ.get("P_VALUES")
# Detection rates need no decoding, so they cover every strength on both codes.
RATE_P = [float(p) for p in _P.split(",")] if _P else [0.0005, 0.001, 0.0015, 0.002]
# Logical error rates: the larger code only from p=0.001, since below that its
# logical error rate is too low to measure in reasonable time.
LOGICAL_P = {n: RATE_P if _P else ps for n, ps in {72: RATE_P, 144: [0.001, 0.0015, 0.002]}.items()}
SEED = 2026
RATE_SHOTS = int(os.environ.get("RATE_SHOTS", 20_000))  # T1, shot by shot
TWIRL_RATE_SHOTS = int(os.environ.get("TWIRL_RATE_SHOTS", 1_000_000))  # Pauli frames
# Per code: (max shots, max errors) for each arm at each strength.
LIMITS = {
    72: (int(os.environ.get("MAX_SHOTS", 300_000)), int(os.environ.get("MAX_ERRORS", 500))),
    144: (int(os.environ.get("MAX_SHOTS_144", 40_000)), int(os.environ.get("MAX_ERRORS_144", 300))),
}

# The same decoder for both arms: BP with localised statistics decoding,
# LSD-CS of order 2. Chosen by qldpc_decoders.py, which decodes the same shots
# with it and with OSD-CS of order 7 after 1000 BP iterations: LSD fails
# 1.5-1.7x as often, but takes a tenth of the time (4 s a [[144,12,12]] shot
# on the benchmark machine, against 47 s) and a sixth of the memory.
DECODER_NAME = "BP-LSD (ldpc), LSD-CS order 2"
DECODER_CLASS = BpLsd
DECODER = dict(max_iter=100, bp_method="minimum_sum", ms_scaling_factor=0.625, lsd_method="lsd_cs", lsd_order=2)


def circuit(n: int, p: float):
    return memory_circuit(bivariate_bicycle(n), "SI1000", p, CODES[n])


def timed_detection_events(sampler, shots: int) -> tuple[np.ndarray, float, float]:
    """Detection events, shots per CPU second, and threads used (CPU time over wall time)."""
    wall, cpu = time.perf_counter(), time.process_time()
    dets, _ = sampler.sample_detection_events(shots)
    wall, cpu = time.perf_counter() - wall, time.process_time() - cpu
    return dets, shots / cpu, cpu / wall


def rate_summary(dets: np.ndarray) -> tuple[float, float]:
    per_shot = dets.mean(axis=1)
    return float(per_shot.mean()), float(per_shot.std(ddof=1) / np.sqrt(len(dets)))


def part_rates(backend: MaestroBackend) -> None:
    records = []
    print(f"{'code':<14} {'p':>6} │ {'T1 det rate':>20} {'twirl det rate':>20} {'twirl/T1':>9} {'z':>6} │ {'shots/CPU-s T1':>14} {'twirl':>9}")
    for n, d in CODES.items():
        for p in RATE_P:
            noisy = circuit(n, p)
            t1_sampler = backend.compile_sampler(noisy, t1=p, decoder=None, seed=SEED)
            twirl = backend.twirled_circuit(noisy, t1=p)
            twirl_sampler = backend.compile_sampler(twirl, decoder=None, seed=SEED + 1)
            t1_dets, t1_speed, t1_threads = timed_detection_events(t1_sampler, RATE_SHOTS)
            tw_dets, tw_speed, tw_threads = timed_detection_events(twirl_sampler, TWIRL_RATE_SHOTS)
            a, b = rate_summary(t1_dets), rate_summary(tw_dets)
            # The first round's detectors, while the data qubits are still in |0⟩.
            coords = noisy.get_detector_coordinates()
            t0 = min(c[-1] for c in coords.values())
            first = [k for k, c in coords.items() if c[-1] == t0]
            records.append(
                {
                    "n": n,
                    "d": d,
                    "rounds": d,
                    "p": p,
                    "t1": p,
                    "qubits": noisy.num_qubits,
                    "detectors": noisy.num_detectors,
                    "t1_shots": RATE_SHOTS,
                    "t1_detection_rate": a[0],
                    "t1_detection_rate_err": a[1],
                    "t1_first_round_rate": float(t1_dets[:, first].mean()),
                    "t1_shots_per_cpu_second": t1_speed,
                    "t1_threads": t1_threads,
                    "twirl_shots": TWIRL_RATE_SHOTS,
                    "twirl_detection_rate": b[0],
                    "twirl_detection_rate_err": b[1],
                    "twirl_first_round_rate": float(tw_dets[:, first].mean()),
                    "twirl_shots_per_cpu_second": tw_speed,
                    "twirl_threads": tw_threads,
                    "z": z_score(b, a),
                }
            )
            print(
                f"[[{n},12,{d}]]".ljust(14)
                + f" {p:>6} │ {a[0]:>11.5f} ± {a[1]:.5f} {b[0]:>11.5f} ± {b[1]:.5f} "
                f"{b[0] / a[0]:>9.4f} {z_score(b, a):>6.1f} │ {t1_speed:>14.0f} {tw_speed:>9.0f}",
                flush=True,
            )
    save("qldpc_rates", records, decoder=None, seed=SEED)


def part_logical(backend: MaestroBackend) -> None:
    tasks = []
    for n in CODES:
        max_shots, max_errors = LIMITS[n]
        options = sinter.CollectionOptions(max_shots=max_shots, max_errors=max_errors)
        for p in LOGICAL_P[n]:
            noisy = circuit(n, p)
            # The decoder is in the metadata so that a resumed run can't mix decoders.
            meta = {"n": n, "d": CODES[n], "p": p, "t1": p, "decoder": DECODER_NAME}
            twirl = backend.twirled_circuit(noisy, t1=p)
            for arm, task in (
                ("t1", backend.as_sinter_task(noisy, t1=p, json_metadata={**meta, "arm": "t1"})),
                ("twirl", backend.as_sinter_task(twirl, json_metadata={**meta, "arm": "twirl"})),
            ):
                task.collection_options = options
                tasks.append(task)
    RESULTS.mkdir(exist_ok=True)
    stats = sinter.collect(
        # A decoder for [[144,12,12]] can hold several GB, so one worker per
        # thread can run out of memory: WORKERS caps them.
        num_workers=int(os.environ.get("WORKERS", os.cpu_count())),
        tasks=tasks,
        custom_decoders=backend.sinter_decoders(decoder=DECODER_CLASS(**DECODER)),
        save_resume_filepath=str(RESULTS / "qldpc_logical.csv"),
        print_progress=True,
    )
    by_key = {
        (s.json_metadata["n"], s.json_metadata["p"], s.json_metadata["arm"]): s
        for s in stats
        if s.json_metadata.get("decoder") == DECODER_NAME
    }

    records = []
    print(f"{'code':<14} {'p':>6} │ {'T1 LER':>21} {'twirl LER':>21} {'twirl/T1':>9} {'z':>6}")
    for n, d in CODES.items():
        for p in LOGICAL_P[n]:
            a, b = by_key[(n, p, "t1")], by_key[(n, p, "twirl")]
            la, lb = proportion(a.errors, a.shots), proportion(b.errors, b.shots)
            records.append(
                {
                    "n": n,
                    "d": d,
                    "rounds": d,
                    "p": p,
                    "t1": p,
                    "t1_shots": a.shots,
                    "t1_errors": a.errors,
                    "t1_seconds": a.seconds,
                    "twirl_shots": b.shots,
                    "twirl_errors": b.errors,
                    "twirl_seconds": b.seconds,
                    "z": z_score(lb, la),
                }
            )
            ratio = lb[0] / la[0] if la[0] else float("nan")
            print(
                f"[[{n},12,{d}]]".ljust(14)
                + f" {p:>6} │ {la[0]:>10.3e} ± {la[1]:.1e} {lb[0]:>10.3e} ± {lb[1]:.1e} "
                f"{ratio:>9.3f} {z_score(lb, la):>6.1f}"
            )
    save("qldpc_logical", records, decoder={"name": DECODER_NAME, **DECODER},
         limits={f"[[{n},12,{CODES[n]}]]": {"max_shots": s, "max_errors": e} for n, (s, e) in LIMITS.items() if n in CODES})


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("parts", nargs="*", choices=["rates", "logical"])
    args = parser.parse_args()
    args.parts = args.parts or ["rates", "logical"]
    backend = MaestroBackend()
    if "rates" in args.parts:
        part_rates(backend)
    if "logical" in args.parts:
        part_logical(backend)


if __name__ == "__main__":
    main()
