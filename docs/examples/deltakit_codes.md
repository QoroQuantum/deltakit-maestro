# Every Deltakit code family

Each of Deltakit's code families through `MaestroBackend` unchanged: repetition,
rotated and unrotated planar, and toric codes decoded with PyMatching, and the
[[72,12,6]] bivariate bicycle code, whose errors aren't graphlike, decoded with
BP-OSD. See [The decoder's detector error model](../guide/decoding.md#codes-whose-errors-arent-graphlike).

```bash
python examples/example_deltakit_codes.py
```

## Output

From the run that built these pages, so the timings are the build machine's.

```{literalinclude} ../_generated/example_deltakit_codes.txt
:language: text
```

## Source

```{literalinclude} ../../examples/example_deltakit_codes.py
:language: python
:caption: examples/example_deltakit_codes.py
:start-at: '"""'
```
