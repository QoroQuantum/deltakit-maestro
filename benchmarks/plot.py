# SPDX-FileCopyrightText: 2026 Qoro Quantum
# SPDX-License-Identifier: GPL-3.0-or-later

"""Figures for the Benchmarks pages, from the results in benchmarks/results/.

    pip install matplotlib
    python benchmarks/plot.py

Writes docs/benchmarks/figures/*.png. A figure whose results file is missing is
skipped.
"""

import argparse
import json
import os
import pathlib

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
RESULTS = pathlib.Path(os.environ.get("BENCHMARK_RESULTS") or HERE / "results")
FIGURES = HERE.parent / "docs" / "benchmarks" / "figures"

# The palette of the example notebook: categorical slots in fixed order.
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK_2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3de", "#fcfcfb"
MAESTRO, STIM = BLUE, ORANGE
DISTANCE_COLORS = {3: BLUE, 5: ORANGE, 7: AQUA}

plt.rcParams.update(
    {
        "figure.dpi": 110,
        "savefig.dpi": 150,
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "font.size": 10,
        "axes.edgecolor": INK_2,
        "axes.labelcolor": INK,
        "axes.titlecolor": INK,
        "axes.titlesize": 11,
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "axes.axisbelow": True,
        "xtick.color": INK_2,
        "ytick.color": INK_2,
        "legend.frameon": False,
        "lines.linewidth": 2,
        "lines.markersize": 7,
        "errorbar.capsize": 0,
    }
)


def load(results: pathlib.Path, name: str) -> dict | None:
    path = results / f"{name}.json"
    if not path.exists():
        print(f"skipping {name}: no {path}")
        return None
    return json.loads(path.read_text())


def save(fig, out: pathlib.Path, name: str):
    out.mkdir(parents=True, exist_ok=True)
    fig.savefig(out / f"{name}.png", bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {out / name}.png")


def binomial(k, n):
    p = np.asarray(k) / np.asarray(n)
    return p, np.sqrt(np.maximum(p * (1 - p), 1 / np.asarray(n) ** 2) / n)


# -----------------------------------------------------------------------------


def stabilizer_speed(data: dict, out: pathlib.Path):
    rows = data["results"]
    fig, (left, right) = plt.subplots(
        1, 2, figsize=(10, 4.2), layout="constrained", gridspec_kw={"width_ratios": [1, 1.1]}
    )

    surface = sorted(
        (r for r in rows if r["code"] == "rotated" and r["noise"] == "SI1000"),
        key=lambda r: r["distance"],
    )
    d = [r["distance"] for r in surface]
    left.plot(d, [r["stim_shots_per_second"] for r in surface], color=STIM, label="Stim", zorder=2)
    left.plot(
        d,
        [r["maestro_shots_per_second"] for r in surface],
        color=MAESTRO,
        marker="o",
        linestyle="none",
        markeredgecolor=SURFACE,
        markeredgewidth=1.5,
        markersize=8,
        label="Maestro",
        zorder=3,
    )
    left.set(
        title="Rotated surface code, SI1000(0.002)",
        xlabel="code distance d (d rounds)",
        ylabel="detection-event shots per second",
        yscale="log",
        xticks=d,
    )
    left.legend(loc="upper right")

    labels = [f"{r['label']}, {r['noise']}" for r in rows]
    ratio = np.array([r["maestro_shots_per_second"] / r["stim_shots_per_second"] for r in rows])
    y = np.arange(len(rows))[::-1]
    right.axvline(1, color=INK_2, linewidth=1)
    right.hlines(y, 1, ratio, color=GRID, linewidth=2, zorder=1)
    right.plot(
        ratio,
        y,
        "o",
        color=MAESTRO,
        markeredgecolor=SURFACE,
        markeredgewidth=1.5,
        markersize=8,
        zorder=3,
    )
    right.set_yticks(y, labels, fontsize=8.5)
    right.grid(axis="y", visible=False)
    right.set(
        title="Maestro ÷ Stim",
        xlabel="throughput ratio (> 1: Maestro faster)",
        xscale="log",
    )
    lo, hi = min(ratio.min(), 0.8) / 1.08, max(ratio.max(), 1.25) * 1.08
    ticks = [t for t in (0.25, 0.4, 0.6, 0.8, 1, 1.25, 1.6, 2.5, 4) if lo <= t <= hi]
    right.set_xticks(ticks, [f"{t:g}×" for t in ticks])
    right.minorticks_off()
    right.set_xlim(lo, hi)
    save(fig, out, "stabilizer_speed")


def stabilizer_ler(data: dict, out: pathlib.Path):
    rows = data["results"]
    noises = list(dict.fromkeys(r["noise"] for r in rows))
    fig, axes = plt.subplots(
        1, len(noises), figsize=(4 * len(noises), 4), layout="constrained", sharey=True
    )
    for ax, noise in zip(np.atleast_1d(axes), noises):
        for d, color in DISTANCE_COLORS.items():
            sel = sorted(
                (r for r in rows if r["noise"] == noise and r["d"] == d), key=lambda r: r["p"]
            )
            if not sel:
                continue
            p = np.array([r["p"] for r in sel])
            stim, stim_err = binomial(
                [r["stim_errors"] for r in sel], [r["stim_shots"] for r in sel]
            )
            mae, mae_err = binomial(
                [r["maestro_errors"] for r in sel], [r["maestro_shots"] for r in sel]
            )
            ok = stim > 0
            ax.plot(p[ok], stim[ok], color=color, linewidth=2, zorder=2)
            ax.fill_between(
                p[ok],
                np.maximum(stim - 2 * stim_err, 1e-9)[ok],
                (stim + 2 * stim_err)[ok],
                color=color,
                alpha=0.18,
                linewidth=0,
            )
            ok = mae > 0
            ax.errorbar(
                p[ok],
                mae[ok],
                yerr=2 * mae_err[ok],
                color=color,
                marker="o",
                linestyle="none",
                markeredgecolor=SURFACE,
                markeredgewidth=1.5,
                markersize=8,
                elinewidth=1.5,
                zorder=3,
                label=f"d={d}",
            )
        ps = sorted({r["p"] for r in rows})
        ax.set(title=noise, xlabel="noise strength p", xscale="log", yscale="log")
        ax.set_xticks(ps, [f"{p:g}" for p in ps], rotation=45)
        ax.minorticks_off()
    axes[0].set_ylabel("logical error rate (per shot)")
    handles, labels = axes[0].get_legend_handles_labels()
    handles += [
        plt.Line2D([], [], color=INK_2, linewidth=2),
        plt.Line2D([], [], color=INK_2, marker="o", linestyle="none", markersize=8),
    ]
    labels += ["Stim (line, ±2σ band)", "Maestro (markers, ±2σ)"]
    fig.legend(handles, labels, loc="outside lower center", ncol=len(labels), fontsize=9)
    save(fig, out, "stabilizer_ler")


def mps_accuracy(pauli: dict | None, exact: dict | None, out: pathlib.Path):
    panels = [(pauli, "pauli"), (exact, "exact")]
    panels = [(d, k) for d, k in panels if d is not None]
    if not panels:
        return
    fig, axes = plt.subplots(1, len(panels), figsize=(5 * len(panels), 4.6), layout="constrained")
    for ax, (data, kind) in zip(np.atleast_1d(axes), panels):
        rows = data["results"]
        if kind == "pauli":
            groups = {"SI1000": BLUE, "SD6": ORANGE, "Toy": AQUA}
            key = "noise"
            ref, ref_name = "stim", "Stim"
            title = "Pauli noise: MPS against Stim"
            note = "rotated d=3, p = 0.002, 0.005, 0.01"
        else:
            groups = {"coherent": BLUE, "T1": ORANGE, "full": AQUA}
            key = "label"
            ref, ref_name = "statevector", "exact statevector"
            title = "Non-Pauli noise: MPS against statevector"
            note = "rotated d=3, repetition d=5, 9, 11"
        lo, hi = 1, 0
        names = {"T1": "Pauli + T1", "full": "Pauli + coherent + T1"}
        for group, color in groups.items():
            # A run that disagrees with its reference (χ too small) is drawn hollow.
            for failed in (False, True):
                x, y, label = [], [], names.get(group, group)
                for r in rows:
                    if r[key] == group and (abs(r["z_detection_rate"]) > 4) == failed:
                        x += r[ref]["per_detector"]
                        y += r["mps"]["per_detector"]
                        if failed:
                            label = f"{label},\n{r['code']} d={r['d']}: χ=32 truncates"
                x, y = np.array(x), np.array(y)
                keep = (x > 0) & (y > 0)
                if not keep.any():
                    continue
                lo = min(lo, x[keep].min(), y[keep].min())
                hi = max(hi, x[keep].max(), y[keep].max())
                ax.scatter(
                    x[keep],
                    y[keep],
                    s=26 if failed else 22,
                    facecolors=SURFACE if failed else color,
                    edgecolors=color if failed else SURFACE,
                    linewidths=1.3 if failed else 0.8,
                    zorder=4 if failed else 3,
                    label=label,
                )
        lo, hi = lo / 1.3, hi * 1.3
        ax.plot([lo, hi], [lo, hi], color=INK_2, linewidth=1, zorder=2)
        ax.set(
            title=title,
            xlabel=f"detector rate, {ref_name}",
            ylabel="detector rate, MPS (χ=32)",
            xscale="log",
            yscale="log",
            xlim=(lo, hi),
            ylim=(lo, hi),
            aspect="equal",
        )
        ticks = [t for t in (0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5) if lo <= t <= hi]
        ax.set_xticks(ticks, [f"{t:g}" for t in ticks])
        ax.set_yticks(ticks, [f"{t:g}" for t in ticks])
        ax.minorticks_off()
        ax.annotate(
            note, (0.02, 0.98), xycoords="axes fraction", va="top", fontsize=8.5, color=INK_2
        )
        ax.legend(loc="lower right", fontsize=9)
    save(fig, out, "mps_accuracy")


def mps_chi(data: dict, out: pathlib.Path):
    cases = data["results"]
    titles = {
        "coherent": "Coherent noise, p = {p:g}",
        "full": "Pauli + coherent + T1, p = {p:g}",
    }
    fig, axes = plt.subplots(1, len(cases), figsize=(5 * len(cases), 3.8), layout="constrained")
    for ax, case in zip(np.atleast_1d(axes), cases):
        rows = sorted(case["results"], key=lambda r: r["chi"])
        sv = case["statevector"]
        chi = np.array([r["chi"] for r in rows])
        val = np.array([r["mps"]["detection_rate"] for r in rows])
        err = np.array([r["mps"]["detection_rate_err"] for r in rows])
        ref, ref_err = sv["detection_rate"], sv["detection_rate_err"]
        ax.axhspan(ref - 2 * ref_err, ref + 2 * ref_err, color=STIM, alpha=0.18, linewidth=0)
        ax.axhline(ref, color=STIM, linewidth=2)
        ax.annotate(
            "exact statevector (±2σ)",
            (chi[0], ref + 2 * ref_err),
            xytext=(0, 4),
            textcoords="offset points",
            ha="left",
            va="bottom",
            fontsize=9,
            color=INK,
        )
        ax.errorbar(
            chi,
            val,
            yerr=2 * err,
            color=MAESTRO,
            marker="o",
            markeredgecolor=SURFACE,
            markeredgewidth=1.5,
            markersize=8,
            elinewidth=1.5,
            label="MPS (±2σ)",
        )
        ax.set(
            title=titles.get(case["name"], case["name"]).format(p=case["p"]),
            xlabel="bond dimension χ",
            ylabel="detection-event rate",
            xscale="log",
        )
        ax.set_xticks(chi, [str(c) for c in chi])
        ax.minorticks_off()
        ax.legend(loc="upper right", fontsize=9)
    save(fig, out, "mps_chi")


def mps_scaling(data: dict, out: pathlib.Path):
    rows = sorted(data["results"], key=lambda r: r["qubits"])
    fig, ax = plt.subplots(figsize=(6.4, 4), layout="constrained")
    q = np.array([r["qubits"] for r in rows])
    mps = np.array([r["mps32"]["seconds_per_shot"] for r in rows]) * 1e3
    ax.plot(q, mps, color=MAESTRO, marker="o", markeredgecolor=SURFACE, markeredgewidth=1.5)
    sv_rows = [r for r in rows if "statevector" in r]
    sv_q = np.array([r["qubits"] for r in sv_rows])
    sv = np.array([r["statevector"]["seconds_per_shot"] for r in sv_rows]) * 1e3
    ax.plot(sv_q, sv, color=STIM, marker="s", markeredgecolor=SURFACE, markeredgewidth=1.5)
    ax.annotate(
        "MPS, χ=32",
        (q[-1], mps[-1]),
        xytext=(0, 10),
        textcoords="offset points",
        ha="right",
        va="bottom",
        fontsize=9,
        color=INK,
    )
    ax.annotate(
        "statevector",
        (sv_q[-1], sv[-1]),
        xytext=(6, 0),
        textcoords="offset points",
        ha="left",
        va="center",
        fontsize=9,
        color=INK,
    )
    ax.set(
        title="Repetition code, coherent noise, d rounds",
        xlabel="qubits (2d − 1)",
        ylabel=f"wall time per shot, {data['environment']['cores']} threads (ms)",
        yscale="log",
    )
    save(fig, out, "mps_scaling")


def coherent(surface: dict | None, repetition: dict | None, out: pathlib.Path):
    """Coherent noise over its Pauli twirl: the d=3 surface code by p, repetition codes by d."""
    panels = [
        (name, data) for name, data in (("surface", surface), ("repetition", repetition)) if data
    ]
    if not panels:
        return
    fig, axes = plt.subplots(1, len(panels), figsize=(5.2 * len(panels), 3.9), layout="constrained")
    for ax, (name, data) in zip(np.atleast_1d(axes), panels):
        ax.axhline(1, color=INK_2, linewidth=1)
        if name == "surface":
            rows = sorted(data["results"], key=lambda r: r["p"])
            x = np.array([r["p"] for r in rows])
            # As on the right: solid and filled for the LEP, dashed and hollow for
            # detection events. Colour is reserved for the noise strength there.
            ax.errorbar(
                x,
                [r["lep_ratio"] for r in rows],
                yerr=[2 * r["lep_ratio_err"] for r in rows],
                color=BLUE,
                marker="o",
                markeredgecolor=SURFACE,
                markeredgewidth=1.5,
                elinewidth=1.5,
                label="logical error rate",
            )
            ax.plot(
                x,
                [r["detection_rate_ratio"] for r in rows],
                color=BLUE,
                linestyle="--",
                linewidth=1.2,
                marker="s",
                markersize=5,
                markerfacecolor=SURFACE,
                label="detection events",
            )
            ax.set(
                title="Rotated d=3 surface code, 3 rounds", xlabel="noise strength p", xscale="log"
            )
            ax.set_xticks(x, [f"{v:g}" for v in x])
            ax.minorticks_off()
        else:
            for p, color in zip(
                sorted({r["p"] for r in data["results"]}, reverse=True), (BLUE, ORANGE)
            ):
                # Points with at least 100 coherent logical errors: fewer say little about a ratio.
                rows = sorted(
                    (r for r in data["results"] if r["p"] == p and r["coherent"]["errors"] >= 100),
                    key=lambda r: r["d"],
                )
                d = np.array([r["d"] for r in rows])
                ax.errorbar(
                    d,
                    [r["lep_ratio"] for r in rows],
                    yerr=[2 * r["lep_ratio_err"] for r in rows],
                    color=color,
                    marker="o",
                    markeredgecolor=SURFACE,
                    markeredgewidth=1.5,
                    elinewidth=1.5,
                    label=f"logical error rate, p = {p:g}",
                )
                ax.plot(
                    d,
                    [r["detection_rate_ratio"] for r in rows],
                    color=color,
                    linestyle="--",
                    linewidth=1.2,
                    marker="s",
                    markersize=5,
                    markerfacecolor=SURFACE,
                    label=f"detection events, p = {p:g}",
                )
            ax.set(title="Repetition codes, d rounds", xlabel="code distance d")
            ax.set_xticks(sorted({r["d"] for r in data["results"]}))
        ax.set_ylim(bottom=min(0.92, ax.get_ylim()[0]))
        ax.annotate(
            "Pauli twirl = 1",
            (ax.get_xlim()[1], 1),
            xytext=(-4, -4),
            textcoords="offset points",
            ha="right",
            va="top",
            fontsize=9,
            color=INK_2,
        )
        ax.set_ylabel("coherent ÷ Pauli twirl (±2σ)")
        # The logical error rate first: it is the result; detection events explain it.
        handles, labels = ax.get_legend_handles_labels()
        order = sorted(range(len(labels)), key=lambda i: not labels[i].startswith("logical"))
        ax.legend(
            [handles[i] for i in order],
            [labels[i] for i in order],
            loc="upper right" if name == "surface" else "upper left",  # Clear of the data.
            fontsize=9,
        )
    save(fig, out, "coherent")


def extended(exact: dict | None, surface: dict | None, qldpc: dict | None, out: pathlib.Path):
    """The extended stabilizer: converging on the statevector, and coherent over twirl past it."""
    twirl = [r for data in (surface, qldpc) if data for r in data["results"]]
    panels = [name for name, ok in (("exact", exact), ("twirl", twirl)) if ok]
    if not panels:
        return
    fig, axes = plt.subplots(1, len(panels), figsize=(5.2 * len(panels), 3.9), layout="constrained")
    for ax, name in zip(np.atleast_1d(axes), panels):
        ax.axhline(1, color=INK_2, linewidth=1)
        if name == "exact":
            for case, color in zip(dict.fromkeys(r["case"] for r in exact["results"]), (BLUE, ORANGE)):
                rows = sorted((r for r in exact["results"] if r["case"] == case), key=lambda r: -r["tolerance"])
                ratio = [r["extended"]["detection_rate"] / r["statevector"]["detection_rate"] for r in rows]
                err = [
                    q * np.hypot(r["extended"]["detection_rate_err"] / r["extended"]["detection_rate"],
                                 r["statevector"]["detection_rate_err"] / r["statevector"]["detection_rate"])
                    for q, r in zip(ratio, rows)
                ]
                x = [r["tolerance"] for r in rows]
                label = {"pauli + coherent": f"Pauli p + coherent {rows[0].get('coherent', 0):g}",
                         "coherent only": f"coherent only, p = {exact['p']:g}"}.get(case, case)
                ax.errorbar(x, ratio, yerr=[2 * e for e in err], color=color, marker="o",
                            markeredgecolor=SURFACE, markeredgewidth=1.5, elinewidth=1.5, label=label)
            ax.set(title="Rotated d=3: against the exact statevector", xlabel="amplitude tolerance",
                   xscale="log", ylabel="detection rate ÷ statevector's (±2σ)")
            ax.invert_xaxis()  # Tighter to the right.
            # Between the loosest two tolerances, where no point sits above the line.
            ax.annotate("exact = 1", (3e-3, 1), xytext=(0, 4), textcoords="offset points",
                        ha="center", va="bottom", fontsize=9, color=INK_2)
            ax.legend(loc="lower right", fontsize=9)
        else:
            labels = [f"rotated d={r['d']}" if r.get("code") == "rotated" else r["code"] for r in twirl]
            x = np.arange(len(twirl))
            tolerance = (surface or qldpc)["tolerance"]
            check_tolerance = (surface or qldpc)["check_tolerance"]
            # Detection events at both tolerances, side by side: pruning only lowers them.
            for shift, key, filled, tol in ((-0.08, "coherent", True, tolerance), (0.08, "check", False, check_tolerance)):
                ratio = [r[key]["detection_rate"] / r["twirl"]["detection_rate"] for r in twirl]
                err = [
                    q * np.hypot(r[key]["detection_rate_err"] / r[key]["detection_rate"],
                                 r["twirl"]["detection_rate_err"] / r["twirl"]["detection_rate"])
                    for q, r in zip(ratio, twirl)
                ]
                ax.errorbar(x + shift, ratio, yerr=[2 * e for e in err], color=BLUE, linestyle="none", marker="s",
                            markersize=6, markerfacecolor=BLUE if filled else SURFACE, elinewidth=1.5,
                            label=f"detection events, tolerance {tol:g}")
            # The LEP only where there are at least 100 coherent logical errors.
            lep = [(i, r) for i, r in enumerate(twirl) if r["coherent"]["errors"] >= 100]
            if lep:
                ax.errorbar([i - 0.08 for i, _ in lep], [r["lep_ratio"] for _, r in lep],
                            yerr=[2 * r["lep_ratio_err"] for _, r in lep], color=ORANGE, linestyle="none",
                            marker="o", markeredgecolor=SURFACE, markeredgewidth=1.5, elinewidth=1.5,
                            label=f"logical error rate, tolerance {tolerance:g}")
            ax.set_xticks(x, [f"{name}\n{r['qubits']} qubits" for name, r in zip(labels, twirl)])
            ax.set(title="Coherent ÷ Pauli twirl", ylabel="coherent ÷ Pauli twirl (±2σ)")
            ax.annotate("Pauli twirl = 1", (ax.get_xlim()[1], 1), xytext=(-4, -4), textcoords="offset points",
                        ha="right", va="top", fontsize=9, color=INK_2)
            bottom, top = min(0.98, ax.get_ylim()[0]), ax.get_ylim()[1]
            ax.set_ylim(bottom, top + 0.4 * (top - bottom))  # Headroom for the legend, clear of the data.
            ax.legend(loc="upper left", fontsize=9)
    save(fig, out, "extended")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--results", type=pathlib.Path, default=RESULTS)
    parser.add_argument("--out", type=pathlib.Path, default=FIGURES)
    args = parser.parse_args()
    if data := load(args.results, "stabilizer_speed"):
        stabilizer_speed(data, args.out)
    if data := load(args.results, "stabilizer_ler"):
        stabilizer_ler(data, args.out)
    mps_accuracy(load(args.results, "mps_pauli"), load(args.results, "mps_exact"), args.out)
    if data := load(args.results, "mps_chi"):
        mps_chi(data, args.out)
    if data := load(args.results, "mps_scaling"):
        mps_scaling(data, args.out)
    coherent(
        load(args.results, "coherent_surface"), load(args.results, "coherent_repetition"), args.out
    )
    extended(
        load(args.results, "extended_exact"),
        load(args.results, "extended_surface"),
        load(args.results, "extended_qldpc"),
        args.out,
    )


if __name__ == "__main__":
    main()
