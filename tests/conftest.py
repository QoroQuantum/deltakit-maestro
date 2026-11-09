# SPDX-FileCopyrightText: 2026 Qoro Quantum
# SPDX-License-Identifier: GPL-3.0-or-later

# Deltakit must be imported before pymatching: with pymatching 2.4 loaded
# first, Deltakit's circuit builders fail with "Caught an unknown exception!".
import pytest
import stim
from deltakit.circuit.gates import PauliBasis
from deltakit.explorer.codes import RotatedPlanarCode, css_code_memory_circuit
from deltakit.explorer.qpu import QPU, SI1000Noise


def error_table(dem: stim.DetectorErrorModel) -> dict:
    """Probability of each symptom, so DEMs compare regardless of instruction order."""
    table = {}
    for inst in dem.flattened():
        if inst.type == "error":
            key = tuple(str(t) for t in inst.targets_copy())
            table[key] = table.get(key, 0.0) + inst.args_copy()[0]
    return table


def si1000_memory(
    distance: int = 3, rounds: int = 3, p: float = 0.01, basis: PauliBasis = PauliBasis.Z
):
    """Deltakit rotated surface code memory with SI1000(p) noise."""
    code = RotatedPlanarCode(width=distance, height=distance)
    circuit = css_code_memory_circuit(code, num_rounds=rounds, logical_basis=basis)
    return QPU(circuit.qubits, noise_model=SI1000Noise(p=p)).compile_and_add_noise_to_circuit(
        circuit
    )


@pytest.fixture(scope="session")
def si1000():
    return si1000_memory()


@pytest.fixture(scope="session")
def si1000_x():
    return si1000_memory(basis=PauliBasis.X)


@pytest.fixture(scope="session")
def si1000_d2():
    return si1000_memory(distance=2, rounds=2)


@pytest.fixture(scope="session")
def trivial_circuit():
    """Stim circuit with gates and measurements but no DETECTOR or OBSERVABLE annotations."""
    return stim.Circuit("""
        R 0 1
        H 0
        CX 0 1
        M 0 1
    """)
