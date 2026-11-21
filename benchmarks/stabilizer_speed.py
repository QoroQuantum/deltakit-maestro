# SPDX-FileCopyrightText: 2026 Qoro Quantum
# SPDX-License-Identifier: GPL-3.0-or-later

"""Detection-event sampling throughput: Maestro's Pauli frames against Stim.

For each memory circuit, both simulators are compiled once, warmed up, then
timed over REPEATS rounds of the same number of shots, Maestro and Stim taking
turns within each round so a change in machine load hits both. The fastest run
of each is reported, the least disturbed by anything else on the machine, and
the median is kept too. Maestro's time is
``MaestroCompiledSampler.sample_detection_events``, which includes converting
measurements to detection events, and Stim's is
``compile_detector_sampler().sample``. Both return unpacked bool arrays. CPU
time is recorded with wall time, to show how many threads each run used, and
the load average before and after, to show what else was running.

Three parts:

``codes``
    Detection events across codes, sizes and noise models (about 5 minutes).
``rates``
    Detection events and raw measurements on one circuit as the noise strength
    changes: Stim's detector sampler gets faster as noise gets sparser, while
    Maestro converts its measurements with Stim's converter, whatever the noise.
``sinter``
    The cost of a shot under sinter, sampling and decoding, by batch size, for
    Maestro's sampler and sinter's own Stim sampler, in one process.

    python benchmarks/stabilizer_speed.py              # every part, about 7 minutes
    python benchmarks/stabilizer_speed.py rates sinter # some of them

Writes benchmarks/results/stabilizer_<part>.json (``codes`` writes
stabilizer_speed.json).
"""

from common import CODES, bivariate_bicycle, memory_circuit, save, surface_code

# isort: split
import argparse
import os
import statistics
import time

import sinter
from sinter._decoding._stim_then_decode_sampler import StimThenDecodeSampler

from deltakit_maestro import MaestroBackend

REPEATS = 7
TARGET_SECONDS = 0.5  # Shots per run are chosen so a run takes about this long.
MAX_OUTPUT_BYTES = 100e6  # ...and so its bool output stays under this size.
P = 0.002

# (label, code, distance, rounds, noise model)
CIRCUITS = [
    *[(f"Rotated d={d}", "rotated", d, d, "SI1000") for d in (3, 5, 7, 9, 11, 13, 15)],
    *[(f"Rotated d={d}", "rotated", d, d, "SD6") for d in (3, 7, 11)],
    *[(f"Rotated d={d}", "rotated", d, d, "Toy") for d in (3, 7, 11)],
    ("Repetition d=25", "repetition", 25, 25, "SI1000"),
    ("Unrotated planar d=7", "unrotated", 7, 7, "SI1000"),
    ("Toric d=7", "toric", 7, 7, "SI1000"),
    ("BB [[72,12,6]]", "bb", 72, 6, "SI1000"),
    ("BB [[144,12,12]]", "bb", 144, 12, "SI1000"),
]


def timed(fns: dict, shots: int) -> dict:
    """Wall and CPU seconds of each ``fn(shots)``, taking turns, REPEATS rounds."""
    runs = {name: [] for name in fns}
    for _ in range(REPEATS):
        for name, fn in fns.items():
            w0, c0 = time.perf_counter(), time.process_time()
            fn(shots)
            runs[name].append((time.perf_counter() - w0, time.process_time() - c0))
    out = {}
    for name, times in runs.items():
        best_wall, best_cpu = min(times)
        out[name] = {
            "seconds": best_wall,
            "cpu_seconds": best_cpu,
            "median_seconds": statistics.median(w for w, _ in times),
            "all_seconds": [w for w, _ in times],
        }
    return out


def part_codes():
    backend = MaestroBackend()
    records = []
    header = f"{'circuit':<22} {'noise':<7} {'qubits':>6} {'dets':>6} │ {'Maestro/s':>10} {'Stim/s':>10} {'ratio':>6} │ {'threads M/S':>11}"
    print(header)
    print("─" * len(header))
    for label, family, d, rounds, noise in CIRCUITS:
        code = bivariate_bicycle(d) if family == "bb" else CODES[family](d)
        circuit = memory_circuit(code, noise, P, rounds)

        t0 = time.perf_counter()
        stim_sampler = circuit.compile_detector_sampler(seed=1)
        stim_compile = time.perf_counter() - t0
        # The second compile is timed, so one-time setup isn't counted. It
        # includes building the DEM, which a Stim user needs to decode too.
        backend.compile_sampler(circuit, decoder=None, seed=1)
        t0 = time.perf_counter()
        maestro_sampler = backend.compile_sampler(circuit, decoder=None, seed=1)
        maestro_compile = time.perf_counter() - t0

        # Size the runs from a short Stim run.
        probe = 2000
        t0 = time.perf_counter()
        stim_sampler.sample(probe)
        per_shot = (time.perf_counter() - t0) / probe
        shots = int(min(TARGET_SECONDS / per_shot, MAX_OUTPUT_BYTES / circuit.num_detectors))
        shots = max(1000, shots // 1000 * 1000)

        # Warm up, then time.
        stim_sampler.sample(shots)
        maestro_sampler.sample_detection_events(shots)
        load_before = os.getloadavg()[0]
        t = timed(
            {"maestro": maestro_sampler.sample_detection_events, "stim": stim_sampler.sample}, shots
        )
        maestro_wall, maestro_cpu = t["maestro"]["seconds"], t["maestro"]["cpu_seconds"]
        stim_wall, stim_cpu = t["stim"]["seconds"], t["stim"]["cpu_seconds"]

        record = {
            "label": label,
            "code": family,
            "distance": d,
            "rounds": rounds,
            "noise": noise,
            "p": P,
            "qubits": circuit.num_qubits,
            "detectors": circuit.num_detectors,
            "shots": shots,
            "maestro": t["maestro"],
            "stim": t["stim"],
            "maestro_compile_seconds": maestro_compile,
            "stim_compile_seconds": stim_compile,
            "load_average": [load_before, os.getloadavg()[0]],
            "maestro_shots_per_second": shots / maestro_wall,
            "stim_shots_per_second": shots / stim_wall,
        }
        records.append(record)
        print(
            f"{label:<22} {noise:<7} {circuit.num_qubits:>6} {circuit.num_detectors:>6} │ "
            f"{record['maestro_shots_per_second']:>10.3g} {record['stim_shots_per_second']:>10.3g} "
            f"{record['maestro_shots_per_second'] / record['stim_shots_per_second']:>6.2f} │ "
            f"{maestro_cpu / maestro_wall:>5.1f} {stim_cpu / stim_wall:>5.1f} │ "
            f"load {load_before:.1f}",
            flush=True,
        )
    save("stabilizer_speed", records, repeats=REPEATS, statistic="fastest of the repeats")


# The rotated d=7 code, 7 rounds, at three strengths of two noise models.
RATES = [(noise, p) for noise in ("Toy", "SI1000") for p in (0.0005, 0.002, 0.008)]
RATES_SHOTS = 200_000


def part_rates():
    backend = MaestroBackend()
    records = []
    for noise, p in RATES:
        circuit = surface_code(7, noise, p)
        maestro_sampler = backend.compile_sampler(circuit, decoder=None, seed=1)
        stim_detectors = circuit.compile_detector_sampler(seed=1)
        stim_measurements = circuit.compile_sampler(seed=1)
        fns = {
            "maestro_detection_events": maestro_sampler.sample_detection_events,
            "stim_detection_events": stim_detectors.sample,
            "maestro_measurements": maestro_sampler.sample_measurements,
            "stim_measurements": stim_measurements.sample,
        }
        for fn in fns.values():
            fn(RATES_SHOTS)  # Warm up.
        t = timed(fns, RATES_SHOTS)
        rates = {name: RATES_SHOTS / t[name]["seconds"] for name in fns}
        records.append({"noise": noise, "p": p, "shots_per_second": rates, "timings": t})
        print(
            f"{noise:<7} p={p:<7} detection events: Maestro {rates['maestro_detection_events']:,.0f}/s "
            f"Stim {rates['stim_detection_events']:,.0f}/s │ measurements: Maestro "
            f"{rates['maestro_measurements']:,.0f}/s Stim {rates['stim_measurements']:,.0f}/s",
            flush=True,
        )
    save("stabilizer_rates", records, code="rotated d=7, 7 rounds", shots=RATES_SHOTS)


SINTER_DISTANCES = [3, 7]
SINTER_BATCHES = [100, 1_000, 10_000, 100_000]
SINTER_SHOTS = 200_000  # Per batch size, so small batches are repeated.


def part_sinter():
    backend = MaestroBackend()
    stim_then_decode = StimThenDecodeSampler(
        decoder=sinter.BUILT_IN_DECODERS["pymatching"],
        count_observable_error_combos=False,
        count_detection_events=False,
        tmp_dir=None,
    )
    records = []
    for d in SINTER_DISTANCES:
        circuit = surface_code(d, "SI1000", P)
        maestro_sampler = backend.compile_sampler(circuit, decoder="pymatching", seed=1)
        # Sinter's own sampler for a plain Stim task, decoding the same DEM.
        stim_task = sinter.Task(
            circuit=circuit,
            decoder="pymatching",
            detector_error_model=maestro_sampler.task.detector_error_model,
        )
        stim_sampler = stim_then_decode.compiled_sampler_for_task(stim_task)
        for batch in SINTER_BATCHES:
            calls = SINTER_SHOTS // batch

            def repeat(sampler, calls=calls):
                return lambda shots: [sampler.sample(shots) for _ in range(calls)]

            fns = {"maestro": repeat(maestro_sampler), "stim": repeat(stim_sampler)}
            for fn in fns.values():
                fn(batch)  # Warm up.
            t = timed(fns, batch)
            per_shot = {name: t[name]["seconds"] / SINTER_SHOTS for name in fns}
            records.append({"d": d, "batch": batch, "seconds_per_shot": per_shot, "timings": t})
            print(
                f"d={d} batch {batch:>7,}: Maestro {per_shot['maestro'] * 1e6:6.3f} µs/shot, "
                f"Stim {per_shot['stim'] * 1e6:6.3f} µs/shot, "
                f"ratio {per_shot['maestro'] / per_shot['stim']:.2f}",
                flush=True,
            )
    save("stabilizer_sinter", records, noise=f"SI1000({P})", decoder="pymatching")


PARTS = {"codes": part_codes, "rates": part_rates, "sinter": part_sinter}


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
