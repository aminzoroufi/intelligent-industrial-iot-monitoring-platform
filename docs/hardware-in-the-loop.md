# Low-voltage hardware-in-the-loop procedure

Status: not executed; no physical hardware was supplied.

This procedure applies only after a reviewed PCB revision has passed ERC, DRC,
assembly inspection, continuity checks, and a current-limited power-up. Revision
`A0-UNVERIFIED` is not eligible.

## Equipment and boundary

- isolated 5 V laboratory supply with adjustable current limit and physical
  output switch;
- oscilloscope, DMM, logic analyzer, and USB-to-3.3 V UART adapter;
- protected low-voltage DC demo load and independent fuse;
- second RS-485 node or isolated USB/RS-485 adapter;
- vibration fixture that cannot eject parts and temperature reference that stays
  within component and handling limits.

Never connect mains. The relay is not an emergency stop, interlock, protective
device, or permission to energize equipment. Keep a physical means to remove
actuator power.

## Ordered checks

1. Inspect polarity, shorts, component orientation, shunt, TVS, flyback diode,
   relay isolation distance, and connector labels with power removed.
2. Measure input-to-ground resistance. Power at 5 V with a 100 mA current limit,
   then raise the limit only after the 3.3 V rail is stable and no part heats.
3. Record 5 V/3.3 V rail min/max during ESP32 Wi-Fi association and relay
   switching; inspect reset reason and brownout counters.
4. Compare TMP117 readings with a traceable reference at three safe points.
   Record raw, previous, and updated calibration coefficients.
5. Apply known DC current through the shunt at zero and at least three load
   points below 2 A. Compare DMM and INA219 values without exceeding shunt power.
6. Check ADXL345 identity, data-ready interrupt rate, stationary noise, axis
   orientation, and response on the guarded vibration fixture.
7. Inspect RS-485 A/B waveforms and DE timing with termination disabled and then
   enabled only at the two bus ends. Exercise valid, CRC-error, exception,
   timeout, and disconnected-node cases.
8. Drive only the fused low-voltage demo relay load. Verify default OFF, command
   expiry, bounded auto-off, flyback behavior, reboot safe state, and MQTT
   acknowledgement for ON/OFF.
9. Disconnect network access long enough to fill/replay the documented queue;
   power-cycle at controlled journal points and check ordering/loss counters.
10. Inject the named firmware scenarios, task stall, and repeated reset. Confirm
    watchdog recovery does not create a reboot loop.

For every run, retain board revision/serial, firmware SHA, equipment IDs,
calibration dates, setup photo, raw measurements, expected tolerances, result,
operator, UTC time, and anomalies. Only actual retained evidence may change a
verification level to `BENCH-VERIFIED`.
