# Noise

`MaestroBackend` reads the noise from the circuit, so you don't build a
`maestro.NoiseModel`. Maestro runs the circuit's own Stim noise, and
`noise_type` and the noise keywords say what to add to it or replace.
[examples/example_noise_modes.py](../examples/noise_modes.md) shows each step
on a Deltakit circuit and a Stim-generated one.

## The circuit's own noise

Maestro executes Stim's Pauli noise channels (`DEPOLARIZE1/2`, `X/Y/Z_ERROR`,
`PAULI_CHANNEL_1/2`) and measurement flips (`M(p)`) natively in the circuit. So
with the default `noise_type='pauli'` and no overrides, a noisy circuit (SI1000,
for example) runs with exactly its own noise.

## Noise types

`noise_type` controls how errors are realised:

| `noise_type` | Gate & circuit errors |
|---|---|
| `'pauli'` | exact in-circuit Stim Pauli & readout noise (or replacement gate noise when `p_1q`/`p_2q` are overridden, and readout when `readout_error` is), sampled on Pauli frames |
| `'coherent'` | gate depolarizing replaced by isotropic coherent over-rotation, ε = 2·arcsin√p about a body diagonal after every gate; idle, reset and readout noise kept |
| `'full'` | circuit noise and coherent over-rotation both |
| `'none'` | none (noiseless) |

Readout error applies in every mode except `'none'`. [Coherent
noise](coherent_noise.md) describes the over-rotation in more detail.

## Overriding the rates

The noise keywords override or extend the rates read from the circuit:

| Keyword | Meaning |
|---|---|
| `p_1q` | depolarizing probability after single-qubit gates |
| `p_2q` | two-qubit depolarizing probability after two-qubit gates |
| `readout_error` | symmetric measurement flip probability |
| `t1` | per-gate `T1` decay probability γ |
| `coherent` | infidelity of the coherent over-rotation; defaults to `p_2q` |

```python
backend.simulate(noisy, 1000, noise_type='full', coherent=0.002, t1=1e-4)
```

Unknown keywords raise `TypeError`, and keywords the `noise_type` never reads
raise `ValueError`, before anything is sampled: `'pauli'` doesn't read
`coherent`, `'coherent'` doesn't read `p_1q`, and `'none'` reads none of them.

`coherent` sets the strength of the over-rotation that `'coherent'` puts in
place of the gate noise and `'full'` adds to it. `t1` adds `T1` decay to
whatever runs, after every gate: `DensityMatrix` and `MatrixProductOperator`
apply amplitude damping γ, and every other simulation type resets the qubit to
|0⟩ with probability γ.

## When the gate noise is replaced

When `noise_type` is `'coherent'`, or a Pauli rate (`p_1q`, `p_2q`,
`readout_error`) is overridden, the circuit's **gate noise** is removed with
{func}`~deltakit_maestro.strip_gate_noise` and the `maestro.NoiseModel`
supplies its replacement: the coherent over-rotation for `'coherent'`, and
otherwise depolarizing at the overridden rates:

| Stim (from Deltakit) | `maestro.NoiseModel` |
|---|---|
| `DEPOLARIZE2(p)` after two-qubit gates | `set_2q_depolarizing` on each pair |
| `DEPOLARIZE1(p)` after single-qubit gates | `set_all_1q_gate_depolarizing` |
| `M(p)`, only when `readout_error=` is overridden | `set_all_readout_error` |

Gate noise is the depolarizing whose qubit's latest operation was a gate of the
same arity. Deltakit places it after the next `TICK`, merged with the idle noise
of other qubits, so one instruction's targets are split: gate noise goes, idle
noise stays. Idle, reset (`X_ERROR`) and measurement (`M(p)`) noise always stay
in the circuit, and the rates come from the stripped instructions themselves. A
warning is raised if they differ across gates, since one rate replaces them
all. Only `DEPOLARIZE1/2` is treated as gate noise; other channels after gates
(`X_ERROR`, for example) stay in the circuit.

## Working with the noise directly

The functions `MaestroBackend` uses are public, for looking at a circuit's noise
yourself:

```python
from deltakit_maestro import build_noise_model, noise_params_from_stim, strip_gate_noise, to_stim

stim_circuit = to_stim(noisy)                 # a Deltakit SI1000(p=0.01) circuit
rates = noise_params_from_stim(stim_circuit)  # {'p_1q': 0.001, 'p_2q': 0.01, 'readout_error': 0.05}
clean_gates = strip_gate_noise(stim_circuit)  # the circuit without its gate noise
model = build_noise_model(clean_gates, 'coherent', p_2q=rates['p_2q'])
```

The [API reference](../api.rst) lists their arguments.
