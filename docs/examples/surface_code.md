# A surface code sweep

A distance-3 rotated surface code (`17` qubits, `3` syndrome extraction rounds)
built with Deltakit under `SI1000Noise`, benchmarked across three physical
noise strengths with direct sampling, multi-worker `sinter.collect`, and
coherent MPS simulation against its Pauli twirl.

:::{admonition} At a glance
:class: note

- **Guides:** [Sampling and Sinter](../guide/sampling.md) · [Coherent noise](../guide/coherent_noise.md)
- **Key APIs:** `MaestroBackend`, `to_stim()`, `compile_sampler()`, `as_sinter_task()`, `sinter_decoders()`, `twirled_circuit()`
- **Simulators used:** Maestro Stabilizer (Pauli frames) and Maestro MatrixProductState (`χ=32`)
- **Run locally:** `python examples/example_surface_code.py` (~12 s)
:::

## Setup: Deltakit surface code with SI1000 noise

We construct a `RotatedPlanarCode(3, 3)` Z-basis memory circuit and attach
superconducting `SI1000Noise(p)` using Deltakit's `QPU` compiler. `MaestroBackend`
accepts the resulting Deltakit `Circuit` directly (converting it internally via
`to_stim()`).

```{literalinclude} ../../examples/example_surface_code.py
:language: python
:start-at: def build_noisy_surface_code(
:end-before: def decode_with_pymatching(
```

## Phase 1: Direct sampling checked against Stim

Because `SI1000Noise` contains only Pauli channels, `MaestroBackend` routes the
run to Maestro's Stabilizer simulator and samples it on Pauli frames. For each
`p` in `[0.002, 0.005, 0.01]`, we draw `20,000` shots with `compile_sampler()`,
decode with PyMatching against `sampler.task.detector_error_model`, and compare
against Stim's own sampler on the exact same circuit.

```{literalinclude} ../../examples/example_surface_code.py
:language: python
:start-at:     for p, noisy_circuit in circuits.items():
:end-before: def phase_2_sinter_sweep(
:dedent: 4
```

**Output:**

```{literalinclude} ../_generated/example_surface_code.txt
:language: text
:start-at:        p │         Maestro
:end-before: ──────────────────────────────────────────────────────────────────────
```

Maestro and Stim agree within statistical error at every physical noise rate.

## Phase 2: Parallel sweep with `sinter.collect`

To scale across CPU cores, `as_sinter_task()` packages each Deltakit circuit
with its noise metadata and `sinter_decoders(decoder="pymatching")` dispatches
sampling and decoding across `4` worker processes.

```{literalinclude} ../../examples/example_surface_code.py
:language: python
:start-at:     tasks = [
:end-before:     print(f"  {'p':>6}
:dedent: 4
```

**Output:**

```{literalinclude} ../_generated/example_surface_code.txt
:language: text
:start-at:        p │  shots
:end-before: ──────────────────────────────────────────────────────────────────────
```

## Phase 3: Coherent over-rotations (MPS) vs. their Pauli twirl

Passing `noise_type="coherent"` replaces gate depolarizing noise with unitary
over-rotations while keeping SI1000's idle, reset, and measurement noise intact.
Maestro automatically switches to its Matrix Product State (`χ=32`) simulator.
To isolate the effect of coherence, we compare against `backend.twirled_circuit()`
on Maestro's Stabilizer and decode both with the twirl's DEM.

```{literalinclude} ../../examples/example_surface_code.py
:language: python
:start-at: def phase_3_coherent_vs_twirl(
:end-before: =============================================================================
```

**Output:**

```{literalinclude} ../_generated/example_surface_code.txt
:language: text
:start-at:        p │ Maestro coherent
:end-before: ===
```

At every noise strength, coherent over-rotations yield a higher logical error
probability than their matched Pauli twirl.

## Key takeaways

- Deltakit `Circuit` objects pass directly into `compile_sampler()` and
  `as_sinter_task()` with no manual translation step.
- Always compare `noise_type="coherent"` against `twirled_circuit(..., noise_type="coherent")`
  rather than the raw SI1000 circuit, because the default coherent strength
  calibration differs from SI1000's 1q/2q gate ratio.
- **Next:** [Every Deltakit code family](deltakit_codes.md) runs the same
  pipeline across five code families, including a non-graphlike qLDPC code.

---

## Full script and complete output

:::{dropdown} View full script (`examples/example_surface_code.py`)
```{literalinclude} ../../examples/example_surface_code.py
:language: python
:start-at: '"""'
```
:::

:::{dropdown} View complete output
```{literalinclude} ../_generated/example_surface_code.txt
:language: text
```
:::
