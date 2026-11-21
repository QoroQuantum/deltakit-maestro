# Performance

Rotated surface code memory, SI1000(0.002) noise, d rounds, detection events in
shots per second. The [Benchmarks](../benchmarks.md) pages have more codes and
noise models, how each number was measured, and checks of the results against
Stim and an exact statevector simulation.

## Pauli noise

Pauli noise is sampled on Pauli frames, on one thread. Which of Maestro and
Stim's own detector sampler is faster depends on the processor (Maestro 0.3.16,
fastest of 7 runs):

| | d=3 | d=5 | d=7 | d=9 |
|---|---|---|---|---|
| Maestro, `compile_sampler(...).sample_detection_events`, x86 | 3.61M | 549k | 196k | 142k |
| Stim, `compile_detector_sampler().sample`, x86 | 8.28M | 810k | 277k | 249k |
| Maestro, Apple M4 Pro | 14.4M | 2.60M | 608k | 445k |
| Stim, Apple M4 Pro | 14.3M | 2.47M | 579k | 408k |

x86 is a Google Cloud `c2-standard-30` (Intel Cascade Lake, 3.1 GHz). There,
Stim's wheel runs a build that uses SIMD; on Apple Silicon it runs a portable
one, so the two are even there (see [The machine
matters](../benchmarks/stabilizer.md#the-machine-matters)).

Maestro draws measurements on Pauli frames faster than Stim does, and converts
them to detection events with Stim's converter, which costs the same whatever
the noise. Stim's detector sampler skips that step and speeds up as noise
thins, so under sparser noise Stim gains further (see [Where the time
goes](../benchmarks/stabilizer.md#where-the-time-goes)).

Under `sinter.collect` decoding takes much of the time. The [[72,12,6]]
bivariate bicycle code (144 qubits, SI1000(0.003), 3 rounds, in
[example_deltakit_codes.py](../examples/deltakit_codes.md)) samples at about
42 µs/shot on the M4 Pro.

## `T1` decay

`T1` decay is not a Pauli channel, so the stabilizer runs it shot by shot: with
`t1=1e-3`, about 23,000 shots/s at d=3 and 2,700 at d=5 on one thread of the M4
Pro. One sampler spreads its shots over every core, about 45,000 and 11,000
shots/s there. `max_simulators=` caps the threads.

## Coherent noise

Coherent noise runs on an MPS: about 9.6 ms a shot on the rotated d=3 code at
χ=32 on the x86 machine above, with one sampler spreading its shots over the
machine, so a single `simulate` or `compile_sampler` call is as fast as
`sinter.collect` over all the cores. On this 17-qubit code an exact statevector
is faster, 2.0 ms a shot: pass
`simulation_type=maestro.SimulationType.Statevector` to use it.

The MPS's cost grows with the bond dimension a code needs (see [Bond
dimension](bond_dimension.md)). Repetition codes, whose MPS stays small, run to
101 qubits at 0.91 s a shot (see
[Benchmarks](../benchmarks/mps.md#beyond-a-statevector)).

## Many cores

On a 128-thread machine, one MPS sampler kept only part of it busy, 7 to 34
threads depending on the run. To use a large machine, run several processes,
each sampling its own share of the shots with its own seed, and set
`OMP_NUM_THREADS` for each so that together they use the threads once: by
default every process uses all of them, and they slow each other down.
