// SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
// SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available

export type DeviceStatus = "online" | "degraded" | "offline";

export interface Device {
  id: string;
  site_id: string;
  display_name: string;
  asset_class: string;
  simulated: boolean;
  firmware_version: string | null;
  status: DeviceStatus;
  last_seen_at: string | null;
  rssi_dbm: number | null;
  reset_reason: string | null;
  reset_count: number;
  queue_depth: number;
  queue_capacity: number;
  dropped_message_count: number;
  modbus_status: string;
  active_faults: string[];
}

export interface Telemetry {
  message_id: string;
  sequence: number;
  device_time: string | null;
  received_at: string;
  quality: string;
  replayed: boolean;
  temperature_c: number | null;
  vibration_rms_mps2: number | null;
  vibration_peak_mps2: number | null;
  vibration_crest_factor: number | null;
  current_a: number | null;
  fault_flags: string[];
  anomaly_score: number | null;
  anomaly_percentile: number | null;
  anomaly_reason: string | null;
}

export interface TelemetryPage {
  items: Telemetry[];
  count: number;
  limit: number;
}

export interface AnomalyModelStatus {
  device_id: string;
  status: "model_not_ready" | "ready" | "stale" | "error";
  ready: boolean;
  diagnostic: string;
  model_version: string | null;
  feature_schema_version: number | null;
  feature_names: string[];
  training_start: string | null;
  training_end: string | null;
  training_sample_count: number;
  validation_sample_count: number;
  contamination: number | null;
  random_seed: number | null;
  sklearn_version: string | null;
  created_at: string | null;
  last_scored_at: string | null;
  score_interpretation: string;
  field_performance_claimed: false;
}

export interface DetectorMetrics {
  true_positive: number;
  false_positive: number;
  true_negative: number;
  false_negative: number;
  precision: number;
  recall: number;
  f1: number;
  false_positive_rate: number;
}

export interface EvaluationScenario {
  scenario: string;
  evaluated_samples: number;
  first_deterministic_detection_delay_s: number | null;
  first_model_detection_delay_s: number | null;
}

export interface AnomalyEvaluation {
  schema_version: number;
  data_kind: "synthetic";
  field_performance_claimed: false;
  model_version: string;
  score_interpretation: string;
  deterministic_detector: DetectorMetrics;
  isolation_forest: DetectorMetrics;
  scenarios: EvaluationScenario[];
  example_model_reasons: Record<string, string[]>;
}

export interface Alarm {
  id: number;
  device_id: string;
  code: string;
  severity: "warning" | "critical";
  source: string;
  state: "active" | "cleared";
  summary: string;
  opened_at: string;
  cleared_at: string | null;
  acknowledged_at: string | null;
  acknowledged_by: string | null;
}

export interface Calibration {
  id: number;
  device_id: string;
  sensor: string;
  previous_coefficients: Record<string, number>;
  new_coefficients: Record<string, number>;
  reason: string;
  operator: string;
  performed_at: string;
}

export interface MaintenanceRecord {
  id: number;
  device_id: string;
  status: "scheduled" | "completed" | "deferred";
  notes: string;
  performed_at: string;
  next_due_at: string | null;
  created_by: string;
  updated_at: string;
}

export interface Thresholds {
  device_id: string;
  temperature_warning_c: number;
  temperature_critical_c: number;
  vibration_warning_mps2: number;
  vibration_critical_mps2: number;
  current_warning_a: number;
  current_critical_a: number;
  hysteresis_percent: number;
  updated_by: string;
  updated_at: string;
}

export interface Command {
  command_id: string;
  device_id: string;
  kind: string;
  parameters: Record<string, unknown>;
  status: string;
  result_code: string | null;
  detail: string | null;
  issued_by: string;
  issued_at: string;
  expires_at: string;
  acknowledged_at: string | null;
}

export interface LiveEvent {
  type: string;
  device_id?: string;
  message_id?: string;
  sequence?: number;
  quality?: string;
  measurements?: Record<string, number | null>;
  fault_flags?: string[];
  status?: string;
  command_id?: string;
  result_code?: string;
  relay_on?: boolean;
}
