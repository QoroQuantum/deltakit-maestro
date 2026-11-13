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
the coherent detection-event rate is 0.294 at χ=8, 0.272 at χ=16, and 0.263 at
χ=32 and 64, against 0.236 for its Pauli twirl. At χ=8 truncation adds about as
much as the coherent effect itself:

```{figure} ../_generated/bond_dimension_check.png
:alt: Two plots against bond dimension χ. Left, the noiseless check: 98% of shots have a detection event at χ=4 and none from χ=8. Right, the coherent detection-event rate falls from 0.31 at χ=4 to 0.26 at χ=32 and stays there at χ=64, above the Pauli twirl's 0.236.

Both checks on the rotated d=3 code, SI1000(0.01), 3 rounds. From the
[coherent noise notebook](../examples/coherent_noise_d3.ipynb).
```

[example_bond_dimension.py](../examples/bond_dimension.md) runs both checks on
a rotated and an unrotated code.

## Which codes are practical

**Only the rotated d=3 code is practical.** Checked with the noiseless test
above (3 rounds, SI1000(0.01) circuits):

| Code | Qubits | Smallest exact χ | Cost |
|---|---|---|---|
| Rotated planar d=3 | 17 | 8 | ~1 ms/shot |
| Unrotated planar d=3 | 25 | > 64 | ~0.9 s/shot at χ=64, still 75% of shots wrong |
| Unrotated toric d=3 | 36 | > 32 | ~1 s/shot at χ=32, every shot wrong |
| Rotated planar d=5 | 49 | > 32 | ~1.5 s/shot at χ=32, every shot wrong |

These noiseless runs have no noise to spread over cores, so they take as long on
one. Renumbering the qubits row by row from their coordinates did not help; it
made the rotated d=3 code need χ=64.
