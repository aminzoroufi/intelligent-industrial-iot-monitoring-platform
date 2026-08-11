# SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
# SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available

from __future__ import annotations

from simulator.telemetry_generator.main import scenario_values


def test_scenario_generation_is_reproducible() -> None:
    first = list(scenario_values("normal", 10))
    second = list(scenario_values("normal", 10))
    assert first == second


def test_fault_scenarios_reach_named_fault_state() -> None:
    temperature = list(scenario_values("rising-temperature", 30))
    vibration = list(scenario_values("vibration-imbalance", 30))
    current = list(scenario_values("current-overload", 30))
    stuck = list(scenario_values("sensor-stuck", 30))

    assert "TEMPERATURE_WARNING" in temperature[-1]["fault_flags"]
    assert "VIBRATION_WARNING" in vibration[-1]["fault_flags"]
    assert "CURRENT_OVERLOAD_WARNING" in current[-1]["fault_flags"]
    assert stuck[-1]["temperature_status"] == "stuck"
