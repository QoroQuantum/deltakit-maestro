# SPDX-FileCopyrightText: 2026 Qoro Quantum
# SPDX-License-Identifier: GPL-3.0-or-later

"""Print the tables the Benchmarks pages quote, as Markdown, from results/.

    python benchmarks/tables.py

A table whose results file is missing is skipped.
"""

import json
import os
import pathlib

import numpy as np

RESULTS = pathlib.Path(
    os.environ.get("BENCHMARK_RESULTS") or pathlib.Path(__file__).resolve().parent / "results"
)


def load(name: str) -> dict | None:
    path = RESULTS / f"{name}.json"
    return json.loads(path.read_text()) if path.exists() else None


def rate(value: float) -> str:
    """Shots per second, to three significant figures."""
    for unit, scale in (("M", 1e6), ("k", 1e3)):
        if value >= scale:
            return f"{value / scale:.3g}{unit}"
    return f"{value:.3g}"


def pm(value: float, err: float, digits: int = 4) -> str:
    return f"{value:.{digits}f} ± {err:.{digits}f}"


def table(header: list[str], rows: list[list[str]], align: str | None = None):
    align = align or "l" + "r" * (len(header) - 1)
    print("| " + " | ".join(header) + " |")
    print("|" + "|".join(":---" if a == "l" else "---:" for a in align) + "|")
    for row in rows:
        print("| " + " | ".join(row) + " |")
    print()


def environment(data: dict):
    env = data["environment"]
    v = env["versions"]
    source = (
        f", qoro-maestro from {env['qoro-maestro source']}" if "qoro-maestro source" in env else ""
    )
    print(
        f"<!-- {env['date']}, {env['cpu']} ({env['cores']} cores), Python {env['python']}, "
        + ", ".join(f"{k} {v[k]}" for k in v)
        + source
        + " -->\n"
    )


def stabilizer_speed(data: dict):
    print("## stabilizer_speed\n")
    environment(data)
    rows = []
    for r in data["results"]:
        m, s = r["maestro_shots_per_second"], r["stim_shots_per_second"]
        rows.append(
            [
                r["label"],
                r["noise"],
                str(r["qubits"]),
                str(r["detectors"]),
                rate(m),
                rate(s),
                f"{m / s:.2f}×",
                f"{r['maestro']['cpu_seconds'] / r['maestro']['seconds']:.1f}",
            ]
        )
    table(
        ["Circuit", "Noise", "Qubits", "Detectors", "Maestro", "Stim", "Maestro ÷ Stim", "Threads"],
        rows,
        "llrrrrrr",
    )
    loads = [x for r in data["results"] for x in r["load_average"]]
    print(f"load average during the run: {min(loads):.1f} to {max(loads):.1f}\n")


def stabilizer_ler(data: dict):
    print("## stabilizer_ler\n")
    environment(data)
    rows = data["results"]
    z = np.array([r["z"] for r in rows])
    print(
        f"{len(z)} comparisons: mean z {z.mean():+.2f}, sd {z.std(ddof=1):.2f}, "
        f"max |z| {np.abs(z).max():.2f}, |z| > 2: {(np.abs(z) > 2).sum()}, "
        f"chi2 {np.sum(z**2):.1f} on {len(z)} dof\n"
    )
    out = []
    for noise in dict.fromkeys(r["noise"] for r in rows):
        sel = [r for r in rows if r["noise"] == noise]
        ms = sum(r["maestro_shots"] for r in sel)
        ss = sum(r["stim_shots"] for r in sel)
        mt = sum(r["maestro_seconds"] for r in sel)
        st = sum(r["stim_seconds"] for r in sel)
        zs = np.array([r["z"] for r in sel])
        out.append(
            [
                noise,
                f"{ms:,}",
                f"{ss:,}",
                f"{np.abs(zs).max():.2f}",
                f"{mt / ms * 1e6:.2f}",
                f"{st / ss * 1e6:.2f}",
            ]
        )
    table(
        ["Noise", "Maestro shots", "Stim shots", "max abs(z)", "Maestro µs/shot", "Stim µs/shot"],
        out,
    )
    out = []
    for d in sorted({r["d"] for r in rows}):
        sel = [r for r in rows if r["d"] == d]
        ms = sum(r["maestro_shots"] for r in sel)
        ss = sum(r["stim_shots"] for r in sel)
        mt = sum(r["maestro_seconds"] for r in sel)
        st = sum(r["stim_seconds"] for r in sel)
        out.append(
            [f"d={d}", f"{mt / ms * 1e6:.2f}", f"{st / ss * 1e6:.2f}", f"{mt / ms / (st / ss):.2f}"]
        )
    table(["Distance", "Maestro µs/shot", "Stim µs/shot", "ratio"], out)


def mps_pauli(data: dict):
    print("## mps_pauli\n")
    environment(data)
    rows = []
    zs = []
    for r in data["results"]:
        a, b = r["mps"], r["stim"]
        zs += [r["z_detection_rate"], r["z_lep"]]
        rows.append(
            [
                r["noise"],
                f"{r['p']:g}",
                pm(a["detection_rate"], a["detection_rate_err"]),
                f"{b['detection_rate']:.4f}",
                f"{r['z_detection_rate']:+.1f}",
                pm(a["lep"], a["lep_err"]),
                f"{b['lep']:.4f}",
                f"{r['z_lep']:+.1f}",
            ]
        )
    table(
        ["Noise", "p", "Detection rate, MPS", "Stim", "z", "LEP, MPS", "Stim", "z"],
        rows,
        "lrrrrrrr",
    )
    zs = np.array(zs)
    print(f"chi2 {np.sum(zs**2):.1f} on {len(zs)}; max |z| {np.abs(zs).max():.2f}")
    print(
        f"MPS shots {data['results'][0]['mps']['shots']:,}, Stim {data['results'][0]['stim']['shots']:,}"
    )
    worst = max(r["max_abs_z_detector"] for r in data["results"])
    print(f"worst single detector |z| {worst:.2f} of {data['results'][0]['num_detectors']}\n")


def mps_exact(data: dict):
    print("## mps_exact\n")
    environment(data)
    rows = []
    zs = []
    for r in data["results"]:
        a, b = r["mps"], r["statevector"]
        zs += [r["z_detection_rate"], r["z_lep"]]
        noise = {"coherent": "coherent", "T1": "`T1`", "full": "Pauli + coherent + `T1`"}[
            r["label"]
        ]
        rows.append(
            [
                f"{r['code']} d={r['d']}",
                str(r["qubits"]),
                noise,
                f"{r['p']:g}",
                f"{a['shots']:,}",
                pm(a["detection_rate"], a["detection_rate_err"]),
                pm(b["detection_rate"], b["detection_rate_err"]),
                f"{r['z_detection_rate']:+.1f}",
                pm(a["lep"], a["lep_err"]),
                pm(b["lep"], b["lep_err"]),
                f"{r['z_lep']:+.1f}",
                f"{a['seconds_per_shot'] * 1e3:.1f}",
                f"{b['seconds_per_shot'] * 1e3:.1f}",
            ]
        )
    table(
        [
            "Code",
            "Qubits",
            "Noise",
            "p",
            "Shots",
            "Det. rate, MPS",
            "Statevector",
            "z",
            "LEP, MPS",
            "Statevector",
            "z",
            "MPS ms",
            "SV ms",
        ],
        rows,
        "lrlrrrrrrrrrr",
    )
    zs = np.array(zs)
    print(f"chi2 {np.sum(zs**2):.1f} on {len(zs)}; max |z| {np.abs(zs).max():.2f}")
    worst = max(r["max_abs_z_detector"] for r in data["results"])
    print(f"worst single detector |z| {worst:.2f}\n")


def mps_chi(data: dict):
    print("## mps_chi\n")
    environment(data)
    for case in data["results"]:
        sv = case["statevector"]
        print(
            f"{case['name']} p={case['p']}: statevector {sv['shots']:,} shots, rate "
            f"{pm(sv['detection_rate'], sv['detection_rate_err'])}, LEP {pm(sv['lep'], sv['lep_err'])}, "
            f"{sv['seconds_per_shot'] * 1e3:.1f} ms/shot\n"
        )
        rows = []
        for r in case["results"]:
            a = r["mps"]
            rows.append(
                [
                    str(r["chi"]),
                    pm(a["detection_rate"], a["detection_rate_err"]),
                    f"{r['z_detection_rate']:+.1f}",
                    pm(a["lep"], a["lep_err"]),
                    f"{r['z_lep']:+.1f}",
                    f"{a['seconds_per_shot'] * 1e3:.1f}",
                ]
            )
        table(["χ", "Detection rate", "z", "LEP", "z", "ms/shot"], rows)


def mps_confirm(data: dict):
    print("## mps_confirm\n")
    environment(data)
    r = data["results"]
    a, b = r["mps"], r["statevector"]
    print(
        f"{data['noise']}, χ={data['max_bond_dimension']}, {a['shots']:,} shots each: "
        f"MPS {pm(a['detection_rate'], a['detection_rate_err'])}, "
        f"statevector {pm(b['detection_rate'], b['detection_rate_err'])}, "
        f"z {r['z_detection_rate']:+.2f}; LEP {pm(a['lep'], a['lep_err'])} against "
        f"{pm(b['lep'], b['lep_err'])}, z {r['z_lep']:+.2f}; "
        f"worst detector |z| {r['max_abs_z_detector']:.2f}\n"
    )


def mps_scaling(data: dict):
    print("## mps_scaling\n")
    environment(data)
    print(f"load average {data.get('load_average')}\n")
    rows = []
    for r in data["results"]:
        sv = r.get("statevector")
        a = r["mps32"]
        rows.append(
            [
                f"d={r['d']}",
                str(r["qubits"]),
                f"{a['seconds_per_shot'] * 1e3:.2f}",
                f"{r['mps64']['seconds_per_shot'] * 1e3:.2f}",
                f"{sv['seconds_per_shot'] * 1e3:.2f}" if sv else "",
                pm(a["detection_rate"], a["detection_rate_err"]),
                f"{r['mps32_vs_mps64']['z_detection_rate']:+.1f}",
                f"{r['mps32_vs_statevector']['z_detection_rate']:+.1f}" if sv else "",
                f"{2 ** r['qubits'] * 16 / 2**20:,.0f} MiB" if r["qubits"] <= 40 else "",
            ]
        )
    table(
        [
            "Code",
            "Qubits",
            "MPS χ=32 ms",
            "MPS χ=64 ms",
            "Statevector ms",
            "Detection rate, χ=32",
            "z, χ=64",
            "z, statevector",
            "SV memory",
        ],
        rows,
    )
    s = data.get("surface")
    if s:
        print(
            f"{s['code']}: MPS χ=32 {s['mps32_seconds_per_shot'] * 1e3:.2f} ms, "
            f"SV {s['sv_seconds_per_shot'] * 1e3:.2f} ms\n"
        )


def coherent(data: dict):
    """Coherent noise on the MPS against its Pauli twirl on Stim."""
    environment(data)
    by_distance = "code" not in data  # The repetition part varies d; the surface part only p.
    rows = []
    for r in sorted(data["results"], key=lambda r: (-r["p"], r["d"])):
        c, t = r["coherent"], r["twirl"]
        rows.append(
            ([f"d={r['d']}"] if by_distance else [])
            + [
                f"{r['p']:g}",
                f"{c['detection_rate']:.4f}",
                f"{t['detection_rate']:.4f}",
                pm(r["detection_rate_ratio"], r["detection_rate_ratio_err"], 3),
                f"{c['lep']:.2e}" if c["lep"] < 1e-3 else f"{c['lep']:.4f}",
                f"{t['lep']:.2e}" if t["lep"] < 1e-3 else f"{t['lep']:.4f}",
                pm(r["lep_ratio"], r["lep_ratio_err"], 2),
                f"{c['errors']:,} in {c['shots']:,}",
            ]
        )
    table(
        (["Code"] if by_distance else [])
        + [
            "p",
            "Detection rate, coherent",
            "Twirl",
            "Ratio",
            "LEP, coherent",
            "Twirl",
            "Ratio",
            "Coherent errors",
        ],
        rows,
    )
    check = data.get("chi_check")
    if check:
        where = f"d={check['d']} " if "d" in check else ""
        print(
            f"χ=32 against χ=64 at {where}p={check['p']}: z {check['z_detection_rate']:+.2f} "
            f"(detection rate), {check['z_lep']:+.2f} (LEP), "
            f"{check['chi32']['shots']:,} shots each\n"
        )
    if not data.get("complete", True):
        print("(incomplete: the run is still going or stopped early)\n")


def ms(seconds: float | None) -> str:
    return "" if seconds is None else f"{seconds * 1e3:.1f}" if seconds < 1 else f"{seconds * 1e3:,.0f}"


def extended_exact(data: dict):
    """The extended stabilizer at several tolerances against the exact statevector."""
    environment(data)
    for case in dict.fromkeys(r["case"] for r in data["results"]):
        rows = [r for r in data["results"] if r["case"] == case]
        sv = rows[0]["statevector"]
        lines = [["statevector (exact)", f"{sv['detection_rate']:.5f}", "", f"{sv['lep']:.4f}", "",
                  ms(sv["seconds_per_shot"])]]
        for r in rows:
            e = r["extended"]
            lines.append([f"tolerance {r['tolerance']:g}", f"{e['detection_rate']:.5f}", f"{r['z_detection_rate']:+.1f}",
                          f"{e['lep']:.4f}", f"{r['z_lep']:+.1f}", ms(e["seconds_per_shot"])])
        print(f"{case}, {sv['shots']:,} shots each:\n")
        table(["Run", "Detection rate", "z", "LEP", "z", "ms/shot"], lines)
    if not data.get("complete", True):
        print("(incomplete: the run is still going or stopped early)\n")


def extended_twirl(data: dict):
    """Coherent on the extended stabilizer, at two tolerances, against its Pauli twirl on Stim."""
    environment(data)
    lines = []
    for r in data["results"]:
        c, k, t = r["coherent"], r["check"], r["twirl"]
        name = f"rotated d={r['d']}" if r.get("code") == "rotated" else r["code"]
        enough = c["errors"] >= 100  # Fewer logical errors say little about a ratio.
        check_ratio = k["detection_rate"] / t["detection_rate"]
        check_err = check_ratio * np.hypot(k["detection_rate_err"] / k["detection_rate"],
                                           t["detection_rate_err"] / t["detection_rate"])
        lines.append([
            name,
            str(r["qubits"]),
            f"{t['detection_rate']:.4f}",
            f"{c['detection_rate']:.4f}",
            pm(r["detection_rate_ratio"], r["detection_rate_ratio_err"], 3),
            pm(r["lep_ratio"], r["lep_ratio_err"], 2) if enough else "—",
            f"{k['detection_rate']:.4f}",
            pm(check_ratio, check_err, 3),
            f"{r['check_agreement']['z_detection_rate']:+.1f}",
            f"{c['seconds_per_shot']:.3g}",
            f"{k['seconds_per_shot']:.3g}",
            f"{c['shots']:,} / {k['shots']:,}",
        ])
    tol, check = f"{data['tolerance']:g}", f"{data['check_tolerance']:g}"
    table(["Code", "Qubits", "Twirl", f"Coherent, {tol}", "Ratio", "LEP ratio", f"Coherent, {check}", "Ratio",
           "z", f"s/shot, {tol}", f"s/shot, {check}", "Shots"], lines)
    if not data.get("complete", True):
        print("(incomplete: the run is still going or stopped early)\n")


def bb(r: dict) -> str:
    return f"[[{r['n']},12,{r['d']}]]"


def qldpc_rates(data: dict):
    """T1 decay on the stabilizer against its twirl: detection rates, and sampling speed."""
    environment(data)
    rows = [
        [
            bb(r),
            f"{r['p']:g}",
            f"{r['t1_first_round_rate']:.4f}",
            f"{r['twirl_first_round_rate']:.4f}",
            f"{r['twirl_first_round_rate'] / r['t1_first_round_rate']:.3f}",
            f"{r['t1_detection_rate']:.4f}",
            f"{r['twirl_detection_rate']:.4f}",
            f"{r['twirl_detection_rate'] / r['t1_detection_rate']:.4f}",
            f"{r['z']:+.1f}",
        ]
        for r in data["results"]
    ]
    table(["Code", "p", "First round, `T1`", "Twirl", "Ratio", "All rounds, `T1`", "Twirl", "Ratio", "z"], rows)
    speeds = {}
    for r in data["results"]:
        speeds.setdefault(bb(r), []).append(r)
    table(
        ["Code", "Qubits", "`T1` decay, shot by shot", "Twirl, Pauli frames"],
        [
            [code, str(rs[0]["qubits"]), rate(np.mean([r["t1_shots_per_cpu_second"] for r in rs])),
             rate(np.mean([r["twirl_shots_per_cpu_second"] for r in rs]))]
            for code, rs in speeds.items()
        ],
    )


def qldpc_logical(data: dict):
    """T1 decay against its twirl: logical error rates, decoded alike."""
    environment(data)
    rows = []
    for r in data["results"]:
        a = (r["t1_errors"] / r["t1_shots"], r["t1_shots"])
        b = (r["twirl_errors"] / r["twirl_shots"], r["twirl_shots"])
        ratio = b[0] / a[0]
        err = ratio * np.hypot(*(np.sqrt((1 - x) / (x * n)) for x, n in (a, b)))
        fmt = (lambda x: f"{x:.2e}") if a[0] < 1e-2 else (lambda x: f"{x:.4f}")
        rows.append([bb(r), f"{r['p']:g}", fmt(a[0]), fmt(b[0]), pm(ratio, err, 2), f"{r['z']:+.1f}",
                     f"{r['t1_errors']:,} in {r['t1_shots']:,}", f"{r['twirl_errors']:,} in {r['twirl_shots']:,}"])
    table(["Code", "p", "LEP, `T1`", "Twirl", "Ratio", "z", "`T1` errors", "Twirl errors"], rows)
    print(f"Decoder: {data['decoder']}\n")


def qldpc_decoders(data: dict):
    """Fast decoders against BP-OSD-CS 7 on the same shots."""
    environment(data)
    rows = [
        [bb(r), f"{r['p']:g}", r["decoder"], f"{r['failures'] / r['shots']:.4f}",
         f"+{r['fail_only_this']} −{r['fail_only_reference']}" if r["decoder"] != data["reference"] else "",
         f"{r['cpu_ms_per_shot'] / 1e3:.2f}", f"{r['peak_worker_gb']:.1f}"]
        for r in data["results"]
    ]
    table(["Code", "p", "Decoder", "Failure rate", "Against OSD-CS 7", "CPU s a shot", "GB a worker"], rows,
          align="lrlrrrr")


def main():
    for name, fn in (
        ("stabilizer_speed", stabilizer_speed),
        ("stabilizer_ler", stabilizer_ler),
        ("mps_pauli", mps_pauli),
        ("mps_exact", mps_exact),
        ("mps_chi", mps_chi),
        ("mps_confirm", mps_confirm),
        ("mps_scaling", mps_scaling),
        ("coherent_surface", coherent),
        ("coherent_repetition", coherent),
        ("extended_exact", extended_exact),
        ("extended_surface", extended_twirl),
        ("extended_qldpc", extended_twirl),
        ("qldpc_rates", qldpc_rates),
        ("qldpc_logical", qldpc_logical),
        ("qldpc_decoders", qldpc_decoders),
    ):
        if (data := load(name)) is not None:
            fn(data)


if __name__ == "__main__":
    main()
