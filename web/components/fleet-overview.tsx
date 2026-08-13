// SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
// SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available

"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ApiError, apiRequest, relativeTime } from "@/lib/api";
import type { Device, LiveEvent } from "@/lib/types";
import { useLiveSocket } from "@/lib/use-live-socket";
import { StatusBadge } from "@/components/status-badge";

export function FleetOverview({ initialDevices }: { initialDevices: Device[] }) {
  const [devices, setDevices] = useState<Device[]>(initialDevices);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      setDevices(await apiRequest<Device[]>("devices"));
      setError("");
    } catch (reason) {
      if (!(reason instanceof ApiError && reason.status === 401)) {
        setError(reason instanceof Error ? reason.message : "Could not load fleet");
      }
    }
  }, []);

  useEffect(() => {
    const timer = window.setInterval(() => void load(), 15_000);
    return () => window.clearInterval(timer);
  }, [load]);

  const onLiveEvent = useCallback(
    (event: LiveEvent) => {
      if (["health", "telemetry"].includes(event.type)) void load();
    },
    [load],
  );
  const liveState = useLiveSocket(onLiveEvent);
  const count = (status: Device["status"]) => devices.filter((device) => device.status === status).length;

  return (
    <main className="page">
      <header className="page-header">
        <div>
          <p className="eyebrow">Fleet overview</p>
          <h1>Asset condition, without the noise.</h1>
          <p>Current device state from retained health and bounded telemetry. All seeded readings are synthetic.</p>
        </div>
        <div className="status-line" aria-live="polite">
          <span className={`status-dot ${liveState}`} aria-hidden="true" />
          {liveState === "live" ? "Live updates connected" : liveState === "connecting" ? "Connecting live updates" : "Reconnecting live updates"}
        </div>
      </header>

      {error ? <div className="notice danger" role="alert">{error}</div> : null}
      <section className="summary-grid" aria-label="Fleet status summary">
        <article className="summary-card"><span>Total assets</span><strong>{devices.length}</strong></article>
        <article className="summary-card"><span>Online</span><strong>{count("online")}</strong></article>
        <article className="summary-card"><span>Degraded</span><strong>{count("degraded")}</strong></article>
        <article className="summary-card"><span>Offline</span><strong>{count("offline")}</strong></article>
      </section>

      <section className="panel">
        <div className="panel-header">
          <div><h2>Monitored assets</h2><p>Site workshop-demo · status recalculated from last seen and reported faults</p></div>
        </div>
        {devices.length === 0 ? (
          <div className="empty-state"><strong>No registered assets</strong>Start the simulated gateway or publish a valid telemetry envelope.</div>
        ) : null}
        <div className="device-grid">
          {devices.map((device) => (
            <Link className="device-card" href={`/dashboard/devices/${device.id}`} key={device.id}>
              <div className="device-card-top"><span className="device-id">{device.site_id} / {device.id}</span><StatusBadge status={device.status} /></div>
              <h2>{device.display_name}</h2>
              <p className="muted">{device.asset_class.replaceAll("-", " ")} · {device.simulated ? "synthetic source" : "physical source"}</p>
              <dl className="device-meta">
                <div><dt>Last seen</dt><dd>{relativeTime(device.last_seen_at)}</dd></div>
                <div><dt>Firmware</dt><dd>{device.firmware_version ?? "unknown"}</dd></div>
                <div><dt>RSSI</dt><dd>{device.rssi_dbm === null ? "—" : `${device.rssi_dbm} dBm`}</dd></div>
                <div><dt>Faults</dt><dd>{device.active_faults.length}</dd></div>
              </dl>
            </Link>
          ))}
        </div>
      </section>
    </main>
  );
}
