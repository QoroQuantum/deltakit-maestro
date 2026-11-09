# SPDX-FileCopyrightText: 2026 Qoro Quantum
# SPDX-License-Identifier: GPL-3.0-or-later

"""Deltakit Maestro Backend.

Runs Riverlane Deltakit QEC circuits on Qoro's Maestro simulator, built on
``maestro.sinter``.

Quick start::

    from deltakit_maestro import MaestroBackend

    backend = MaestroBackend(max_bond_dimension=32)
    result = backend.simulate(deltakit_circuit, shots=1000)
    result.detection_events     # (1000, n_detectors) bool
"""

from importlib.metadata import PackageNotFoundError, version

from .maestro_backend import (
    SINTER_DECODER,
    MaestroBackend,
    SimulationResult,
    to_stim,
)
from .noise import (
    NOISE_KEYS,
    NOISE_TYPES,
    build_noise_model,
    noise_params_from_stim,
    pauli_twirl_circuit,
    strip_gate_noise,
)

try:
    __version__ = version("deltakit-maestro")
except PackageNotFoundError:  # Running from a source tree that isn't installed.
    __version__ = "0.0.0"

__all__ = [
    "NOISE_KEYS",
    "NOISE_TYPES",
    "SINTER_DECODER",
    "MaestroBackend",
    "SimulationResult",
    "__version__",
    "build_noise_model",
    "noise_params_from_stim",
    "pauli_twirl_circuit",
    "strip_gate_noise",
    "to_stim",
]
