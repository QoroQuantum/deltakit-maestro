# A surface code sweep

A d=3 rotated surface code from Deltakit under SI1000 noise: Pauli noise sampled
directly and checked against Stim, a `sinter.collect` sweep over four workers, and
coherent noise on an MPS against its Pauli twirl.

```bash
python examples/example_surface_code.py
```

## Output

From the run that built these pages, so the timings are the build machine's.

```{literalinclude} ../_generated/example_surface_code.txt
:language: text
```

## Source

```{literalinclude} ../../examples/example_surface_code.py
:language: python
:caption: examples/example_surface_code.py
:start-at: '"""'
```
