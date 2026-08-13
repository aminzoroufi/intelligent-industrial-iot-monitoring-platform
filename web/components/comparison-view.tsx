// SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
// SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available

"use client";

import { StatusBadge } from "@/components/status-badge";
import { formatUtc } from "@/lib/api";
import type {
  Alarm,
  AnomalyEvaluation,
  AnomalyModelStatus,
  EvaluationScenario,
  TelemetryPage,
} from "@/lib/types";

interface ComparisonViewProps {
  alarms: Alarm[];
  telemetry: TelemetryPage;
  model: AnomalyModelStatus;
  evaluation: AnomalyEvaluation;
}

function percent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function detectionLabel(scenario: EvaluationScenario, model: boolean): string {
  const delay = model
    ? scenario.first_model_detection_delay_s
    : scenario.first_deterministic_detection_delay_s;
  const faultExpected = scenario.scenario !== "normal";
  if (delay === null) return faultExpected ? "Not detected" : "No alert";
  if (!faultExpected) return `False alert at ${delay.toFixed(0)} s`;
  if (delay === 0) return "Detected at first eligible window";
  return `Detected after ${delay.toFixed(0)} s`;
}

function scenarioName(value: string): string {
  return value.replaceAll("-", " ").replace(/^./, (letter) => letter.toUpperCase());
}

export function ComparisonView({
  alarms,
  telemetry,
  model,
  evaluation,
}: ComparisonViewProps) {
  const scored = telemetry.items.filter((row) => row.anomaly_score !== null);
  const activeThresholds = alarms.filter(
    (alarm) => alarm.state === "active" && alarm.source === "threshold",
  );
  const modelBadge = model.ready ? "completed" : model.status;

  return (
    <main className="page">
      <header className="page-header">
        <div>
          <p className="eyebrow">Detector comparison</p>
          <h1>Rules remain authoritative; ML earns its place.</h1>
          <p>
            Threshold/hysteresis outcomes and Isolation Forest outputs are shown separately. An
            anomaly score or empirical percentile is never presented as a probability.
          </p>
        </div>
      </header>

      <section className="comparison-grid">
        <article className="panel">
          <div className="panel-header">
            <div>
              <h2>Threshold detector</h2>
              <p>Deterministic warning / critical limits</p>
            </div>
            <StatusBadge status="active" />
          </div>
          <div className="detector-state">
            <strong>
              {activeThresholds.length} active condition
              {activeThresholds.length === 1 ? "" : "s"}
            </strong>
            <p className="muted">
              Hysteresis controls clearing. Sensor quality, impossible ranges, and rate checks
              remain deterministic even when no statistical model is usable.
            </p>
            {activeThresholds.map((alarm) => (
              <span className="tag" key={alarm.id}>
                {alarm.code}
              </span>
            ))}
          </div>
        </article>

        <article className="panel">
          <div className="panel-header">
            <div>
              <h2>Isolation Forest</h2>
              <p>Versioned per-device comparison model</p>
            </div>
            <StatusBadge status={modelBadge} />
          </div>
          <div className="detector-state">
            <strong>
              {model.ready
                ? `${scored.length} displayed sample${scored.length === 1 ? "" : "s"} scored`
                : model.status.replaceAll("_", " ").toUpperCase()}
            </strong>
            <p className="muted">{model.diagnostic}</p>
            {model.model_version && <span className="tag">{model.model_version}</span>}
            {model.ready && (
              <span className="tag">
                {model.training_sample_count} train / {model.validation_sample_count} validate
              </span>
            )}
            <span className="tag">No probability claim</span>
            <p className="muted">
              Last scored: {formatUtc(model.last_scored_at)} · trained: {formatUtc(model.created_at)}
            </p>
          </div>
        </article>
      </section>

      <section className="panel" style={{ marginTop: "0.85rem" }}>
        <div className="panel-header">
          <div>
            <h2>Versioned synthetic evaluation</h2>
            <p>
              Reproducible fixture evidence for {evaluation.model_version}; this is not bench or
              field performance.
            </p>
          </div>
          <StatusBadge status="simulated" />
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Detector</th>
                <th>Precision</th>
                <th>Recall</th>
                <th>F1</th>
                <th>False-positive rate</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Threshold + sensor rules</td>
                <td>{percent(evaluation.deterministic_detector.precision)}</td>
                <td>{percent(evaluation.deterministic_detector.recall)}</td>
                <td>{percent(evaluation.deterministic_detector.f1)}</td>
                <td>{percent(evaluation.deterministic_detector.false_positive_rate)}</td>
              </tr>
              <tr>
                <td>Isolation Forest</td>
                <td>{percent(evaluation.isolation_forest.precision)}</td>
                <td>{percent(evaluation.isolation_forest.recall)}</td>
                <td>{percent(evaluation.isolation_forest.f1)}</td>
                <td>{percent(evaluation.isolation_forest.false_positive_rate)}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel" style={{ marginTop: "0.85rem" }}>
        <div className="panel-header">
          <div>
            <h2>Seeded scenario matrix</h2>
            <p>Detection delay starts at the first feature-eligible synthetic sample.</p>
          </div>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Scenario</th>
                <th>Eligible windows</th>
                <th>Threshold + rules</th>
                <th>Isolation Forest</th>
              </tr>
            </thead>
            <tbody>
              {evaluation.scenarios.map((scenario) => (
                <tr key={scenario.scenario}>
                  <td>{scenarioName(scenario.scenario)}</td>
                  <td>{scenario.evaluated_samples}</td>
                  <td>{detectionLabel(scenario, false)}</td>
                  <td>{detectionLabel(scenario, true)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}
