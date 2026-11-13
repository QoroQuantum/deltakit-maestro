# SPDX-FileCopyrightText: 2026 Qoro Quantum
# SPDX-License-Identifier: GPL-3.0-or-later

"""Sphinx configuration for the deltakit-maestro documentation.

Build from the repository root:

    pip install -e ".[docs,examples]"
    sphinx-build -W --keep-going -b html docs docs/_build/html

The API reference imports ``deltakit_maestro``, so the package must be installed.
The build also runs the example scripts, which need the ``examples`` extra.
"""

import base64
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
from importlib.metadata import version as installed_version

DOCS = pathlib.Path(__file__).resolve().parent
ROOT = DOCS.parent
EXAMPLES = ROOT / "examples"
# What the build makes from examples/: the scripts' output and the notebook's figures.
GENERATED = DOCS / "_generated"
GENERATED.mkdir(exist_ok=True)

project = "deltakit-maestro"
author = "Qoro Quantum"
copyright = "2026, Qoro Quantum"
release = installed_version("deltakit-maestro")
version = release

extensions = [
    "myst_nb",
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",
    "sphinx_copybutton",
]

exclude_patterns = ["_build", "_generated", "jupyter_execute"]

myst_enable_extensions = ["colon_fence", "dollarmath"]
myst_heading_anchors = 3

# The example notebook lives in examples/ with the scripts, outside the source
# tree, so copy it in. It's shown with the outputs saved in it rather than run
# again: its text quotes those outputs.
NOTEBOOK = "coherent_noise_d3.ipynb"
shutil.copy2(EXAMPLES / NOTEBOOK, DOCS / "examples")
nb_execution_mode = "off"

# The guide shows some of the notebook's figures, each the image output of the
# cell with that id.
NOTEBOOK_FIGURES = {
    "b3b27928": "bond_dimension_check.png",
    "bd3c9d43": "coherent_vs_twirl.png",
    "43dc4733": "coherent_per_detector.png",
}


def _save_notebook_figures():
    notebook = json.loads((EXAMPLES / NOTEBOOK).read_text())
    cells = {cell.get("id"): cell for cell in notebook["cells"]}
    for cell_id, name in NOTEBOOK_FIGURES.items():
        outputs = cells[cell_id].get("outputs", []) if cell_id in cells else []
        images = [out["data"]["image/png"] for out in outputs if "image/png" in out.get("data", {})]
        if len(images) != 1:
            raise RuntimeError(
                f"examples/{NOTEBOOK}: expected one figure in the cell with id {cell_id}, "
                f"found {len(images)}. Update NOTEBOOK_FIGURES in docs/conf.py."
            )
        (GENERATED / name).write_bytes(base64.b64decode(images[0]))


# Each example page shows its script's output from a run at build time, so a
# broken example fails the build. A run is reused until the script, the package,
# or the version of a library it runs on changes. Each script takes under a
# minute, so one still running after the timeout has hung.
EXAMPLE_TIMEOUT = 300


def _run_examples():
    package = b"".join(
        path.read_bytes() for path in sorted((ROOT / "src" / "deltakit_maestro").glob("*.py"))
    )
    versions = " ".join(
        installed_version(name) for name in ("deltakit", "qoro-maestro", "stim", "sinter")
    )
    for script in sorted(EXAMPLES.glob("example_*.py")):
        output = GENERATED / f"{script.stem}.txt"
        stamp = GENERATED / f"{script.stem}.sha256"
        key = hashlib.sha256(script.read_bytes() + package + versions.encode()).hexdigest()
        if output.exists() and stamp.exists() and stamp.read_text() == key:
            continue
        print(f"running examples/{script.name}", flush=True)
        try:
            run = subprocess.run(
                [sys.executable, "-u", str(script)],
                check=False,  # A failure is reported below, with the script's output.
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=EXAMPLE_TIMEOUT,
            )
        except subprocess.TimeoutExpired as timeout:
            raise RuntimeError(
                f"examples/{script.name} was still running after {EXAMPLE_TIMEOUT} s:\n"
                f"{(timeout.output or '')[-3000:]}"
            ) from None
        if run.returncode:
            raise RuntimeError(
                f"examples/{script.name} failed with exit code {run.returncode}:\n"
                f"{run.stdout[-3000:]}"
            )
        output.write_text(run.stdout)
        stamp.write_text(key)


_save_notebook_figures()
_run_examples()

# API reference. Docstrings are Google style. api.rst lists the members to show.
autodoc_default_options = {"member-order": "bysource"}
autodoc_typehints = "description"
autodoc_typehints_description_target = "documented_params"
# Show defaults as written, e.g. maestro.SimulatorType.QCSim rather than its repr.
autodoc_preserve_defaults = True
add_module_names = False
napoleon_google_docstring = True
napoleon_numpy_docstring = False

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "numpy": ("https://numpy.org/doc/stable", None),
    "maestro": ("https://qoroquantum.github.io/maestro", None),
}

# Theme. Matches the Maestro, PennyLane-Maestro and Divi docs: Furo with Qoro's
# brand colours and fonts.
html_theme = "furo"
html_title = f"{project} {release}"
html_favicon = "_static/favicon.ico"
html_theme_options = {
    "navigation_with_keys": True,
    "source_repository": "https://github.com/QoroQuantum/deltakit-maestro/",
    "source_branch": "main",
    "source_directory": "docs/",
    "light_css_variables": {
        "color-brand-primary": "#CC3366",
        "color-brand-content": "#CC3366",
        "font-stack": "Poppins, sans-serif",
        "font-stack--headings": "Poppins, sans-serif",
        "font-stack--monospace": "ui-monospace, 'Cascadia Code', 'Source Code Pro', Menlo, Consolas, 'Liberation Mono', monospace",
    },
    "dark_css_variables": {
        "color-brand-primary": "#FDB9FD",
        "color-brand-content": "#FDB9FD",
        "color-background-primary": "#131313",
        "color-background-secondary": "#1a1a1a",
        "color-foreground-primary": "#E9EEF6",
    },
}
pygments_style = "sphinx"
pygments_dark_style = "monokai"
# toc-scroll-room.js keeps the "On this page" highlight on the section clicked.
html_static_path = ["_static"]
html_js_files = ["toc-scroll-room.js"]

# GitHub renders README anchors client-side, so linkcheck can't see them.
linkcheck_anchors_ignore_for_url = [r"https://github\.com/"]
