# deltakit-maestro

<!-- The documentation's home page (docs/index.md) shows the README from here to "end-docs". -->
<!-- start-docs -->

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
Pauli frames sample a Clifford circuit with Pauli noise as fast as Stim does; coherent
over-rotations, which no Clifford simulator can run, need the matrix product state.

## Install

Needs Python **3.10 or later**, within what Deltakit supports (3.10 to 3.15
across its current releases). Tested on 3.10 to 3.14.

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
# Import deltakit before pymatching: the other way round, Deltakit's circuit builders fail.
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
  - [Examples](https://qoroquantum.github.io/deltakit-maestro/examples/): a notebook with plots of coherent noise on the
    d=3 surface code, and scripts for the noise modes, a plain Stim circuit,
    coherent noise on a repetition code, a surface code sweep, every Deltakit
    code family, and the bond dimension, each shown with its output.
  - [API reference](https://qoroquantum.github.io/deltakit-maestro/api.html).
- [Maestro docs](https://qoroquantum.github.io/maestro/).
- [Changelog](https://github.com/QoroQuantum/deltakit-maestro/blob/main/CHANGELOG.md).
- [Contributing](https://github.com/QoroQuantum/deltakit-maestro/blob/main/CONTRIBUTING.md): running the tests and building the docs.

## License

GPL-3.0, like Maestro. See [LICENSE](https://github.com/QoroQuantum/deltakit-maestro/blob/main/LICENSE).
