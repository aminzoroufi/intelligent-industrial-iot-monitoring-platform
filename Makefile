# SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
# SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available

.PHONY: demo demo-status demo-logs scenario-normal scenario-temperature scenario-vibration \
	scenario-current scenario-stuck test lint check clean-demo reset-demo

demo:
	@test -f .env || (echo "Copy .env.example to .env first" && exit 1)
	docker compose up --build -d

demo-status:
	docker compose ps

demo-logs:
	docker compose logs -f --tail=100

scenario-normal:
	.venv/bin/python -m simulator.telemetry_generator.main normal

scenario-temperature:
	.venv/bin/python -m simulator.telemetry_generator.main rising-temperature --sequence-start 2000 --session-id temperature

scenario-vibration:
	.venv/bin/python -m simulator.telemetry_generator.main vibration-imbalance --sequence-start 3000 --session-id vibration

scenario-current:
	.venv/bin/python -m simulator.telemetry_generator.main current-overload --sequence-start 4000 --session-id current

scenario-stuck:
	.venv/bin/python -m simulator.telemetry_generator.main sensor-stuck --sequence-start 5000 --session-id stuck

test:
	.venv/bin/pytest tests services simulator -q

lint:
	.venv/bin/ruff format --check contracts services simulator tests conftest.py
	.venv/bin/ruff check contracts services simulator tests conftest.py
	.venv/bin/mypy contracts services simulator

check: lint test
	IIOT_ENV_FILE=.env.example docker compose --env-file .env.example config --quiet

clean-demo:
	docker compose down --remove-orphans

reset-demo:
	@echo "Removing only the iiot-monitoring-demo containers and named volumes"
	docker compose down --volumes --remove-orphans
