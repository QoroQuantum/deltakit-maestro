# deltakit-maestro

Qoro **Maestro** simulator backend for **Riverlane Deltakit** QEC circuits.

A thin adapter over `maestro.sinter`. A Deltakit `Circuit` is converted to Stim with
`as_stim_circuit()`:

| From the noisy Stim circuit | Goes to |
|---|---|
| noisy `stim.Circuit` (or with its gate noise stripped) | Maestro, which executes it |
| hardware noise layers (`coherent`, `t1`) or rate overrides | a `maestro.NoiseModel` |
| the Pauli twirl of everything that is simulated | the decoder's detector error model |

The result comes back as raw measurements, detection events, or Sinter statistics.

Every run is simulated by Maestro. With the default `simulation_type=None` the
simulation type follows the noise:

| Run | Maestro simulation type |
|---|---|
| `'pauli'` (rate overrides included) or `'none'` | `Stabilizer`, sampled on Pauli frames |
| any run with `t1=` but no coherent noise | `Stabilizer`, shot by shot (`T1` decay is not a Pauli channel) |
| `'coherent'` or `'full'` | `MatrixProductState` |
| any run, with `simulation_type=` set | that simulation type |

`backend.config_for(noise_type, **noise).simulation_type` says which one a run uses.
Pauli frames sample a Clifford circuit with Pauli noise about as fast as Stim does; coherent
over-rotations, which no Clifford simulator can run, need the matrix product state.

## Install

Needs Python **3.10–3.13** (`deltakit` requires `<3.14`).

```bash
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install -e ".[examples]"     # examples extra adds pymatching
```

Verify:

```bash
python -c "from deltakit_maestro import MaestroBackend; print(MaestroBackend())"
```

## Quick start

```python
# Import deltakit before pymatching. See Gotchas.
from deltakit.circuit.gates import PauliBasis
from deltakit.explorer.codes import RotatedPlanarCode, css_code_memory_circuit
from deltakit.explorer.qpu import QPU, SI1000Noise
import sinter

from deltakit_maestro import MaestroBackend

code = RotatedPlanarCode(width=3, height=3)
circuit = css_code_memory_circuit(code, num_rounds=3, logical_basis=PauliBasis.Z)
noisy = QPU(circuit.qubits, noise_model=SI1000Noise(p=0.01)) \
            .compile_and_add_noise_to_circuit(circuit)

backend = MaestroBackend()   # Stabilizer for Pauli runs, MPS (χ=32) for coherent ones

# 1. Detection events straight from Maestro
sampler = backend.compile_sampler(noisy, seed=1)
dets, obs = sampler.sample_detection_events(1000)
# decode against sampler.task.detector_error_model

# 2. Sinter
stats = sinter.collect(
    num_workers=4,
    tasks=[backend.as_sinter_task(noisy, json_metadata={'p': 0.01})],
    custom_decoders=backend.sinter_decoders(decoder='pymatching'),
    max_shots=10_000,
)

# 3. Raw measurements (and detection events) in one call
result = backend.simulate(noisy, shots=1000)
result.measurements       # (1000, n_meas) uint8, Stim record order

# 4. Coherent noise, and its Pauli twirl to compare against
coherent = backend.simulate(noisy, shots=300, noise_type='coherent')
twirl = backend.simulate(backend.twirled_circuit(noisy, noise_type='coherent'), shots=100_000)
```

## Examples

| Script | Shows | Run time |
|---|---|---|
| `examples/example_noise_modes.py` | How the noise is read from a circuit, split into gate and other noise, and what each `noise_type` and override runs, and on which simulation type, on a Deltakit and a Stim-generated circuit | ~2 s |
| `examples/example_stim_circuit.py` | Raw measurements, detection events, observable flips, seeds, manual decoding and `sinter.collect` on a plain Stim circuit (no Deltakit) | ~1 s |
| `examples/example_coherent_noise.py` | Coherent over-rotation against its Pauli twirl on a repetition code: about 1.5× the logical errors and detection events | ~3 s |
| `examples/example_surface_code.py` | A d=3 Deltakit surface code sweep: Pauli noise on Pauli frames and `sinter.collect`, then coherent noise on an MPS against its twirl | ~10 s |
| `examples/example_deltakit_codes.py` | Every Deltakit code family through the backend: repetition, rotated and unrotated planar and toric codes with PyMatching, and the [[72,12,6]] bivariate bicycle code with BP-OSD | ~20 s |
| `examples/example_bond_dimension.py` | Setting the MPS bond dimension χ, the noiseless truncation check, and coherent noise converging in χ | ~30 s |
| `examples/coherent_noise_d3.ipynb` | Notebook, saved with its outputs: coherent noise on the d=3 surface code against its Pauli twirl and SI1000, with the χ check, an LEP sweep and per-detector plots. Needs `matplotlib` and Jupyter | ~40 s |

Times are on a 12-core laptop. Stim's own sampler appears in a few examples only as an
independent reference that Maestro's results agree with.

The first three run in the test suite (`tests/test_examples.py`).

## API

```python
MaestroBackend(simulator_type=QCSim, simulation_type=None,
               max_bond_dimension=32, **simulator_config)

backend.simulate(circuit, shots, noise_type='pauli', seed=None, **noise)
    # -> SimulationResult(.measurements, .detection_events,
    #                     .observable_flips, .metadata, .num_measurements)

backend.compile_sampler(circuit, noise_type='pauli', decoder='pymatching',
                        seed=None, **noise)
    # -> maestro.sinter.MaestroCompiledSampler
    #    .sample_measurements(shots)      -> measurements (bool)
    #    .sample_detection_events(shots)  -> (dets, obs)
    #    .sample(shots)                   -> sinter.AnonTaskStats (decoded)

backend.as_sinter_task(circuit, noise_type='pauli', json_metadata=None, **noise)
    # -> sinter.Task(circuit=..., detector_error_model=dem, decoder='maestro')

backend.sinter_decoders(decoder='pymatching')
    # -> {'maestro': sinter.Sampler}, pass as custom_decoders= to sinter.collect

backend.twirled_circuit(circuit, noise_type='pauli', **noise)
    # -> stim.Circuit whose DEM the decoder uses; simulate it for a twirled baseline

backend.config_for(noise_type='pauli', **noise)
    # -> the maestro.SimulatorConfig such a run uses
```

`circuit` is a Deltakit `Circuit` or a `stim.Circuit`. `simulation_type=None` picks the
simulation type per run, as in the table above; pass a `maestro.SimulationType` to run
everything with it. The type that runs is pinned (`fixed_backend=True`): unpinned, Maestro
samples any Clifford circuit on Pauli frames whatever the type, so an MPS run of a Pauli
circuit would never touch the MPS. Pass `fixed_backend=False` to allow that.
`**simulator_config` is any other `maestro.SimulatorConfig` field, such as
`simulator_type=maestro.SimulatorType.Gpu` or `max_simulators=` (the threads one sampler
uses), except `seed`, which `simulate` and `compile_sampler` take instead.
Shots come back in random order, so any slice of them is a fair sample.
`decoder='vacuous'` (or `decoder=None`) gives undecoded statistics.

Lower-level helpers: `to_stim`, `noise_params_from_stim`, `strip_gate_noise`,
`build_noise_model`, `pauli_twirl_circuit`.

### Noise

Maestro executes Stim's own Pauli noise channels (`DEPOLARIZE1/2`, `X/Y/Z_ERROR`,
`PAULI_CHANNEL_1/2`) and measurement flips (`M(p)`) natively in the circuit. When
`noise_type` is `'coherent'` or when Pauli rates are explicitly overridden via `**noise`,
the circuit's **gate noise** is removed with `strip_gate_noise` and the `maestro.NoiseModel`
supplies its replacement:

| Stim (from Deltakit) | `maestro.NoiseModel` |
|---|---|
| `DEPOLARIZE2(p)` after two-qubit gates | `set_2q_depolarizing` on each pair |
| `DEPOLARIZE1(p)` after single-qubit gates | `set_all_1q_gate_depolarizing` |
| `M(p)`, only when `readout_error=` is overridden | `set_all_readout_error` |

Gate noise is the depolarizing whose qubit's latest operation was a gate of the same
arity. Deltakit places it after the next `TICK`, merged with the idle noise of other
qubits, so one instruction's targets are split: gate noise goes, idle noise stays. Idle,
reset (`X_ERROR`) and measurement (`M(p)`) noise always stay in the circuit, and the rates
come from the stripped instructions themselves. A warning is raised if they differ across
gates, since one rate replaces them all. Only `DEPOLARIZE1/2` is treated as gate noise;
other channels after gates (e.g. `X_ERROR`) stay in the circuit.

`noise_type` controls how errors are realised:

| `noise_type` | Gate & circuit errors |
|---|---|
| `'pauli'` | exact in-circuit Stim Pauli & readout noise (or replacement gate noise when `p_1q`/`p_2q` are overridden, and readout when `readout_error` is), sampled on Pauli frames |
| `'coherent'` | gate depolarizing replaced by isotropic coherent over-rotation, ε = 2·arcsin√p about a body diagonal after every gate; idle, reset and readout noise kept |
| `'full'` | circuit noise and coherent over-rotation both |
| `'none'` | none (noiseless) |

Readout error applies in every mode except `'none'`.

The `**noise` keywords override or extend the extracted rates: `p_1q`, `p_2q`,
`readout_error`, `t1` (per-gate `T1` decay probability γ) and `coherent` (over-rotation
infidelity, default `p_2q`). For example:

```python
backend.simulate(noisy, 1000, noise_type='full', coherent=0.002, t1=1e-4)
```

Unknown keywords raise `TypeError`, and keywords the `noise_type` never reads (such as
`coherent=` with `'pauli'`) raise `ValueError`, before anything is sampled.

Every shot is a fresh noise realisation (`noise_realizations=shots`).

### The decoder's detector error model

The DEM is built from `twirled_circuit`: the circuit Maestro runs plus the Pauli twirl of
every `NoiseModel` layer, placed after each gate as Maestro injects it. The coherent
over-rotation twirls exactly to `DEPOLARIZE1(coherent)`. `T1` decay γ depends on the
simulation type: `DensityMatrix` and `MatrixProductOperator` run amplitude damping, which
twirls to `PAULI_CHANNEL_1(γ/4, γ/4, (1-√(1-γ))²/4)`; every other type, the automatic
choices included, resets the qubit to |0⟩ with probability γ, which twirls to
`PAULI_CHANNEL_1(γ/4, γ/4, γ/4)` and dephases about twice as fast. So the decoder always
knows the strength of the noise it is decoding, overrides included, and the gap between
a `'coherent'` run and a run of its `twirled_circuit` is the effect of coherence alone.

For `'pauli'` without overrides the DEM is the input circuit's own. For `'none'`, which
simulates no noise, the decoder keeps the input circuit's DEM as its prior.

The DEM is decomposed into graphlike errors for matching decoders where it can be. qLDPC
codes such as Deltakit's `BivariateBicycleCode` have errors that can't be, so their DEM is
left whole; decode those with a decoder such as BP-OSD, as `example_deltakit_codes.py` does
with `ldpc`.

### Coherent noise is only roughly calibrated against SI1000

`'coherent'` keeps SI1000's idle, reset and readout noise and replaces only the gate noise,
so it is close to SI1000, but not equal. `maestro.NoiseModel` sets one coherent strength
per qubit, applied after every gate whatever its arity. With the default
`coherent = p_2q`, an SI1000(p) circuit gets an over-rotation of infidelity p after each
single-qubit gate (SI1000 has p/10 there) and on both qubits of each two-qubit gate (about
2p in total, where SI1000 has p). That over-counts gate noise.

Measured on the d=3, 3-round memory at p=0.01 (logical error rate, PyMatching):

| Noise | LEP |
|---|---|
| SI1000 Pauli (stabilizer) | 0.1990 ± 0.0009 |
| Pauli twirl of `'coherent'` (stabilizer) | 0.2330 ± 0.0009 |
| `'coherent'` (MPS, 800 shots) | 0.270 ± 0.016 |

So `'coherent'` and `'pauli'` at the same p differ by about 17% in LEP from strength alone,
before any effect of coherence. To isolate coherence, compare `'coherent'` against its own
twirl (`twirled_circuit`), as the example does. A per-gate-type coherent strength in
Maestro would close the rest of the gap.

## Performance

Measured on an Apple M4 Pro (12 cores), rotated surface code memory, SI1000(0.002)
noise, d rounds, detection events in shots per second.

**Pauli noise** is sampled on Pauli frames, on one thread, about as fast as Stim's own
detector sampler from d=5 up (1M shots):

| | d=3 | d=5 | d=7 | d=9 |
|---|---|---|---|---|
| Maestro, `compile_sampler(...).sample_detection_events` | 9.8M | 2.2M | 490k | 220k |
| Stim, `compile_detector_sampler().sample` | 14M | 2.4M | 500k | 220k |

Under `sinter.collect` decoding takes most of the time. The [[72,12,6]] bivariate
bicycle code (144 qubits, SI1000(0.003), 3 rounds, in `example_deltakit_codes.py`)
samples at about 46 µs/shot.

**`T1` decay** is not a Pauli channel, so the stabilizer runs it shot by shot: about
19,000 shots/s at d=3 and 2,100 at d=5 on one thread. One sampler spreads its shots over
every core, about 36,000 and 10,000 shots/s here. `max_simulators=` caps the threads.

**Coherent noise** runs on an MPS: about 57 ms a shot per core on the rotated d=3 code at
χ=32. One sampler again uses every core, about 6 ms a shot here, so a single
`simulate` or `compile_sampler` call is as fast as `sinter.collect` over all the cores.

Coherent runs need MPS, with bond dimension χ set by `MaestroBackend(max_bond_dimension=)`
(default 32). Too small a χ truncates the state, which shows up as extra detection
events, the same direction as the coherent effect being studied. **Only the rotated d=3
code is practical.** Checked with the noiseless test below (3 rounds, SI1000(0.01) circuits):

| Code | Qubits | Smallest exact χ | Cost |
|---|---|---|---|
| Rotated planar d=3 | 17 | 8 | ~1 ms/shot |
| Unrotated planar d=3 | 25 | > 64 | ~0.9 s/shot at χ=64, still 75% of shots wrong |
| Unrotated toric d=3 | 36 | > 32 | ~1 s/shot at χ=32, every shot wrong |
| Rotated planar d=5 | 49 | > 32 | ~1.5 s/shot at χ=32, every shot wrong |

These noiseless runs have no noise to spread over cores, so they take as long on one.

Renumbering the qubits row by row from their coordinates did not help; it made the
rotated d=3 code need χ=64.

To check χ:

1. **Noiseless check.** Run with `simulation_type=MatrixProductState` and
   `noise_type='none'`. Every detector must stay silent, so any detection event is
   truncation error. It needs no reference and a few dozen shots. It relies on the
   pinned type: with `fixed_backend=False`, Maestro would sample this Clifford circuit on
   Pauli frames and the check would always pass.
2. **Coherent convergence.** Coherent noise needs more χ than the noiseless check: on the
   rotated d=3 code at p=0.01 the detection-event rate is 0.294 at χ=8, 0.272 at χ=16 and
   0.263 at χ=32 and 64, against 0.236 for its Pauli twirl. At χ=8 truncation adds about
   as much as the coherent effect itself. Double χ until the result is unchanged within
   its error bars.

`example_bond_dimension.py` runs both.

## Gotchas

- **Import Deltakit before PyMatching.** With `pymatching` 2.4 imported first, Deltakit's
  circuit builders fail with `RuntimeError: Caught an unknown exception!`. Either order
  works once `deltakit.explorer` has been imported.
- **Don't mix Stim circuits.** `PyMatchingDecoder.construct_decoder_and_stim_circuit`
  orders gates and detectors differently from `as_stim_circuit()`. Decode against
  `sampler.task.detector_error_model` or `as_sinter_task(...).detector_error_model`.
- **Seeded `sinter.collect` is not supported** by `maestro.sinter`. For reproducible runs,
  use `compile_sampler(..., seed=)` or `simulate(..., seed=)`. `MaestroBackend(seed=)`
  is rejected, since every worker would draw the same shots.
- `MPP`, correlated `E` / heralded noise, classically controlled gates and inverted
  measurement targets are rejected by `maestro.sinter.translate_stim_to_maestro`.

## Tests

```bash
uv pip install -e ".[test]"
pytest
```

## Dependencies

`numpy`, `deltakit>=0.8.0` (tested on 0.8.0, 0.9.0 and 0.10.2, with Python 3.12, Stim and
Sinter 1.16 and PyMatching 2.4) and `qoro-maestro[sinter]>=0.3.14,<0.4.0`. The only Deltakit API used is the public
`Circuit.as_stim_circuit()`. The `examples` extra adds `pymatching` and `ldpc` (for
BP-OSD), which `deltakit` already pulls in through `deltakit-decode` and `deltakit-explorer`.

## License

GPL-3.0, like Maestro. See [LICENSE](LICENSE).

## Layout

```
pyproject.toml
src/deltakit_maestro/
  maestro_backend.py    MaestroBackend, SimulationResult, Sinter glue
  noise.py              noisy Stim circuit ↔ maestro.NoiseModel and its Pauli twirl
examples/
  example_noise_modes.py
  example_stim_circuit.py
  example_coherent_noise.py
  example_deltakit_codes.py
  example_bond_dimension.py
  coherent_noise_d3.ipynb
  example_surface_code.py
tests/
```
