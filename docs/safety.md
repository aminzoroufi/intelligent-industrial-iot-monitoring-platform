# Electrical and operational safety boundary

The reference setup is extra-low-voltage DC only. The relay output is a demo
actuator and is not a safety interlock.

- Never connect the PCB, relay contacts, or measurement front end directly to
  mains voltage.
- Use a current-limited, isolated bench supply appropriate to the selected DC
  motor and board ratings.
- Place a clearly labeled, directly accessible switch in series with actuator
  power so the operator can remove energy without software.
- Power down before altering wiring. Verify polarity and current-shunt ratings.
- Keep rotating parts guarded and secure the motor to a stable fixture.
- Treat temperature and vibration fault injection as controlled demonstrations;
  do not intentionally damage equipment.
- Relay firmware boots OFF, commands expire quickly, and loss of communication
  never energizes the output.

Any move beyond the documented bench requires an electrical, mechanical,
cybersecurity, and functional-safety assessment by qualified people.

