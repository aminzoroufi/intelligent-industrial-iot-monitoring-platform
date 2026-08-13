// SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
// SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available

"use client";

import { useRef, useState, type FormEvent } from "react";
import type { MetricKey } from "@/components/telemetry-chart";

function localInputDate(date: Date): string {
  const offset = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
}

export function ExportDialog({ deviceId, initialMetric }: { deviceId: string; initialMetric: MetricKey }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const now = new Date();
  const yesterday = new Date(now.getTime() - 24 * 60 * 60 * 1000);

  async function download(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const data = new FormData(event.currentTarget);
    const params = new URLSearchParams({
      metric: String(data.get("metric")),
      start: new Date(String(data.get("start"))).toISOString(),
      end: new Date(String(data.get("end"))).toISOString(),
    });
    try {
      const response = await fetch(`/api/backend/devices/${deviceId}/export.csv?${params}`);
      if (!response.ok) {
        const payload = (await response.json()) as { detail?: string };
        throw new Error(payload.detail ?? "Export failed");
      }
      const blobUrl = URL.createObjectURL(await response.blob());
      const anchor = document.createElement("a");
      anchor.href = blobUrl;
      anchor.download = `${deviceId}-${String(data.get("metric"))}.csv`;
      anchor.click();
      URL.revokeObjectURL(blobUrl);
      dialog.current?.close();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Export failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <button className="button" type="button" onClick={() => dialog.current?.showModal()}>
        Export CSV
      </button>
      <dialog ref={dialog} onCancel={() => setError("")}>
        <div className="dialog-body">
          <div className="dialog-header">
            <div><p className="eyebrow">Bounded export</p><h2>Download telemetry</h2></div>
            <button className="icon-button" type="button" aria-label="Close export dialog" onClick={() => dialog.current?.close()}>×</button>
          </div>
          <p className="muted">UTC timestamps, one metric, at most 31 days and 10,000 rows.</p>
          <form className="stack-form" onSubmit={download}>
            {error ? <div className="notice danger" role="alert">{error}</div> : null}
            <label><span>Metric</span><select name="metric" defaultValue={initialMetric}>
              <option value="temperature_c">Temperature (°C)</option>
              <option value="vibration_rms_mps2">Vibration RMS (m/s²)</option>
              <option value="vibration_peak_mps2">Vibration peak (m/s²)</option>
              <option value="current_a">Current (A)</option>
            </select></label>
            <div className="form-grid">
              <label><span>Start</span><input name="start" type="datetime-local" defaultValue={localInputDate(yesterday)} required /></label>
              <label><span>End</span><input name="end" type="datetime-local" defaultValue={localInputDate(now)} required /></label>
            </div>
            <button className="button primary" type="submit" disabled={busy}>{busy ? "Preparing…" : "Download CSV"}</button>
          </form>
        </div>
      </dialog>
    </>
  );
}
