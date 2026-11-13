# Sampling and Sinter

`MaestroBackend` takes a Deltakit `Circuit` or a `stim.Circuit` and returns raw
measurements, detection events, or Sinter statistics. A Deltakit circuit is
converted with its `as_stim_circuit()` (see {func}`~deltakit_maestro.to_stim`),
so everything below works the same on a plain Stim circuit.

```python
from deltakit_maestro import MaestroBackend

backend = MaestroBackend()   # Stabilizer for Pauli runs, MPS (χ=32) for coherent ones
```

The [Simulation types](simulation_types.md) page says which of Maestro's
simulators runs each call, and [Noise](noise.md) says what noise it runs with.

## Measurements and detection events: `simulate`

```python
result = backend.simulate(noisy, shots=1000)
result.measurements       # (1000, n_meas) uint8, Stim record order
result.detection_events   # (1000, n_detectors) bool
result.observable_flips   # (1000, n_observables) bool
result.metadata           # the backend, the shot count and the noise parameters used
```

`simulate` samples the measurement record and converts it to detection events
and observable flips with Stim's measurement-to-detection converter for the
circuit that ran.

## A compiled sampler: `compile_sampler`

`compile_sampler` returns a `maestro.sinter.MaestroCompiledSampler` for the
circuit, to sample from as often as you like:

```python
sampler = backend.compile_sampler(noisy, seed=1)
sampler.sample_measurements(1000)                    # measurements (bool)
dets, obs = sampler.sample_detection_events(1000)    # detection events, observable flips
stats = sampler.sample(1000)                         # sinter.AnonTaskStats, decoded
```

`decoder=` (default `'pymatching'`) is compiled against the task's detector
error model and used only by `.sample()`. `decoder='vacuous'` (or `None`) gives
undecoded statistics. To decode detection events yourself, build your decoder
from `sampler.task.detector_error_model`:

```python
import numpy as np
import pymatching

matcher = pymatching.Matching.from_detector_error_model(sampler.task.detector_error_model)
failures = np.any(matcher.decode_batch(dets) != obs, axis=1)
print(f"logical error probability: {failures.mean():.4f}")
```

[The decoder's detector error model](decoding.md) explains what that model
contains.

## Sinter: `as_sinter_task` and `sinter_decoders`

```python
import sinter

stats = sinter.collect(
    num_workers=4,
    tasks=[backend.as_sinter_task(noisy, json_metadata={'p': 0.01})],
    custom_decoders=backend.sinter_decoders(decoder='pymatching'),
    max_shots=10_000,
)
```

`as_sinter_task` returns a `sinter.Task` holding the circuit Maestro runs, the
matching detector error model, and the decoder name `'maestro'`
({data}`~deltakit_maestro.SINTER_DECODER`). Its `json_metadata` is yours plus a
`'noise'` entry with the noise layers, so each worker can rebuild them.
`sinter_decoders()` maps `'maestro'` to a `sinter.Sampler` that builds each
task's sampler as `compile_sampler` does, decoding with the `decoder=` you give
it.

Under `sinter.collect` decoding takes most of the time: see
[Performance](performance.md).

## Seeds

`simulate(..., seed=)` and `compile_sampler(..., seed=)` make a run
reproducible. Seeded `sinter.collect` is not supported by `maestro.sinter`, and
`MaestroBackend(seed=)` is rejected, since every worker would draw the same
shots. For reproducible runs, use `simulate` or `compile_sampler`.

## Shot order

Shots come back in random order, so any slice of them is a fair sample. Every
shot is a fresh noise realisation.
