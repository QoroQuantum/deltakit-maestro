# Noise modes

How `MaestroBackend` reads the noise in a circuit, splits off the gate noise from
the rest, and what each `noise_type` and override runs, on which simulation type,
for a Deltakit circuit and a Stim-generated one. The [Noise](../guide/noise.md) page
of the guide explains each step.

```bash
python examples/example_noise_modes.py
```

## Output

From the run that built these pages, so the timings are the build machine's.

```{literalinclude} ../_generated/example_noise_modes.txt
:language: text
```

## Source

```{literalinclude} ../../examples/example_noise_modes.py
:language: python
:caption: examples/example_noise_modes.py
:start-at: '"""'
```
