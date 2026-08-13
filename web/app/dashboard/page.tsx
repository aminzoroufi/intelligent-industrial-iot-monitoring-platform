// SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
// SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available

import type { Metadata } from "next";
import { FleetOverview } from "@/components/fleet-overview";
import { serverApi } from "@/lib/server-api";
import type { Device } from "@/lib/types";

export const metadata: Metadata = { title: "Fleet" };

export default async function FleetPage() {
  const devices = await serverApi<Device[]>("devices");
  return <FleetOverview initialDevices={devices} />;
}
