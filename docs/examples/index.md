# Examples

Worked walkthroughs and a notebook backed by the runnable scripts in
[examples/](https://github.com/QoroQuantum/deltakit-maestro/tree/main/examples).
Each guide breaks down a live script step by step alongside its build-time
output, so every number and snippet matches the current code.

:::{note} Running the examples locally
Install the `examples` extra from the repository root and run any script directly:

```bash
pip install -e ".[examples]"
python examples/example_stim_circuit.py
```

The notebook (`coherent_noise_d3.ipynb`) also requires `matplotlib` and Jupyter.
Timings shown below are from a 12-core laptop; Stim's own sampler appears in a
few guides only as an independent reference. The test suite also runs the
Stim circuit, noise modes, and coherent noise scripts.
:::

## Learning path

Follow the three tracks below in order if you are new to `deltakit-maestro`,
or jump straight to the topic you need.

### 1. Fundamentals

Start here to learn the core `MaestroBackend` sampling API, how circuit noise
is parsed and routed between Maestro's Stabilizer and Matrix Product State
simulators, and how to attach a custom `maestro.NoiseModel`.

::::{grid} 1 1 2 3
:gutter: 3

:::{grid-item-card} 1. A plain Stim circuit
:link: stim_circuit
:link-type: doc

**Goal:** Sample, seed, decode, and sweep a Stim circuit without Deltakit.

- `simulate()`, `compile_sampler()`, and `sinter.collect`
- Bit-for-bit noiseless check against Stim and manual PyMatching decoding

~1 s · `examples/example_stim_circuit.py`
:::

:::{grid-item-card} 2. Noise modes
:link: noise_modes
:link-type: doc

**Goal:** See how `MaestroBackend` splits gate noise from circuit noise.

- `noise_params_from_stim()` and `strip_gate_noise()`
- All four `noise_type` modes (`'pauli'`, `'coherent'`, `'full'`, `'none'`) and overrides

~2 s · `examples/example_noise_modes.py`
:::

:::{grid-item-card} 3. Custom Maestro noise model
:link: custom_noise_model
:link-type: doc

**Goal:** Configure per-qubit calibration, asymmetric readout, and crosstalk.

- Seed a `maestro.NoiseModel` from `build_noise_model()` and override hot qubits/couplers
- Direct sampling with `MaestroCompiledSampler` and Sinter sweeps with `MaestroSinterSampler`

~6 s · `examples/example_custom_noise_model.py`
:::

::::

### 2. Scaling & Code Families

Move from single circuits to multi-worker Sinter parameter sweeps and across
Deltakit's topological and qLDPC code families.

::::{grid} 1 1 2 2
:gutter: 3

:::{grid-item-card} 4. A surface code sweep
:link: surface_code
:link-type: doc

**Goal:** Benchmark a d=3 rotated surface code under SI1000 and coherent noise.

- Deltakit `RotatedPlanarCode` + `SI1000Noise`
- 4-worker `sinter.collect` sweep and coherent vs. Pauli twirl comparison

~12 s · `examples/example_surface_code.py`
:::

:::{grid-item-card} 5. Every Deltakit code family
:link: deltakit_codes
:link-type: doc

**Goal:** Run repetition, planar, toric, and bivariate bicycle codes unchanged.

- Graphlike DEM decoding with PyMatching
- Non-graphlike `[[72,12,6]]` qLDPC decoding with BP-OSD

~20 s · `examples/example_deltakit_codes.py`
:::

::::

### 3. Coherent Noise & MPS Precision

Use Maestro's Matrix Product State (MPS) engine to simulate non-Clifford
coherent over-rotations and verify convergence with bond dimension χ.

::::{grid} 1 1 2 2
:gutter: 3

:::{grid-item-card} 6. Coherent noise on a repetition code
:link: coherent_noise
:link-type: doc

**Goal:** Measure the coherence penalty over a matched Pauli twirl.

- `noise_type="coherent"` on MPS vs. `twirled_circuit()` on Stabilizer
- Logical error ratio and detection-event ratio decoded with the twirl's DEM

~3 s · `examples/example_coherent_noise.py`
:::

:::{grid-item-card} 7. Bond dimension
:link: bond_dimension
:link-type: doc

**Goal:** Choose and verify the MPS bond dimension χ for coherent runs.

- Noiseless truncation check (`simulation_type=MPS`, `noise_type="none"`)
- Convergence sweep showing how under-resolved χ inflates coherent rates

~50 s · `examples/example_bond_dimension.py`
:::

::::

### Visual Notebook

::::{card} 8. Coherent noise on a distance-3 surface code
:link: coherent_noise_d3
:link-type: doc

An interactive Jupyter notebook with publication-ready figures comparing coherent
over-rotations (`χ=32`) against their Pauli twirl and SI1000 across noise
strengths `p`, plus per-detector rate maps and event-count distributions.

```{figure} ../_generated/coherent_vs_twirl.png
:alt: Two plots against noise strength p. Left, logical error probability: coherent noise is highest at every p, then its Pauli twirl, then SI1000. Right, the ratio of coherent noise to its twirl, between 1.1 and 1.3.

Coherent noise on the d=3 surface code against its Pauli twirl and SI1000.
```

~40 s · `examples/coherent_noise_d3.ipynb`
::::

```{toctree}
:hidden:

stim_circuit
noise_modes
custom_noise_model
surface_code
deltakit_codes
coherent_noise
bond_dimension
coherent_noise_d3
```
