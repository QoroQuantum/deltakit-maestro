# Custom Maestro noise model

`MaestroBackend` extracts uniform gate and readout rates from a circuit so you
don't have to construct a `maestro.NoiseModel` for standard benchmarks. When you
want to model per-qubit calibration tables—such as a degraded "hot" qubit, a
noisy two-qubit coupler, asymmetric readout errors, directed coherent rotations,
or ZZ crosstalk—you can build a custom `maestro.NoiseModel` and pass it
directly to `maestro.sinter.MaestroCompiledSampler` or
`maestro.sinter.MaestroSinterSampler`.

:::{admonition} At a glance
:class: note

- **Guides:** [Noise](../guide/noise.md#working-with-the-noise-directly) · [Sampling and Sinter](../guide/sampling.md)
- **Key APIs:** `maestro.NoiseModel`, `MaestroCompiledSampler`, `MaestroSinterSampler`, `noise_params_from_stim()`, `strip_gate_noise()`, `build_noise_model()`
- **Simulators used:** Maestro Stabilizer (heterogeneous Pauli + `T1`) and Maestro MatrixProductState (`χ=32`, coherent rotation + ZZ crosstalk)
- **Run locally:** `python examples/example_custom_noise_model.py` (~6 s)
:::

## Setup: stripping uniform gate and readout noise

To avoid applying gate or readout noise twice, we first extract the baseline
`SI1000Noise(p=0.005)` rates with `noise_params_from_stim()` and strip the
after-gate depolarizing and `M(p)` measurement flips with
`strip_gate_noise(noisy, readout=True)`. SI1000's idle and reset noise remain in
`stripped`, while the custom `maestro.NoiseModel` takes over all gate and
readout channels.

```{literalinclude} ../../examples/example_custom_noise_model.py
:language: python
:start-at: def build_surface_code_base(
:end-before: def build_hot_qubit_model(
```

## Step 1: Customizing per-qubit and per-coupler channels

Starting from the uniform baseline model returned by
`build_noise_model(stripped, "pauli", **rates)`, you can call any per-qubit or
per-coupler setter on `maestro.NoiseModel`:

- `set_1q_gate_depolarizing(qubit, p)` and `set_2q_depolarizing(q1, q2, p)` for
  inhomogeneous gate error rates.
- `set_t1(qubit, gamma)` for per-qubit amplitude damping / reset relaxation.
- `set_readout_error(qubit, p_meas1_prep0, p_meas0_prep1)` for asymmetric
  readout assignment errors.
- `set_coherent_rotation(qubit, rx, ry, rz)` and `set_crosstalk(q1, q2, strength)`
  for non-Clifford unitary errors simulated on MPS.

```{literalinclude} ../../examples/example_custom_noise_model.py
:language: python
:start-at: def build_hot_qubit_model(
:end-before: def decode_logical_error_rate(
```

**Output:**

```{literalinclude} ../_generated/example_custom_noise_model.txt
:language: text
:start-at:   Base SI1000 rates:
:end-before: ───
```

## Step 2: Direct sampling with `MaestroCompiledSampler`

`MaestroCompiledSampler` accepts a `sinter.Task` (carrying the stripped circuit
and the uniform baseline circuit's Detector Error Model), your custom
`noise_model`, and a `maestro.SimulatorConfig` (built conveniently via
`MaestroBackend.config_for()`).

Here we compare three configurations decoded against the same baseline DEM:
1. Uniform SI1000 baseline (`Stabilizer`).
2. A `10×` hot qubit (`q0`), hot coupler `(0, 2)`, `T1`, and asymmetric readout
   on ancilla `q2` (`Stabilizer`).
3. Adding a systematic coherent rotation on `q0` and ZZ crosstalk on `(0, 2)`
   (`MatrixProductState`, `χ=32`).

```{literalinclude} ../../examples/example_custom_noise_model.py
:language: python
:start-at:     dem = noisy.detector_error_model(decompose_errors=True)
:end-before: def step_3_sinter_sweep(
:dedent: 4
```

**Output:**

```{literalinclude} ../_generated/example_custom_noise_model.txt
:language: text
:start-at:   model configuration
:end-before: ────────────────────────────────────────────────────────────────────────────
```

Both the mean detection-event rate and the decoded logical error probability
increase as per-qubit degradation and non-Clifford coherent/crosstalk errors
are added.

## Step 3: Multi-worker sweeps with `MaestroSinterSampler`

Because `maestro.NoiseModel` is picklable across worker processes, you can wrap
each custom noise model in `MaestroSinterSampler(noise_model=..., config=..., decoder="pymatching")`
and pass the mapping to `sinter.collect(custom_decoders=...)` to sweep
calibration parameters across multiple CPU workers:

```{literalinclude} ../../examples/example_custom_noise_model.py
:language: python
:start-at:     tasks = []
:end-before:     print(f"  {'hot_scale':>9}
:dedent: 4
```

**Output:**

```{literalinclude} ../_generated/example_custom_noise_model.txt
:language: text
:start-at:   hot_scale │  shots
:end-before: ===
```

## Key takeaways

- Seed a custom `maestro.NoiseModel` from `build_noise_model(stripped, "pauli", **rates)`
  after calling `strip_gate_noise(noisy, readout=True)` so uniform qubits keep
  their baseline rates while degraded qubits/couplers are overridden cleanly.
- Use `MaestroCompiledSampler` for seeded direct sampling and
  `MaestroSinterSampler` for multi-worker `sinter.collect` sweeps.
- **Next:** [A surface code sweep](surface_code.md) scales up to a 4-worker
  surface code benchmark and coherent vs. Pauli twirl comparison.

---

## Full script and complete output

:::{dropdown} View full script (`examples/example_custom_noise_model.py`)
```{literalinclude} ../../examples/example_custom_noise_model.py
:language: python
:start-at: '"""'
```
:::

:::{dropdown} View complete output
```{literalinclude} ../_generated/example_custom_noise_model.txt
:language: text
```
:::

