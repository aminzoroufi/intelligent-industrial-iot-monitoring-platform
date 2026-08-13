# Hardware design status

Revision `A0-UNVERIFIED` is an editable engineering review package for the
extra-low-voltage demonstrator. It is not fabrication-ready. Do not order a PCB,
assemble it, or connect a load from these files until the review gates in
`fabrication/fabrication-status.json` are completed and independently checked.

The canonical, machine-readable source is `design.json`. It records the board
envelope, selected manufacturer part numbers, ratings, placement, pin/net
intent, safety policy, and which 3D shapes are dimensional engineering envelopes
rather than official component models. Run:

```sh
.venv/bin/python scripts/generate_hardware_artifacts.py
.venv/bin/python scripts/generate_hardware_artifacts.py --check
```

The generator creates the BOM, placement, editable KiCad review sources,
mechanical envelopes, FreeCAD rebuild macro, preview SVGs, and review-only
fabrication files. The generation check verifies metadata and model checksums;
it does not substitute for electrical or layout verification.

## Circuit intent

- 5 V SELV/PELV input through resettable overcurrent, polarity, transient, and
  bulk-decoupling stages;
- AP2112K 3.3 V rail with local bulk and high-frequency decoupling;
- ESP32-WROOM-32E gateway with explicit enable/boot bias and UART header;
- TMP117 temperature, INA219 high-side current, 50 mΩ/1 W shunt, and ADXL345
  SPI vibration sensor with interrupt;
- MAX3485 3.3 V half-duplex RS-485, SM712 clamp, selectable 120 Ω termination,
  optional 680 Ω bias, ground reference, and bus test points;
- AO3400A low-side 5 V relay-coil driver, gate resistor/pull-down, and SS14
  flyback diode;
- relay COM/NO connector restricted by project policy to 30 VDC and 2 A. It
  must never switch mains, implement an emergency stop, or control a hazardous
  load.

## KiCad boundary

`iiot-monitor.kicad_pcb` is an editable KiCad board review placement. The
schematic is deliberately retained in KiCad legacy v4 form with a project cache
library because `kicad-cli` is unavailable here; KiCad 10 must import and save it
as `.kicad_sch`. The board is un-routed. Custom review footprints and every pin
mapping must be replaced or verified against current official datasheets and
manufacturer land patterns.

The checked-in ERC/DRC reports say `NOT RUN` and are not passes. The Gerber-like
review set contains outline/status geometry only; copper production geometry is
intentionally absent. After schematic migration, symbol/footprint review,
routing, and actual zero-unexplained-violation ERC/DRC, regenerate outputs with
KiCad 10.0.4 and replace the reports with raw tool output.

## Mechanical and provenance boundary

The project-authored ESP32 and relay STEP files are only datasheet-sized
engineering envelopes. They are visibly named `-envelope`, recorded with source
URL and checksum in `model-provenance.csv`, and must not be described as vendor
3D models. The board assembly STEP is likewise a placement/clearance envelope,
not a KiCad component-accurate export.

`enclosure/iiot-enclosure.FCMacro` is the editable FreeCAD rebuild source.
Project-generated STEP/STL review geometry uses the same board-derived
dimensions. FreeCAD is unavailable in the current environment, so no `.FCStd`
save or FreeCAD-vs-export comparison is claimed.
