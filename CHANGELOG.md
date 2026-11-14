# Changelog

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

