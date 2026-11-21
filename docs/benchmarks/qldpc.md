# `T1` decay on qLDPC codes

`T1` decay pulls a qubit toward |0⟩. It isn't a Pauli channel, so a Clifford
simulator such as Stim can run only its Pauli twirl, which applies X, Y and Z
with probability γ/4 each, whatever state the qubit is in. Maestro's stabilizer
runs the decay itself, shot by shot: after every gate it resets each qubit the
gate touched to |0⟩ with probability γ (see [Noise](../guide/noise.md)). So it
runs on any code the stabilizer holds. Here that is the [[72,12,6]] and
[[144,12,12]] bivariate bicycle codes of [Bravyi et
al.](https://arxiv.org/abs/2308.07915), with 144 and 288 qubits, far past what a
statevector or a matrix product state can hold.

```python
from deltakit_maestro import MaestroBackend

backend = MaestroBackend()
decay = backend.as_sinter_task(noisy, t1=p)                           # the decay, shot by shot
twirl = backend.as_sinter_task(backend.twirled_circuit(noisy, t1=p))  # its twirl, on Pauli frames
```

Every circuit is a Deltakit Z-basis memory experiment of d rounds (6 and 12)
under SI1000(p), with `T1` decay of γ = p after every gate. Both are decoded
alike, with the twirl's detector error model, by BP with localised statistics
decoding ([below](#the-decoder)).

In short: the decay and its twirl differ where a qubit sits in |0⟩, which the
decay leaves alone and the twirl flips. In the first round, when the data qubits
are still in |0⟩, the twirl gives 6–9% more detection events than the decay.
Over all rounds it gives under 1% more, and the logical error rates agree within
their errors, 5–9%, at every strength on both codes. On these codes, under this
noise, the twirl is a good stand-in for `T1` decay. Decoding costs far more than
sampling either one.

## Detection events

20,000 shots of the decay and 1,000,000 of its twirl at each strength:

| Code | p | First round, `T1` | Twirl | Ratio | All rounds, `T1` | Twirl | Ratio | z |
|:---|---:|---:|---:|---:|---:|---:|---:|---:|
| [[72,12,6]] | 0.0005 | 0.0197 | 0.0208 | 1.058 | 0.0430 | 0.0432 | 1.0065 | +2.0 |
| [[72,12,6]] | 0.001 | 0.0385 | 0.0408 | 1.059 | 0.0820 | 0.0827 | 1.0086 | +3.9 |
| [[72,12,6]] | 0.0015 | 0.0563 | 0.0600 | 1.065 | 0.1177 | 0.1187 | 1.0078 | +4.4 |
| [[72,12,6]] | 0.002 | 0.0741 | 0.0784 | 1.058 | 0.1505 | 0.1515 | 1.0064 | +4.3 |
| [[144,12,12]] | 0.0005 | 0.0192 | 0.0209 | 1.087 | 0.0445 | 0.0446 | 1.0040 | +2.5 |
| [[144,12,12]] | 0.001 | 0.0379 | 0.0409 | 1.078 | 0.0850 | 0.0853 | 1.0032 | +2.9 |
| [[144,12,12]] | 0.0015 | 0.0559 | 0.0601 | 1.075 | 0.1219 | 0.1223 | 1.0032 | +3.6 |
| [[144,12,12]] | 0.002 | 0.0732 | 0.0785 | 1.072 | 0.1555 | 0.1560 | 1.0030 | +4.1 |

The first round's detectors, 36 on [[72,12,6]] and 72 on [[144,12,12]], compare
the Z checks with their starting values while the data qubits are still in |0⟩.
There the decay does nothing and the twirl flips a qubit with probability γ/2,
so the twirl fires them 6–9% more often, 7 to 24 standard errors apart (counting
the detectors as independent). Measuring the X checks then spreads each data
qubit's state evenly over |0⟩ and |1⟩, and on such a qubit the decay and its
twirl cause errors equally often on average. The ancillas are reset to |0⟩
every round, so they can keep some of the difference, but over all rounds the
twirl's excess falls to 0.3–0.9%. It is real, 2 to 4.4 standard errors at each strength, but
small. The twirl errs on the pessimistic side here, unlike for coherent noise
(see [Coherent noise against its Pauli twirl](coherent.md)).

## Logical error rates

Under `sinter.collect`, any of the 12 logical qubits wrong counts as a logical
error. Each point ran to 500 logical errors in each arm on [[72,12,6]] and 300 on
[[144,12,12]]:

| Code | p | LEP, `T1` | Twirl | Ratio | z | `T1` errors | Twirl errors |
|:---|---:|---:|---:|---:|---:|---:|---:|
| [[72,12,6]] | 0.0005 | 3.92e-03 | 3.86e-03 | 0.98 ± 0.06 | −0.2 | 503 in 128,272 | 503 in 130,253 |
| [[72,12,6]] | 0.001 | 0.0442 | 0.0424 | 0.96 ± 0.06 | −0.7 | 506 in 11,437 | 511 in 12,061 |
| [[72,12,6]] | 0.0015 | 0.1660 | 0.1681 | 1.01 ± 0.06 | +0.2 | 541 in 3,260 | 507 in 3,016 |
| [[72,12,6]] | 0.002 | 0.3573 | 0.3612 | 1.01 ± 0.05 | +0.2 | 557 in 1,559 | 509 in 1,409 |
| [[144,12,12]] | 0.001 | 0.0112 | 0.0125 | 1.11 ± 0.09 | +1.3 | 303 in 26,941 | 304 in 24,403 |
| [[144,12,12]] | 0.0015 | 0.1398 | 0.1476 | 1.06 ± 0.08 | +0.7 | 305 in 2,182 | 304 in 2,060 |
| [[144,12,12]] | 0.002 | 0.5084 | 0.5016 | 0.99 ± 0.06 | −0.2 | 303 in 596 | 311 in 620 |

The decay and its twirl agree at every point, within 1.3 standard errors. The
first round's difference is too small to show: it is one round of 6 or 12, and
the logical error comes from all of them. [[144,12,12]] starts at p=0.001: at
5–11 s a shot, lower strengths would take days.

## The decoder

BP-OSD with an ordered-statistics search of order 7 after up to 1,000 BP
iterations decodes these codes well but slowly: 47 s a [[144,12,12]] shot, with
4.5 GB a worker. So the decoder here is BP with localised statistics decoding,
LSD-CS of order 2 after up to 100 iterations, from `ldpc` 2.4.1. Both arms use
it, so the comparison is fair; the logical error rates above are 1.4–1.7× what
the slow decoder gives, so they compare the two noise models, not the codes at
their best. The choice comes from decoding the same shots of the twirl with
four decoders:

| Code | p | Decoder | Failure rate | Against OSD-CS 7 | CPU s a shot | GB a worker |
|:---|---:|:---|---:|---:|---:|---:|
| [[72,12,6]] | 0.001 | OSD-CS 7, 1000 iterations | 0.0257 |  | 8.23 | 0.6 |
| [[72,12,6]] | 0.001 | OSD-0, 100 iterations | 0.0503 | +107 −9 | 0.88 | 0.4 |
| [[72,12,6]] | 0.001 | LSD-CS 2, 100 iterations | 0.0432 | +87 −17 | 0.83 | 0.4 |
| [[72,12,6]] | 0.001 | LSD-0, 100 iterations | 0.0503 | +107 −9 | 0.82 | 0.4 |
| [[72,12,6]] | 0.0015 | OSD-CS 7, 1000 iterations | 0.1143 |  | 8.48 | 0.6 |
| [[72,12,6]] | 0.0015 | OSD-0, 100 iterations | 0.1783 | +228 −36 | 0.99 | 0.5 |
| [[72,12,6]] | 0.0015 | LSD-CS 2, 100 iterations | 0.1640 | +199 −50 | 1.02 | 0.5 |
| [[72,12,6]] | 0.0015 | LSD-0, 100 iterations | 0.1763 | +224 −38 | 0.99 | 0.5 |
| [[144,12,12]] | 0.0015 | OSD-CS 7, 1000 iterations | 0.1175 |  | 47.21 | 4.5 |
| [[144,12,12]] | 0.0015 | OSD-0, 100 iterations | 0.1975 | +36 −4 | 3.83 | 0.7 |
| [[144,12,12]] | 0.0015 | LSD-CS 2, 100 iterations | 0.1750 | +30 −7 | 4.25 | 0.7 |
| [[144,12,12]] | 0.0015 | LSD-0, 100 iterations | 0.1975 | +36 −4 | 4.24 | 0.7 |

"Against OSD-CS 7" counts the shots only that decoder failed, then those only
OSD-CS 7 failed. 4,000, 3,000 and 400 shots, with 30 workers on [[72,12,6]] and
16 on [[144,12,12]], whose OSD-CS 7 decoder doesn't fit in memory 30 times
over. LSD-CS 2 is the most accurate of the fast decoders at the same speed.
`sinter_decoders` takes any Sinter decoder with `compile_decoder_for_dem`; the
benchmark builds one for `ldpc`'s BP-OSD and BP-LSD in `benchmarks/common.py`.

## What it costs

Sampling detection events on one thread, in shots a second:

| Code | Qubits | `T1` decay, shot by shot | Twirl, Pauli frames |
|:---|---:|---:|---:|
| [[72,12,6]] | 144 | 116 | 125k |
| [[144,12,12]] | 288 | 15.6 | 31.5k |

The decay samples 1,000–2,000 times slower than its twirl, since each shot runs
on its own. In a decoded study that hardly matters: a decay shot takes 9 ms on
[[72,12,6]] and 64 ms on [[144,12,12]], and decoding one takes 0.6–1.2 s and
5–11 s. A whole point of the logical error rates, decay and twirl, took about the
same time in each arm.

## How it was run

On the Google Cloud `c2-standard-30` of the other pages, in November 2026, with
nothing else running; Maestro 0.3.16, Deltakit 0.10.2, Stim 1.16.0, Sinter
1.16.0, `ldpc` 2.4.1, Python 3.12. The detection rates ran on one thread, the
decoder check and the logical error rates on 30 worker processes of one thread
each, so a decoding time is one worker's with every other thread busy.

```bash
OMP_NUM_THREADS=1 python benchmarks/qldpc_decoders.py              # ~1½ hours on 30 threads
OMP_NUM_THREADS=1 python benchmarks/qldpc.py rates                 # ~1¾ hours on one thread
OMP_NUM_THREADS=1 WORKERS=30 python benchmarks/qldpc.py logical    # ~5 hours on 30 threads
```
