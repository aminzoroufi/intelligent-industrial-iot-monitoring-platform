# Authenticated operations workflows

All examples are for the local, simulated, extra-low-voltage demonstrator. The
relay command is not a safety function and does not authorize connection to
mains voltage or uncontrolled machinery.

## Roles and audit behavior

Authenticated operators can view fleet, telemetry, alarms, calibrations,
maintenance, thresholds, commands, and bounded CSV exports. Administrators are
required to change thresholds, create calibrations, and issue relay commands.
Alarm acknowledgements, calibration changes, maintenance changes, threshold
updates, command issuance, and device acknowledgements create durable audit
events.

## Live browser connection

After obtaining an OAuth access token, create the browser socket with a bearer
subprotocol pair:

```js
const socket = new WebSocket("ws://localhost:8000/api/v1/ws", ["bearer", accessToken]);
socket.addEventListener("message", (event) => {
  const update = JSON.parse(event.data);
  console.log(update.type, update);
});
```

The server negotiates `bearer`. It emits `telemetry`, `health`,
`alarm_acknowledged`, and `command_ack` events. The access token is deliberately
absent from the URL so routine access logging does not record it.

## Alarm and threshold behavior

Each metric has warning and critical thresholds. A reading opens or updates one
active alarm per device and metric. The alarm clears only after the value drops
below the warning threshold by the configured hysteresis percentage. An
acknowledgement records the operator but does not clear an active condition.

## Relay behavior

The API first writes the command and audit event, then publishes a short-lived,
device-addressed MQTT command. The simulated gateway validates identity,
expiry, command kind, and bounded parameters. It starts OFF, reports the applied
state, automatically returns to OFF after an ON timeout, and forces OFF on
disconnect or shutdown. The API command record is authoritative for delivery
status; an HTTP `202` alone is not proof that a device applied a command.

## CSV export boundaries

Exports require authentication, one allow-listed metric, at most 31 days, and
at most 10,000 rows. Text fields that could be interpreted as spreadsheet
formulas are prefixed before serialization. Timestamps are UTC ISO-8601 values.
