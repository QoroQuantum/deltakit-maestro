# Stabilizer against Stim

Pauli noise, which every noise model below is, runs on Maestro's stabilizer
simulator, sampled on Pauli frames (see [Simulation
types](../guide/simulation_types.md)). Stim is the standard for this, so it is
the reference for both speed and statistics.

In short: Maestro gives the same logical error rates as Stim. Stim samples
detection events faster on x86, 1.4–2.6× on these circuits. Maestro draws a
shot's measurements faster than Stim does, but converting them to detection
events costs more than drawing them, and Stim's detector sampler skips that
step. On Apple Silicon, where Stim has no SIMD build, the two are even.

## Throughput

Detection events from memory experiments (d rounds), on one thread each.
Each simulator is compiled once, warmed up, then run 7 times on the same number
of shots, the two taking turns so that anything else running on the machine
slows both alike. The fastest of the 7 runs is reported:

```python
sampler = backend.compile_sampler(noisy, decoder=None)
sampler.sample_detection_events(shots)              # Maestro
noisy.compile_detector_sampler().sample(shots)      # Stim
```

Both return unpacked bool arrays, and Maestro's time includes converting its
measurements to detection events with Stim's converter. Shots per second:

| Circuit | Noise | Qubits | Detectors | Maestro | Stim | Maestro ÷ Stim |
|:---|:---|---:|---:|---:|---:|---:|
| Rotated d=3 | SI1000 | 17 | 24 | 3.61M | 8.28M | 0.44× |
| Rotated d=5 | SI1000 | 49 | 120 | 549k | 810k | 0.68× |
| Rotated d=7 | SI1000 | 97 | 336 | 196k | 277k | 0.71× |
| Rotated d=9 | SI1000 | 161 | 720 | 142k | 249k | 0.57× |
| Rotated d=11 | SI1000 | 241 | 1,320 | 76.5k | 133k | 0.57× |
| Rotated d=13 | SI1000 | 337 | 2,184 | 30.2k | 77.0k | 0.39× |
| Rotated d=15 | SI1000 | 449 | 3,360 | 21.5k | 46.5k | 0.46× |
| Rotated d=3 | SD6 | 17 | 24 | 3.60M | 8.05M | 0.45× |
| Rotated d=7 | SD6 | 97 | 336 | 196k | 272k | 0.72× |
| Rotated d=11 | SD6 | 241 | 1,320 | 76.8k | 132k | 0.58× |
| Rotated d=3 | Toy | 17 | 24 | 3.72M | 9.45M | 0.39× |
| Rotated d=7 | Toy | 97 | 336 | 203k | 296k | 0.69× |
| Rotated d=11 | Toy | 241 | 1,320 | 79.0k | 158k | 0.50× |
| Repetition d=25 | SI1000 | 49 | 624 | 179k | 301k | 0.59× |
| Unrotated planar d=7 | SI1000 | 169 | 588 | 157k | 262k | 0.60× |
| Toric d=7 | SI1000 | 196 | 686 | 136k | 225k | 0.61× |
| Bivariate bicycle [[72,12,6]], 6 rounds | SI1000 | 144 | 432 | 197k | 322k | 0.61× |
| Bivariate bicycle [[144,12,12]], 12 rounds | SI1000 | 288 | 1,728 | 61.1k | 110k | 0.55× |

All at p=0.002. The 7 runs of each differ by 1–2%, so differences larger than
that are real. Both simulators ran on exactly one thread: CPU time equalled
wall time.

Stim is faster on every circuit, by 1.4× to 2.6×.

```{figure} figures/stabilizer_speed.png
:alt: Left, detection-event shots per second against distance for the rotated surface code, Maestro below Stim at every distance from d=3 to d=15. Right, Maestro's throughput over Stim's for every circuit, between 0.39 and 0.72.

Left: the rotated surface code under SI1000(0.002). Right: Maestro's throughput
over Stim's for every circuit in the table.
```

### Where the time goes

Maestro draws a shot's measurement record on Pauli frames, 2.6–4.3× faster than
Stim's measurement sampler. Its detection events then go through Stim's
measurement-to-detection converter, which costs more than the sampling on these
circuits. Stim's detector sampler skips that step, and it gets faster as noise
gets sparser, so the lighter the noise, the further ahead it is. On the rotated
d=7 code, 7 rounds:

| Noise | p | Detection events, Maestro ÷ Stim | Measurements, Maestro ÷ Stim |
|:---|---:|---:|---:|
| Toy | 0.0005 | 0.57× | 4.25× |
| Toy | 0.002 | 0.60× | 3.83× |
| Toy | 0.008 | 0.69× | 3.18× |
| SI1000 | 0.0005 | 0.58× | 3.91× |
| SI1000 | 0.002 | 0.62× | 3.40× |
| SI1000 | 0.008 | 0.77× | 2.57× |

Measurements are `sample_measurements` against Stim's
`compile_sampler().sample`. Toy noise is lighter than SI1000 at the same p, with
readout error p rather than 5p and no reset error or extra idling during
readout.

### The machine matters

Stim's PyPI wheels pick a build for the processor at import: on x86, one that
works on 128-bit SIMD words (`stim._stim_sse2`); on Apple Silicon, a portable
build without SIMD (`stim._stim_polyfill`). Maestro's sampler is the same on
both. The same benchmark on an Apple M4 Pro laptop, with the same Maestro, gave
Maestro ÷ Stim of 0.91–1.14× under SI1000 and SD6, faster than Stim on 13 of
15 circuits, and 0.63–0.86× under Toy noise. Which machine you run on decides
which simulator is faster; on x86, where most QEC simulation runs, it is Stim.

## Logical error rates

Under `sinter.collect`, each rotated surface code memory experiment (d=3, 5
and 7, d rounds) was sampled twice, by Stim, as sinter does by default, and by
Maestro, through `as_sinter_task`, and both were decoded by PyMatching with the
circuit's own detector error model. Up to 50 million shots or 5,000 logical
errors a point, under three Deltakit noise models:

- **SI1000**, superconducting-inspired: two-qubit gates p, single-qubit gates
  and idling p/10, readout 5p, reset and idling during readout and reset 2p.
- **SD6**, standard depolarizing: every gate, idle, reset and readout p.
- **Toy**: two-qubit gates p, single-qubit gates and idling p/10, readout p.

```python
tasks = []
for circuit, meta in circuits:
    tasks.append(sinter.Task(circuit=circuit, decoder='pymatching', json_metadata=meta))
    tasks.append(backend.as_sinter_task(circuit, json_metadata=meta))
sinter.collect(num_workers=os.cpu_count(), tasks=tasks,
               custom_decoders=backend.sinter_decoders(decoder='pymatching'), ...)
```

```{figure} figures/stabilizer_ler.png
:alt: Three log-log plots of logical error rate against physical noise strength p, for SI1000, SD6 and Toy noise, with curves for d=3, 5 and 7. Maestro's markers sit on Stim's lines at every point.

Logical error rate per shot against p. Stim is the line, with a ±2σ band;
Maestro is the markers, with ±2σ bars.
```

Maestro and Stim agree at all 54 points. If the two sample the same
distribution, the 54 z-scores behave like draws from a standard normal, and
they do: mean +0.09, standard deviation 1.03, χ² = 56.2 where agreement gives
54 ± 10, and three beyond ±2 (the largest 2.6), where chance gives about 2.5.
Every point reached 5,000 logical errors from each sampler except two that
stopped at 50 million shots: Toy noise at p=0.001 on d=5, with 4,001 (Maestro)
and 3,937 (Stim), and on d=7, with 450 and 505.

### The cost of a shot under sinter

Under `sinter.collect`, a shot's cost is sampling plus decoding. Run one at a
time in one process, with PyMatching decoding each batch (SI1000(0.002), d
rounds, microseconds a shot):

| Batch | d=3, Maestro | d=3, Stim | Ratio | d=7, Maestro | d=7, Stim | Ratio |
|---:|---:|---:|---:|---:|---:|---:|
| 100 | 1.605 | 0.723 | 2.22× | 16.12 | 9.71 | 1.66× |
| 1,000 | 0.698 | 0.486 | 1.44× | 9.81 | 8.16 | 1.20× |
| 10,000 | 0.530 | 0.398 | 1.33× | 9.22 | 7.94 | 1.16× |
| 100,000 | 0.508 | 0.385 | 1.32× | 9.39 | 8.02 | 1.17× |

Decoding narrows the gap: at d=7 a Maestro shot costs 1.17× a Stim one, against
1.4× for sampling alone. Small batches cost Maestro more, from a fixed cost per
call.

In the logical error rate runs above, with 30 workers at once, sinter recorded
1.7× as many worker seconds a shot for Maestro's tasks as for Stim's: 0.86
against 0.50 µs at d=3, 3.22 against 1.93 at d=5, and 9.75 against 5.88 at
d=7. That is more than the 1.2–1.3× one process gives at the same batch sizes,
and we haven't found where the difference comes from.
