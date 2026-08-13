# Roadmap and known limitations

## Current release boundary

The repository is a software-complete, simulated engineering demonstrator. It
is not a V1 fabrication or field release. The API, ingestion, dashboard source,
detectors, telemetry/Modbus simulators, shared embedded logic, reports, and
review hardware artifacts are implemented. The verification report is the
authority for executed evidence.

Known gaps are deliberately not hidden:

- the ESP32 ESP-IDF target has not been compiled, measured, or run in Wokwi;
- the STM32 ARM target has not been compiled or run in Wokwi;
- the carrier is intentionally un-routed and the stored ERC/DRC reports say
  `NOT RUN`; current Gerber-like files are review artifacts, not build data;
- engineering-envelope STEP shapes are not component-accurate vendor models;
- no physical bench, environmental, EMC, isolation, endurance, or field data
  exists;
- the fixed live browser channel still needs a rebuilt Compose/Playwright run
  and a real screenshot;
- the GitHub workflows are source-validated locally but cannot pass until a
  repository is published and the hosted jobs actually execute;
- exact container tags are selected, but immutable image digests are a future
  supply-chain hardening step;
- the custom source-available license remains marked for legal review.

## Phase 1 — toolchain closure

Run shared C tests on Linux CI, compile ESP-IDF 6.0.2 with a size report, and
compile STM32CubeF1 1.8.6 with the pinned ARM toolchain. Run both Wokwi projects
and retain normal, sensor-fault, reconnect/replay, watchdog, CRC, and timeout
serial evidence. Exit when failures and skips are zero or explicitly waived by
a dated engineering decision.

## Phase 2 — native ECAD/MCAD and bench

Import the review schematic into KiCad 10, replace custom review constructs
with validated library items, complete the power/return/RS-485 layout, inspect
creepage and connector clearances, and pass ERC/DRC without unexplained waivers.
Use official vendor/KiCad models where licenses and part identity are verified,
then export the actual board STEP and regenerate the FreeCAD enclosure. Build
one extra-low-voltage prototype and execute the HIL guide with a directly
accessible actuator-power disconnect.

## Phase 3 — release and measured evaluation

Publish the pre-release, let CI run the clean Compose and desktop/mobile browser
flow, capture a source-traceable dashboard screenshot, and pin deployment image
digests. Collect a reviewed healthy baseline and named controlled faults from
the bench; report confidence intervals and false alarms without promoting the
result to field validation. Field validation requires a separate protocol,
site authorization, qualified safety review, and enough representative
operating time to support the claim.
