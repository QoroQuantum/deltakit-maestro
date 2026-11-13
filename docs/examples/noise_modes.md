# Noise modes

Rather than requiring you to construct a `maestro.NoiseModel` by hand,
`MaestroBackend` inspects the noise already embedded in a Stim or Deltakit
circuit, separates gate noise from idle/reset/readout noise when needed, and
automatically selects Maestro's Stabilizer or Matrix Product State simulator.

:::{admonition} At a glance
:class: note

- **Guides:** [Noise](../guide/noise.md) · [Simulation types](../guide/simulation_types.md)
- **Key APIs:** `MaestroBackend`, `noise_params_from_stim()`, `strip_gate_noise()`, `config_for()`, `as_sinter_task()`
- **Run locally:** `python examples/example_noise_modes.py` (~2 s)
:::

## Setup: two noisy circuits

The script compares a Deltakit-compiled `RotatedPlanarCode(3, 3)` circuit under
`SI1000Noise(p=0.01)` against a Stim-generated `surface_code:rotated_memory_z`
circuit with explicit gate, idle, reset, and measurement error rates.

```{literalinclude} ../../examples/example_noise_modes.py
:language: python
:start-at: def si1000_circuit(
:end-before: def noise_summary(
```

## Step 1: Separating gate noise from circuit noise

When overriding gate rates or switching to coherent noise, `MaestroBackend`
calls `noise_params_from_stim()` to read the circuit's gate and readout rates,
and `strip_gate_noise()` to remove after-gate depolarizing channels so Maestro's
`NoiseModel` can apply the replacement without double-counting. Idle, reset,
and readout channels remain inside the circuit.

```{literalinclude} ../../examples/example_noise_modes.py
:language: python
:start-at: def run_section_1_noise_extraction(
:end-before:     print("  Stripped keeps
```

**Output:**

```{literalinclude} ../_generated/example_noise_modes.txt
:language: text
:start-at:   Deltakit SI1000(p=0.01)
:end-before:   Stripped keeps
```

Notice why `DEPOLARIZE1(0.02)×36` stays in the Deltakit circuit and
`DEPOLARIZE1(0.02)×27` stays in the Stim circuit: Deltakit merges idle noise with
gate noise on a per-qubit basis, while Stim's `before_round_data_depolarization`
follows a `CX` rather than a single-qubit gate, so both are preserved as
non-gate noise.

## Step 2: Exploring the four `noise_type` modes and overrides

`MaestroBackend` supports four `noise_type` values (`'pauli'`, `'coherent'`,
`'full'`, and `'none'`) plus optional keyword overrides (`p_1q`, `p_2q`,
`readout_error`, `t1`, `coherent`). Inspecting `as_sinter_task()` and
`config_for()` reveals the exact circuit, `NoiseModel` layers, simulator, and
decoder DEM produced for each configuration:

```{literalinclude} ../../examples/example_noise_modes.py
:language: python
:start-at:     for scenario in scenarios:
:end-before:         label = (
:dedent: 4
```

**Output across all eight configurations:**

```{literalinclude} ../_generated/example_noise_modes.txt
:language: text
:start-after: baseline verification.
:end-before: ───
```

Key routing behavior visible in the output:
- **`pauli` (default):** runs the circuit as-is on `Maestro Stabilizer` (Pauli
  frames). Overriding `p_2q` or `readout_error` strips the matching instructions
  from the circuit and supplies them via `NoiseModel`. Adding `t1` keeps
  everything on `Maestro Stabilizer`, simulated shot by shot.
- **`coherent` / `full`:** automatically routes to `Maestro MatrixProductState`.
  `coherent` replaces gate depolarizing with unitary over-rotations; `full`
  keeps the circuit's gate depolarizing and adds the coherent rotation on top.
- **`none`:** strips all noise from the circuit for noiseless validation.

## Step 3: Round-trip fidelity verification

To verify that stripping gate noise from a Stim circuit and re-applying the
same rates through `MaestroBackend`'s `NoiseModel` produces identical physics,
the script compares mean detection-event rates across three paths: Stim's native
sampler, Maestro running the unmodified circuit, and Maestro running with
extracted `p_1q`/`p_2q` overrides.

```{literalinclude} ../../examples/example_noise_modes.py
:language: python
:start-at: def run_section_3_fidelity_verification(
:end-before: def run_section_4_bad_arguments(
```

**Output:**

```{literalinclude} ../_generated/example_noise_modes.txt
:language: text
:start-at:   circuit                    │
:end-before:   Mean detection-event rate
```

All three columns match within 3,000-shot sampling error.

## Step 4: Fast-fail validation of invalid arguments

Misspelled keywords or incompatible mode/parameter combinations (such as passing
`coherent=` under `noise_type="pauli"`, or `t1=` under `noise_type="none"`)
raise `TypeError` or `ValueError` immediately at task-construction time rather
than failing inside worker processes.

```{literalinclude} ../../examples/example_noise_modes.py
:language: python
:start-at:     invalid_configurations = [
:end-before: =============================================================================
:dedent: 4
```

**Output:**

```{literalinclude} ../_generated/example_noise_modes.txt
:language: text
:start-at: Typo in keyword argument
:end-before: ===
```

## Key takeaways

- You rarely need to build a `maestro.NoiseModel` manually: `MaestroBackend`
  extracts gate rates and preserves non-gate noise automatically.
- Switching between Pauli frame sampling, T1 decay, and coherent MPS simulation
  only requires changing `noise_type` or keyword arguments.
- **Next:** [Custom Maestro noise model](custom_noise_model.md) shows how to
  configure per-qubit calibration rates, asymmetric readout, and crosstalk on a
  custom `maestro.NoiseModel`.

---

## Full script and complete output

:::{dropdown} View full script (`examples/example_noise_modes.py`)
```{literalinclude} ../../examples/example_noise_modes.py
:language: python
:start-at: '"""'
```
:::

:::{dropdown} View complete output
```{literalinclude} ../_generated/example_noise_modes.txt
:language: text
```
:::
