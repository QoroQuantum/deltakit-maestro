# Benchmarks

QEC experiments on Deltakit circuits under several noise models, each run on
Maestro and checked against a reference that doesn't depend on it:

- [Coherent noise against its Pauli twirl](benchmarks/coherent.md). What
  Maestro's matrix product state adds: coherent over-rotations, which a Clifford
  simulator can only approximate by their Pauli twirl. The twirl underestimates
  the logical error rate by 17–40% on the rotated d=3 surface code, and on
  repetition codes by more the larger the code, up to 45% at d=15: it overstates
  how fast the logical error rate falls with distance.
- [Extended stabilizer: coherent errors past a statevector](benchmarks/extended.md).
  With a coherent part smaller than the Pauli noise, as on hardware, Maestro's
  extended stabilizer runs coherent errors on surface codes up to d=7 (97
  qubits) and on the [[72,12,6]] bivariate bicycle code (144 qubits), and
  agrees with an exact statevector where one fits. The twirl misses 5–9% of
  the detection events there, and at d=5 at least 16% of the logical errors.
- [`T1` decay on qLDPC codes](benchmarks/qldpc.md). Maestro's stabilizer runs
  `T1` decay itself, shot by shot, on the [[72,12,6]] and [[144,12,12]]
  bivariate bicycle codes (144 and 288 qubits). Its Pauli twirl gives 6–9% more
  detection events in the first round, under 1% more over all rounds, and the
  same logical error rates within sampling error.
- [Matrix product state](benchmarks/mps.md). Maestro's MPS samples QEC circuits
  with the statistics of an exact simulation: an exact statevector's under
  coherent over-rotations and `T1` decay, which no Clifford simulator can run,
  and Stim's under Pauli noise, as a check. It runs far past what a statevector
  can hold on repetition codes.
- [Stabilizer against Stim](benchmarks/stabilizer.md). Maestro's Pauli frames
  give the same logical error rates as Stim under Deltakit's SI1000, SD6 and
  Toy noise. On x86, Stim samples detection events 1.4–2.6× faster on surface,
  repetition, toric and bivariate bicycle codes; on Apple Silicon, where Stim
  has no SIMD build, the two are even.

```{toctree}
:hidden:

benchmarks/coherent
benchmarks/extended
benchmarks/qldpc
benchmarks/mps
benchmarks/stabilizer
```

## How they were run

On a Google Cloud `c2-standard-30` virtual machine (Intel Xeon, Cascade Lake,
3.1 GHz, 15 cores with 30 threads, 120 GB, Debian 12) in November 2026, with
nothing else running on it, except the extended stabilizer's, which ran on a
`c4-standard-32` (see its page). Software: deltakit-maestro 0.1.2, Maestro
(`qoro-maestro`) 0.3.16, Deltakit 0.10.2, Stim 1.16.0, Sinter 1.16.0,
PyMatching 2.4.0 and Python 3.12. Every circuit is a Deltakit memory experiment in the Z basis with
Deltakit's noise, converted to Stim with `as_stim_circuit()`.

Every comparison is between independent samples, so two runs agree when they
differ by no more than their sampling error. Each result is given with its
standard error, and agreement is measured by the z-score, the difference over
its standard error: about 95% of z-scores from runs that agree lie within ±2.
A logical error probability (LEP) is the fraction of shots the decoder gets
wrong, using the detector error model of the task: PyMatching, or a BP decoder
from `ldpc` on the bivariate bicycle codes.

## Reproducing them

The scripts are in
[benchmarks/](https://github.com/QoroQuantum/deltakit-maestro/tree/main/benchmarks)
in the repository, with the results quoted here:

```bash
pip install -e ".[examples]" matplotlib    # from the repository root
python benchmarks/stabilizer_speed.py      # throughput against Stim, ~10 min
python benchmarks/stabilizer_ler.py        # logical error rates against Stim, ~3 min
python benchmarks/mps.py                   # MPS against statevector and Stim, ~2 hours
OMP_NUM_THREADS=1 WORKERS=120 python benchmarks/coherent.py   # coherent against twirl, ~2½ hours on 128 threads
OMP_NUM_THREADS=1 WORKERS=32 python benchmarks/extended.py    # extended stabilizer, ~4½ hours on 32 threads
OMP_NUM_THREADS=1 python benchmarks/qldpc_decoders.py         # decoders for the qLDPC codes, ~1¼ hours
OMP_NUM_THREADS=1 python benchmarks/qldpc.py rates            # T1 against twirl, detection events, ~1¾ hours
OMP_NUM_THREADS=1 WORKERS=30 python benchmarks/qldpc.py logical  # and logical error rates, ~5 hours
python benchmarks/plot.py                  # the figures on these pages
python benchmarks/tables.py                # the tables on these pages
```

Each script writes `benchmarks/results/<name>.json` with the machine and the
library versions it ran on. Timings need an otherwise idle machine; accuracy
doesn't.
