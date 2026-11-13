# SPDX-FileCopyrightText: 2026 Qoro Quantum
# SPDX-License-Identifier: GPL-3.0-or-later

"""Smoke tests: the fast examples run end to end and say what they claim.

Only structural output is checked, never a statistical result. The surface code
example takes about a minute and is not run here.
"""

import importlib.util
from pathlib import Path

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def run_example(name: str, capsys) -> str:
    spec = importlib.util.spec_from_file_location(name, EXAMPLES / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.main()
    return capsys.readouterr().out


def test_noise_modes_example(capsys):
    out = run_example("example_noise_modes", capsys)
    # Both circuits are read, and gate noise leaves while the rest stays.
    assert "Deltakit SI1000(p=0.01)" in out and "Stim-generated" in out
    assert (
        "stripped:  DEPOLARIZE1(0.001)×183  DEPOLARIZE1(0.02)×36  M(0.05)×33  X_ERROR(0.02)×33"
        in out
    )
    # Every run is on Maestro: the stabilizer without coherent noise, MPS with it.
    modes = out.split("2. What each mode runs")[1].split("3. Overriding")[0]
    for label, simulator in [
        ("\n  pauli\n", "Maestro Stabilizer"),
        ("\n  pauli, {'p_2q': 0.02}\n", "Maestro Stabilizer"),
        ("\n  pauli, {'t1': 0.002}\n", "Maestro Stabilizer"),
        ("\n  coherent\n", "Maestro MatrixProductState"),
        ("\n  full\n", "Maestro MatrixProductState"),
        ("\n  none\n", "Maestro Stabilizer"),
    ]:
        block = modes.split(label)[1].split("\n\n")[0]
        assert f"simulator:             {simulator}" in block
    # All four bad-argument cases are reported.
    assert out.count("TypeError:") == 1 and out.count("ValueError:") == 3


def test_stim_circuit_example(capsys):
    out = run_example("example_stim_circuit", capsys)
    assert "measurement record identical to Stim's: True" in out
    assert "same seed, same record:       True" in out
    assert "different seed, same record:  False" in out
    sweep = out.split("5. sinter.collect")[1]
    assert sweep.count("4000") == 4


def test_coherent_noise_example(capsys):
    out = run_example("example_coherent_noise", capsys)
    assert "MatrixProductState" in out
    rows = [line for line in out.splitlines() if line.strip().startswith(("0.01", "0.03"))]
    assert len(rows) == 4


def test_custom_noise_model_example(capsys):
    out = run_example("example_custom_noise_model", capsys)
    assert "has_1q=True, has_2q=True, has_t1=True, has_readout=True" in out
    assert "has_coherent=True, has_crosstalk=True" in out
    assert "Uniform SI1000 baseline" in out
    assert "+ Coherent rot & ZZ crosstalk" in out
    sweep = out.split("3. Multi-worker sinter.collect")[1]
    assert sweep.count("2000") == 3
