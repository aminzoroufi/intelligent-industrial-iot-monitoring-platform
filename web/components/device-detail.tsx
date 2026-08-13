// SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
// SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available

"use client";

import Link from "next/link";
import { useCallback, useMemo, useState } from "react";
import { ApiError, apiRequest, formatUtc } from "@/lib/api";
import type { Command, Device, LiveEvent, Telemetry, TelemetryPage, Thresholds } from "@/lib/types";
import { useLiveSocket } from "@/lib/use-live-socket";
import { ExportDialog } from "@/components/export-dialog";
import { RelayControl } from "@/components/relay-control";
import { StatusBadge } from "@/components/status-badge";
import { TelemetryChart, type MetricKey } from "@/components/telemetry-chart";
import { ThresholdEditor } from "@/components/threshold-editor";

const metricDetails = {
  temperature_c: { label: "Temperature", unit: "°C", warning: "temperature_warning_c", critical: "temperature_critical_c" },
  vibration_rms_mps2: { label: "Vibration RMS", unit: "m/s²", warning: "vibration_warning_mps2", critical: "vibration_critical_mps2" },
  current_a: { label: "Current", unit: "A", warning: "current_warning_a", critical: "current_critical_a" },
} as const;

function latestValue(rows: Telemetry[], key: MetricKey): number | null {
  return rows.find((row) => row[key] !== null)?.[key] ?? null;
}

export function DeviceDetail({ deviceId, initialDevice, initialTelemetry, initialThresholds, initialCommands }: { deviceId: string; initialDevice: Device; initialTelemetry: TelemetryPage; initialThresholds: Thresholds; initialCommands: Command[] }) {
  const [device, setDevice] = useState<Device>(initialDevice);
  const [rows, setRows] = useState<Telemetry[]>(initialTelemetry.items);
  const [thresholds, setThresholds] = useState<Thresholds>(initialThresholds);
  const [commands, setCommands] = useState<Command[]>(initialCommands);
  const [metric, setMetric] = useState<MetricKey>("temperature_c");
  const [mode, setMode] = useState<"live" | "history">("live");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const [nextDevice, telemetry, nextThresholds, nextCommands] = await Promise.all([
        apiRequest<Device>(`devices/${deviceId}`),
        apiRequest<TelemetryPage>(`devices/${deviceId}/telemetry?limit=240`),
        apiRequest<Thresholds>(`devices/${deviceId}/thresholds`),
        apiRequest<Command[]>(`devices/${deviceId}/commands`),
      ]);
      setDevice(nextDevice);
      setRows(telemetry.items);
      setThresholds(nextThresholds);
      setCommands(nextCommands);
      setError("");
    } catch (reason) {
      if (!(reason instanceof ApiError && reason.status === 401)) {
        setError(reason instanceof Error ? reason.message : "Could not load asset");
      }
    }
  }, [deviceId]);

  const onLiveEvent = useCallback(
    (event: LiveEvent) => {
      if (event.device_id !== deviceId) return;
      if (event.type === "telemetry" && mode === "live" && event.measurements) {
        const liveRow: Telemetry = {
          message_id: event.message_id ?? `live-${event.sequence ?? Date.now()}`,
          sequence: event.sequence ?? 0,
          device_time: null,
          received_at: new Date().toISOString(),
          quality: event.quality ?? "good",
          replayed: false,
          temperature_c: event.measurements.temperature_c ?? null,
          vibration_rms_mps2: event.measurements.vibration_rms_mps2 ?? null,
          vibration_peak_mps2: event.measurements.vibration_peak_mps2 ?? null,
          vibration_crest_factor: event.measurements.vibration_crest_factor ?? null,
          current_a: event.measurements.current_a ?? null,
          fault_flags: event.fault_flags ?? [],
          anomaly_score: null,
          anomaly_percentile: null,
          anomaly_reason: null,
        };
        setRows((current) => [liveRow, ...current.filter((row) => row.message_id !== liveRow.message_id)].slice(0, 240));
      }
      if (event.type === "health") void apiRequest<Device>(`devices/${deviceId}`).then(setDevice);
      if (event.type === "command_ack" && event.command_id) {
        setCommands((current) => current.map((command) => command.command_id === event.command_id ? {
          ...command,
          status: event.status ?? command.status,
          result_code: event.result_code ?? command.result_code,
          acknowledged_at: new Date().toISOString(),
        } : command));
      }
    },
    [deviceId, mode],
  );
  const liveState = useLiveSocket(onLiveEvent);

  const selected = metricDetails[metric];
  const warning = thresholds[selected.warning];
  const critical = thresholds[selected.critical];
  const latest = useMemo(() => ({
    temperature_c: latestValue(rows, "temperature_c"),
    vibration_rms_mps2: latestValue(rows, "vibration_rms_mps2"),
    current_a: latestValue(rows, "current_a"),
  }), [rows]);

  return (
    <main className="page">
      <header className="page-header">
        <div>
          <p className="eyebrow"><Link href="/dashboard">Fleet</Link> / {deviceId}</p>
          <h1>{device.display_name}</h1>
          <p>{device.site_id} · {device.simulated ? "Synthetic telemetry source" : "Physical telemetry source"} · timestamps shown in UTC</p>
        </div>
        <div className="header-actions">
          <div className="status-line"><span className={`status-dot ${liveState}`} />{liveState === "live" ? "Live" : "Reconnecting"}</div>
          <StatusBadge status={device.status} />
          <ExportDialog deviceId={deviceId} initialMetric={metric} />
        </div>
      </header>
      {error ? <div className="notice danger" role="alert">{error}</div> : null}

      <section className="metric-grid" aria-label="Latest measurements">
        {(Object.entries(metricDetails) as [MetricKey, (typeof metricDetails)[MetricKey]][]).map(([key, details]) => {
          const value = latest[key];
          return (
            <button className="metric-card" type="button" key={key} onClick={() => setMetric(key)} aria-pressed={metric === key}>
              <div className="metric-card-top"><span className="muted">{details.label}</span><span className={`status-dot ${value !== null && value >= thresholds[details.critical] ? "critical" : value !== null && value >= thresholds[details.warning] ? "degraded" : "online"}`} /></div>
              <div className="metric-value">{value === null ? "—" : value.toFixed(key === "temperature_c" ? 1 : 2)}<span>{details.unit}</span></div>
              <p>{value === null ? "Missing sample" : `Latest of ${rows.length} bounded points`}</p>
            </button>
          );
        })}
      </section>

      <div className="content-grid">
        <div className="content-stack">
          <section className="panel">
            <div className="panel-header">
              <div><h2>{selected.label}</h2><p>{mode === "live" ? "Real-time bounded window" : "Historical 24-hour API window"} · gaps remain gaps</p></div>
              <div className="segmented" aria-label="Chart data mode">
                <button className={mode === "live" ? "active" : ""} type="button" onClick={() => setMode("live")}>Live</button>
                <button className={mode === "history" ? "active" : ""} type="button" onClick={() => { setMode("history"); void load(); }}>History</button>
              </div>
            </div>
            <TelemetryChart rows={rows} metric={metric} unit={selected.unit} warning={warning} critical={critical} label={selected.label} />
          </section>

          <section className="panel">
            <div className="panel-header"><div><h2>Threshold configuration</h2><p>Warning / critical values with clearing hysteresis · administrator audited</p></div></div>
            <ThresholdEditor value={thresholds} onChange={setThresholds} />
          </section>

          <section className="panel">
            <div className="panel-header"><div><h2>Recent command audit</h2><p>HTTP acceptance is not device completion; acknowledgements are shown explicitly.</p></div></div>
            <div className="table-wrap"><table><thead><tr><th>Issued UTC</th><th>Command</th><th>Status</th><th>Result</th></tr></thead><tbody>
              {commands.slice(0, 8).map((command) => <tr key={command.command_id}><td>{formatUtc(command.issued_at)}</td><td className="mono">{String(command.parameters.relay_on) === "true" ? "Relay ON" : "Relay OFF"}</td><td><StatusBadge status={command.status} /></td><td className="mono">{command.result_code ?? "waiting"}</td></tr>)}
            </tbody></table></div>
            {commands.length === 0 ? <div className="empty-state"><strong>No commands issued</strong>Command history will appear here after an audited request.</div> : null}
          </section>
        </div>

        <aside className="content-stack">
          <section className="panel">
            <div className="panel-header"><div><h2>Device health</h2><p>Latest retained heartbeat</p></div></div>
            <>
              <dl className="definition-grid">
                <div><dt>Firmware</dt><dd>{device.firmware_version ?? "unknown"}</dd></div>
                <div><dt>RSSI</dt><dd>{device.rssi_dbm === null ? "—" : `${device.rssi_dbm} dBm`}</dd></div>
                <div><dt>Reset reason</dt><dd>{device.reset_reason ?? "unknown"}</dd></div>
                <div><dt>Reset count</dt><dd>{device.reset_count}</dd></div>
                <div><dt>Offline queue</dt><dd>{device.queue_depth} / {device.queue_capacity}</dd></div>
                <div><dt>Dropped</dt><dd>{device.dropped_message_count}</dd></div>
                <div><dt>Modbus</dt><dd>{device.modbus_status}</dd></div>
                <div><dt>Last seen UTC</dt><dd>{formatUtc(device.last_seen_at)}</dd></div>
              </dl>
              {device.active_faults.length ? <ul className="fault-list">{device.active_faults.map((fault) => <li key={fault}>{fault}</li>)}</ul> : <div className="notice info">No active device-reported faults.</div>}
            </>
          </section>

          <section className="panel">
            <div className="panel-header"><div><h2>Demo relay</h2><p>Short-lived, audited MQTT command</p></div></div>
            <RelayControl deviceId={deviceId} commands={commands} onIssued={(command) => setCommands((current) => [command, ...current])} />
          </section>

          <section className="panel">
            <div className="panel-header"><div><h2>Anomaly overlay</h2><p>Explainable model status</p></div></div>
            {rows.some((row) => row.anomaly_score !== null) ? <div className="notice info">Persisted anomaly scores are displayed as chart markers. Scores are not probabilities.</div> : <div className="notice warning"><strong>Model not ready.</strong> Deterministic thresholds remain active; no ML confidence is implied.</div>}
          </section>
        </aside>
      </div>
    </main>
  );
}
