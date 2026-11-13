# Coherent noise on a repetition code

Clifford simulators like Stim cannot run coherent gate over-rotations because
they are non-Clifford unitaries that preserve relative phases across rounds.
This walkthrough uses Maestro's Matrix Product State (MPS) simulator on a
distance-3 repetition code and measures the "coherence penalty" against the
exact Pauli twirl on Maestro's Stabilizer.

:::{admonition} At a glance
:class: note

- **Guides:** [Coherent noise](../guide/coherent_noise.md) · [Visual notebook](coherent_noise_d3.ipynb)
- **Key APIs:** `MaestroBackend`, `compile_sampler()`, `twirled_circuit()`
- **Simulators used:** Maestro MatrixProductState (`coherent`) vs. Maestro Stabilizer (`twirl`)
- **Run locally:** `python examples/example_coherent_noise.py` (~3 s)
:::

## Setup: gate-noise-only repetition code

We build a `d=3` repetition code memory circuit with `after_clifford_depolarization=p`
for `p` in `[0.01, 0.03]` and `rounds` in `[3, 9]`. Using gate depolarization
only ensures that `noise_type="coherent"` replaces all circuit noise with
isotropic coherent over-rotations.

```{literalinclude} ../../examples/example_coherent_noise.py
:language: python
:start-at: def repetition_code(
:end-before: def compute_logical_error_rate(
```

## Step 1: Simulate coherent over-rotations on MPS

Calling `backend.compile_sampler(circuit, noise_type="coherent", seed=SEED)`
strips the gate depolarization and configures Maestro's `MatrixProductState`
simulator to apply an isotropic over-rotation after every gate. Because MPS
runs take longer than Pauli frames, we draw `8,000` shots per point.

```{literalinclude} ../../examples/example_coherent_noise.py
:language: python
:start-at:             start_time = time.time()
:end-before: -----------------------------------------------------------------
:dedent: 12
```

## Step 2: Build and sample the matched Pauli twirl

To isolate coherence from noise strength, `backend.twirled_circuit(circuit, noise_type="coherent")`
constructs the exact Pauli-twirled circuit with the same average per-gate
infidelity. We extract the matching Detector Error Model from the coherent
task (`coherent_sampler.task.detector_error_model`, which itself describes the
twirl) and sample `200,000` shots of the twirl on Maestro's Stabilizer.

```{literalinclude} ../../examples/example_coherent_noise.py
:language: python
:start-at:             matcher = pymatching.Matching.from_detector_error_model(
:end-before: -----------------------------------------------------------------
:dedent: 12
```

## Step 3: Decode both and measure the coherence penalty

Both datasets are decoded with the same PyMatching matcher so any difference in
logical error probability (`LEP ratio`) or mean detection-event rate
(`det. ratio`) comes purely from coherent interference rather than calibration
or decoder differences.

```{literalinclude} ../../examples/example_coherent_noise.py
:language: python
:start-at:             coherent_lep, coherent_err = compute_logical_error_rate(
:end-before:             print(
:dedent: 12
```

**Output:**

```{literalinclude} ../_generated/example_coherent_noise.txt
:language: text
:start-at:       p rounds │
:end-before: ===
```

At both `p=0.01` and `p=0.03`, coherent over-rotations produce roughly `1.5×–2.0×`
more logical errors and `~1.5×` more detection events than their Pauli twirl.

## Key takeaways

- Coherent error amplitudes accumulate constructively between stabilizer
  measurements, causing more frequent detection events and higher logical error
  rates than the twirled depolarizing model predicts.
- The detection-event ratio (`det. ratio`) converges with far fewer shots than
  the logical error rate, making it a useful low-variance diagnostic.
- **Next:** [Bond dimension](bond_dimension.md) shows how to verify that the
  MPS bond dimension `χ` is large enough so truncation error does not masquerade
  as coherent noise.

---

## Full script and complete output

:::{dropdown} View full script (`examples/example_coherent_noise.py`)
```{literalinclude} ../../examples/example_coherent_noise.py
:language: python
:start-at: '"""'
```
:::

:::{dropdown} View complete output
```{literalinclude} ../_generated/example_coherent_noise.txt
:language: text
```
:::
