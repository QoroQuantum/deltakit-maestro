# Examples

A notebook and six scripts, from the repository's
[examples/](https://github.com/QoroQuantum/deltakit-maestro/tree/main/examples)
folder. To run them, install the `examples` extra from the repository root and
run any script from there:

```bash
pip install -e ".[examples]"
python examples/example_coherent_noise.py
```

The notebook also needs `matplotlib` and Jupyter. Each script's page shows the
output of the run that built these pages, so the numbers on it are current. The
test suite also runs the noise modes, Stim circuit and coherent noise scripts.

```{figure} ../_generated/coherent_vs_twirl.png
:alt: Two plots against noise strength p. Left, logical error probability: coherent noise is highest at every p, then its Pauli twirl, then SI1000. Right, the ratio of coherent noise to its twirl, between 1.1 and 1.3.
:target: coherent_noise_d3.html

From the notebook: coherent noise on the d=3 surface code against its Pauli
twirl and SI1000.
```

| Example | What it shows | Run time |
|---|---|---|
| [Coherent noise on a distance-3 surface code](coherent_noise_d3.ipynb) | The notebook, with plots: coherent noise on the d=3 surface code against its Pauli twirl and SI1000, the χ check, a sweep of the logical error probability, and per-detector rates | ~40 s |
| [Noise modes](noise_modes.md) | How the noise is read from a circuit, split into gate and other noise, and what each `noise_type` and override runs, on which simulation type, for a Deltakit and a Stim-generated circuit | ~2 s |
| [A plain Stim circuit](stim_circuit.md) | Raw measurements, detection events, observable flips, seeds, decoding by hand and `sinter.collect` on a Stim circuit, without Deltakit | ~1 s |
| [Coherent noise on a repetition code](coherent_noise.md) | Coherent over-rotation against its Pauli twirl: about 1.5× the logical errors and detection events | ~3 s |
| [A surface code sweep](surface_code.md) | A d=3 Deltakit surface code: Pauli noise sampled directly and through `sinter.collect`, then coherent noise on an MPS against its twirl | ~12 s |
| [Every Deltakit code family](deltakit_codes.md) | Repetition, rotated and unrotated planar and toric codes with PyMatching, and the [[72,12,6]] bivariate bicycle code with BP-OSD | ~20 s |
| [Bond dimension](bond_dimension.md) | Setting the MPS bond dimension χ, the noiseless truncation check, and coherent noise converging in χ | ~50 s |

Times are on a 12-core laptop. Stim's own sampler appears in a few examples only
as an independent reference that Maestro's results agree with.

```{toctree}
:hidden:

coherent_noise_d3
noise_modes
stim_circuit
coherent_noise
surface_code
deltakit_codes
bond_dimension
```
