# Contributing to deltakit-maestro

Thanks for helping. Bug reports and feature requests are welcome as
[issues](https://github.com/QoroQuantum/deltakit-maestro/issues). Everyone taking
part follows the [Code of Conduct](CODE_OF_CONDUCT.md).

## We don't accept pull requests

Qoro Quantum holds the copyright to all the code in this repository, so we don't
merge code written by anyone outside Qoro Quantum. Pull requests from outside
contributors are closed without review. If you've found the cause of a bug,
describe it in words in an issue rather than as a patch, and we'll write the
fix.

## Reporting a problem

Open an issue at
[github.com/QoroQuantum/deltakit-maestro/issues](https://github.com/QoroQuantum/deltakit-maestro/issues)
with:

- a short circuit or script that shows the problem, and what you expected;
- the output of
  `python -c "import deltakit, deltakit_maestro, importlib.metadata as m; print(m.version('deltakit'), deltakit_maestro.__version__, m.version('qoro-maestro'))"`;
- for wrong results, the same circuit's result when simulated directly with Stim or Maestro.

If the problem is in Maestro itself rather than in the Deltakit adapter layer, the
[Maestro repository](https://github.com/QoroQuantum/maestro) is the place for it.

## Development setup

This is how maintainers work on the package, and it's also useful for
reproducing a problem before you report it.

```bash
git clone https://github.com/QoroQuantum/deltakit-maestro
cd deltakit-maestro
python -m venv .venv && source .venv/bin/activate
pip install -e ".[test,examples]" ruff
pytest
```

The repository is laid out as:

```
pyproject.toml
src/deltakit_maestro/
  maestro_backend.py    MaestroBackend, SimulationResult, Sinter glue
  noise.py              noisy Stim circuit ↔ maestro.NoiseModel and its Pauli twirl
examples/               example scripts and the coherent_noise_d3.ipynb notebook
docs/                   the documentation site
tests/
```

## Building the docs

The documentation in `docs/` is a Sphinx site with the
[Furo](https://pradyunsg.me/furo/) theme in Qoro's colours, as the Maestro docs
are, published at
[qoroquantum.github.io/deltakit-maestro](https://qoroquantum.github.io/deltakit-maestro/).
To build it:

```bash
pip install -e ".[docs,examples]"
sphinx-build -W --keep-going -b html docs docs/_build/html
```

Then open `docs/_build/html/index.html`. The first build runs every example
script, which takes a minute or two; later builds rerun a script only when it,
the package, or the version of Deltakit, Maestro, Stim or Sinter changes. Some
pages come from files outside `docs/`, so each is edited in one place:

- the home page shows `README.md` between its `start-docs` and `end-docs`
  markers, and the Changelog page shows `CHANGELOG.md`;
- each example page shows a script from `examples/` and the output of running
  it, which the build saves in `docs/_generated/`. A script that fails fails
  the build. A new script needs its own page in `docs/examples/` and a row in
  `docs/examples/index.md`;
- the build copies `examples/coherent_noise_d3.ipynb` in and shows it with its
  saved outputs, without running it. The guide shows three of its figures,
  found by cell id in `NOTEBOOK_FIGURES` in `docs/conf.py`, so if you replace
  one of those cells, update its id there;
- the API reference, `docs/api.rst`, takes the docstrings, but lists the
  members it shows, so add new public functions and methods there.

The Docs workflow (`.github/workflows/docs.yml`) builds the site on every pull
request into `main` and every push to it, failing on any Sphinx warning, and
publishes it to GitHub Pages from `main`.

## Making a change (maintainers)

- Start every new source file with the SPDX header:

  ```python
  # SPDX-FileCopyrightText: 2026 Qoro Quantum
  # SPDX-License-Identifier: GPL-3.0-or-later
  ```

- Run `ruff check .` and `ruff format .` before opening a pull request, and
  add a line to [CHANGELOG.md](CHANGELOG.md) under "Unreleased".

## Releasing (maintainers)

1. Move the "Unreleased" changelog entries under a new version heading.
2. Set `version` in `pyproject.toml` to match.
3. Publish a GitHub release for the tag `vX.Y.Z`. The publish workflow checks the
   tag against `pyproject.toml`, runs the tests, builds and verifies the
   distributions, and uploads them to PyPI through trusted publishing. To
   publish by hand, or to dry-run the build without uploading, use "Run
   workflow" on the Publish to PyPI workflow in the Actions tab.

