// SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
// SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available

"use client";

import { useState } from "react";
import { apiRequest } from "@/lib/api";
import type { Command } from "@/lib/types";
import { StatusBadge } from "@/components/status-badge";

export function RelayControl({ deviceId, commands, onIssued }: { deviceId: string; commands: Command[]; onIssued: (command: Command) => void }) {
  const [confirmed, setConfirmed] = useState(false);
  const [timeout, setTimeoutValue] = useState(5);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const latest = commands[0];

  async function issue(relayOn: boolean) {
    setBusy(true);
    setError("");
    try {
      const command = await apiRequest<Command>(`devices/${deviceId}/commands/relay`, {
        method: "POST",
        body: JSON.stringify({ relay_on: relayOn, timeout_s: relayOn ? timeout : 1 }),
      });
      onIssued(command);
      if (relayOn) setConfirmed(false);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Command failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="content-stack">
      <div className="safety-callout"><strong>Demo actuator only.</strong> The relay is not an interlock. Keep a physical power-isolation control within reach.</div>
      {error ? <div className="notice danger" role="alert">{error}</div> : null}
      {latest ? <div className="device-card-top"><span className="muted">Latest: {latest.result_code ?? latest.status}</span><StatusBadge status={latest.status} /></div> : null}
      <label className="field"><span>Automatic OFF timeout (seconds)</span><input type="number" min="1" max="30" value={timeout} onChange={(event) => setTimeoutValue(Number(event.target.value))} /></label>
      <label className="field"><span><input style={{ width: "auto", marginRight: "0.55rem" }} type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} />I confirm this is the low-voltage simulated demo.</span></label>
      <div className="inline-actions">
        <button className="button danger-button" type="button" disabled={busy || !confirmed} onClick={() => void issue(true)}>Relay ON</button>
        <button className="button" type="button" disabled={busy} onClick={() => void issue(false)}>Force OFF</button>
      </div>
    </div>
  );
}
