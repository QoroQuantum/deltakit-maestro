# Performance

Measured on an Apple M4 Pro (12 cores), rotated surface code memory,
SI1000(0.002) noise, d rounds, detection events in shots per second.

## Pauli noise

Pauli noise is sampled on Pauli frames, on one thread, as fast as Stim's own
detector sampler (1M shots, Maestro 0.3.14):

| | d=3 | d=5 | d=7 | d=9 |
|---|---|---|---|---|
| Maestro, `compile_sampler(...).sample_detection_events` | 14.8M | 2.64M | 530k | 240k |
| Stim, `compile_detector_sampler().sample` | 14.9M | 2.55M | 510k | 230k |

Under `sinter.collect` decoding takes most of the time. The [[72,12,6]]
bivariate bicycle code (144 qubits, SI1000(0.003), 3 rounds, in
[example_deltakit_codes.py](../examples/deltakit_codes.md)) samples at about
46 µs/shot.

## `T1` decay

`T1` decay is not a Pauli channel, so the stabilizer runs it shot by shot: about
19,000 shots/s at d=3 and 2,100 at d=5 on one thread. One sampler spreads its
shots over every core, about 25,000 and 11,000 shots/s here. `max_simulators=`
caps the threads.

## Coherent noise

Coherent noise runs on an MPS: about 57 ms a shot per core on the rotated d=3
code at χ=32. One sampler again uses every core, about 6 ms a shot here, so a
single `simulate` or `compile_sampler` call is as fast as `sinter.collect` over
all the cores.

The cost grows quickly with the bond dimension a code needs, and only the
rotated d=3 code is practical: see [Bond dimension](bond_dimension.md).
