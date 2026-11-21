# SPDX-FileCopyrightText: 2026 Qoro Quantum
# SPDX-License-Identifier: GPL-3.0-or-later

"""Which decoder for the qLDPC T1 study: speed, memory and accuracy on the same shots.

Detection events are sampled once per code from the T1 twirl (Pauli frames, Stim),
and every decoder decodes the same shots, so failures compare pair by pair.
OSD-CS of order 7 with 1000 BP iterations (the pilot's) is the reference.

Each (code, decoder) pair runs in its own pool of fresh processes, so the peak
memory of a worker is that decoder's. On [[144,12,12]] a reference worker holds
about 5 GB, so that code runs on fewer workers (WORKERS_144) to stay inside RAM.

    OMP_NUM_THREADS=1 python benchmarks/qldpc_decoders.py

Writes benchmarks/results/qldpc_decoders.json. qldpc.py uses the fastest decoder
that stays closest to the reference.
"""

from common import BpLsd, BpOsd, bivariate_bicycle, memory_circuit, save

# isort: split
import multiprocessing as mp
import os
import resource
import time

import numpy as np
import stim

from deltakit_maestro import MaestroBackend

MS = dict(bp_method="minimum_sum", ms_scaling_factor=0.625)
REFERENCE = "OSD-CS 7, 1000 iterations"
DECODERS = {
    REFERENCE: (BpOsd, dict(max_iter=1000, osd_method="osd_cs", osd_order=7, **MS)),
    "OSD-0, 100 iterations": (BpOsd, dict(max_iter=100, osd_method="osd0", osd_order=0, **MS)),
    "LSD-CS 2, 100 iterations": (BpLsd, dict(max_iter=100, lsd_method="lsd_cs", lsd_order=2, **MS)),
    "LSD-0, 100 iterations": (BpLsd, dict(max_iter=100, lsd_method="lsd0", lsd_order=0, **MS)),
}
WORKERS = {72: int(os.environ.get("WORKERS_72", os.cpu_count())), 144: int(os.environ.get("WORKERS_144", 16))}
# (n, distance = rounds, p, shots)
POINTS = [(72, 6, 0.001, 4000), (72, 6, 0.0015, 3000), (144, 12, 0.0015, 400)]

_decoder = {}


def work(task):
    dem_text, dec_name, idx, dets, obs = task
    if dec_name not in _decoder:  # One decoder per process: each pool runs one.
        cls, settings = DECODERS[dec_name]
        _decoder[dec_name] = cls(**settings).compile_decoder_for_dem(dem=stim.DetectorErrorModel(dem_text))
    t0 = time.process_time()
    pred = _decoder[dec_name].decode_shots_bit_packed(bit_packed_detection_event_data=dets)
    seconds = time.process_time() - t0
    peak_gb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2**20  # KiB on Linux
    return idx, np.any(pred != obs, axis=1), seconds, peak_gb


def main():
    backend = MaestroBackend()
    out = []
    for n, d, p, shots in POINTS:
        key = f"[[{n},12,{d}]] p={p}"
        twirl = backend.twirled_circuit(memory_circuit(bivariate_bicycle(n), "SI1000", p, d), t1=p)
        dem = twirl.detector_error_model(decompose_errors=False)
        dets, obs = twirl.compile_detector_sampler(seed=2026).sample(shots, separate_observables=True, bit_packed=True)
        workers = WORKERS[n]
        chunks = 2 * workers
        bounds = np.linspace(0, shots, chunks + 1).astype(int)
        print(f"\n{key}: {shots} shots, {dem.num_detectors} detectors, {dem.num_errors} error mechanisms, "
              f"{workers} workers", flush=True)
        fails = {}
        for dec_name in DECODERS:
            tasks = [(str(dem), dec_name, i, dets[bounds[i]:bounds[i + 1]], obs[bounds[i]:bounds[i + 1]])
                     for i in range(chunks)]
            parts, seconds, peak = {}, 0.0, 0.0
            wall = time.perf_counter()
            with mp.get_context("spawn").Pool(workers) as pool:
                for idx, f, s, gb in pool.imap_unordered(work, tasks):
                    parts[idx], seconds, peak = f, seconds + s, max(peak, gb)
            wall = time.perf_counter() - wall
            fails[dec_name] = np.concatenate([parts[i] for i in range(chunks)])
            f, ref = fails[dec_name], fails.get(REFERENCE, fails[dec_name])
            rec = {"n": n, "d": d, "rounds": d, "p": p, "t1": p, "shots": shots, "detectors": dem.num_detectors,
                   "error_mechanisms": dem.num_errors, "decoder": dec_name, "settings": DECODERS[dec_name][1],
                   "failures": int(f.sum()), "cpu_ms_per_shot": seconds / shots * 1e3, "workers": workers,
                   "wall_seconds": wall, "peak_worker_gb": peak,
                   "fail_only_this": int((f & ~ref).sum()), "fail_only_reference": int((ref & ~f).sum())}
            out.append(rec)
            print(f"  {dec_name:<26} failures {f.sum():>4} ({f.mean():.4f})  vs reference +{rec['fail_only_this']}"
                  f" −{rec['fail_only_reference']}  {rec['cpu_ms_per_shot']:9.1f} CPU ms/shot  "
                  f"{peak:4.1f} GB/worker  {wall:5.0f} s", flush=True)
    save("qldpc_decoders", out, reference=REFERENCE, workers={f"[[{n},12]]": w for n, w in WORKERS.items()})


if __name__ == "__main__":
    main()
