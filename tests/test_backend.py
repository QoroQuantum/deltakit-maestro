# SPDX-FileCopyrightText: 2026 Qoro Quantum
# SPDX-License-Identifier: GPL-3.0-or-later

import maestro
import numpy as np
import pytest
import sinter
import stim
from conftest import error_table
from maestro.sinter import MaestroCompiledSampler

from deltakit_maestro import MaestroBackend, SimulationResult, strip_gate_noise, to_stim
from deltakit_maestro.maestro_backend import SINTER_DECODER, _noise_model_for_task

STABILIZER = maestro.SimulationType.Stabilizer
MPS = maestro.SimulationType.MatrixProductState


def assert_detection_rates_match(dets, reference):
    """Per-detector rates agree within 5 binomial sigmas of ``dets``' shots."""
    rates, expected = dets.mean(axis=0), reference.mean(axis=0)
    sigma = np.sqrt(np.maximum(expected * (1 - expected), 1e-3) / len(dets))
    assert np.all(np.abs(rates - expected) < 5 * sigma)


def test_to_stim_converts_deltakit_circuits(si1000):
    circuit = to_stim(si1000)
    assert isinstance(circuit, stim.Circuit)
    assert to_stim(circuit) is circuit


def test_pauli_task_runs_the_circuit_noise_and_decodes_with_its_dem(si1000):
    noisy = to_stim(si1000)
    task = MaestroBackend().as_sinter_task(si1000)
    assert task.circuit == noisy
    assert task.detector_error_model == noisy.detector_error_model(decompose_errors=True)
    assert task.json_metadata["noise"] == {"noise_type": "pauli", "stim_noise": True}


@pytest.mark.parametrize(
    "noise_type, noise, simulation_type, frames",
    [
        ("pauli", {}, STABILIZER, True),
        ("pauli", {"p_2q": 0.02, "readout_error": 0.03}, STABILIZER, True),
        ("none", {}, STABILIZER, True),
        ("full", {"coherent": 0.0}, STABILIZER, True),
        ("pauli", {"t1": 0.001}, STABILIZER, False),  # T1 is not a Pauli channel
        ("coherent", {}, MPS, False),
        ("full", {}, MPS, False),
    ],
)
def test_every_run_is_on_maestro_and_pauli_runs_use_frames(
    si1000, noise_type, noise, simulation_type, frames
):
    """Pauli-only runs sample on Maestro's Pauli frames, not one simulation per shot."""
    sampler = MaestroBackend().compile_sampler(si1000, noise_type, decoder=None, **noise)
    assert isinstance(sampler, MaestroCompiledSampler)
    assert sampler.config.simulation_type == simulation_type
    assert (sampler._reference_sampler is not None) == frames


def test_a_chosen_simulation_type_is_used(si1000):
    """Pinned, so a Clifford circuit runs on the MPS rather than Maestro's frames."""
    backend = MaestroBackend(simulation_type=MPS, max_bond_dimension=8)
    sampler = backend.compile_sampler(si1000, decoder=None)
    assert sampler.config.simulation_type == MPS
    assert sampler.config.max_bond_dimension == 8
    assert sampler.config.fixed_backend
    assert sampler._reference_sampler is None


def test_unpinned_backend_lets_maestro_use_frames(si1000):
    backend = MaestroBackend(simulation_type=MPS, fixed_backend=False)
    sampler = backend.compile_sampler(si1000, decoder=None)
    assert not sampler.config.fixed_backend
    assert sampler._reference_sampler is not None


def test_noiseless_check_sees_mps_truncation(si1000):
    """At χ=2 the d=3 code truncates; a noiseless run must show it, not hide it."""
    backend = MaestroBackend(simulation_type=MPS, max_bond_dimension=2)
    assert backend.simulate(si1000, 12, "none", seed=1).detection_events.any()


def test_maestro_pauli_matches_stim(si1000):
    """Maestro samples Stim's Pauli noise exactly: rates agree with Stim's own sampler."""
    result = MaestroBackend().simulate(si1000, 2000, seed=1)
    stim_circuit = to_stim(si1000)
    reference, ref_obs = stim_circuit.compile_detector_sampler(seed=1).sample(
        50_000, separate_observables=True
    )
    assert_detection_rates_match(result.detection_events, reference)
    assert_detection_rates_match(result.observable_flips, ref_obs)
    assert result.measurements.shape == (2000, stim_circuit.num_measurements)
    assert result.num_measurements == stim_circuit.num_measurements


def test_overridden_rates_reach_the_dem(si1000):
    """The DEM follows the overridden rates, not the circuit's original ones."""
    backend = MaestroBackend()
    rates = {"p_1q": 0.01, "p_2q": 0.02, "readout_error": 0.03}
    task = backend.as_sinter_task(si1000, **rates)
    twirled = backend.twirled_circuit(si1000, **rates)
    assert task.circuit == strip_gate_noise(to_stim(si1000), readout=True)
    assert task.detector_error_model == twirled.detector_error_model(decompose_errors=True)
    assert task.detector_error_model != to_stim(si1000).detector_error_model(decompose_errors=True)

    # And it describes what Maestro's NoiseModel simulates.
    result = backend.simulate(si1000, 2000, seed=2, **rates)
    reference = twirled.compile_detector_sampler(seed=2).sample(50_000)
    assert_detection_rates_match(result.detection_events, reference)


def test_overriding_with_the_circuits_own_rates_reproduces_the_circuit(si1000):
    """Only gate noise moves to the NoiseModel; idle, reset and readout noise stay."""
    circuit = to_stim(si1000)
    backend = MaestroBackend()
    task = backend.as_sinter_task(si1000, p_1q=0.001, p_2q=0.01)
    assert task.circuit == strip_gate_noise(circuit)
    twirled = backend.twirled_circuit(si1000, p_1q=0.001, p_2q=0.01)
    assert error_table(twirled.detector_error_model()) == pytest.approx(
        error_table(circuit.detector_error_model()), abs=1e-12
    )

    result = backend.simulate(si1000, 2000, seed=5, p_1q=0.001, p_2q=0.01)
    reference = circuit.compile_detector_sampler(seed=5).sample(50_000)
    assert_detection_rates_match(result.detection_events, reference)


def test_coherent_mode_keeps_reset_idle_and_readout_noise(si1000):
    task = MaestroBackend().as_sinter_task(si1000, "coherent")
    kept = {(i.name, tuple(i.gate_args_copy())) for i in task.circuit}
    assert ("X_ERROR", (0.02,)) in kept and ("M", (0.05,)) in kept
    assert ("DEPOLARIZE1", (0.02,)) in kept
    assert not any(name == "DEPOLARIZE2" for name, _ in kept)
    assert task.json_metadata["noise"]["p_2q"] == 0.01


def test_coherent_run_uses_mps_and_a_twirl_matched_dem(si1000):
    backend = MaestroBackend()
    result = backend.simulate(si1000, 20, "coherent", seed=3)
    assert result.detection_events.shape[0] == 20
    assert result.metadata["noise"]["noise_type"] == "coherent"
    assert backend.config_for("coherent", p_2q=0.01).simulation_type == MPS

    task = backend.as_sinter_task(si1000, "coherent")
    twirled = backend.twirled_circuit(si1000, "coherent")
    assert task.detector_error_model == twirled.detector_error_model(decompose_errors=True)


def test_none_runs_noiseless_and_decodes_with_the_circuit_dem(si1000):
    backend = MaestroBackend()
    result = backend.simulate(si1000, 50, "none", seed=4)
    assert not result.detection_events.any()
    assert not result.observable_flips.any()
    assert result.num_measurements == to_stim(si1000).num_measurements
    task = backend.as_sinter_task(si1000, "none")
    assert task.detector_error_model == to_stim(si1000).detector_error_model(decompose_errors=True)


@pytest.mark.parametrize(
    "noise_type, noise, expected",
    [
        ("pauli", {}, STABILIZER),
        ("pauli", {"t1": 0.001}, STABILIZER),
        ("none", {}, STABILIZER),
        ("coherent", {"p_2q": 0.01}, MPS),
        ("coherent", {}, MPS),  # strength is the circuit's p_2q: assumed nonzero
        ("coherent", {"p_2q": 0.0}, STABILIZER),
        ("coherent", {"coherent": 0.005}, MPS),
        ("full", {}, MPS),
        ("full", {"coherent": 0.01}, MPS),
        ("full", {"coherent": 0.0}, STABILIZER),
    ],
)
def test_auto_simulation_type(noise_type, noise, expected):
    assert MaestroBackend().config_for(noise_type, **noise).simulation_type == expected


def test_a_runs_actual_simulator_matches_config_for(si1000):
    """The sampler resolves the circuit's own p_2q, so it agrees with config_for."""
    backend = MaestroBackend()
    for noise_type, noise, expected in [
        ("pauli", {"t1": 0.001}, STABILIZER),
        ("coherent", {}, MPS),
        ("full", {}, MPS),
    ]:
        sampler = backend.compile_sampler(si1000, noise_type, **noise)
        assert sampler.config.simulation_type == expected
        assert backend.config_for(noise_type, **noise).simulation_type == expected


def test_explicit_simulation_type_wins():
    backend = MaestroBackend(simulation_type=MPS, max_bond_dimension=8)
    config = backend.config_for("pauli")
    assert config.simulation_type == MPS and config.max_bond_dimension == 8


@pytest.mark.parametrize(
    "noise_type, noise, error",
    [
        ("pauli", {"p2q": 0.01}, TypeError),
        ("pauli", {"coherent": 0.01}, ValueError),
        ("coherent", {"p_1q": 0.01}, ValueError),
        ("none", {"t1": 0.01}, ValueError),
        ("depolarizing", {}, ValueError),
    ],
)
def test_bad_noise_arguments_reject_before_sampling(si1000, noise_type, noise, error):
    with pytest.raises(error):
        MaestroBackend().as_sinter_task(si1000, noise_type, **noise)


def test_sinter_collect_across_workers(si1000):
    backend = MaestroBackend()
    stats = sinter.collect(
        num_workers=2,
        tasks=[backend.as_sinter_task(si1000, json_metadata={"p": 0.01})],
        custom_decoders=backend.sinter_decoders(),
        max_shots=400,
        max_batch_size=100,
    )
    assert len(stats) == 1
    assert stats[0].shots == 400 and stats[0].json_metadata["p"] == 0.01
    assert 0 < stats[0].errors < 400


def test_simulation_result_class():
    meas = np.zeros((10, 5), dtype=np.uint8)
    dets = np.zeros((10, 3), dtype=bool)
    obs = np.zeros((10, 1), dtype=bool)
    res = SimulationResult(
        measurements=meas,
        detection_events=dets,
        observable_flips=obs,
        metadata={"shots": 10, "backend": "Test"},
    )
    assert res.num_measurements == 5
    assert res.measurements.shape == (10, 5)
    assert res.detection_events.shape == (10, 3)
    assert res.observable_flips.shape == (10, 1)
    assert res.metadata["shots"] == 10


def test_backend_repr():
    b_default = MaestroBackend()
    assert "simulation_type=auto" in repr(b_default)
    assert "max_bond_dimension=32" in repr(b_default)

    b_mps = MaestroBackend(simulation_type=MPS, max_bond_dimension=16)
    assert "MatrixProductState" in repr(b_mps)
    assert "max_bond_dimension=16" in repr(b_mps)


def test_invalid_simulator_config_rejected_on_init():
    with pytest.raises(TypeError):
        MaestroBackend(nonexistent_config_field=123)


def test_seed_in_simulator_config_rejected_on_init():
    """Every sinter.collect worker would otherwise draw the same shots."""
    with pytest.raises(ValueError, match="seed="):
        MaestroBackend(seed=1)


@pytest.mark.parametrize("noise", [{}, {"t1": 0.01}])
def test_shots_come_back_in_random_order(noise):
    """Any slice of the shots is a fair sample, on Pauli frames and shot by shot (T1)."""
    circuit = stim.Circuit.generated(
        "repetition_code:memory", distance=3, rounds=3, after_clifford_depolarization=0.05
    )
    backend = MaestroBackend()
    dets, _ = backend.compile_sampler(circuit, seed=1, **noise).sample_detection_events(2000)
    simulated = backend.simulate(circuit, 2000, seed=1, **noise).detection_events
    for fired in (dets.any(axis=1), simulated.any(axis=1)):
        assert abs(fired[:1000].mean() - fired[1000:].mean()) < 0.1


def test_to_stim_string_and_custom_circuit():
    stim_text = "H 0\nCX 0 1\nM 0 1"
    c = to_stim(stim_text)
    assert isinstance(c, stim.Circuit)
    assert c == stim.Circuit(stim_text)

    class CustomCircuitWrapper:
        def as_stim_circuit(self):
            return "X 0\nM 0"

    wrapped = to_stim(CustomCircuitWrapper())
    assert isinstance(wrapped, stim.Circuit)
    assert wrapped == stim.Circuit("X 0\nM 0")


def test_compile_sampler_methods_and_decoding(si1000):
    backend = MaestroBackend()
    sampler = backend.compile_sampler(si1000, decoder="pymatching", seed=11)
    assert sampler.num_measurements == to_stim(si1000).num_measurements
    meas = sampler.sample_measurements(20)
    assert meas.shape == (20, to_stim(si1000).num_measurements)
    dets, obs = sampler.sample_detection_events(20)
    assert dets.shape[0] == 20
    assert obs.shape[0] == 20

    stats_decoded = backend.compile_sampler(si1000, decoder="pymatching", seed=12).sample(300)
    stats_vacuous = backend.compile_sampler(si1000, decoder=None, seed=12).sample(300)
    assert stats_decoded.shots == 300
    assert stats_vacuous.shots == 300
    assert 0 <= stats_decoded.errors < stats_vacuous.errors


def test_compile_sampler_decoders(si1000):
    backend = MaestroBackend()
    sampler_vacuous = backend.compile_sampler(si1000, noise_type="none", decoder="vacuous")
    assert sampler_vacuous.decoder == "vacuous"

    sampler_none = backend.compile_sampler(si1000, noise_type="none", decoder=None)
    assert sampler_none.decoder == "vacuous"


def test_partial_pauli_overrides_preserve_unoverridden_circuit_rates(si1000):
    circuit = to_stim(si1000)
    backend = MaestroBackend()

    # Overriding only p_1q strips gate noise, keeps M(0.05) in circuit, and fills p_2q from circuit.
    task_1q = backend.as_sinter_task(si1000, p_1q=0.005)
    assert task_1q.circuit == strip_gate_noise(circuit, readout=False)
    assert task_1q.json_metadata["noise"] == {
        "noise_type": "pauli",
        "stim_noise": False,
        "p_1q": 0.005,
        "p_2q": 0.01,
    }

    # Overriding only readout_error strips gate noise and M(0.05), filling p_1q and p_2q from circuit.
    task_ro = backend.as_sinter_task(si1000, readout_error=0.02)
    assert task_ro.circuit == strip_gate_noise(circuit, readout=True)
    assert task_ro.json_metadata["noise"] == {
        "noise_type": "pauli",
        "stim_noise": False,
        "p_1q": 0.001,
        "p_2q": 0.01,
        "readout_error": 0.02,
    }

    # Overriding p_2q in 'full' mode without explicit coherent defaults coherent to new p_2q.
    task_full = backend.as_sinter_task(si1000, "full", p_2q=0.02)
    assert task_full.circuit == strip_gate_noise(circuit, readout=False)
    nm = _noise_model_for_task(task_full)
    assert ("set_all_coherent_depolarizing", (circuit.num_qubits, 0.02), {}) in nm._call_log


def test_full_noise_task_twirl_and_simulation(si1000):
    backend = MaestroBackend()
    pauli_task = backend.as_sinter_task(si1000, "pauli")

    # When coherent is omitted, defaults to the circuit's p_2q rate
    task = backend.as_sinter_task(si1000, "full")
    assert task.json_metadata["noise"] == {
        "noise_type": "full",
        "stim_noise": True,
        "coherent": 0.01,
    }

    twirled = backend.twirled_circuit(si1000, "full")
    assert task.detector_error_model == twirled.detector_error_model(decompose_errors=True)
    assert task.detector_error_model != pauli_task.detector_error_model
    assert sum(error_table(task.detector_error_model).values()) > sum(
        error_table(pauli_task.detector_error_model).values()
    )

    # Explicit coherent rate override
    task_explicit = backend.as_sinter_task(si1000, "full", coherent=0.005)
    assert task_explicit.json_metadata["noise"]["coherent"] == 0.005

    result = backend.simulate(si1000, 15, "full", seed=7)
    assert result.detection_events.shape[0] == 15
    assert result.metadata["noise"]["noise_type"] == "full"


def test_t1_noise_in_as_sinter_task_and_simulation(si1000):
    backend = MaestroBackend()
    pauli_task = backend.as_sinter_task(si1000, "pauli")
    task = backend.as_sinter_task(si1000, "pauli", t1=0.005)
    assert task.json_metadata["noise"]["t1"] == 0.005
    twirled = backend.twirled_circuit(si1000, "pauli", t1=0.005)
    assert task.detector_error_model == twirled.detector_error_model(decompose_errors=True)
    assert task.detector_error_model != pauli_task.detector_error_model
    assert sum(error_table(task.detector_error_model).values()) > sum(
        error_table(pauli_task.detector_error_model).values()
    )

    result = backend.simulate(si1000, 100, "pauli", seed=8, t1=0.01)
    assert result.detection_events.shape[0] == 100
    assert result.detection_events.any()


@pytest.mark.parametrize("simulation_type", [None, MPS, maestro.SimulationType.DensityMatrix])
def test_t1_dem_matches_what_maestro_simulates(simulation_type):
    """|+> after one gate dephases at γ/2 under a sampled reset, (1-√(1-γ))/2 under damping."""
    circuit = stim.Circuit("RX 0\nZ 0\nMX 0")
    backend = MaestroBackend(simulation_type=simulation_type)
    flips = 1 - backend.simulate(circuit, 4000, seed=1, t1=0.4).measurements.mean()
    twirled = backend.twirled_circuit(circuit, t1=0.4)
    expected = 1 - twirled.compile_sampler(seed=1).sample(100_000).mean()
    assert flips == pytest.approx(expected, abs=0.03)


def test_noise_model_for_task(si1000):
    backend = MaestroBackend()
    # Unadorned pauli task keeps noise in the Stim circuit; supplementary NoiseModel is None.
    assert _noise_model_for_task(backend.as_sinter_task(si1000, "pauli")) is None
    assert _noise_model_for_task(backend.as_sinter_task(si1000, "none")) is None
    assert _noise_model_for_task(sinter.Task(circuit=to_stim(si1000), json_metadata=None)) is None
    assert _noise_model_for_task(sinter.Task(circuit=to_stim(si1000), json_metadata={})) is None

    # Adding T1 or overriding Pauli rates builds a supplementary NoiseModel.
    nm_t1 = _noise_model_for_task(backend.as_sinter_task(si1000, "pauli", t1=0.01))
    assert nm_t1 is not None and nm_t1.has_t1()


def test_task_with_zero_detectors(trivial_circuit):
    backend = MaestroBackend()
    task = backend.as_sinter_task(trivial_circuit, "none")
    assert task.detector_error_model is None


def test_sinter_decoders_mapping(si1000):
    backend = MaestroBackend()
    decoders = backend.sinter_decoders()
    assert SINTER_DECODER in decoders
    sinter_sampler = decoders[SINTER_DECODER]
    task = backend.as_sinter_task(si1000, "none")
    compiled = sinter_sampler.compiled_sampler_for_task(task)
    assert hasattr(compiled, "sample_measurements")


def test_non_graphlike_dem_is_left_whole():
    """An error with three symptoms can't be decomposed for matching, as in qLDPC codes."""
    circuit = stim.Circuit("""
        R 0 1 2
        X_ERROR(0.1) 0
        CX 0 1 0 2
        M 0 1 2
        DETECTOR rec[-1]
        DETECTOR rec[-2]
        DETECTOR rec[-3]
    """)
    backend = MaestroBackend()
    task = backend.as_sinter_task(circuit)
    assert task.detector_error_model == circuit.detector_error_model()
    fired = backend.simulate(circuit, 2000, seed=1).detection_events
    assert np.all(fired == fired[:, :1]) and 0.05 < fired.mean() < 0.15


def test_x_basis_memory_circuit(si1000_x):
    backend = MaestroBackend()
    task = backend.as_sinter_task(si1000_x)
    assert task.circuit == to_stim(si1000_x)
    assert task.detector_error_model == to_stim(si1000_x).detector_error_model(
        decompose_errors=True
    )
    result = backend.simulate(si1000_x, 50, seed=9)
    assert result.detection_events.shape[0] == 50
    assert result.observable_flips.shape == (50, 1)


def test_distance_2_circuit(si1000_d2):
    backend = MaestroBackend()
    task = backend.as_sinter_task(si1000_d2)
    assert task.circuit == to_stim(si1000_d2)
    assert task.detector_error_model is not None
    result = backend.simulate(si1000_d2, 50, seed=10)
    assert result.detection_events.shape[0] == 50


def test_seed_reproducibility(si1000):
    backend = MaestroBackend()
    result1 = backend.simulate(si1000, 100, "pauli", seed=42)
    result2 = backend.simulate(si1000, 100, "pauli", seed=42)
    result3 = backend.simulate(si1000, 100, "pauli", seed=43)
    assert result1.detection_events.any()
    np.testing.assert_array_equal(result1.measurements, result2.measurements)
    np.testing.assert_array_equal(result1.detection_events, result2.detection_events)
    np.testing.assert_array_equal(result1.observable_flips, result2.observable_flips)
    assert not np.array_equal(result1.measurements, result3.measurements)
    assert not np.array_equal(result1.detection_events, result3.detection_events)
