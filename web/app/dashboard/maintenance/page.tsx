// SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
// SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available

import type { Metadata } from "next";
import { MaintenanceView } from "@/components/maintenance-view";
import { serverApi } from "@/lib/server-api";
import type { MaintenanceRecord } from "@/lib/types";

export const metadata: Metadata = { title: "Maintenance" };
export default async function MaintenancePage() {
  const records = await serverApi<MaintenanceRecord[]>("devices/motor-01/maintenance");
  return <MaintenanceView initialRecords={records} />;
}
