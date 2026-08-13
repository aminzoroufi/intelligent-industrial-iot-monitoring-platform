// SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
// SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available

import type { Metadata } from "next";
import { ComparisonView } from "@/components/comparison-view";
import { serverApi } from "@/lib/server-api";
import type {
  Alarm,
  AnomalyEvaluation,
  AnomalyModelStatus,
  TelemetryPage,
} from "@/lib/types";

export const metadata: Metadata = { title: "Detection comparison" };
export default async function ComparisonPage() {
  const [alarms, telemetry, model, evaluation] = await Promise.all([
    serverApi<Alarm[]>("alarms?device_id=motor-01&limit=200"),
    serverApi<TelemetryPage>("devices/motor-01/telemetry?limit=240"),
    serverApi<AnomalyModelStatus>("devices/motor-01/anomaly-model"),
    serverApi<AnomalyEvaluation>("anomaly/evaluation-demo"),
  ]);
  return (
    <ComparisonView
      alarms={alarms}
      telemetry={telemetry}
      model={model}
      evaluation={evaluation}
    />
  );
}
