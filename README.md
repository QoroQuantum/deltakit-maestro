# deltakit-maestro

[![PyPI](https://img.shields.io/pypi/v/deltakit-maestro)](https://pypi.org/project/deltakit-maestro/)
[![Python](https://img.shields.io/pypi/pyversions/deltakit-maestro)](https://pypi.org/project/deltakit-maestro/)
[![Tests](https://github.com/QoroQuantum/deltakit-maestro/actions/workflows/tests.yml/badge.svg)](https://github.com/QoroQuantum/deltakit-maestro/actions/workflows/tests.yml)
[![Docs](https://github.com/QoroQuantum/deltakit-maestro/actions/workflows/docs.yml/badge.svg)](https://qoroquantum.github.io/deltakit-maestro/)

<!-- The documentation's home page (docs/index.md) shows the README from here to "end-docs". -->
<!-- start-docs -->

Run **Riverlane Deltakit** QEC circuits on Qoro's **Maestro** simulator, including
noise that a Clifford simulator can't run: coherent over-rotations and `T1` decay.
The decoder gets the detector error model of the Pauli twirl of whatever is
simulated, so a run shows what the Pauli approximation misses. On the rotated d=3
surface code, coherent noise gives 17–40% more logical errors than its Pauli
twirl, and on repetition codes the gap grows with distance, to 45% at d=15 (see
[benchmarks](https://qoroquantum.github.io/deltakit-maestro/benchmarks/coherent.html)).

Pauli noise runs on Pauli frames, with the same logical error rates as Stim,
which samples it faster on x86 (see
[benchmarks](https://qoroquantum.github.io/deltakit-maestro/benchmarks.html)).
Coherent noise needs a matrix product state, which is practical for the rotated
d=3 surface code and for repetition codes up to 101 qubits, the largest
measured.

## When to use it

- To measure what the Pauli twirl misses: one run gives the real noise and the
  detector error model of its twirl, decoded alike.
- For coherent over-rotations, on the rotated d=3 surface code and on
  repetition codes up to 101 qubits.
- For `T1` decay, which isn't a Pauli channel either; the stabilizer simulator
  runs it shot by shot.
- For noise shaped like hardware: per-qubit and per-coupler rates, asymmetric
  readout, directed over-rotations and ZZ crosstalk.

For Pauli noise alone, Stim is faster on x86 and gives the same logical error
rates. See [when to use Maestro](https://qoroquantum.github.io/deltakit-maestro/guide/when_to_use.html).

## How it works

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
Pauli frames sample a Clifford circuit with Pauli noise with the same statistics as Stim; coherent
over-rotations, which no Clifford simulator can run, need the matrix product state.

## Install

```bash
pip install deltakit-maestro
pip install "deltakit-maestro[examples]"   # also what the examples use: pymatching, ldpc
```

Needs Python **3.10 or later**, within what Deltakit supports (3.10 to 3.15
across its current releases), on macOS or Linux. Tested on 3.10 to 3.14.

Verify:

```bash
python -c "from deltakit_maestro import MaestroBackend; print(MaestroBackend())"
```

To work on the package itself, install it from a clone with
`pip install -e ".[test,examples]"` (see
[Contributing](https://github.com/QoroQuantum/deltakit-maestro/blob/main/CONTRIBUTING.md)).

## Quick start

```python
# Import Deltakit before pymatching (see "Gotchas" in the guide).
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

The [guide](https://qoroquantum.github.io/deltakit-maestro/guide.html) covers each of these in depth:
[sampling and Sinter](https://qoroquantum.github.io/deltakit-maestro/guide/sampling.html), the
[noise modes](https://qoroquantum.github.io/deltakit-maestro/guide/noise.html), the
[decoder's detector error model](https://qoroquantum.github.io/deltakit-maestro/guide/decoding.html), and
[coherent noise](https://qoroquantum.github.io/deltakit-maestro/guide/coherent_noise.html) with the
[bond dimension](https://qoroquantum.github.io/deltakit-maestro/guide/bond_dimension.html) it needs.

<!-- end-docs -->

## Learn more

- [Documentation](https://qoroquantum.github.io/deltakit-maestro/):
  - [Guide](https://qoroquantum.github.io/deltakit-maestro/guide.html): sampling and Sinter, how each run is simulated,
    the noise modes and overrides, the decoder's detector error model, coherent
    noise and its calibration against SI1000, the MPS bond dimension,
    performance, and gotchas.
  - [Benchmarks](https://qoroquantum.github.io/deltakit-maestro/benchmarks.html): Maestro's
    stabilizer against Stim, for speed and logical error rates under three noise
    models, and its matrix product state against Stim and exact statevector
    simulation, under Pauli noise, coherent noise and `T1` decay.
  - [Examples](https://qoroquantum.github.io/deltakit-maestro/examples/): a notebook with plots of coherent noise on the
    d=3 surface code, and scripts for the noise modes, a plain Stim circuit,
    coherent noise on a repetition code, a surface code sweep, every Deltakit
    code family, and the bond dimension, each shown with its output.
  - [API reference](https://qoroquantum.github.io/deltakit-maestro/api.html).
- [PyPI](https://pypi.org/project/deltakit-maestro/).
- [Maestro docs](https://qoroquantum.github.io/maestro/).
- [Changelog](https://github.com/QoroQuantum/deltakit-maestro/blob/main/CHANGELOG.md).
- [Contributing](https://github.com/QoroQuantum/deltakit-maestro/blob/main/CONTRIBUTING.md): running the tests and building the docs.

## License

GPL-3.0, like Maestro. See [LICENSE](https://github.com/QoroQuantum/deltakit-maestro/blob/main/LICENSE).
