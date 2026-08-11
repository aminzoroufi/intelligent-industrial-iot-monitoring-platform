# ADR 0008: Deterministic simulation and editable CAD

Status: accepted — 2026-08-11

Host fixtures and Wokwi provide repeatable fault scenarios while production
drivers retain actual register behavior. KiCad 10 is the editable ECAD source
and FreeCAD is the editable enclosure source. Generated artifacts are retained
only when reproducible from those sources. Every 3D model requires provenance;
an unavailable vendor model is represented only by a clearly labeled,
datasheet-sized engineering envelope. Simulation cannot validate analog
fidelity, RF, flash wear, interrupt jitter, or RS-485 electrical margins.

