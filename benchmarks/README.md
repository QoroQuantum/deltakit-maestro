# Benchmarks

The scripts behind the
[Benchmarks](https://qoroquantum.github.io/deltakit-maestro/benchmarks.html) pages
of the documentation. Each writes its results to `results/`, `plot.py` turns
them into the figures in `docs/benchmarks/figures/`, and `tables.py` prints the
tables the pages quote.

| Script | Measures | Time |
|---|---|---|
| `stabilizer_speed.py` | detection-event throughput against Stim on one thread, across codes, noise models and noise strengths, and the cost of a shot under sinter | ~10 min |
| `stabilizer_ler.py` | logical error rates under `sinter.collect`, Maestro against Stim, three noise models | ~3 min |
| `mps.py pauli` | MPS against Stim on Pauli noise, a correctness check | ~5 min |
| `mps.py exact` | MPS against exact statevector on coherent noise and `T1` decay | ~50 min |
| `mps.py chi` | convergence in the bond dimension χ, against exact statevector | ~40 min |
| `mps.py confirm` | one converged run with 40,000 shots each, against exact statevector | ~5 min |
| `mps.py scaling` | time a shot against code size, MPS and statevector, with χ=64 and statevector checks | ~25 min |
| `coherent.py` | coherent noise on MPS against its Pauli twirl on Stim: the d=3 surface code against noise strength, repetition codes against distance | ~2½ hours on 128 threads |
| `extended.py` | Pauli noise plus a small coherent part on the extended stabilizer: against exact statevector on d=3, against its Pauli twirl on surface codes to d=7 and the [[72,12,6]] bivariate bicycle code. Needs Maestro 0.3.16 | ~4½ hours on 32 threads |
| `qldpc_decoders.py` | speed, memory and accuracy of four `ldpc` decoders on the same shots of the [[72,12,6]] and [[144,12,12]] bivariate bicycle codes, against BP-OSD-CS 7 | ~1¼ hours |
| `qldpc.py rates` | `T1` decay, shot by shot, against its Pauli twirl on those codes: detection rates, overall and in the first round, and sampling speed on one thread | ~1¾ hours on one thread |
| `qldpc.py logical` | the same, logical error rates under `sinter.collect` with BP-LSD | ~5 hours |

Times are on 30 threads unless noted.

```bash
pip install -e ".[examples]" matplotlib    # from the repository root
python benchmarks/stabilizer_speed.py
python benchmarks/stabilizer_ler.py
python benchmarks/mps.py                    # every part
OMP_NUM_THREADS=1 WORKERS=120 python benchmarks/coherent.py   # on a large machine
OMP_NUM_THREADS=1 WORKERS=32 python benchmarks/extended.py    # needs Maestro 0.3.16
OMP_NUM_THREADS=1 python benchmarks/qldpc_decoders.py
OMP_NUM_THREADS=1 python benchmarks/qldpc.py rates            # one thread, for the sampling speed
OMP_NUM_THREADS=1 WORKERS=30 python benchmarks/qldpc.py logical
python benchmarks/plot.py
python benchmarks/tables.py
```

## Checking a new Maestro build

To see what an unreleased Maestro changes, build it into a separate
environment, run the benchmarks with `BENCHMARK_RESULTS` pointing to a
directory of their own, and compare against the published results:

```bash
uv venv ../venv-maestro-main && source ../venv-maestro-main/bin/activate
uv pip install -e ".[examples,test]" matplotlib
uv pip install --reinstall-package qoro-maestro "qoro-maestro[sinter] @ ../maestro"
BENCHMARK_RESULTS=../results-maestro-main python benchmarks/stabilizer_speed.py
BENCHMARK_RESULTS=../results-maestro-main python benchmarks/mps.py
...
python benchmarks/compare.py ../results-maestro-main
```

An unreleased Maestro carries the last release's version number, so each
results file also records the checkout it was built from (`git describe`).
`compare.py` prints Maestro's speed in both runs, with Stim's as a check that
the machine ran alike, and each run's agreement with its reference.

## Timing

The timing benchmarks (`stabilizer_speed.py`, `mps.py scaling`) need an
otherwise idle machine; each records the load average it ran under. The others
measure accuracy, which doesn't depend on load. `stabilizer_ler.py` resumes
from sinter's `results/stabilizer_ler.csv`, which isn't committed; delete it to
sample afresh.
