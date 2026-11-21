# Matrix product state

A matrix product state (MPS) stores a state as a chain of tensors whose size is
set by the bond dimension χ. It is exact while χ holds the entanglement across
every cut of the chain, and it truncates, losing accuracy, past that. Coherent
noise in `deltakit-maestro` runs on Maestro's MPS (see [Simulation
types](../guide/simulation_types.md)), so whether its samples can be trusted is
the question here. Each check below compares MPS samples with a reference that
has no truncation, on the same circuits, decoded with the same detector error
model.

## Pauli noise: against Stim

Stim is an independent simulator, and exact for Pauli noise, so it checks the
MPS sampler end to end: circuit translation, noise, measurement and the
conversion to detection events. This is a check of correctness only. For Pauli
noise alone, use Stim or Maestro's stabilizer (see [Stabilizer against
Stim](stabilizer.md)). With the simulation type pinned to MPS (χ=32), Maestro
runs Pauli noise on the MPS, one trajectory a shot:

```python
import maestro
from deltakit_maestro import MaestroBackend

mps = MaestroBackend(simulation_type=maestro.SimulationType.MatrixProductState,
                     max_bond_dimension=32)
dets, obs = mps.compile_sampler(noisy, seed=2026).sample_detection_events(20_000)
```

On the rotated d=3 surface code (17 qubits, 3 rounds) under three Deltakit
noise models, 20,000 MPS shots against 2,000,000 Stim shots a point:

| Noise | p | Detection rate, MPS | Stim | z | LEP, MPS | Stim | z |
|:---|---:|---:|---:|---:|---:|---:|---:|
| SI1000 | 0.002 | 0.0515 ± 0.0004 | 0.0516 | −0.2 | 0.0141 ± 0.0008 | 0.0134 | +0.9 |
| SI1000 | 0.005 | 0.1195 ± 0.0006 | 0.1194 | +0.0 | 0.0693 ± 0.0018 | 0.0711 | −1.0 |
| SI1000 | 0.01 | 0.2114 ± 0.0007 | 0.2112 | +0.2 | 0.2020 ± 0.0028 | 0.2005 | +0.5 |
| SD6 | 0.002 | 0.0406 ± 0.0004 | 0.0404 | +0.4 | 0.0109 ± 0.0007 | 0.0104 | +0.7 |
| SD6 | 0.005 | 0.0945 ± 0.0006 | 0.0948 | −0.5 | 0.0561 ± 0.0016 | 0.0555 | +0.3 |
| SD6 | 0.01 | 0.1703 ± 0.0007 | 0.1706 | −0.5 | 0.1623 ± 0.0026 | 0.1628 | −0.2 |
| Toy | 0.002 | 0.0176 ± 0.0003 | 0.0176 | −0.0 | 0.0020 ± 0.0003 | 0.0019 | +0.3 |
| Toy | 0.005 | 0.0432 ± 0.0004 | 0.0429 | +0.7 | 0.0129 ± 0.0008 | 0.0111 | +2.2 |
| Toy | 0.01 | 0.0820 ± 0.0006 | 0.0819 | +0.2 | 0.0386 ± 0.0014 | 0.0395 | −0.7 |

Stim's standard errors are a tenth of the MPS's, so they're left out.

MPS and Stim agree at every point. The 18 z-scores have χ² = 9.3, where
agreement gives 18 ± 6, and the largest is 2.2. Detector by detector, the worst
of the 216 rates is 3.3σ from Stim's, about what 216 comparisons give by
chance.

## Coherent noise and `T1` decay: against exact statevector

Coherent over-rotations and `T1` amplitude damping aren't Pauli channels, so
Stim can't run them. Maestro's `Statevector` runs them without truncation, and
draws `T1` damping the same way, one branch a shot, so it is the reference here.
Both are pinned, and run the same circuits with the same noise:

```python
sv = MaestroBackend(simulation_type=maestro.SimulationType.Statevector)
mps.compile_sampler(noisy, noise_type='coherent', seed=1)
sv.compile_sampler(noisy, noise_type='coherent', seed=2)
```

| Code | Qubits | Noise | p | Detection rate, MPS | Statevector | z | LEP, MPS | Statevector | z |
|:---|---:|:---|---:|---:|---:|---:|---:|---:|---:|
| rotated d=3 | 17 | coherent | 0.002 | 0.0725 ± 0.0007 | 0.0736 ± 0.0007 | −1.1 | 0.0218 ± 0.0015 | 0.0255 ± 0.0016 | −1.7 |
| rotated d=3 | 17 | coherent | 0.005 | 0.1622 ± 0.0009 | 0.1617 ± 0.0009 | +0.3 | 0.1077 ± 0.0031 | 0.1119 ± 0.0032 | −0.9 |
| rotated d=3 | 17 | coherent | 0.01 | 0.2681 ± 0.0010 | 0.2693 ± 0.0011 | −0.8 | 0.2689 ± 0.0044 | 0.2675 ± 0.0044 | +0.2 |
| rotated d=3 | 17 | Pauli + `T1` | 0.005 | 0.1410 ± 0.0009 | 0.1390 ± 0.0009 | +1.5 | 0.1054 ± 0.0031 | 0.1041 ± 0.0031 | +0.3 |
| rotated d=3 | 17 | Pauli + coherent + `T1` | 0.005 | **0.2127 ± 0.0010** | 0.1944 ± 0.0010 | **+13.0** | **0.2166 ± 0.0041** | 0.1770 ± 0.0038 | **+7.1** |
| repetition d=5 | 9 | coherent | 0.01 | 0.1947 ± 0.0010 | 0.1948 ± 0.0010 | −0.1 | 0.0282 ± 0.0017 | 0.0299 ± 0.0017 | −0.7 |
| repetition d=5 | 9 | Pauli + coherent + `T1` | 0.01 | 0.2101 ± 0.0011 | 0.2103 ± 0.0010 | −0.1 | 0.0401 ± 0.0020 | 0.0379 ± 0.0019 | +0.8 |
| repetition d=9 | 17 | coherent | 0.01 | 0.2025 ± 0.0006 | 0.2029 ± 0.0006 | −0.5 | 0.0090 ± 0.0009 | 0.0102 ± 0.0010 | −0.9 |
| repetition d=9 | 17 | Pauli + coherent + `T1` | 0.01 | 0.2211 ± 0.0006 | 0.2199 ± 0.0006 | +1.5 | 0.0186 ± 0.0014 | 0.0216 ± 0.0015 | −1.5 |
| repetition d=11 | 21 | coherent | 0.01 | 0.2045 ± 0.0007 | 0.2039 ± 0.0007 | +0.6 | 0.0057 ± 0.0012 | 0.0075 ± 0.0014 | −1.0 |
| repetition d=11 | 21 | Pauli + coherent + `T1` | 0.01 | 0.2240 ± 0.0008 | 0.2231 ± 0.0008 | +0.8 | 0.0152 ± 0.0019 | 0.0127 ± 0.0018 | +1.0 |

Each circuit is a Deltakit SI1000(p) memory experiment (d rounds on the
repetition codes, 3 on the surface code), with χ=32. "Coherent" is
`noise_type='coherent'`, an over-rotation of strength p in place of the gate
noise; "Pauli + `T1`" is the circuit's own noise with `t1=0.005`; "Pauli +
coherent + `T1`" is `noise_type='full'` with `t1=0.005`. Shots: 10,000 each, and
4,000 on the 21-qubit code.

Coherent noise and `T1` decay each agree with the exact result on the surface
code, and all of it together agrees on the repetition codes. The 20 z-scores of
those rows have χ² = 17.9, where agreement gives 20 ± 6.

The exception is in bold: on the surface code, Pauli noise, coherent noise and
`T1` together give 9% more detection events at χ=32 than the exact statevector,
13σ off. That is truncation. Coherent noise alone needs χ=32 on this code, but
with `T1` damping as well it needs χ=48, and from there the same run agrees
(see [below](#bond-dimension-converging-to-the-exact-result)). It's the error
[Bond dimension](../guide/bond_dimension.md) warns of, in the direction it
warns of: truncation adds detection events, as coherence does, so it can pass
for a coherent effect. Checking χ against the noise you run catches it.

```{figure} figures/mps_accuracy.png
:alt: Two scatter plots of per-detector rates, MPS on the vertical axis against the reference on the horizontal. Left, Pauli noise against Stim; right, coherent noise, T1 decay and both with Pauli noise against exact statevector. The points lie on the diagonal, except the hollow ones of the surface code's combined run at χ=32, which lie above it.

Every detector's rate, MPS against its reference. Left: the Pauli runs above.
Right: the coherent, `T1` and combined runs; hollow, the run that χ=32
truncates.
```

## Bond dimension: converging to the exact result

Too small a χ truncates the state, and shows up as extra detection events (see
[Bond dimension](../guide/bond_dimension.md)). Against the exact statevector,
on the rotated d=3 code, the detection-event rate at each χ, for coherent noise
alone and for the combination that χ=32 truncates above (5,000 MPS shots a
point, 20,000 statevector):

| χ | Coherent, p=0.01 | z | Pauli + coherent + `T1`, p=0.005 | z |
|---:|---:|---:|---:|---:|
| 4 | 0.3196 ± 0.0015 | +31.1 | | |
| 8 | 0.3043 ± 0.0015 | +22.0 | | |
| 12 | 0.3031 ± 0.0014 | +21.4 | | |
| 16 | 0.2692 ± 0.0015 | +0.5 | 0.2348 ± 0.0014 | +25.0 |
| 24 | 0.2777 ± 0.0015 | +5.7 | | |
| 32 | 0.2695 ± 0.0015 | +0.6 | 0.2141 ± 0.0014 | +11.1 |
| 48 | 0.2692 ± 0.0015 | +0.5 | 0.1944 ± 0.0014 | −1.2 |
| 64 | 0.2695 ± 0.0015 | +0.7 | 0.1951 ± 0.0014 | −0.8 |
| 96 | | | 0.1928 ± 0.0014 | −2.3 |
| 128 | | | 0.1982 ± 0.0014 | +1.2 |
| **statevector** | **0.2684 ± 0.0007** | | **0.1964 ± 0.0007** | |

```{figure} figures/mps_chi.png
:alt: Two plots of detection-event rate against bond dimension χ, with the exact statevector value as a band. Left, coherent noise: the MPS falls from 0.32 at χ=4, touches the band at χ=16, rises off it at χ=24, and is inside it from χ=32 on. Right, Pauli plus coherent noise plus T1: the MPS falls from 0.235 at χ=16, is still above the band at χ=32, and is inside it from χ=48 to 128.

MPS against bond dimension χ, with the exact statevector value (±2σ) as the
band.
```

Coherent noise converges at χ=32, as the [noiseless and coherent
checks](../guide/bond_dimension.md#checking-χ) found without an exact
reference. Below it, truncation adds up to 19% more detection events, and not
steadily: χ=16 happens to agree here while χ=24 is 6σ off. Maestro routes gates
along the chain differently below χ=32, where its routing optimisations are off
by default, so convergence below the default isn't monotonic. Adding `T1`
damping and the circuit's Pauli noise moves the convergence to χ=48: at χ=32 the
run still has 9% too many. Past convergence, the MPS agrees with the exact
result at every χ, so a larger χ costs time but not accuracy. A longer run at
χ=64, 40,000 shots each, gives 0.1951 ± 0.0005 against the statevector's
0.1946 ± 0.0005 (z = +0.8).

The logical error probability is a blunter test. At χ=8 the coherent LEP,
0.274 ± 0.006, is within 0.4σ of the exact 0.272, while the detection-event
rate is 22σ off. A χ check by LEP alone would pass a truncated run; check the
detection events.

## Beyond a statevector

A statevector of n qubits holds 2ⁿ amplitudes, so its cost doubles with every
qubit. An MPS costs what the entanglement across its chain costs, and a
repetition code is a chain. On repetition codes with coherent noise
(SI1000(0.01), d rounds), with each sampler spreading its shots over the
machine's 30 threads, each MPS run is checked twice: against the exact
statevector where one fits, and against χ=64, double the default, everywhere:

| Code | Qubits | MPS, χ=32 | Statevector | Statevector memory | Detection rate, MPS | z, χ=64 | z, statevector |
|:---|---:|---:|---:|---:|---:|---:|---:|
| d=3 | 5 | 0.04 ms | 0.03 ms | 512 B | 0.184 ± 0.005 | +0.1 | −0.9 |
| d=5 | 9 | 0.28 ms | 0.08 ms | 8 KiB | 0.193 ± 0.003 | −0.7 | +1.4 |
| d=7 | 13 | 1.08 ms | 0.21 ms | 128 KiB | 0.204 ± 0.002 | +2.0 | +2.6 |
| d=9 | 17 | 2.92 ms | 5.12 ms | 2 MiB | 0.203 ± 0.002 | +0.8 | +1.4 |
| d=11 | 21 | 6.04 ms | 560 ms | 32 MiB | 0.201 ± 0.001 | −1.5 | −0.4 |
| d=13 | 25 | 10.8 ms | 12.7 s | 512 MiB | 0.205 ± 0.001 | −0.2 | −0.1 |
| d=15 | 29 | 17.5 ms | | 8 GiB | 0.207 ± 0.001 | −0.5 | |
| d=21 | 41 | 54.0 ms | | 32 TiB | 0.208 ± 0.001 | +1.0 | |
| d=25 | 49 | 94.8 ms | | 8 PiB | 0.208 ± 0.001 | +0.9 | |
| d=31 | 61 | 190 ms | | | 0.209 ± 0.001 | +0.9 | |
| d=41 | 81 | 467 ms | | | 0.209 ± 0.001 | +0.3 | |
| d=51 | 101 | 912 ms | | | 0.209 ± 0.001 | +0.2 | |

Statevector memory is one state, 2ⁿ complex doubles; a sampler holds one per
thread it runs. Shots: 1,200 an MPS run up to d=15, 480 to d=31 and 120 beyond;
the statevector ran 240 at 21 qubits and 30 at 25.

```{figure} figures/mps_scaling.png
:alt: Wall time per shot against qubits for repetition codes with coherent noise. The statevector's time rises exponentially up to 25 qubits; the MPS's rises slowly up to 101 qubits.

Time per shot over 30 threads, repetition codes with coherent noise.
```

Up to 13 qubits the statevector is faster. Past that its cost climbs steeply,
from 5.1 ms a shot at 17 qubits to 560 ms at 21 and 12.7 s at 25, where a shot
on the MPS takes 11 ms. The MPS's cost grows with the circuit instead: a shot of
the 101-qubit code, 51 rounds, takes 0.91 s.

The MPS agrees with the statevector at every size both run, and with χ=64 at
every size. The largest z-score, +2.6 at d=7, is one high χ=32 sample: χ=64
and the statevector agree with each other there (z = +0.5), and the 10,000-shot
runs [above](#coherent-noise-and-t1-decay-against-exact-statevector) find no
offset on these codes.

On a 2D layout, small as it is, the statevector wins: on the rotated d=3
surface code (17 qubits) a coherent shot takes 2.0 ms on the statevector and
9.6 ms on the MPS at χ=32. Pass
`MaestroBackend(simulation_type=maestro.SimulationType.Statevector)` to run it
that way; the decoder's detector error model is the same.
