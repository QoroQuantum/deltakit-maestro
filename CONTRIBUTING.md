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

