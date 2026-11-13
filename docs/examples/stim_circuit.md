# A plain Stim circuit

`MaestroBackend` accepts standard `stim.Circuit` objects directly without
requiring Deltakit. This walkthrough uses a distance-5 repetition code memory
circuit built by Stim to cover the core sampling, seeding, decoding, and
`sinter.collect` workflows.

:::{admonition} At a glance
:class: note

- **Guide:** [Sampling and Sinter](../guide/sampling.md)
- **Key APIs:** `MaestroBackend`, `simulate()`, `compile_sampler()`, `as_sinter_task()`, `sinter_decoders()`
- **Simulator used:** Maestro Stabilizer (Pauli noise sampled on Pauli frames)
- **Run locally:** `python examples/example_stim_circuit.py` (~1 s)
:::

## Setup: building the test circuit

We generate a 5-round, distance-5 repetition code (`9` qubits, `25`
measurements, `24` detectors, `1` logical observable) with depolarizing,
measurement-flip, and reset-flip noise at strength `p`.

```{literalinclude} ../../examples/example_stim_circuit.py
:language: python
:start-at: def build_repetition_code(p: float)
:end-before: def compute_logical_error_rate(
```

## Step 1: Noiseless validation against Stim

Before introducing noise, passing `noise_type="none"` strips every noise
instruction from the circuit. On a noiseless stabilizer circuit, Maestro's
measurement record must match `circuit.without_noise()` bit-for-bit, with zero
detection events or observable flips.

```{literalinclude} ../../examples/example_stim_circuit.py
:language: python
:start-at: clean_result = backend.simulate(
:end-before: def step_2_simulate_api(
:dedent: 4
```

**Output:**

```{literalinclude} ../_generated/example_stim_circuit.txt
:language: text
:start-at:   measurement record identical to Stim's:
:end-before: ───
```

## Step 2: Inspecting `simulate()` results

`backend.simulate(circuit, shots=..., seed=...)` returns a `SimulationResult`
with three aligned NumPy arrays (`measurements`, `detection_events`, and
`observable_flips`) plus `metadata` recording the backend, shot count, and
effective noise configuration.

```{literalinclude} ../../examples/example_stim_circuit.py
:language: python
:start-at: result = backend.simulate(circuit, shots=SHOTS
:end-before: def step_3_deterministic_seeding(
:dedent: 4
```

**Output:**

```{literalinclude} ../_generated/example_stim_circuit.txt
:language: text
:start-at:   measurements      (4000
:end-before: ───
```

Maestro's mean detection-event rate agrees with Stim's independent detector
sampler within sampling variance.

## Step 3: Reproducible seeded sampling

Passing an integer `seed` to `simulate()` (or `compile_sampler()`) produces an
identical measurement record across runs, while changing the seed produces an
independent sample. Note that `sinter.collect` runs across multiple workers and
does not use a single global seed.

```{literalinclude} ../../examples/example_stim_circuit.py
:language: python
:start-at: run_a = backend.simulate(
:end-before: def step_4_manual_decoding(
:dedent: 4
```

**Output:**

```{literalinclude} ../_generated/example_stim_circuit.txt
:language: text
:start-at:   same seed, same record:
:end-before: ───
```

## Step 4: Compiling a sampler and decoding with PyMatching

When you want to draw multiple batches or access the matching Detector Error
Model (DEM), use `backend.compile_sampler()`. Its `sampler.task.detector_error_model`
matches the exact noise model being simulated, so you can pass it straight to
`pymatching.Matching.from_detector_error_model()`.

```{literalinclude} ../../examples/example_stim_circuit.py
:language: python
:start-at: sampler = backend.compile_sampler(
:end-before: def step_5_sinter_parameter_sweep(
:dedent: 4
```

**Output:**

```{literalinclude} ../_generated/example_stim_circuit.txt
:language: text
:start-at:   Maestro  logical error rate
:end-before:   The DEM is the sampler task's own
```

## Step 5: Parallel parameter sweeps with `sinter.collect`

For sweeping across physical error rates `p`, `backend.as_sinter_task()` packages
each circuit and its noise metadata into a `sinter.Task`, and
`backend.sinter_decoders()` registers Maestro's sampler with PyMatching so
`sinter.collect()` can distribute shots across worker processes.

```{literalinclude} ../../examples/example_stim_circuit.py
:language: python
:start-at: tasks = [
:end-before:     print(f"  {'p':>6}
:dedent: 4
```

**Output:**

```{literalinclude} ../_generated/example_stim_circuit.txt
:language: text
:start-at:        p │  shots
:end-before: ===
```

As expected for a distance-5 repetition code, the logical error rate (LER) drops
sharply as physical noise decreases from `0.06` down to `0.01`.

## Key takeaways

- `MaestroBackend` works identically on raw `stim.Circuit` objects and
  Deltakit-compiled circuits.
- Use `simulate()` for one-off NumPy array access, `compile_sampler()` when you
  need the DEM or repeated sampling, and `as_sinter_task()` + `sinter_decoders()`
  for multi-worker sweeps.
- **Next:** [Noise modes](noise_modes.md) shows how `MaestroBackend` extracts,
  overrides, and routes circuit noise between Stabilizer and MPS.

---

## Full script and complete output

:::{dropdown} View full script (`examples/example_stim_circuit.py`)
```{literalinclude} ../../examples/example_stim_circuit.py
:language: python
:start-at: '"""'
```
:::

:::{dropdown} View complete output
```{literalinclude} ../_generated/example_stim_circuit.txt
:language: text
```
:::
