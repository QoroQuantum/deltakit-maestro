# SPDX-FileCopyrightText: 2026 Qoro Quantum
# SPDX-License-Identifier: GPL-3.0-or-later

import math
from collections import Counter

import pytest
import stim
from conftest import error_table

from deltakit_maestro import (
    build_noise_model,
    noise_params_from_stim,
    pauli_twirl_circuit,
    strip_gate_noise,
    to_stim,
)
from deltakit_maestro.noise import _dominant, _two_qubit_pairs


def target_count(circuit: stim.Circuit, *names: str) -> int:
    return sum(len(i.targets_copy()) for i in circuit.flattened() if i.name in names)


def test_si1000_rates_come_from_the_gate_noise(si1000):
    assert noise_params_from_stim(to_stim(si1000)) == pytest.approx(
        {"p_1q": 0.001, "p_2q": 0.01, "readout_error": 0.05}
    )


def test_strip_gate_noise_splits_gate_from_idle_noise(si1000):
    circuit = to_stim(si1000)
    stripped = strip_gate_noise(circuit)
    assert target_count(stripped, "DEPOLARIZE2") == 0
    # Exactly one DEPOLARIZE1 target per single-qubit gate target is gone.
    assert target_count(circuit, "DEPOLARIZE1") - target_count(
        stripped, "DEPOLARIZE1"
    ) == target_count(circuit, "H")
    # Reset, readout and idle-during-readout noise are untouched.
    for name in ("X_ERROR", "M"):
        assert target_count(stripped, name) == target_count(circuit, name)
    assert any(i.name == "DEPOLARIZE1" and i.gate_args_copy() == [0.02] for i in stripped)
    assert any(i.name == "M" and i.gate_args_copy() == [0.05] for i in stripped)


def test_strip_gate_noise_can_drop_the_readout_flip(si1000):
    stripped = strip_gate_noise(to_stim(si1000), readout=True)
    assert all(not i.gate_args_copy() for i in stripped if i.name == "M")
    assert target_count(stripped, "X_ERROR") == target_count(to_stim(si1000), "X_ERROR")


def test_stripping_then_twirling_with_the_circuit_rates_restores_it(si1000):
    circuit = to_stim(si1000)
    rates = noise_params_from_stim(circuit)
    restored = pauli_twirl_circuit(
        strip_gate_noise(circuit), "pauli", p_1q=rates["p_1q"], p_2q=rates["p_2q"]
    )
    assert error_table(restored.detector_error_model()) == pytest.approx(
        error_table(circuit.detector_error_model()), abs=1e-12
    )


def test_gate_noise_is_the_depolarizing_after_the_latest_gate_on_each_qubit():
    circuit = stim.Circuit("""
        R 0 1 2 3
        H 0
        TICK
        DEPOLARIZE1(0.1) 0 1 2
        CX 2 3
        DEPOLARIZE1(0.3) 2 3
        DEPOLARIZE2(0.4) 2 3
        H 0
        DEPOLARIZE1(0.5) 0
        DEPOLARIZE1(0.6) 0
        M 0 1 2 3
    """)
    stripped = strip_gate_noise(circuit)
    assert stripped == stim.Circuit("""
        R 0 1 2 3
        H 0
        TICK
        DEPOLARIZE1(0.1) 1 2
        CX 2 3
        DEPOLARIZE1(0.3) 2 3
        H 0
        DEPOLARIZE1(0.6) 0
        M 0 1 2 3
    """)
    # 0.1 follows H on qubit 0, 0.4 follows CX, 0.5 follows the second H.
    # Qubit 2 had no 1-qubit gate and a CX's qubits take 2-qubit noise only.
    # The two 1-qubit rates tie on count, so the larger one is used.
    with pytest.warns(UserWarning, match="single-qubit gate rates"):
        assert noise_params_from_stim(circuit) == pytest.approx(
            {"p_1q": 0.5, "p_2q": 0.4, "readout_error": 0.0}
        )


def test_noise_after_a_reset_or_measurement_is_not_gate_noise():
    circuit = stim.Circuit("H 0\nR 0\nDEPOLARIZE1(0.1) 0\nH 1\nM 1\nDEPOLARIZE1(0.2) 1")
    assert strip_gate_noise(circuit) == circuit


def test_several_two_qubit_rates_warn():
    circuit = stim.Circuit("CX 0 1\nDEPOLARIZE2(0.01) 0 1\nCZ 0 1\nDEPOLARIZE2(0.02) 0 1")
    with pytest.warns(UserWarning, match="two-qubit gate rates"):
        assert noise_params_from_stim(circuit)["p_2q"] == 0.02


def test_every_two_qubit_gate_gets_two_qubit_noise():
    circuit = stim.Circuit("CX 0 1\nCY 2 3\nCZ 4 5\nSWAP 6 7\nH 8")
    assert _two_qubit_pairs(circuit) == {(0, 1), (2, 3), (4, 5), (6, 7)}


def test_twirl_without_layers_is_the_circuit(si1000):
    circuit = to_stim(si1000)
    assert pauli_twirl_circuit(circuit, "pauli") == circuit
    assert pauli_twirl_circuit(circuit, "none", p_1q=0.1) == circuit


def test_pauli_twirl_places_channels_after_each_gate():
    circuit = stim.Circuit("R 0 1 2\nH 0 1\nCX 0 2\nI 1\nM 0 1 2")
    twirled = pauli_twirl_circuit(circuit, "pauli", p_1q=0.1, p_2q=0.2)
    assert twirled == stim.Circuit("""
        R 0 1 2
        H 0
        DEPOLARIZE1(0.1) 0
        H 1
        DEPOLARIZE1(0.1) 1
        CX 0 2
        DEPOLARIZE2(0.2) 0 2
        I 1
        M 0 1 2
    """)


def test_coherent_twirls_to_depolarize1_per_qubit_after_every_gate():
    circuit = stim.Circuit("R 0 1\nH 0\nCX 0 1\nM 0 1")
    twirled = pauli_twirl_circuit(circuit, "coherent", p_1q=0.5, p_2q=0.01)
    assert twirled == stim.Circuit("""
        R 0 1
        H 0
        DEPOLARIZE1(0.01) 0
        CX 0 1
        DEPOLARIZE1(0.01) 0 1
        M 0 1
    """)


def test_readout_error_composes_with_the_measurement_flip():
    twirled = pauli_twirl_circuit(stim.Circuit("M(0.1) 0"), "pauli", readout_error=0.2)
    assert twirled[0].gate_args_copy() == pytest.approx([0.1 + 0.2 - 2 * 0.1 * 0.2])


def test_t1_twirls_to_the_sampled_reset_by_default():
    gamma = 0.36
    twirled = pauli_twirl_circuit(stim.Circuit("X 0"), "pauli", t1=gamma)
    assert twirled[1].name == "PAULI_CHANNEL_1"
    assert twirled[1].gate_args_copy() == pytest.approx([gamma / 4] * 3)


def test_t1_twirls_to_amplitude_damping_on_request():
    gamma = 0.36
    twirled = pauli_twirl_circuit(stim.Circuit("X 0"), "pauli", t1=gamma, amplitude_damping=True)
    assert twirled[1].name == "PAULI_CHANNEL_1"
    assert twirled[1].gate_args_copy() == pytest.approx(
        [gamma / 4, gamma / 4, (1 - math.sqrt(1 - gamma)) ** 2 / 4]
    )


def test_build_noise_model_none():
    circuit = stim.Circuit("H 0\nCX 0 2\nM 0 2")
    nm = build_noise_model(circuit, "none", p_1q=0.1, p_2q=0.2, readout_error=0.3, t1=0.4)
    assert not nm.has_any()
    assert nm._call_log == []


def test_build_noise_model_invalid_type():
    circuit = stim.Circuit("H 0")
    with pytest.raises(ValueError, match="noise_type must be one of"):
        build_noise_model(circuit, "invalid_noise_type")


def test_build_noise_model_layers():
    circuit = stim.Circuit("H 0\nCX 0 2\nM 0 2")
    nm = build_noise_model(
        circuit,
        "pauli",
        p_1q=0.01,
        p_2q=0.02,
        readout_error=0.03,
        t1=0.04,
    )
    assert nm.has_1q_gate_noise()
    assert nm.has_any_2q_depolarizing()
    assert nm.has_readout_error()
    assert nm.has_t1()
    assert not nm.has_coherent()
    assert nm._call_log == [
        ("set_all_1q_gate_depolarizing", (3, 0.01), {}),
        ("set_2q_depolarizing", (0, 2, 0.02), {}),
        ("set_all_readout_error", (3, 0.03), {}),
        ("set_all_t1", (3, 0.04), {}),
    ]


def test_build_noise_model_coherent():
    circuit = stim.Circuit("H 0\nCX 0 2\nM 0 2")
    nm_default = build_noise_model(circuit, "coherent", p_1q=0.01, p_2q=0.02)
    assert nm_default.has_coherent()
    assert not nm_default.has_1q_gate_noise()
    assert not nm_default.has_any_2q_depolarizing()
    assert nm_default._call_log == [
        ("set_all_coherent_depolarizing", (3, 0.02), {}),
    ]

    nm_explicit = build_noise_model(circuit, "coherent", p_2q=0.02, coherent=0.05)
    assert nm_explicit._call_log == [
        ("set_all_coherent_depolarizing", (3, 0.05), {}),
    ]


def test_build_noise_model_full():
    circuit = stim.Circuit("H 0\nCX 0 2\nM 0 2")
    nm = build_noise_model(circuit, "full", p_1q=0.01, p_2q=0.02, coherent=0.03)
    assert nm.has_1q_gate_noise()
    assert nm.has_any_2q_depolarizing()
    assert nm.has_coherent()
    assert nm._call_log == [
        ("set_all_1q_gate_depolarizing", (3, 0.01), {}),
        ("set_2q_depolarizing", (0, 2, 0.02), {}),
        ("set_all_coherent_depolarizing", (3, 0.03), {}),
    ]

    nm_default_coh = build_noise_model(circuit, "full", p_1q=0.01, p_2q=0.02)
    assert nm_default_coh._call_log == [
        ("set_all_1q_gate_depolarizing", (3, 0.01), {}),
        ("set_2q_depolarizing", (0, 2, 0.02), {}),
        ("set_all_coherent_depolarizing", (3, 0.02), {}),
    ]


@pytest.mark.parametrize("meas", ["MZ", "MX", "MY", "MR", "MRZ", "MRX", "MRY"])
def test_measurement_variants_strip_readout(meas):
    circuit = stim.Circuit(f"H 0\n{meas}(0.05) 0")
    stripped = strip_gate_noise(circuit, readout=True)
    expected_name = {"MZ": "M", "MRZ": "MR"}.get(meas, meas)
    assert any(i.name == expected_name and not i.gate_args_copy() for i in stripped)


@pytest.mark.parametrize("meas", ["MZ", "MX", "MY", "MR", "MRZ", "MRX", "MRY"])
def test_measurement_variants_pauli_twirl(meas):
    circuit = stim.Circuit(f"{meas}(0.1) 0")
    twirled = pauli_twirl_circuit(circuit, "pauli", readout_error=0.2)
    assert twirled[0].gate_args_copy() == pytest.approx([0.1 + 0.2 - 2 * 0.1 * 0.2])


def test_readout_error_on_noiseless_measurement():
    twirled = pauli_twirl_circuit(stim.Circuit("M 0 1"), "pauli", readout_error=0.2)
    assert twirled == stim.Circuit("M(0.2) 0 1")


def test_dominant_prefers_most_frequent_rate_over_largest():
    circuit = stim.Circuit("""
        H 0 1 2
        DEPOLARIZE1(0.01) 0 1 2
        X 0
        DEPOLARIZE1(0.05) 0
    """)
    with pytest.warns(UserWarning, match="single-qubit gate rates"):
        assert noise_params_from_stim(circuit)["p_1q"] == pytest.approx(0.01)


def test_several_readout_rates_warn_and_pick_max():
    circuit = stim.Circuit("M(0.01) 0 1\nM(0.05) 2")
    with pytest.warns(UserWarning, match="measurement flip rates"):
        assert noise_params_from_stim(circuit)["readout_error"] == pytest.approx(0.05)


def test_identity_gate_clears_pending_gate_before_noise():
    circuit = stim.Circuit("H 0\nI 0\nDEPOLARIZE1(0.1) 0")
    assert strip_gate_noise(circuit) == circuit
    assert noise_params_from_stim(circuit)["p_1q"] == 0.0


def test_strip_gate_noise_two_qubit_partner_matching():
    # Reversed qubit order in DEPOLARIZE2 still matches the preceding 2-qubit gate pair.
    reversed_pair = stim.Circuit("CX 0 1\nDEPOLARIZE2(0.1) 1 0")
    assert strip_gate_noise(reversed_pair) == stim.Circuit("CX 0 1")

    # Cross-pair DEPOLARIZE2 across two independent 2-qubit gates is not stripped.
    cross_pair = stim.Circuit("CX 0 1\nCX 2 3\nDEPOLARIZE2(0.1) 0 2")
    assert strip_gate_noise(cross_pair) == cross_pair


def test_strip_gate_noise_and_twirl_unroll_repeat_blocks():
    circuit = stim.Circuit("REPEAT 2 {\n    H 0\n    DEPOLARIZE1(0.1) 0\n}")
    stripped = strip_gate_noise(circuit)
    assert stripped == stim.Circuit("H 0\nH 0")
    assert noise_params_from_stim(circuit)["p_1q"] == pytest.approx(0.1)

    twirled = pauli_twirl_circuit(stim.Circuit("REPEAT 2 {\n    H 0\n}"), "pauli", p_1q=0.1)
    assert twirled == stim.Circuit("H 0\nDEPOLARIZE1(0.1) 0\nH 0\nDEPOLARIZE1(0.1) 0")


def test_coherent_twirl_with_explicit_override():
    circuit = stim.Circuit("H 0\nCX 0 1")
    twirled = pauli_twirl_circuit(circuit, "coherent", p_2q=0.01, coherent=0.05)
    assert twirled == stim.Circuit("""
        H 0
        DEPOLARIZE1(0.05) 0
        CX 0 1
        DEPOLARIZE1(0.05) 0 1
    """)


def test_full_twirl_places_all_channels_and_splits_multi_pair_gates():
    circuit = stim.Circuit("H 0\nCX 0 1 2 3\nX_ERROR(0.04) 0")
    twirled = pauli_twirl_circuit(circuit, "full", p_1q=0.01, p_2q=0.02, coherent=0.03)
    assert twirled == stim.Circuit("""
        H 0
        DEPOLARIZE1(0.01) 0
        DEPOLARIZE1(0.03) 0
        CX 0 1
        DEPOLARIZE2(0.02) 0 1
        DEPOLARIZE1(0.03) 0 1
        CX 2 3
        DEPOLARIZE2(0.02) 2 3
        DEPOLARIZE1(0.03) 2 3
        X_ERROR(0.04) 0
    """)


def test_strip_gate_noise_empty_circuit():
    circuit = stim.Circuit()
    assert strip_gate_noise(circuit) == stim.Circuit()
    assert target_count(strip_gate_noise(circuit), "DEPOLARIZE1") == 0


def test_two_qubit_pairs_empty():
    assert _two_qubit_pairs(stim.Circuit("H 0\nDEPOLARIZE1(0.01) 0")) == set()


def test_dominant_empty():
    assert _dominant(Counter()) == 0.0


def test_noise_params_from_stim_noiseless():
    circuit = stim.Circuit("H 0\nCX 0 1\nM 0 1")
    assert noise_params_from_stim(circuit) == {"p_1q": 0.0, "p_2q": 0.0, "readout_error": 0.0}


def test_pauli_twirl_invalid_noise_type():
    with pytest.raises(ValueError, match="noise_type must be one of"):
        pauli_twirl_circuit(stim.Circuit(), "unsupported")
