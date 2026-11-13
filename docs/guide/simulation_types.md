# Simulation types

Every run is simulated by Maestro. `MaestroBackend` picks Maestro's simulation
type for each run from the noise in it, unless you pick one yourself.

## How the type is picked

With the default `simulation_type=None`:

| Run | Maestro simulation type |
|---|---|
| `'pauli'` (rate overrides included) or `'none'` | `Stabilizer`, sampled on Pauli frames |
| any run with `t1=` but no coherent noise | `Stabilizer`, shot by shot (`T1` decay is not a Pauli channel) |
| `'coherent'` or `'full'` | `MatrixProductState` |
| any run, with `simulation_type=` set | that simulation type |

Pauli frames sample a Clifford circuit with Pauli noise as fast as Stim does
(see [Performance](performance.md)). Coherent over-rotations, which no Clifford
simulator can run, need the matrix product state (MPS), whose bond dimension has
to be checked: see [Bond dimension](bond_dimension.md).

`config_for` returns the `maestro.SimulatorConfig` a run uses, so its
`simulation_type` says which type that is:

```python
from deltakit_maestro import MaestroBackend

backend = MaestroBackend()
backend.config_for('pauli').simulation_type                 # SimulationType.Stabilizer
backend.config_for('pauli', t1=1e-3).simulation_type        # SimulationType.Stabilizer
backend.config_for('coherent').simulation_type              # SimulationType.MatrixProductState
backend.config_for('coherent', coherent=0).simulation_type  # SimulationType.Stabilizer
```

`config_for` doesn't see the circuit. For `'coherent'` and `'full'` the coherent
strength is the `coherent=` keyword, else `p_2q=`. Without either, the strength
is the circuit's two-qubit gate noise, which `config_for` can't know, so it
takes it to be nonzero and answers `MatrixProductState`. The sampler knows the
circuit and decides exactly.

## Picking the type yourself

Pass a `maestro.SimulationType` to run everything with it, Pauli runs included:

```python
import maestro

mps = MaestroBackend(
    simulation_type=maestro.SimulationType.MatrixProductState,
    max_bond_dimension=64,
)
```

That is how the [noiseless check](bond_dimension.md#checking-χ) tests the bond
dimension. The simulation type also changes how `T1` decay runs: `DensityMatrix`
and `MatrixProductOperator` apply amplitude damping, and every other type resets
the qubit to |0⟩ (see [The decoder's detector error model](decoding.md)).

## The type is pinned

The type that runs is pinned (`fixed_backend=True`). Unpinned, Maestro samples
any Clifford circuit on Pauli frames whatever the type, so an MPS run of a Pauli
circuit would never touch the MPS. Pass `fixed_backend=False` to allow that:

```python
MaestroBackend(simulation_type=maestro.SimulationType.MatrixProductState, fixed_backend=False)
```

A pinned `Stabilizer` still uses Pauli frames.

## Other simulator options

`MaestroBackend` takes any other
[`maestro.SimulatorConfig`](https://qoroquantum.github.io/maestro/api/configuration.html)
field as a keyword argument, such as:

- `simulator_type=maestro.SimulatorType.Gpu` to run on your GPU
  ([get GPU access](https://qoroquantum.github.io/maestro/getting-started/gpu-access.html));
- `max_simulators=` to cap the threads one sampler uses.

The exception is `seed`, which `simulate` and `compile_sampler` take instead
(see [Seeds](sampling.md#seeds)). The fields are checked when the backend is
created, so a misspelt one raises `TypeError` at once.
