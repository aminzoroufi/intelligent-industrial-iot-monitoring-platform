// SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
// SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available

import type { Telemetry } from "@/lib/types";

export type MetricKey =
  | "temperature_c"
  | "vibration_rms_mps2"
  | "current_a";

interface ChartPoint {
  value: number | null;
  anomaly: boolean;
}

const WIDTH = 780;
const HEIGHT = 250;
const PADDING = { top: 18, right: 18, bottom: 28, left: 49 };

export function boundedPoints(rows: Telemetry[], metric: MetricKey, limit = 240): ChartPoint[] {
  const chronological = [...rows].sort(
    (left, right) => new Date(left.received_at).getTime() - new Date(right.received_at).getTime(),
  );
  if (chronological.length === 0) return [];
  const stride = Math.max(1, Math.ceil(chronological.length / limit));
  return chronological
    .filter((_, index) => index % stride === 0 || index === chronological.length - 1)
    .slice(-limit)
    .map((row) => ({
      value: row[metric],
      anomaly: row.anomaly_percentile !== null && row.anomaly_percentile >= 0.99,
    }));
}

export function linePath(
  points: ChartPoint[],
  minimum: number,
  maximum: number,
): string {
  const innerWidth = WIDTH - PADDING.left - PADDING.right;
  const innerHeight = HEIGHT - PADDING.top - PADDING.bottom;
  const range = Math.max(maximum - minimum, 0.0001);
  let drawing = false;
  return points
    .map((point, index) => {
      if (point.value === null) {
        drawing = false;
        return "";
      }
      const x = PADDING.left + (index / Math.max(points.length - 1, 1)) * innerWidth;
      const y = PADDING.top + (1 - (point.value - minimum) / range) * innerHeight;
      const operation = drawing ? "L" : "M";
      drawing = true;
      return `${operation}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .filter(Boolean)
    .join(" ");
}

function yPosition(value: number, minimum: number, maximum: number): number {
  const innerHeight = HEIGHT - PADDING.top - PADDING.bottom;
  return PADDING.top + (1 - (value - minimum) / Math.max(maximum - minimum, 0.0001)) * innerHeight;
}

export function TelemetryChart({
  rows,
  metric,
  unit,
  warning,
  critical,
  label,
}: {
  rows: Telemetry[];
  metric: MetricKey;
  unit: string;
  warning: number;
  critical: number;
  label: string;
}) {
  const points = boundedPoints(rows, metric);
  const values = points.flatMap((point) => (point.value === null ? [] : [point.value]));
  const rawMinimum = Math.min(...values, warning, critical);
  const rawMaximum = Math.max(...values, warning, critical);
  const padding = Math.max((rawMaximum - rawMinimum) * 0.12, 0.5);
  const minimum = rawMinimum - padding;
  const maximum = rawMaximum + padding;
  const path = linePath(points, minimum, maximum);
  const gridValues = [maximum, (maximum + minimum) / 2, minimum];

  return (
    <div className="chart-wrap">
      {points.length === 0 ? (
        <div className="empty-state">
          <strong>No samples in range</strong>
          Missing data is shown as a gap rather than interpolated.
        </div>
      ) : (
        <>
          <svg className="chart" viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label={`${label} history in ${unit}`}>
            {gridValues.map((value) => {
              const y = yPosition(value, minimum, maximum);
              return (
                <g key={value}>
                  <line className="chart-grid-line" x1={PADDING.left} x2={WIDTH - PADDING.right} y1={y} y2={y} />
                  <text className="chart-axis-label" x={PADDING.left - 7} y={y + 3} textAnchor="end">
                    {value.toFixed(1)}
                  </text>
                </g>
              );
            })}
            <line
              className="chart-threshold-warning"
              x1={PADDING.left}
              x2={WIDTH - PADDING.right}
              y1={yPosition(warning, minimum, maximum)}
              y2={yPosition(warning, minimum, maximum)}
            />
            <line
              className="chart-threshold-critical"
              x1={PADDING.left}
              x2={WIDTH - PADDING.right}
              y1={yPosition(critical, minimum, maximum)}
              y2={yPosition(critical, minimum, maximum)}
            />
            <path className="chart-line" d={path} />
            {points.map((point, index) => {
              if (!point.anomaly || point.value === null) return null;
              const x = PADDING.left + (index / Math.max(points.length - 1, 1)) * (WIDTH - PADDING.left - PADDING.right);
              return <circle key={index} className="chart-anomaly" cx={x} cy={yPosition(point.value, minimum, maximum)} r="5" />;
            })}
            <text className="chart-axis-label" x={PADDING.left} y={HEIGHT - 7}>older</text>
            <text className="chart-axis-label" x={WIDTH - PADDING.right} y={HEIGHT - 7} textAnchor="end">newest · {unit}</text>
          </svg>
          <div className="chart-legend" aria-label="Chart legend">
            <span>measured</span>
            <span className="warning-key">warning {warning}</span>
            <span className="critical-key">critical {critical}</span>
            <span>anomaly marker when model ready</span>
          </div>
        </>
      )}
    </div>
  );
}
