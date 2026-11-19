# Changelog

## [Unreleased]

- The README opens with what the package is for and what it measures, says
  where coherent noise is practical, and installs from PyPI
  (`pip install deltakit-maestro`) rather than from a clone. It gains PyPI,
  Python, Tests and Docs badges.
- CI tests Deltakit 0.8.0, 0.9.0 and 0.10.2 as released: a new job pins each to
  the subpackages it shipped with, from `.github/constraints/`. The docs said
  these versions were tested, but Deltakit 0.8.0 and 0.9.0 only set minimums
  for their subpackages, so installing either one got today's subpackages. All
  three pass. Deltakit 0.9.0 shipped with `deltakit-stim` 0.2.0, which crashes
  once Stim is imported too (deltakit#310), so its job uses 0.2.4, the first
  fixed release. The docs now say so.

## [0.1.2]

- Requires `qoro-maestro>=0.3.15`. From 0.3.15, Maestro's `Statevector` and
  `MatrixProductState` on the QCSim and Qiskit Aer engines run `T1` decay as
  amplitude damping, one branch drawn each shot, where they reset the qubit to
  |0⟩ before. The decoder's detector error model now twirls `T1` as amplitude
  damping on those types, including the `MatrixProductState` picked
  automatically for coherent noise; it twirled a reset there before, which
  dephases about twice as fast. `Stabilizer`, the GPU and QuEST engines and the
  other pure-state types still reset the qubit, and their twirl is unchanged.
- Declares `stim>=1.14` and `sinter>=1.16`, which it imports. They came only
  through `qoro-maestro[sinter]`, since Deltakit uses its own Stim fork
  (`deltakit-stim`) from 0.9.0. Sinter 1.14 needs `numpy<2`, and with Sinter
  1.15 `sinter.collect` fails on the numpy error counts Maestro reports. The
  test suite passes on Stim 1.14 with Sinter 1.16.
- The documentation is measured on Maestro 0.3.15: the example notebook is run
  again, since seeded noise on the matrix product state is drawn differently,
  and the guide's figures, the bond dimension table and the performance page
  follow it. Coherent noise gives 12–19% more detection events than its twirl
  in this run, where the 0.3.14 run gave 11–16%. The docs no longer say that
  Deltakit installs `ldpc`: `deltakit-explorer` dropped it in 0.9.2, and the
  `examples` extra installs it.

## [0.1.1]

- No upper bound on Python of its own: `requires-python` is now `>=3.10`, and
  Deltakit's own metadata sets the ceiling. 0.1.0 capped it at `<3.14`, which
  followed Deltakit 0.8 and 0.9; Deltakit 0.10.0 and 0.10.1 support 3.10 to
  3.14, and 0.10.2 supports 3.11 to 3.15. The test suite passes on 3.14, and CI
  now tests it.
- `examples/example_custom_noise_model.py`: build a custom `maestro.NoiseModel`
  from a Deltakit SI1000 circuit (a hot qubit and coupler, asymmetric readout,
  directed coherent over-rotations and ZZ crosstalk) and sample it with
  `MaestroCompiledSampler` and `sinter.collect`.
- A documentation site, at
  [qoroquantum.github.io/deltakit-maestro](https://qoroquantum.github.io/deltakit-maestro/),
  built with Sphinx: the README's overview, a guide, the example notebook with
  its plots, each example script with the output of a run made by the build, an
  API reference from the docstrings, and this changelog. The guide holds what
  the README used to cover in depth: the noise modes, the decoder's detector
  error model, coherent noise, the bond dimension, performance and gotchas. The
  Docs workflow builds the site on every pull request, failing on any Sphinx
  warning or failing example, and publishes it from `main`.
  `pip install -e ".[docs,examples]"` installs what the build needs, and the
  README and the PyPI Documentation link point at the site.

## [0.1.0]

First release.

- `MaestroBackend` adapter for Riverlane Deltakit QEC circuits and Stim circuits over `maestro.sinter`.
- Every run is simulated by Maestro (`qoro-maestro>=0.3.14`), with the simulation type
  picked from the noise:
  - Pauli-only and noiseless runs on `Stabilizer`, which samples them on Pauli frames.
  - T1 decay without coherent noise on `Stabilizer`, shot by shot (T1 is not a Pauli
    channel).
  - Coherent over-rotations on `MatrixProductState` (MPS).
  - An explicit `simulation_type` overrides the choice. The chosen type is pinned
    (`fixed_backend=True`), so Maestro does not swap it for Pauli frames; pass
    `fixed_backend=False` to allow that.
- Shots come back in random order, so any slice of them is a fair sample.
- Noise model translation:
  - Extracts gate noise, idle noise, reset noise, and readout errors from Deltakit circuits.
  - Supports Pauli twirling of coherent channels and hardware noise layers for detector error model (DEM) generation.
- Sinter integration:
  - `as_sinter_task` produces Sinter-compatible tasks with matched DEMs and JSON metadata.
  - `sinter_decoders` provides configured decoders (including PyMatching).
  - `compile_sampler` for direct sampling of detection events and observable flips.
- Source distribution packaging includes the full test suite and examples, verified with `scripts/verify_dist.py`.
- Supports Python 3.10 to 3.13 on macOS and Linux.

