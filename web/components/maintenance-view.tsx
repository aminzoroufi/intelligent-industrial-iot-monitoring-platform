// SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
// SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available

"use client";

import { useState, type FormEvent } from "react";
import { apiRequest, formatUtc } from "@/lib/api";
import type { MaintenanceRecord } from "@/lib/types";
import { StatusBadge } from "@/components/status-badge";

const DEVICE_ID = "motor-01";

function localInputDate(date: Date): string {
  return new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
}

export function MaintenanceView({ initialRecords }: { initialRecords: MaintenanceRecord[] }) {
  const [records, setRecords] = useState<MaintenanceRecord[]>(initialRecords);
  const [editing, setEditing] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError("");
    const form = event.currentTarget; const data = new FormData(form); const nextDue = String(data.get("next_due_at") ?? "");
    try {
      const record = await apiRequest<MaintenanceRecord>(`devices/${DEVICE_ID}/maintenance`, { method: "POST", body: JSON.stringify({ status: data.get("status"), notes: data.get("notes"), performed_at: new Date(String(data.get("performed_at"))).toISOString(), next_due_at: nextDue ? new Date(nextDue).toISOString() : null }) });
      setRecords((current) => [record, ...current]); form.reset();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not add maintenance record"); } finally { setBusy(false); }
  }

  async function update(event: FormEvent<HTMLFormElement>, id: number) {
    event.preventDefault(); setBusy(true); setError(""); const data = new FormData(event.currentTarget); const nextDue = String(data.get("next_due_at") ?? "");
    try {
      const record = await apiRequest<MaintenanceRecord>(`maintenance/${id}`, { method: "PATCH", body: JSON.stringify({ status: data.get("status"), notes: data.get("notes"), next_due_at: nextDue ? new Date(nextDue).toISOString() : null }) });
      setRecords((current) => current.map((item) => item.id === id ? record : item)); setEditing(null);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not update maintenance record"); } finally { setBusy(false); }
  }

  return <main className="page">
    <header className="page-header"><div><p className="eyebrow">Maintenance log</p><h1>Work performed, work still due.</h1><p>Operator-owned records for motor-01, with explicit status, notes, performed time, and next due date.</p></div></header>
    {error ? <div className="notice danger" role="alert">{error}</div> : null}
    <div className="section-grid"><section className="panel"><div className="panel-header"><div><h2>Add maintenance entry</h2><p>Times are entered locally and stored as UTC</p></div></div>
      <form className="stack-form" onSubmit={create}><label><span>Status</span><select name="status"><option value="completed">Completed</option><option value="scheduled">Scheduled</option><option value="deferred">Deferred</option></select></label>
        <label><span>Notes</span><textarea name="notes" minLength={3} maxLength={4000} placeholder="Inspection, work performed, observations, and parts used" required /></label>
        <div className="form-grid"><label><span>Performed at</span><input name="performed_at" type="datetime-local" defaultValue={localInputDate(new Date())} required /></label><label><span>Next due (optional)</span><input name="next_due_at" type="datetime-local" /></label></div>
        <button className="button primary" type="submit" disabled={busy}>{busy ? "Saving…" : "Add maintenance entry"}</button></form>
    </section>
    <section className="panel"><div className="panel-header"><div><h2>Maintenance history</h2><p>{records.length} retained records · newest first</p></div></div>
      <div className="content-stack">{records.map((record) => editing === record.id ? <form className="stack-form alarm-card" key={record.id} onSubmit={(event) => void update(event, record.id)}>
        <div className="alarm-top"><strong>Edit entry #{record.id}</strong><button className="text-button" type="button" onClick={() => setEditing(null)}>Cancel</button></div>
        <label><span>Status</span><select name="status" defaultValue={record.status}><option value="completed">Completed</option><option value="scheduled">Scheduled</option><option value="deferred">Deferred</option></select></label>
        <label><span>Notes</span><textarea name="notes" defaultValue={record.notes} minLength={3} maxLength={4000} required /></label>
        <label><span>Next due</span><input name="next_due_at" type="datetime-local" defaultValue={record.next_due_at ? localInputDate(new Date(record.next_due_at)) : ""} /></label>
        <button className="button primary" type="submit" disabled={busy}>Save changes</button>
      </form> : <article className="alarm-card" key={record.id}><div className="alarm-top"><strong>{formatUtc(record.performed_at)}</strong><StatusBadge status={record.status} /></div><p>{record.notes}</p><footer><span>By {record.created_by} · next due {formatUtc(record.next_due_at)}</span><button className="button" type="button" onClick={() => setEditing(record.id)}>Edit</button></footer></article>)}</div>
      {records.length === 0 ? <div className="empty-state"><strong>No maintenance records</strong>Add the first controlled inspection or service entry.</div> : null}
    </section></div>
  </main>;
}
