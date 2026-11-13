# Every Deltakit code family

Every CSS memory circuit Deltakit builds passes through `MaestroBackend`
unchanged. This guide runs five topological codes (decoded with PyMatching) and
the `[[72,12,6]]` bivariate bicycle qLDPC code (decoded with BP-OSD) under
`SI1000Noise(p=0.003)` and 3 syndrome extraction rounds.

:::{admonition} At a glance
:class: note

- **Guide:** [The decoder's detector error model](../guide/decoding.md#codes-whose-errors-arent-graphlike)
- **Key APIs:** `MaestroBackend`, `compile_sampler()`, `to_stim()`
- **Decoders used:** `pymatching.Matching` (graphlike) and `ldpc.BpOsdDecoder` (qLDPC)
- **Run locally:** `python examples/example_deltakit_codes.py` (~20 s)
:::

## Setup: code families and memory circuit builder

The script defines five topological codes (`RepetitionCode`, `RotatedPlanarCode`
at `d=3` and `d=5`, `UnrotatedPlanarCode`, `UnrotatedToricCode`) alongside a
`6×6` `BivariateBicycleCode` (`144` physical qubits, `12` logical qubits), and
compiles each into a 3-round `SI1000Noise(p=0.003)` Stim circuit.

```{literalinclude} ../../examples/example_deltakit_codes.py
:language: python
:start-at: CODES = {
:end-before: =============================================================================
```

```{literalinclude} ../../examples/example_deltakit_codes.py
:language: python
:start-at: def memory_circuit(
:end-before: def lep(
```

## Step 1: Matching-decoded topological codes

For repetition, planar, and toric codes, `backend.compile_sampler()` decomposes
the detector error model into graphlike errors so `pymatching.Matching` can
decode batches directly from `sampler.task.detector_error_model`. Because
`SI1000Noise` is purely Pauli, Maestro runs all five on its Stabilizer with
Pauli frames at sub-microsecond per-shot sampling times.

```{literalinclude} ../../examples/example_deltakit_codes.py
:language: python
:start-at:     for name, code in CODES.items():
:end-before: -------------------------------------------------------------------------
:dedent: 4
```

**Output:**

```{literalinclude} ../_generated/example_deltakit_codes.txt
:language: text
:start-at:   code                  │
:end-before:   BB [[72,12,6]]
```

## Step 2: Bivariate bicycle qLDPC code with BP-OSD

A bivariate bicycle code's errors trigger more than two detectors at once, so
they are not graphlike and `decompose_errors=True` cannot split them for
matching. `MaestroBackend` handles this automatically by falling back to the
un-decomposed DEM (`decompose_errors=False`), and passing `decoder=None` lets
you sample detection events for a general linear decoder such as BP-OSD.

Here `BpOsd` parses the DEM into sparse parity-check (`checks`) and observable
(`observables`) matrices over the error priors:

```{literalinclude} ../../examples/example_deltakit_codes.py
:language: python
:start-at: class BpOsd:
:end-before: def _matrix(
```

We sample `1,000` shots on `144` qubits (`216` detectors) and count a logical
failure whenever any of the `12` logical observables is mispredicted:

```{literalinclude} ../../examples/example_deltakit_codes.py
:language: python
:start-at:     circuit = memory_circuit(BB_CODE)
:end-before:     print(f"\n{'=' * 94}")
:dedent: 4
```

**Output:**

```{literalinclude} ../_generated/example_deltakit_codes.txt
:language: text
:start-at:   BB [[72,12,6]]
:end-before: ===
```

## Key takeaways

- `MaestroBackend` requires no code-specific configuration across repetition,
  surface, toric, or qLDPC circuits.
- When a circuit's DEM is not graphlike, `compile_sampler(..., decoder=None)`
  still produces a valid DEM for BP-OSD or other hypergraph decoders.
- **Next:** [Coherent noise on a repetition code](coherent_noise.md) moves from
  Pauli noise to non-Clifford coherent over-rotations on Maestro's MPS engine.

---

## Full script and complete output

:::{dropdown} View full script (`examples/example_deltakit_codes.py`)
```{literalinclude} ../../examples/example_deltakit_codes.py
:language: python
:start-at: '"""'
```
:::

:::{dropdown} View complete output
```{literalinclude} ../_generated/example_deltakit_codes.txt
:language: text
```
:::
