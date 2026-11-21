# Changelog

## [Unreleased]

- A "When to use Maestro" page opens the guide, and the README gains a short
  "When to use it" section: deltakit-maestro is for noise that isn't a Pauli
  channel (coherent over-rotations, `T1` decay, hardware-shaped noise models),
  and for measuring what its Pauli twirl misses. For Pauli noise alone, Stim is
  faster on x86.
- A Benchmarks section in the documentation, with the scripts behind it and
  their results in `benchmarks/`:
  - Coherent noise on the matrix product state against its Pauli twirl on
    Stim, decoded alike (`benchmarks/coherent.py`). The twirl underestimates
    the logical error rate by 17–40% on the rotated d=3 surface code, most at
    the weakest noise, and on repetition codes by more the larger the code, up
    to 45% at d=15: it overstates the error-suppression factor Λ by about the
    6–9% excess of detection events.
  - Pauli noise plus a small coherent part on Maestro's extended stabilizer,
    pruned with `extended_stabilizer_amplitude_tolerance`
    (`benchmarks/extended.py`; needs Maestro 0.3.16): against an exact
    statevector on the rotated d=3 code, and against its Pauli twirl on
    surface codes up to d=7 (97 qubits) and the [[72,12,6]] bivariate bicycle
    code (144 qubits), past what a statevector or an MPS holds. A coherent
    part a quarter the size of SI1000(0.002)'s gate noise gives 5–9% more
    detection events than its twirl, and at d=5 at least 16% more logical
    errors. Measured on a `c4-standard-32`.
  - `T1` decay on Maestro's stabilizer, shot by shot, against its Pauli twirl
    on the [[72,12,6]] and [[144,12,12]] bivariate bicycle codes (144 and 288
    qubits), decoded alike by BP-LSD (`benchmarks/qldpc.py`, with the decoder
    chosen by `benchmarks/qldpc_decoders.py`). The twirl gives 6–9% more
    detection events in the first round, while the data qubits are in |0⟩,
    under 1% more over all rounds, and the same logical error rates within
    sampling error. `benchmarks/common.py` gains Sinter decoders for `ldpc`'s BP-OSD and
    BP-LSD that Maestro's sampler can compile.
  - Maestro's stabilizer against Stim: detection-event throughput on one
    thread, on surface, repetition, toric and bivariate bicycle codes under
    Deltakit's SI1000, SD6 and Toy noise, and logical error rates under
    `sinter.collect` on the rotated surface code, d=3 to 7. The logical error
    rates agree at all 54 points. On x86 Stim samples detection events 1.4–2.6×
    faster: Maestro draws measurements faster, but converting them to
    detection events costs more than drawing them. On Apple Silicon, where
    Stim's wheel has no SIMD build, the two are even.
  - Maestro's matrix product state against an exact statevector under coherent
    noise and `T1` decay, and against Stim under Pauli noise as a correctness
    check; its convergence in the bond dimension; and its cost against a
    statevector's on repetition codes past what a statevector can hold.
  - Measured on a Google Cloud `c2-standard-30` (Intel Cascade Lake) with
    Maestro 0.3.16.
- The Bond dimension page says that coherent noise with `T1` decay needs more
  than the default χ=32 on the rotated d=3 code: with SI1000(0.005) and
  `t1=0.005` it needs χ=48, and at χ=32 gives 9% too many detection events.
- The README, the Simulation types page and the Performance page no longer
  say Pauli frames are as fast as Stim: Stim is faster on x86, and the two are
  even on Apple Silicon. The Performance page's table gives both, and a new
  section says how to run several samplers on a large machine.
- The Bond dimension page, `example_bond_dimension.py` and the coherent noise
  notebook cover the codes the docs check the matrix product state on: the
  rotated d=3 surface code and repetition codes. The table of other codes, and
  the unrotated d=3 code in the example, are gone.
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

