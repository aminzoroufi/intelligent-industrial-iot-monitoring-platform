// SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
// SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available

import type { Metadata } from "next";
import { AlarmsView } from "@/components/alarms-view";
import { serverApi } from "@/lib/server-api";
import type { Alarm } from "@/lib/types";

export const metadata: Metadata = { title: "Alarms" };
export default async function AlarmsPage() {
  const alarms = await serverApi<Alarm[]>("alarms?limit=200");
  return <AlarmsView initialAlarms={alarms} />;
}
