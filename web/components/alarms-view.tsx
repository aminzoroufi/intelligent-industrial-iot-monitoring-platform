// SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
// SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available

"use client";

import { useCallback, useState } from "react";
import { apiRequest, formatUtc } from "@/lib/api";
import type { Alarm, LiveEvent } from "@/lib/types";
import { useLiveSocket } from "@/lib/use-live-socket";
import { StatusBadge } from "@/components/status-badge";

export function AlarmsView({ initialAlarms }: { initialAlarms: Alarm[] }) {
  const [alarms, setAlarms] = useState<Alarm[]>(initialAlarms);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState<number | null>(null);

  const load = useCallback(async () => {
    try {
      setAlarms(await apiRequest<Alarm[]>("alarms?limit=200"));
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not load alarms");
    }
  }, []);

  const liveState = useLiveSocket(useCallback((event: LiveEvent) => {
    if (["telemetry", "alarm_acknowledged"].includes(event.type)) void load();
  }, [load]));

  async function acknowledge(id: number) {
    setBusyId(id);
    try {
      const updated = await apiRequest<Alarm>(`alarms/${id}/acknowledge`, { method: "POST", body: "{}" });
      setAlarms((current) => current.map((alarm) => alarm.id === id ? updated : alarm));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Acknowledgement failed");
    } finally {
      setBusyId(null);
    }
  }

  const active = alarms.filter((alarm) => alarm.state === "active");
  const history = alarms.filter((alarm) => alarm.state === "cleared");
  return (
    <main className="page">
      <header className="page-header"><div><p className="eyebrow">Alarm operations</p><h1>Conditions, acknowledgement, history.</h1><p>Acknowledging records operator awareness; it never clears an active physical or simulated condition.</p></div><div className="status-line"><span className={`status-dot ${liveState}`} />{liveState === "live" ? "Live alarm updates" : "Reconnecting"}</div></header>
      {error ? <div className="notice danger" role="alert">{error}</div> : null}
      <div className="section-grid">
        <section className="panel"><div className="panel-header"><div><h2>Active conditions</h2><p>{active.length} currently open</p></div></div>
          <div className="alarm-list">{active.map((alarm) => <article className="alarm-card" key={alarm.id}>
            <div className="alarm-top"><strong>{alarm.code.replaceAll("_", " ")}</strong><StatusBadge status={alarm.severity} /></div>
            <p>{alarm.summary}</p><footer><span>{alarm.device_id} · {formatUtc(alarm.opened_at)}</span>{alarm.acknowledged_at ? <span>Acknowledged by {alarm.acknowledged_by}</span> : <button className="button" type="button" disabled={busyId === alarm.id} onClick={() => void acknowledge(alarm.id)}>{busyId === alarm.id ? "Recording…" : "Acknowledge"}</button>}</footer>
          </article>)}</div>
          {active.length === 0 ? <div className="empty-state"><strong>No active alarms</strong>Threshold conditions will appear here with live updates.</div> : null}
        </section>
        <section className="panel"><div className="panel-header"><div><h2>Cleared history</h2><p>Newest first · retained for audit</p></div></div>
          <div className="table-wrap"><table><thead><tr><th>Opened UTC</th><th>Device</th><th>Condition</th><th>Acknowledgement</th></tr></thead><tbody>{history.map((alarm) => <tr key={alarm.id}><td>{formatUtc(alarm.opened_at)}</td><td className="mono">{alarm.device_id}</td><td>{alarm.code.replaceAll("_", " ")}<br /><span className="faint">cleared {formatUtc(alarm.cleared_at)}</span></td><td>{alarm.acknowledged_by ?? "Not acknowledged"}</td></tr>)}</tbody></table></div>
          {history.length === 0 ? <div className="empty-state"><strong>No cleared alarm history</strong>Cleared threshold conditions are retained here.</div> : null}
        </section>
      </div>
    </main>
  );
}
