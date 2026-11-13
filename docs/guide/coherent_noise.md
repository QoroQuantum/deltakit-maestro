# Coherent noise

Real gate errors are often coherent: small, systematic over-rotations whose
amplitudes can add up across gates before a measurement collapses them. No
Clifford simulator can run them, so decoder studies usually replace them by
their Pauli twirl, which has the same per-gate infidelity but no coherence.
`noise_type='coherent'` runs the over-rotations themselves, on Maestro's matrix
product state.

## What `'coherent'` simulates

Each gate's depolarizing is replaced by an isotropic coherent over-rotation of
ε = 2·arcsin√p about a body diagonal of the Bloch sphere, after every gate, on
every qubit it touches. The signs are drawn once per qubit per shot, so a
qubit's rotations add coherently between measurements. Idle, reset and readout
noise stay as they are. `'full'` keeps the circuit's gate noise too and adds the
over-rotation to it.

The strength p is the `coherent=` keyword, by default the circuit's two-qubit
gate rate `p_2q`.

## Comparing against the twirl

The comparison that isolates coherence is a coherent run against its own Pauli
twirl, decoded with the same detector error model:

```python
coherent = backend.simulate(noisy, shots=300, noise_type='coherent')
twirl = backend.simulate(backend.twirled_circuit(noisy, noise_type='coherent'), shots=100_000)
```

The twirl runs on Pauli frames, so it can take far more shots than the MPS run.
On the d=3 rotated surface code, coherent noise gives about 11–16% more
detection events than its twirl, and a higher logical error probability at
every strength tested:

```{figure} ../_generated/coherent_vs_twirl.png
:alt: Two plots against noise strength p from 0.003 to 0.01. Left, logical error probability on log axes: coherent noise is highest at every p, then its Pauli twirl, then SI1000. Right, coherent over twirl: the logical error ratio falls from 1.32 to 1.15 with wide error bars, and the detection-event ratio stays between 1.11 and 1.16.

The d=3 rotated surface code, 3 rounds: coherent noise (MPS, χ=32, 800 shots a
point) against its Pauli twirl and SI1000 (stabilizer, 200,000 shots each), all
decoded by PyMatching with the twirl's detector error model. From the
[coherent noise notebook](../examples/coherent_noise_d3.ipynb).
```

The excess is spread across the code. Most detectors fire more often under
coherent noise, the mid-circuit rounds most of all, and shots with no detection
event at all become rarer:

```{figure} ../_generated/coherent_per_detector.png
:alt: Two plots at p = 0.01. Left, each detector's rate under coherent noise against under the twirl: most points lie above the diagonal. Right, the distribution of detection events per shot: the coherent distribution is shifted to more events than the twirl's.

Per-detector rates and detection events per shot at p = 0.01. The coherent
histogram ends where its 800 shots run out, near 10⁻³.
```

The detection-event ratio is the sharper measure here: the logical error ratios
carry wide error bars from the few coherent shots. Too small a bond dimension
inflates the coherent effect, so check it first: see [Bond
dimension](bond_dimension.md).

## Calibration against SI1000

`'coherent'` keeps SI1000's idle, reset and readout noise and replaces only the
gate noise, so it is close to SI1000, but not equal. `maestro.NoiseModel` sets
one coherent strength per qubit, applied after every gate whatever its arity.
With the default `coherent = p_2q`, an SI1000(p) circuit gets an over-rotation
of infidelity p after each single-qubit gate (SI1000 has p/10 there) and on both
qubits of each two-qubit gate (about 2p in total, where SI1000 has p). That
over-counts gate noise.

Measured on the d=3, 3-round memory at p=0.01 (logical error probability,
PyMatching):

| Noise | LEP |
|---|---|
| SI1000 Pauli (stabilizer) | 0.1990 ± 0.0009 |
| Pauli twirl of `'coherent'` (stabilizer) | 0.2330 ± 0.0009 |
| `'coherent'` (MPS, 800 shots) | 0.270 ± 0.016 |

So `'coherent'` and `'pauli'` at the same p differ by about 17% in LEP from
strength alone, before any effect of coherence. To isolate coherence, compare
`'coherent'` against its own twirl, as above. A per-gate-type coherent strength
in Maestro would close the rest of the gap.
