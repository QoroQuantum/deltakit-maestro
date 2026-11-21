# Coherent noise against its Pauli twirl

Decoder studies replace coherent gate errors by their Pauli twirl: the same
error probability per gate, but no coherence, so a Clifford simulator such as
Stim can run it. On hardware, small over-rotations add up in amplitude between
measurements, and the twirl can't show what that does. Here both run on the
same circuits and are decoded the same way: the over-rotations on Maestro's
matrix product state (MPS), their twirl on Stim, both by PyMatching with the
twirl's detector error model. What differs is only what the twirl leaves out.

```python
sampler = backend.compile_sampler(noisy, decoder=None, noise_type='coherent')
coherent = sampler.sample_detection_events(shots)              # MPS
twirl = backend.twirled_circuit(noisy, noise_type='coherent')
pauli = twirl.compile_detector_sampler().sample(shots)          # Stim
dem = sampler.task.detector_error_model                         # decodes both
```

`noise_type='coherent'` replaces each gate's depolarizing noise in a Deltakit
SI1000(p) circuit by an over-rotation of the same infidelity about a body
diagonal of the Bloch sphere, with a sign drawn once per qubit per shot. Idle,
reset and readout noise stay as they are (see [Coherent
noise](../guide/coherent_noise.md)).

In short: the twirl underestimates the logical error rate by 17–40% on the
rotated d=3 surface code, most at the weakest noise. On repetition codes the
gap grows with distance, to 45% at d=15, because the twirl overstates how fast
the logical error rate falls as the code grows.

## The rotated d=3 surface code

3 rounds, 600,000 coherent shots and 120 million twirl shots a point:

| p | Detection rate, coherent | Twirl | Ratio | LEP, coherent | Twirl | Ratio |
|---:|---:|---:|---:|---:|---:|---:|
| 0.002 | 0.0730 | 0.0603 | 1.211 ± 0.002 | 0.0243 | 0.0174 | **1.395 ± 0.011** |
| 0.003 | 0.1048 | 0.0876 | 1.196 ± 0.001 | 0.0488 | 0.0363 | 1.344 ± 0.008 |
| 0.005 | 0.1614 | 0.1372 | 1.177 ± 0.001 | 0.1126 | 0.0875 | 1.286 ± 0.005 |
| 0.007 | 0.2092 | 0.1807 | 1.158 ± 0.001 | 0.1813 | 0.1465 | 1.238 ± 0.003 |
| 0.01 | 0.2678 | 0.2364 | 1.133 ± 0.001 | 0.2732 | 0.2330 | 1.172 ± 0.002 |

The coherent runs have 14,587 logical errors at p=0.002 and 163,933 at
p=0.01, so every ratio is measured to about 1%. Coherent noise gives more
detection events and more logical errors at every strength, and the weaker the
noise, the larger the excess: at p=0.002 the twirl misses 40% of the logical
errors.

## Repetition codes, by distance

d rounds, until 400 coherent logical errors or 400,000 shots, at two strengths,
with 120 million twirl shots a point. At p=0.005, from d=11 on, too few logical
errors fit in 400,000 shots to measure a ratio, so those points are left out:

| Code | p | Detection rate, coherent | Twirl | Ratio | LEP, coherent | Twirl | Ratio |
|:---|---:|---:|---:|---:|---:|---:|---:|
| d=3 | 0.01 | 0.1828 | 0.1700 | 1.075 ± 0.002 | 0.0428 | 0.0416 | 1.03 ± 0.01 |
| d=5 | 0.01 | 0.1943 | 0.1812 | 1.073 ± 0.001 | 0.0265 | 0.0244 | 1.08 ± 0.01 |
| d=7 | 0.01 | 0.1995 | 0.1863 | 1.071 ± 0.001 | 0.0161 | 0.0141 | 1.14 ± 0.02 |
| d=9 | 0.01 | 0.2022 | 0.1894 | 1.067 ± 0.001 | 0.0100 | 0.0081 | 1.22 ± 0.04 |
| d=11 | 0.01 | 0.2041 | 0.1914 | 1.066 ± 0.001 | 0.0063 | 0.0048 | 1.32 ± 0.05 |
| d=13 | 0.01 | 0.2054 | 0.1929 | 1.065 ± 0.001 | 0.0038 | 0.0028 | 1.35 ± 0.06 |
| d=15 | 0.01 | 0.2062 | 0.1940 | 1.063 ± 0.0004 | 0.0024 | 0.0017 | **1.45 ± 0.07** |
| d=3 | 0.005 | 0.1009 | 0.0929 | 1.085 ± 0.002 | 0.0116 | 0.0113 | 1.03 ± 0.02 |
| d=5 | 0.005 | 0.1082 | 0.0998 | 1.084 ± 0.001 | 0.0035 | 0.0032 | 1.10 ± 0.03 |
| d=7 | 0.005 | 0.1117 | 0.1029 | 1.085 ± 0.001 | 0.00104 | 0.00083 | 1.24 ± 0.06 |
| d=9 | 0.005 | 0.1135 | 0.1048 | 1.083 ± 0.001 | 0.00029 | 0.00021 | 1.36 ± 0.13 |

```{figure} figures/coherent.png
:alt: Two plots of coherent over Pauli twirl. Left, the rotated d=3 surface code against noise strength p from 0.002 to 0.01: the logical error rate ratio falls from 1.40 to 1.17 and the detection-event ratio from 1.21 to 1.13. Right, repetition codes against distance d from 3 to 15: the detection-event ratio is flat near 1.07, while the logical error rate ratio rises from 1.03 at d=3 to 1.45 at d=15.

Coherent noise over its Pauli twirl, ±2σ: solid lines the logical error rate,
dashed lines detection events. Left: the d=3 surface code against p. Right:
repetition codes against distance, where detection events stay flat and the
logical error rate rises.
```

The detection-event excess stays the same at every distance, 6–7% at p=0.01
and 8% at p=0.005: round by round, coherent noise acts like Pauli noise a few
percent stronger. A logical error needs about (d+1)/2 errors, so the excess
compounds as the code grows. Fitting the logical error rate against distance,
the factor Λ it falls by for every 2 of distance is:

| p | Distances | Λ, coherent | Λ, twirl | Twirl ÷ coherent |
|---:|:---|---:|---:|---:|
| 0.01 | 3 to 15 | 1.622 ± 0.007 | 1.717 ± 0.001 | 1.06 |
| 0.005 | 3 to 9 | 3.37 ± 0.06 | 3.66 ± 0.004 | 1.09 |

The twirl overstates Λ by about the detection-event excess, so a projection of
the logical error rate to larger codes from twirled simulations is optimistic,
and more so the further it reaches.

## Checking χ

Truncation adds detection events too (see [Bond
dimension](../guide/bond_dimension.md)), so each part reran its most demanding
point at χ=64, double the default, with independent seeds. On the d=15
repetition code at p=0.01, χ=32 and χ=64 agree: z = +0.1 on the detection rate
and +0.6 on the LEP, 28,800 shots each. On the d=3 surface code at p=0.01, with
200,000 shots each, χ=32 has 0.2% fewer detection events than χ=64 (z = −1.9),
the opposite of what truncation does, and the same LEP (z = −0.6). Either way,
0.2% is small next to the coherent excess of 13%.
The surface code at χ=32 also agrees with an exact statevector on these
circuits (see [Matrix product state](mps.md#coherent-noise-and-t1-decay-against-exact-statevector)).

## How these were run

On a Google Cloud `n2d-highcpu-128` (AMD EPYC 7B13, 128 threads), with the
same software as the other pages. A sampler doesn't use a machine that size by
itself, so `coherent.py` runs 120 single-threaded processes
(`OMP_NUM_THREADS=1`), each sampling its own seeded chunk of shots, and merges
their counts. Only accuracy is reported here, so the machine doesn't matter to
the results. The whole run took about 2½ hours.
