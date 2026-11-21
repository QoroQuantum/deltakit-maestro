# When to use Maestro

deltakit-maestro is for noise that isn't a Pauli channel, and for finding out
how much the Pauli approximation of that noise misses. Pauli noise alone is
Stim's job: it is the standard, and faster on x86. deltakit-maestro runs Pauli
noise too, with the same logical error rates, so one workflow covers both.

## Where it is most useful

**Measuring what the Pauli twirl misses.** Decoder studies replace coherent
errors and decay by their Pauli twirl so that a Clifford simulator can run them.
deltakit-maestro simulates the noise itself and hands the decoder the twirl's
detector error model, so the real noise and its Pauli approximation come out of
the same circuit, decoded alike. Measured so far (see
[Benchmarks](../benchmarks/coherent.md)):

- On the rotated d=3 surface code, coherent over-rotations give 17–40% more
  logical errors than their twirl, most at the weakest noise.
- On repetition codes the gap grows with distance, to 45% at d=15. The twirl
  overstates how fast the logical error rate falls with distance, the
  error-suppression factor Λ, by 6–9%, so projections to larger codes from
  twirled simulations are optimistic.

**Coherent over-rotations.** No Clifford simulator can run them. Maestro's
matrix product state (MPS) does, and agrees with an exact statevector on every
circuit checked (see [Matrix product state](../benchmarks/mps.md)):

- the rotated d=3 surface code, about 10 ms a shot;
- repetition codes up to 101 qubits, 0.91 s a shot on 30 threads, far past what
  a statevector can hold: at 25 qubits a statevector takes 12.7 s a shot, the
  MPS 11 ms.

**Small coherent errors on larger codes.** When the coherent part is smaller
than the Pauli noise, Maestro's extended stabilizer runs codes no statevector
or MPS holds: surface codes up to d=7 (97 qubits) and the [[72,12,6]]
bivariate bicycle code (144 qubits), with a coherent part a quarter of
SI1000(0.002)'s gate noise. There the twirl misses 5–9% of the detection events,
and at d=5 at least 16% of the logical errors (see [Extended
stabilizer](../benchmarks/extended.md)). It needs Maestro 0.3.16.

**`T1` decay.** Decay toward |0⟩ isn't a Pauli channel either. The stabilizer
simulator runs it as a reset with probability γ, shot by shot: about 23,000
shots a second at d=3 and 2,700 at d=5 on one thread of an Apple M4 Pro (see
[Performance](performance.md)). The statevector and the
MPS run it as amplitude damping, one branch a shot, and `'full'` runs it with
coherent noise (see [Noise](noise.md)). On the [[72,12,6]] and [[144,12,12]]
bivariate bicycle codes, the twirl gives 6–9% more detection events than the
decay in the first round, while the data qubits are in |0⟩, but the same
logical error rates within sampling error (see [`T1` decay on qLDPC
codes](../benchmarks/qldpc.md)).

**Hardware-shaped noise.** A `maestro.NoiseModel` can give each qubit and
coupler its own rates, asymmetric readout, directed coherent over-rotations and
ZZ crosstalk (see
[example_custom_noise_model.py](../examples/custom_noise_model.md)).

**One workflow for all of it.** Deltakit circuits, and plain Stim circuits, go
in as they are, and come back as measurements, detection events or Sinter
statistics. `sinter_decoders` takes PyMatching, or any Sinter decoder that
implements `compile_decoder_for_dem`. `ldpc`'s Sinter BP-OSD decoder doesn't, so
decode the detection events yourself for BP-OSD, as
[example_deltakit_codes.py](../examples/deltakit_codes.md) does. Changing the
noise model doesn't change the pipeline (see [Sampling](sampling.md)).

## Where something else is better

- **Pauli noise alone, at scale:** Stim samples it faster on x86. Maestro gives
  the same logical error rates (see [Pauli noise](../benchmarks/stabilizer.md)).
- **Coherent noise on a small 2D code:** Maestro's statevector is faster than
  its MPS on the rotated d=3 code, 2.0 ms a shot against 9.6 ms. Pass
  `simulation_type=maestro.SimulationType.Statevector`.
- **Strong coherent noise on codes with long-range connections, such as qLDPC
  codes:** their entanglement is beyond what an MPS can hold, and the extended
  stabilizer's cost climbs fast as the coherent part grows (see [Extended
  stabilizer](../benchmarks/extended.md#what-it-costs)).
