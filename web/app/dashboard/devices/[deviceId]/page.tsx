// SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
// SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available

import type { Metadata } from "next";
import { DeviceDetail } from "@/components/device-detail";
import { serverApi } from "@/lib/server-api";
import type { Command, Device, TelemetryPage, Thresholds } from "@/lib/types";

type Props = { params: Promise<{ deviceId: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { deviceId } = await params;
  return { title: `Asset ${deviceId}` };
}

export default async function DevicePage({ params }: Props) {
  const { deviceId } = await params;
  const [device, telemetry, thresholds, commands] = await Promise.all([
    serverApi<Device>(`devices/${deviceId}`),
    serverApi<TelemetryPage>(`devices/${deviceId}/telemetry?limit=240`),
    serverApi<Thresholds>(`devices/${deviceId}/thresholds`),
    serverApi<Command[]>(`devices/${deviceId}/commands`),
  ]);
  return <DeviceDetail deviceId={deviceId} initialDevice={device} initialTelemetry={telemetry} initialThresholds={thresholds} initialCommands={commands} />;
}
