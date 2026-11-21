# SPDX-FileCopyrightText: 2026 Qoro Quantum
# SPDX-License-Identifier: GPL-3.0-or-later

"""Circuits, statistics and result files shared by the benchmark scripts."""

# Deltakit must be imported before pymatching: with pymatching 2.4 loaded
# first, Deltakit's circuit builders fail with "Caught an unknown exception!".
from deltakit.circuit.gates import PauliBasis
from deltakit.explorer.codes import (
    BivariateBicycleCode,
    RepetitionCode,
    RotatedPlanarCode,
    UnrotatedPlanarCode,
    UnrotatedToricCode,
    css_code_memory_circuit,
)
from deltakit.explorer.qpu import QPU, SD6Noise, SI1000Noise, ToyNoise

# isort: split
import datetime
import importlib.metadata
import json
import os
import pathlib
import platform
import subprocess

import numpy as np
import pymatching
import scipy.sparse
import sinter
import stim
from ldpc import BpLsdDecoder, BpOsdDecoder

from deltakit_maestro import to_stim

# Where results go: benchmarks/results/, or $BENCHMARK_RESULTS to keep a run
# (on another Maestro build, say) apart from the published one.
RESULTS = pathlib.Path(
    os.environ.get("BENCHMARK_RESULTS") or pathlib.Path(__file__).resolve().parent / "results"
)

# Deltakit's circuit-level Pauli noise models, each set by one strength p.
NOISE_MODELS = {
    "SI1000": SI1000Noise,  # superconducting-inspired: p_2q = p, p_1q = p/10, readout 5p
    "SD6": SD6Noise,  # standard depolarizing: every gate, idle, reset and readout at p
    "Toy": ToyNoise,  # p_2q = p, p_1q = p/10, readout p
}

CODES = {
    "rotated": lambda d: RotatedPlanarCode(d, d),
    "unrotated": lambda d: UnrotatedPlanarCode(d, d),
    "toric": lambda d: UnrotatedToricCode(d, d),
    "repetition": RepetitionCode,
}


def bivariate_bicycle(n: int):
    """The [[72,12,6]] and [[144,12,12]] bivariate bicycle codes of arXiv:2308.07915."""
    param_l = {72: 6, 144: 12}[n]
    return BivariateBicycleCode(
        param_l=param_l, param_m=6, m_A_powers=[3, 1, 2], m_B_powers=[3, 1, 2]
    )


def memory_circuit(code, noise: str, p: float, rounds: int) -> stim.Circuit:
    """A Z-basis memory experiment on ``code`` with Deltakit noise, as Stim."""
    circuit = css_code_memory_circuit(code, num_rounds=rounds, logical_basis=PauliBasis.Z)
    qpu = QPU(circuit.qubits, noise_model=NOISE_MODELS[noise](p=p))
    return to_stim(qpu.compile_and_add_noise_to_circuit(circuit))


def surface_code(d: int, noise: str = "SI1000", p: float = 0.002, rounds: int | None = None):
    """Rotated surface code memory, ``d`` rounds unless ``rounds`` is given."""
    return memory_circuit(RotatedPlanarCode(d, d), noise, p, d if rounds is None else rounds)


def repetition_code(d: int, noise: str = "SI1000", p: float = 0.002, rounds: int | None = None):
    """Repetition code memory, ``d`` rounds unless ``rounds`` is given."""
    return memory_circuit(RepetitionCode(d), noise, p, d if rounds is None else rounds)


# -----------------------------------------------------------------------------
# BP-OSD and BP-LSD as Sinter decoders
# -----------------------------------------------------------------------------


class BpOsd(sinter.Decoder):
    """``ldpc``'s BP-OSD, compiled once per detector error model.

    ``ldpc.sinter_decoders.SinterBpOsdDecoder`` decodes only through files,
    and Maestro's sampler needs ``compile_decoder_for_dem``, so this builds the
    decoder from the DEM directly: one column per error, one row per detector.
    """

    decoder_class = BpOsdDecoder

    def __init__(self, **settings):
        self.settings = settings

    def compile_decoder_for_dem(self, *, dem: stim.DetectorErrorModel) -> sinter.CompiledDecoder:
        return _CompiledBpOsd(dem, self.settings, self.decoder_class)


class BpLsd(BpOsd):
    """``ldpc``'s BP with localised statistics decoding, built the same way."""

    decoder_class = BpLsdDecoder


class _CompiledBpOsd(sinter.CompiledDecoder):
    def __init__(self, dem: stim.DetectorErrorModel, settings: dict, decoder_class=BpOsdDecoder):
        checks, observables, priors = [], [], []
        for inst in dem.flattened():
            if inst.type != "error":
                continue
            column = len(priors)
            priors.append(inst.args_copy()[0])
            for t in inst.targets_copy():
                if t.is_relative_detector_id():
                    checks.append((t.val, column))
                elif t.is_logical_observable_id():
                    observables.append((t.val, column))
        shape = (dem.num_detectors, len(priors))
        self.observables = _matrix(observables, (dem.num_observables, len(priors)))
        self.num_detectors = dem.num_detectors
        self.decoder = decoder_class(_matrix(checks, shape), error_channel=priors, **settings)

    def decode_shots_bit_packed(self, *, bit_packed_detection_event_data: np.ndarray) -> np.ndarray:
        dets = np.unpackbits(
            bit_packed_detection_event_data, axis=1, count=self.num_detectors, bitorder="little"
        )
        errors = np.array([self.decoder.decode(d) for d in dets], dtype=np.uint8)
        predicted = (self.observables @ errors.T).T % 2
        return np.packbits(predicted.astype(np.uint8), axis=1, bitorder="little")


def _matrix(entries, shape) -> scipy.sparse.csr_matrix:
    rows, cols = zip(*entries) if entries else ((), ())
    data = np.ones(len(rows), dtype=np.uint8)
    return scipy.sparse.csr_matrix((data, (rows, cols)), shape=shape)


# -----------------------------------------------------------------------------
# Statistics
# -----------------------------------------------------------------------------


def proportion(k: int, n: int) -> tuple[float, float]:
    """A binomial proportion and its standard error."""
    p = k / n
    return p, float(np.sqrt(max(p * (1 - p), 1 / n**2) / n))


def z_score(a: tuple[float, float], b: tuple[float, float]) -> float:
    """How many standard errors apart two independent estimates are."""
    se = np.hypot(a[1], b[1])
    return float((a[0] - b[0]) / se) if se > 0 else 0.0


def detection_summary(dets: np.ndarray, obs: np.ndarray, dem: stim.DetectorErrorModel) -> dict:
    """Detection-event rate, per-detector rates and PyMatching LEP of one run.

    The detection-event rate's standard error comes from the spread of each
    shot's own rate, so it allows for detectors that fire together.
    """
    shots = len(dets)
    per_shot = dets.mean(axis=1)
    matcher = pymatching.Matching.from_detector_error_model(dem)
    failures = np.any(matcher.decode_batch(dets) != obs, axis=1)
    lep, lep_err = proportion(int(failures.sum()), shots)
    return {
        "shots": shots,
        "detection_rate": float(per_shot.mean()),
        "detection_rate_err": float(per_shot.std(ddof=1) / np.sqrt(shots)),
        "per_detector": dets.mean(axis=0).tolist(),
        "lep": lep,
        "lep_err": lep_err,
        "errors": int(failures.sum()),
    }


def compare(a: dict, b: dict) -> dict:
    """z-scores of two ``detection_summary`` results, and the worst detector's."""
    pa, pb = np.array(a["per_detector"]), np.array(b["per_detector"])
    se = np.sqrt(pa * (1 - pa) / a["shots"] + pb * (1 - pb) / b["shots"])
    with np.errstate(divide="ignore", invalid="ignore"):
        z = np.where(se > 0, (pa - pb) / se, 0.0)
    return {
        "z_detection_rate": z_score(
            (a["detection_rate"], a["detection_rate_err"]),
            (b["detection_rate"], b["detection_rate_err"]),
        ),
        "z_lep": z_score((a["lep"], a["lep_err"]), (b["lep"], b["lep_err"])),
        "max_abs_z_detector": float(np.abs(z).max()),
        "num_detectors": len(pa),
    }


# -----------------------------------------------------------------------------
# Result files
# -----------------------------------------------------------------------------


def environment() -> dict:
    """The machine and library versions a result was measured with."""
    try:
        cpu = subprocess.run(
            ["sysctl", "-n", "machdep.cpu.brand_string"],
            check=False,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except OSError:
        cpu = ""
    if not cpu and os.path.exists("/proc/cpuinfo"):  # Linux
        with open("/proc/cpuinfo") as f:
            cpu = next((ln.split(":", 1)[1].strip() for ln in f if ln.startswith("model name")), "")
    versions = {
        name: importlib.metadata.version(name)
        for name in ("deltakit-maestro", "qoro-maestro", "deltakit", "stim", "sinter", "pymatching")
    }
    env = {
        "date": datetime.date.today().isoformat(),
        "cpu": cpu or platform.processor(),
        "cores": os.cpu_count(),
        "python": platform.python_version(),
        "versions": versions,
    }
    if source := maestro_source():
        env["qoro-maestro source"] = source
    return env


def maestro_source() -> str | None:
    """``git describe`` of the checkout Maestro was built from, if not from PyPI.

    A build of an unreleased Maestro carries the last release's version number,
    so the version alone doesn't say which Maestro ran.
    """
    try:
        direct_url = importlib.metadata.distribution("qoro-maestro").read_text("direct_url.json")
    except importlib.metadata.PackageNotFoundError:
        return None
    if not direct_url:
        return None
    url = json.loads(direct_url).get("url", "")
    if not url.startswith("file://"):
        return url or None
    path = url.removeprefix("file://")
    if not os.path.isdir(path):  # A wheel file: nothing to describe.
        return path
    try:
        described = subprocess.run(
            ["git", "-C", path, "describe", "--tags", "--dirty", "--always"],
            check=False,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except OSError:  # No git on this machine.
        described = ""
    return f"{path} at {described}" if described else path


def save(name: str, records: list | dict, **extra) -> pathlib.Path:
    """Write ``results/<name>.json`` with the environment it was measured in."""
    RESULTS.mkdir(parents=True, exist_ok=True)
    path = RESULTS / f"{name}.json"
    path.write_text(
        json.dumps({"environment": environment(), **extra, "results": records}, indent=1) + "\n"
    )
    print(f"wrote {path}")
    return path


def load(name: str) -> dict:
    return json.loads((RESULTS / f"{name}.json").read_text())
