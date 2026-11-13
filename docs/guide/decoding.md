# The decoder's detector error model

Every task carries the detector error model (DEM) its decoder uses:
`sampler.task.detector_error_model` from `compile_sampler`, or
`as_sinter_task(...).detector_error_model`. It describes the noise Maestro
simulates, overrides included, so the decoder always knows the strength of the
noise it is decoding.

## The Pauli twirl of what is simulated

The DEM is built from `twirled_circuit`: the circuit Maestro runs plus the Pauli
twirl of every `maestro.NoiseModel` layer, placed after each gate as Maestro
injects it:

| Layer | Its twirl in the DEM |
|---|---|
| `p_1q`, `p_2q` depolarizing | the same `DEPOLARIZE1`, `DEPOLARIZE2` (exact) |
| coherent over-rotation | `DEPOLARIZE1(coherent)` (exact) |
| `T1` decay γ, on `DensityMatrix` and `MatrixProductOperator` (amplitude damping) | `PAULI_CHANNEL_1(γ/4, γ/4, (1-√(1-γ))²/4)` |
| `T1` decay γ, on every other type, the automatic choices included (reset to \|0⟩) | `PAULI_CHANNEL_1(γ/4, γ/4, γ/4)`, which dephases about twice as fast |
| `readout_error` | composed with each measurement's own flip |

For `'pauli'` without overrides the DEM is the input circuit's own. For
`'none'`, which simulates no noise, the decoder keeps the input circuit's DEM as
its prior.

## The twirl as a baseline

`twirled_circuit` returns that circuit. Sampling it, with the default `'pauli'`,
which runs a circuit's own noise as it is, gives the Pauli-twirled baseline:

```python
coherent = backend.compile_sampler(noisy, noise_type='coherent', seed=1)
twirl = backend.compile_sampler(backend.twirled_circuit(noisy, noise_type='coherent'), seed=1)
```

Both are decoded with the same DEM, so the gap between a `'coherent'` run and a
run of its twirled circuit is the effect of coherence alone. See [Coherent
noise](coherent_noise.md).

## Decoding with your own decoder

Build the decoder from the task's DEM:

```python
import pymatching

sampler = backend.compile_sampler(noisy)
matcher = pymatching.Matching.from_detector_error_model(sampler.task.detector_error_model)
```

Don't build it from another Stim conversion of the same Deltakit circuit.
Deltakit's `PyMatchingDecoder.construct_decoder_and_stim_circuit` orders gates
and detectors differently from `as_stim_circuit()`, so its decoder doesn't match
the detection events Maestro returns.

## Codes whose errors aren't graphlike

The DEM is decomposed into graphlike errors for matching decoders where it can
be. qLDPC codes such as Deltakit's `BivariateBicycleCode` have errors that
can't be, so their DEM is left whole. Decode those with a decoder such as
BP-OSD, as [example_deltakit_codes.py](../examples/deltakit_codes.md) does with
`ldpc` on the [[72,12,6]] bivariate bicycle code.
