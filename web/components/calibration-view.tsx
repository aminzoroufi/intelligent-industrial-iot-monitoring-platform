// SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
// SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available

"use client";

import { useState, type FormEvent } from "react";
import { apiRequest, formatUtc } from "@/lib/api";
import type { Calibration } from "@/lib/types";

const DEVICE_ID = "motor-01";

export function CalibrationView({ initialRecords }: { initialRecords: Calibration[] }) {
  const [records, setRecords] = useState<Calibration[]>(initialRecords);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [busy, setBusy] = useState(false);
  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(""); setSuccess("");
    const form = event.currentTarget; const data = new FormData(form);
    const coefficients: Record<string, number> = { scale: Number(data.get("scale")), offset: Number(data.get("offset")) };
    try {
      const record = await apiRequest<Calibration>(`devices/${DEVICE_ID}/calibrations`, { method: "POST", body: JSON.stringify({ sensor: data.get("sensor"), new_coefficients: coefficients, reason: data.get("reason") }) });
      setRecords((current) => [record, ...current]); setSuccess(`Calibration ${record.id} recorded and audited.`); form.reset();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Calibration failed"); } finally { setBusy(false); }
  }

  return <main className="page">
    <header className="page-header"><div><p className="eyebrow">Calibration control</p><h1>Coefficients with a visible history.</h1><p>Administrative workflow for motor-01. Every change retains previous values, reason, operator, and UTC time.</p></div></header>
    <div className="section-grid"><section className="panel"><div className="panel-header"><div><h2>Record calibration</h2><p>Scale 0.1–10 · offset −100–100</p></div></div>
      <form className="stack-form" onSubmit={create}>{error ? <div className="notice danger" role="alert">{error}</div> : null}{success ? <div className="notice info" role="status">{success}</div> : null}
        <label><span>Sensor</span><select name="sensor" required><option value="temperature">Temperature</option><option value="vibration">Vibration</option><option value="current">Current</option></select></label>
        <div className="form-grid"><label><span>Scale</span><input name="scale" type="number" min="0.1" max="10" step="0.0001" defaultValue="1" required /></label><label><span>Offset</span><input name="offset" type="number" min="-100" max="100" step="0.0001" defaultValue="0" required /></label></div>
        <label><span>Reason</span><textarea name="reason" minLength={4} maxLength={240} placeholder="Reference instrument and observed deviation" required /></label>
        <button className="button primary" type="submit" disabled={busy}>{busy ? "Recording…" : "Record audited calibration"}</button>
      </form></section>
      <section className="panel"><div className="panel-header"><div><h2>Calibration history</h2><p>{records.length} retained records · newest first</p></div></div>
        <div className="table-wrap"><table><thead><tr><th>UTC</th><th>Sensor</th><th>Previous → new</th><th>Operator / reason</th></tr></thead><tbody>{records.map((record) => <tr key={record.id}><td>{formatUtc(record.performed_at)}</td><td>{record.sensor}</td><td className="mono">{JSON.stringify(record.previous_coefficients)}<br />→ {JSON.stringify(record.new_coefficients)}</td><td>{record.operator}<br /><span className="faint">{record.reason}</span></td></tr>)}</tbody></table></div>
        {records.length === 0 ? <div className="empty-state"><strong>No calibration records</strong>The first approved coefficient change will establish the history.</div> : null}
      </section></div>
  </main>;
}
