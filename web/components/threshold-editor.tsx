// SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
// SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available

"use client";

import { useState, type FormEvent } from "react";
import { apiRequest } from "@/lib/api";
import type { Thresholds } from "@/lib/types";

const fields = [
  ["temperature_warning_c", "Temperature warning", "°C"],
  ["temperature_critical_c", "Temperature critical", "°C"],
  ["vibration_warning_mps2", "Vibration warning", "m/s²"],
  ["vibration_critical_mps2", "Vibration critical", "m/s²"],
  ["current_warning_a", "Current warning", "A"],
  ["current_critical_a", "Current critical", "A"],
  ["hysteresis_percent", "Clear hysteresis", "%"],
] as const;

export function ThresholdEditor({ value, onChange }: { value: Thresholds; onChange: (next: Thresholds) => void }) {
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const data = new FormData(event.currentTarget);
    const payload = Object.fromEntries(fields.map(([name]) => [name, Number(data.get(name))]));
    try {
      const updated = await apiRequest<Thresholds>(`devices/${value.device_id}/thresholds`, {
        method: "PUT",
        body: JSON.stringify(payload),
      });
      onChange(updated);
      setEditing(false);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not update thresholds");
    } finally {
      setBusy(false);
    }
  }

  if (!editing) {
    return (
      <>
        <dl className="definition-grid">
          <div><dt>Temperature</dt><dd>{value.temperature_warning_c} / {value.temperature_critical_c} °C</dd></div>
          <div><dt>Vibration RMS</dt><dd>{value.vibration_warning_mps2} / {value.vibration_critical_mps2} m/s²</dd></div>
          <div><dt>Current</dt><dd>{value.current_warning_a} / {value.current_critical_a} A</dd></div>
          <div><dt>Hysteresis</dt><dd>{value.hysteresis_percent}%</dd></div>
        </dl>
        <button className="button" type="button" onClick={() => setEditing(true)}>Edit thresholds</button>
      </>
    );
  }
  return (
    <form className="stack-form" onSubmit={save}>
      {error ? <div className="notice danger" role="alert">{error}</div> : null}
      <div className="form-grid">
        {fields.map(([name, label, unit]) => (
          <label key={name}><span>{label} ({unit})</span><input name={name} type="number" step="0.1" min="0" defaultValue={value[name]} required /></label>
        ))}
      </div>
      <div className="inline-actions">
        <button className="button primary" type="submit" disabled={busy}>{busy ? "Saving…" : "Save thresholds"}</button>
        <button className="button" type="button" onClick={() => setEditing(false)}>Cancel</button>
      </div>
    </form>
  );
}
