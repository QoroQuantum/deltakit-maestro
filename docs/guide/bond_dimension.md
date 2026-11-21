# Bond dimension

Coherent runs need a matrix product state (MPS), with bond dimension χ set by
`MaestroBackend(max_bond_dimension=)` (default 32). Too small a χ truncates the
state, which shows up as extra detection events, the same direction as the
coherent effect being studied. So χ has to be checked, not assumed.

## Checking χ

1. **Noiseless check.** Run with `simulation_type=MatrixProductState` and
   `noise_type='none'`. Every detector must stay silent, so any detection event
   is truncation error. It needs no reference and a few dozen shots. It relies
   on the [pinned type](simulation_types.md#the-type-is-pinned): with
   `fixed_backend=False`, Maestro would sample this Clifford circuit on Pauli
   frames and the check would always pass.
2. **Coherent convergence.** Coherent noise needs more χ than the noiseless
   check. Double χ until the result is unchanged within its error bars.

```python
import maestro
from deltakit_maestro import MaestroBackend

MPS = maestro.SimulationType.MatrixProductState

for chi in (4, 8, 16, 32):
    mps = MaestroBackend(simulation_type=MPS, max_bond_dimension=chi)
    dets = mps.simulate(noisy, 200, noise_type='none', seed=1).detection_events
    print(chi, dets.any(axis=1).mean())   # shots with a detection event: 0 once χ is enough

for chi in (8, 16, 32, 64):
    backend = MaestroBackend(max_bond_dimension=chi)
    dets = backend.simulate(noisy, 400, noise_type='coherent', seed=1).detection_events
    print(chi, dets.mean())               # raise χ until this stops changing
```

On the rotated d=3 code at p=0.01, the noiseless circuit is exact from χ=8, but
the coherent detection-event rate is 0.298 at χ=8, 0.273 at χ=16, and 0.259 and
0.260 at χ=32 and 64, against 0.236 for its Pauli twirl. At χ=8 truncation adds
more than the coherent effect itself:

```{figure} ../_generated/bond_dimension_check.png
:alt: Two plots against bond dimension χ. Left, the noiseless check: 96% of shots have a detection event at χ=4 and none from χ=8. Right, the coherent detection-event rate falls from 0.31 at χ=4 to 0.26 at χ=32 and stays there at χ=64, above the Pauli twirl's 0.236.

Both checks on the rotated d=3 code, SI1000(0.01), 3 rounds. From the
[coherent noise notebook](../examples/coherent_noise_d3.ipynb).
```

Other noise can need more. With `T1` decay as well (`noise_type='full'`,
`t1=0.005`, on SI1000(0.005)), the same code needs χ=48: at the default χ=32 it
gives 9% too many detection events. So check χ with the noise you will run. The
[benchmarks](../benchmarks/mps.md#bond-dimension-converging-to-the-exact-result)
check both cases against an exact statevector simulation.

[example_bond_dimension.py](../examples/bond_dimension.md) runs both checks on
the rotated d=3 code.

## Which codes are checked

These docs check the MPS on two families: the rotated d=3 surface code and
repetition codes. On the rotated d=3 code (17 qubits), the noiseless circuit is
exact from χ=8, at about 1 ms a shot, and coherent noise needs χ=32 (above).

A repetition code is a chain, so its MPS stays small. With coherent noise, χ=32
agrees with χ=64 at every size up to 101 qubits (d=51), and with an exact
statevector up to 25 qubits; the 101-qubit code takes 0.91 s a shot on 30 threads
(see [Benchmarks](../benchmarks/mps.md#beyond-a-statevector)).
