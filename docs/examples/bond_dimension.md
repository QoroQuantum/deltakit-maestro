# Bond dimension

Coherent runs execute on Maestro's Matrix Product State (MPS) simulator with a
finite maximum bond dimension `χ` (default `32`). If `χ` is too small, MPS
truncation injects spurious bit flips that look like extra detection events—the
exact same signature as coherent interference. Always verify `χ` rather than
assuming the default is enough.

:::{admonition} At a glance
:class: note

- **Guide:** [Bond dimension](../guide/bond_dimension.md)
- **Key APIs:** `MaestroBackend(max_bond_dimension=..., simulation_type=...)`, `config_for()`, `twirled_circuit()`
- **Simulator used:** Maestro MatrixProductState (`χ` from `4` to `64`)
- **Run locally:** `python examples/example_bond_dimension.py` (~50 s)
:::

## Step 1: Configuring `χ` and forcing MPS

`max_bond_dimension` sets `χ` for MPS runs (`coherent` and `full` select MPS
automatically). To force Pauli or noiseless runs onto MPS—which is needed for
the noiseless truncation check in Step 2—also pass `simulation_type=maestro.SimulationType.MatrixProductState`.

```{literalinclude} ../../examples/example_bond_dimension.py
:language: python
:start-at:     backend = MaestroBackend(max_bond_dimension=64)
:end-before:     print("  Coherent runs pick
:dedent: 4
```

**Output:**

```{literalinclude} ../_generated/example_bond_dimension.txt
:language: text
:start-at:   MaestroBackend(max_bond_dimension=64)
:end-before:   Coherent runs pick
```

## Step 2: The noiseless truncation check

With `noise_type="none"`, every detector in a valid CSS memory circuit must be
`0` on every shot. Any shot with at least one fired detector on a noiseless MPS
run is pure bond-dimension truncation error. Testing across `χ` in
`[4, 8, 16, 32]` takes only `50` shots and needs no reference simulator:

```{literalinclude} ../../examples/example_bond_dimension.py
:language: python
:start-at:     for name, circuit in codes.items():
:end-before:     print("  The unrotated code
:dedent: 4
```

**Output:**

```{literalinclude} ../_generated/example_bond_dimension.txt
:language: text
:start-at:   code                  │ qubits
:end-before:   The unrotated code
```

The rotated `d=3` surface code (`17` qubits) is exact from `χ=8` onward,
whereas the unrotated `d=3` code (`25` qubits) still truncates almost every
shot at `χ=32` (~`0.36 s/shot`), telling you immediately that `χ=32` is not
sufficient for that qubit layout.

## Step 3: Convergence sweep under coherent noise

Passing the noiseless check is necessary, not sufficient: coherent rotations
create additional entanglement across the circuit. On the rotated `d=3` code,
we raise `χ` across `[8, 16, 32, 64]` with `400` shots each and track the
detection-event rate against the Stabilizer Pauli-twirl baseline:

```{literalinclude} ../../examples/example_bond_dimension.py
:language: python
:start-at:     twirl = MaestroBackend().twirled_circuit(
:end-before:     print(f"\n{'=' * 74}")
:dedent: 4
```

**Output:**

```{literalinclude} ../_generated/example_bond_dimension.txt
:language: text
:start-at:   Pauli twirl of the same noise
:end-before: ===
```

Notice the trap at `χ=8`: even though the noiseless circuit was exact at `χ=8`,
with coherent noise `χ=8` inflates the excess over the twirl to `+0.0595`,
more than double the converged excess (`+0.0227`) where `χ=32` and `χ=64`
agree within error bars.

## Key takeaways

- Always run the two-stage check before trusting coherent MPS results:
  1. **Noiseless check:** confirm `0%` detection events with `simulation_type=MPS`
     and `noise_type="none"`.
  2. **Convergence check:** double `χ` until the coherent detection-event rate
     stabilizes within statistical uncertainty.
- **Next:** Explore the [Coherent noise on a distance-3 surface code](coherent_noise_d3.ipynb)
  notebook for full plots of the `χ` check, logical error sweep, and
  per-detector excess rates.

---

## Full script and complete output

:::{dropdown} View full script (`examples/example_bond_dimension.py`)
```{literalinclude} ../../examples/example_bond_dimension.py
:language: python
:start-at: '"""'
```
:::

:::{dropdown} View complete output
```{literalinclude} ../_generated/example_bond_dimension.txt
:language: text
```
:::
