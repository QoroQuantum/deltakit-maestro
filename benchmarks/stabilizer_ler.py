# SPDX-FileCopyrightText: 2026 Qoro Quantum
# SPDX-License-Identifier: GPL-3.0-or-later

"""Logical error rates under sinter.collect: Maestro's stabilizer against Stim.

Rotated surface code memory experiments (d rounds) under three Deltakit noise
models, each sampled twice in one ``sinter.collect``: by Stim, as sinter does by
default, and by Maestro through ``MaestroBackend.as_sinter_task``. Both are
decoded by PyMatching with the circuit's own detector error model, so any
difference between them is a difference in sampling. Sinter records each task's
worker seconds, which gives the end-to-end cost of sampling and decoding.

    python benchmarks/stabilizer_ler.py         # a few minutes on 12 cores

Writes benchmarks/results/stabilizer_ler.csv (sinter's own format, not committed;
rerunning resumes from it, so delete it to sample afresh) and
benchmarks/results/stabilizer_ler.json.
"""

from common import RESULTS, proportion, save, surface_code, z_score

# isort: split
import os

import sinter

from deltakit_maestro import MaestroBackend

NOISES = ["SI1000", "SD6", "Toy"]
DISTANCES = [3, 5, 7]
P_VALUES = [0.001, 0.002, 0.003, 0.005, 0.007, 0.01]
MAX_SHOTS = 50_000_000
MAX_ERRORS = 5_000


def tasks(backend: MaestroBackend) -> list[sinter.Task]:
    out = []
    for noise in NOISES:
        for d in DISTANCES:
            for p in P_VALUES:
                circuit = surface_code(d, noise, p)
                # Not "noise": as_sinter_task puts the noise layers there.
                meta = {"noise_model": noise, "d": d, "p": p}
                out.append(
                    sinter.Task(
                        circuit=circuit,
                        decoder="pymatching",
                        json_metadata={**meta, "sampler": "stim"},
                    )
                )
                out.append(
                    backend.as_sinter_task(circuit, json_metadata={**meta, "sampler": "maestro"})
                )
    return out


def main():
    backend = MaestroBackend()
    csv = RESULTS / "stabilizer_ler.csv"
    RESULTS.mkdir(exist_ok=True)
    stats = sinter.collect(
        num_workers=os.cpu_count(),
        tasks=tasks(backend),
        custom_decoders=backend.sinter_decoders(decoder="pymatching"),
        max_shots=MAX_SHOTS,
        max_errors=MAX_ERRORS,
        save_resume_filepath=str(csv),
        print_progress=True,
    )

    by_key = {}
    for s in stats:
        m = s.json_metadata
        by_key[(m["noise_model"], m["d"], m["p"], m["sampler"])] = s

    records = []
    print(
        f"{'noise':<7} {'d':>2} {'p':>6} │ {'Maestro LER':>22} {'Stim LER':>22} {'z':>6} │ {'µs/shot M/S':>13}"
    )
    for noise in NOISES:
        for d in DISTANCES:
            for p in P_VALUES:
                m = by_key[(noise, d, p, "maestro")]
                s = by_key[(noise, d, p, "stim")]
                lm, ls = proportion(m.errors, m.shots), proportion(s.errors, s.shots)
                z = z_score(lm, ls)
                records.append(
                    {
                        "noise": noise,
                        "d": d,
                        "p": p,
                        "maestro_shots": m.shots,
                        "maestro_errors": m.errors,
                        "maestro_seconds": m.seconds,
                        "stim_shots": s.shots,
                        "stim_errors": s.errors,
                        "stim_seconds": s.seconds,
                        "z": z,
                    }
                )
                print(
                    f"{noise:<7} {d:>2} {p:>6} │ {lm[0]:>10.3e} ± {lm[1]:.1e} "
                    f"{ls[0]:>10.3e} ± {ls[1]:.1e} {z:>6.2f} │ "
                    f"{m.seconds / m.shots * 1e6:>6.2f} {s.seconds / s.shots * 1e6:>6.2f}"
                )
    save("stabilizer_ler", records, max_shots=MAX_SHOTS, max_errors=MAX_ERRORS)


if __name__ == "__main__":
    main()
