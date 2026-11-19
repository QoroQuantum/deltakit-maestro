# Supported circuits and gotchas

## Circuits

`circuit` is a Deltakit `Circuit` or a `stim.Circuit`. A Deltakit circuit is
converted with `Circuit.as_stim_circuit()`, the only Deltakit API this package
uses. Every Deltakit code family runs through the backend unchanged: repetition,
rotated and unrotated planar, toric, and bivariate bicycle codes (see
[example_deltakit_codes.py](../examples/deltakit_codes.md)).

Deltakit's stability experiments and `use_iswap_gates=True` need a Deltakit
cloud `client`, so the examples don't show them.

## What isn't supported

- `MPP`, correlated `E` and heralded noise, classically controlled gates and
  inverted measurement targets are rejected by
  `maestro.sinter.translate_stim_to_maestro`.
- Seeded `sinter.collect`. Use `compile_sampler(..., seed=)` or
  `simulate(..., seed=)` for reproducible runs (see [Seeds](sampling.md#seeds)).

## Gotchas

- **Import Deltakit before PyMatching.** With `pymatching` 2.4 imported first,
  Deltakit's circuit builders fail with
  `RuntimeError: Caught an unknown exception!`. Either order works once
  `deltakit.explorer` has been imported.
- **Don't mix Stim circuits.** `PyMatchingDecoder.construct_decoder_and_stim_circuit`
  orders gates and detectors differently from `as_stim_circuit()`. Decode
  against `sampler.task.detector_error_model` or
  `as_sinter_task(...).detector_error_model`.
- **`MaestroBackend(seed=)` is rejected**, since every `sinter.collect` worker
  would draw the same shots. Pass `seed=` to `simulate` or `compile_sampler`.

## Versions

Python 3.10 or later, within what Deltakit supports (3.10 to 3.15 across its
current releases), on macOS and Linux. CI tests 3.10 to 3.14.

The dependencies are `numpy`, `deltakit>=0.8.0` and
`qoro-maestro[sinter]>=0.3.15,<0.4.0`, plus `stim>=1.14` and `sinter>=1.16`,
which the package imports itself: Deltakit runs on its own Stim fork,
`deltakit-stim`, and doesn't install them. The `examples` extra adds `pymatching`,
which `deltakit` already pulls in through `deltakit-decode`, and `ldpc` (for
BP-OSD), which it no longer does: `deltakit-explorer` dropped it in 0.9.2.

CI tests Deltakit 0.8.0, 0.9.0 and 0.10.2 on Python 3.12, each with the
`deltakit-circuit`, `-core`, `-decode` and `-explorer` it was released with, and
the latest Deltakit on every Python version above. Pinning the subpackages
matters: Deltakit 0.8.0 and 0.9.0 only set their minimums, so installing
`deltakit==0.8.0` alone gets today's. Deltakit 0.9 and later run on
`deltakit-stim`, and this package needs 0.2.4 or later of it, which pip installs
unless an older one is pinned: earlier versions crash once Stim is imported too
([deltakit#310](https://github.com/Deltakit/deltakit/issues/310)), as this
package does.
