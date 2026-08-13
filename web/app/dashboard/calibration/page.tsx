// SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
// SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available

import type { Metadata } from "next";
import { CalibrationView } from "@/components/calibration-view";
import { serverApi } from "@/lib/server-api";
import type { Calibration } from "@/lib/types";

export const metadata: Metadata = { title: "Calibration" };
export default async function CalibrationPage() {
  const records = await serverApi<Calibration[]>("devices/motor-01/calibrations");
  return <CalibrationView initialRecords={records} />;
}
