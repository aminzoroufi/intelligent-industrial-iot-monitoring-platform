# Deterministic scenarios

All scenarios are synthetic and use a fixed pseudo-random seed. `normal` keeps
signals inside the reference envelope. The other named scenarios introduce one
controlled change at a time: temperature ramp, vibration growth, current ramp,
or a stuck temperature value. These are reproducibility fixtures, not evidence
of field performance or mechanical root cause.

Run a scenario against the local broker with:

```sh
.venv/bin/python -m simulator.telemetry_generator.main normal
```

