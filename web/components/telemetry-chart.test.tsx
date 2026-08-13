// SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
// SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { Telemetry } from "@/lib/types";
import { boundedPoints, linePath, TelemetryChart } from "@/components/telemetry-chart";

function row(sequence: number, value: number | null): Telemetry {
  return {
    message_id: String(sequence),
    sequence,
    device_time: null,
    received_at: new Date(1_780_000_000_000 + sequence * 1000).toISOString(),
    quality: value === null ? "bad" : "good",
    replayed: false,
    temperature_c: value,
    vibration_rms_mps2: null,
    vibration_peak_mps2: null,
    vibration_crest_factor: null,
    current_a: null,
    fault_flags: [],
    anomaly_score: null,
    anomaly_percentile: null,
    anomaly_reason: null,
  };
}

describe("TelemetryChart", () => {
  it("bounds point counts and keeps newest data", () => {
    const points = boundedPoints(Array.from({ length: 600 }, (_, index) => row(index, index)), "temperature_c", 240);
    expect(points.length).toBeLessThanOrEqual(240);
    expect(points.at(-1)?.value).toBe(599);
  });

  it("creates separate path segments across missing samples", () => {
    const path = linePath(boundedPoints([row(1, 41), row(2, null), row(3, 43)], "temperature_c"), 40, 44);
    expect(path.match(/M/g)).toHaveLength(2);
    expect(path).not.toContain("NaN");
  });

  it("renders units and explicit threshold legend", () => {
    render(<TelemetryChart rows={[row(1, 42), row(2, 43)]} metric="temperature_c" unit="°C" warning={65} critical={75} label="Temperature" />);
    expect(screen.getByRole("img", { name: /Temperature history in °C/ })).toBeInTheDocument();
    expect(screen.getByText("warning 65")).toBeInTheDocument();
    expect(screen.getByText("critical 75")).toBeInTheDocument();
  });
});
