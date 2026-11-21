# SPDX-FileCopyrightText: 2026 Qoro Quantum
# SPDX-License-Identifier: GPL-3.0-or-later

"""Compare two sets of benchmark results, as Markdown, for a new Maestro build.

    python benchmarks/compare.py NEW_RESULTS_DIR [--base benchmarks/results]

Run the benchmarks against the new build with ``BENCHMARK_RESULTS`` set to a
directory of its own, then compare. For each benchmark both sets have, this
prints Maestro's speed in each (with Stim's, as a check that the machine ran
alike) and how well each agrees with its reference: Stim, or an exact
statevector.
"""

import argparse
import json
import pathlib

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent


def load(directory: pathlib.Path, name: str) -> dict | None:
    path = directory / f"{name}.json"
    return json.loads(path.read_text()) if path.exists() else None


def table(header: list[str], rows: list[list[str]]):
    print("| " + " | ".join(header) + " |")
    print("|:---|" + "---:|" * (len(header) - 1))
    for row in rows:
        print("| " + " | ".join(row) + " |")
    print()


def label(data: dict) -> str:
    env = data["environment"]
    source = env.get("qoro-maestro source")
    version = env["versions"]["qoro-maestro"]
    return f"qoro-maestro {version}" + (f" ({source.split(' at ')[-1]})" if source else "")


def change(new: float, base: float) -> str:
    return f"{new / base:.2f}×"


def z(a: float, ea: float, b: float, eb: float) -> float:
    se = np.hypot(ea, eb)
    return (a - b) / se if se else 0.0


def speed(base: dict, new: dict):
    print("## Detection-event throughput, one thread (shots/s)\n")
    rows = []
    for b, n in zip(base["results"], new["results"]):
        assert (b["label"], b["noise"]) == (n["label"], n["noise"])
        bm, nm = b["maestro_shots_per_second"], n["maestro_shots_per_second"]
        bs, ns = b["stim_shots_per_second"], n["stim_shots_per_second"]
        rows.append(
            [
                f"{b['label']}, {b['noise']}",
                f"{bm:,.0f}",
                f"{nm:,.0f}",
                change(nm, bm),
                change(ns, bs),
                f"{bm / bs:.2f}× → {nm / ns:.2f}×",
            ]
        )
    table(
        ["Circuit", "Maestro, base", "Maestro, new", "Change", "Stim change", "Maestro ÷ Stim"],
        rows,
    )


def rates(base: dict, new: dict):
    print("## Throughput against noise strength, rotated d=7 (Maestro ÷ Stim)\n")
    rows = []
    for b, n in zip(base["results"], new["results"]):
        bs, ns = b["shots_per_second"], n["shots_per_second"]
        rows.append(
            [
                f"{b['noise']} p={b['p']}",
                (
                    f"{bs['maestro_detection_events'] / bs['stim_detection_events']:.2f}× → "
                    f"{ns['maestro_detection_events'] / ns['stim_detection_events']:.2f}×"
                ),
                (
                    f"{bs['maestro_measurements'] / bs['stim_measurements']:.2f}× → "
                    f"{ns['maestro_measurements'] / ns['stim_measurements']:.2f}×"
                ),
            ]
        )
    table(["Noise", "Detection events", "Measurements"], rows)


def sinter_cost(base: dict, new: dict):
    print("## Cost of a shot under sinter, one process (µs/shot)\n")
    rows = []
    for b, n in zip(base["results"], new["results"]):
        bm, nm = b["seconds_per_shot"]["maestro"], n["seconds_per_shot"]["maestro"]
        rows.append(
            [
                f"d={b['d']}, batch {b['batch']:,}",
                f"{bm * 1e6:.3f}",
                f"{nm * 1e6:.3f}",
                change(nm, bm),
                (
                    f"{bm / b['seconds_per_shot']['stim']:.2f}× → "
                    f"{nm / n['seconds_per_shot']['stim']:.2f}×"
                ),
            ]
        )
    table(["Point", "Maestro, base", "Maestro, new", "Change", "Maestro ÷ Stim"], rows)


def ler(base: dict, new: dict):
    print("## Logical error rates against Stim\n")
    rows = []
    for name, data in (("base", base), ("new", new)):
        zs = np.array([r["z"] for r in data["results"]])
        rows.append(
            [
                name,
                str(len(zs)),
                f"{np.sum(zs**2):.1f}",
                f"{zs.mean():+.2f}",
                f"{np.abs(zs).max():.2f}",
                str(int((np.abs(zs) > 2).sum())),
            ]
        )
    table(["Run", "Points", "χ²", "Mean z", "Max abs(z)", "abs(z) > 2"], rows)
    # Maestro's own LER, base against new: the same distribution if nothing changed.
    zs = []
    for b, n in zip(base["results"], new["results"]):
        pb, pn = b["maestro_errors"] / b["maestro_shots"], n["maestro_errors"] / n["maestro_shots"]
        eb = np.sqrt(pb * (1 - pb) / b["maestro_shots"])
        en = np.sqrt(pn * (1 - pn) / n["maestro_shots"])
        zs.append(z(pn, en, pb, eb))
    zs = np.array(zs)
    print(
        f"Maestro's LER, new against base: χ² {np.sum(zs**2):.1f} on {len(zs)}, "
        f"max abs(z) {np.abs(zs).max():.2f}\n"
    )


def against_reference(base: dict, new: dict, name: str, ref: str, key):
    rows = []
    for b, n in zip(base["results"], new["results"]):
        bm, nm = b["mps"], n["mps"]
        rows.append(
            [
                key(b),
                f"{bm['detection_rate']:.4f}",
                f"{nm['detection_rate']:.4f}",
                f"{z(nm['detection_rate'], nm['detection_rate_err'], bm['detection_rate'], bm['detection_rate_err']):+.1f}",
                f"{b['z_detection_rate']:+.1f} → {n['z_detection_rate']:+.1f}",
                f"{b['z_lep']:+.1f} → {n['z_lep']:+.1f}",
                f"{bm['seconds_per_shot'] * 1e3:.2f} → {nm['seconds_per_shot'] * 1e3:.2f}",
            ]
        )
    table(
        [
            "Run",
            "MPS rate, base",
            "MPS rate, new",
            "z, new vs base",
            f"z vs {ref}, rate",
            f"z vs {ref}, LEP",
            "MPS ms/shot",
        ],
        rows,
    )


def mps_pauli(base: dict, new: dict):
    print("## MPS against Stim, Pauli noise\n")
    against_reference(base, new, "mps_pauli", "Stim", lambda r: f"{r['noise']}({r['p']})")


def mps_exact(base: dict, new: dict):
    print("## MPS against exact statevector\n")
    against_reference(
        base, new, "mps_exact", "SV", lambda r: f"{r['code']} d={r['d']} {r['label']} p={r['p']}"
    )


def mps_chi(base: dict, new: dict):
    print("## Bond dimension against exact statevector (detection-event rate)\n")
    for bc, nc in zip(base["results"], new["results"]):
        rows = []
        for b, n in zip(bc["results"], nc["results"]):
            rows.append(
                [
                    str(b["chi"]),
                    f"{b['mps']['detection_rate']:.4f} ({b['z_detection_rate']:+.1f})",
                    f"{n['mps']['detection_rate']:.4f} ({n['z_detection_rate']:+.1f})",
                    f"{b['mps']['seconds_per_shot'] * 1e3:.1f} → {n['mps']['seconds_per_shot'] * 1e3:.1f}",
                ]
            )
        print(
            f"{bc['name']} p={bc['p']}: statevector {bc['statevector']['detection_rate']:.4f} → "
            f"{nc['statevector']['detection_rate']:.4f}\n"
        )
        table(["χ", "Base (z vs SV)", "New (z vs SV)", "MPS ms/shot"], rows)


def mps_confirm(base: dict, new: dict):
    print("## Converged run, 40,000 shots\n")
    for name, data in (("base", base), ("new", new)):
        r = data["results"]
        print(
            f"- {name}: MPS {r['mps']['detection_rate']:.4f} against statevector "
            f"{r['statevector']['detection_rate']:.4f}, z {r['z_detection_rate']:+.2f}"
        )
    print()


def mps_scaling(base: dict, new: dict):
    print("## Repetition codes, coherent noise: time a shot on 12 cores\n")
    rows = []
    for b, n in zip(base["results"], new["results"]):
        sv = ""
        if "statevector" in b and "statevector" in n:
            sv = (
                f"{b['statevector']['seconds_per_shot'] * 1e3:.2f} → "
                f"{n['statevector']['seconds_per_shot'] * 1e3:.2f}"
            )
        rows.append(
            [
                f"d={b['d']} ({b['qubits']} qubits)",
                f"{b['mps32']['seconds_per_shot'] * 1e3:.2f}",
                f"{n['mps32']['seconds_per_shot'] * 1e3:.2f}",
                change(n["mps32"]["seconds_per_shot"], b["mps32"]["seconds_per_shot"]),
                f"{b['mps32_vs_mps64']['z_detection_rate']:+.1f} → {n['mps32_vs_mps64']['z_detection_rate']:+.1f}",
                sv,
            ]
        )
    table(["Code", "MPS χ=32 ms, base", "new", "Change", "z vs χ=64", "Statevector ms"], rows)
    bs, ns = base.get("surface"), new.get("surface")
    if bs and ns:
        print(
            f"Rotated d=3: MPS {bs['mps32_seconds_per_shot'] * 1e3:.2f} → "
            f"{ns['mps32_seconds_per_shot'] * 1e3:.2f} ms, statevector "
            f"{bs['sv_seconds_per_shot'] * 1e3:.2f} → {ns['sv_seconds_per_shot'] * 1e3:.2f} ms\n"
        )


PARTS = {
    "stabilizer_speed": speed,
    "stabilizer_rates": rates,
    "stabilizer_sinter": sinter_cost,
    "stabilizer_ler": ler,
    "mps_pauli": mps_pauli,
    "mps_exact": mps_exact,
    "mps_chi": mps_chi,
    "mps_confirm": mps_confirm,
    "mps_scaling": mps_scaling,
}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("new", type=pathlib.Path, help="results of the new build")
    parser.add_argument("--base", type=pathlib.Path, default=HERE / "results")
    args = parser.parse_args()
    shown = False
    for name, fn in PARTS.items():
        base, new = load(args.base, name), load(args.new, name)
        if base is None or new is None:
            continue
        if not shown:
            print(f"Base: {label(base)}. New: {label(new)}.\n")
            shown = True
        fn(base, new)


if __name__ == "__main__":
    main()
