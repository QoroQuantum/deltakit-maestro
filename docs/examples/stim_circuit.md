# A plain Stim circuit

`MaestroBackend` without Deltakit, on a distance-5 repetition code built by Stim:
a noiseless comparison with Stim, the structure of `simulate`'s result, seeds,
decoding by hand with PyMatching, and a `sinter.collect` sweep. See
[Sampling and Sinter](../guide/sampling.md).

```bash
python examples/example_stim_circuit.py
```

## Output

From the run that built these pages, so the timings are the build machine's.

```{literalinclude} ../_generated/example_stim_circuit.txt
:language: text
```

## Source

```{literalinclude} ../../examples/example_stim_circuit.py
:language: python
:caption: examples/example_stim_circuit.py
:start-at: '"""'
```
