# SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
# SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available

.PHONY: demo demo-status demo-logs scenario-normal scenario-temperature scenario-vibration \
	scenario-current scenario-stuck test lint web-test web-lint firmware-test check clean-demo \
	reset-demo anomaly-evaluate anomaly-train hardware-generate hardware-check reports report-check \
	coverage license-inventory license-check hygiene compose-smoke

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

anomaly-evaluate:
	.venv/bin/python -m services.anomaly_worker.main evaluate-demo

anomaly-train:
	@test -n "$(START)" -a -n "$(END)" || (echo "Usage: make anomaly-train START=... END=... [DEVICE=motor-01]" && exit 1)
	docker compose exec anomaly-worker python -m services.anomaly_worker.main train --device-id $(or $(DEVICE),motor-01) --start "$(START)" --end "$(END)"

test:
	.venv/bin/pytest tests services simulator -q

coverage:
	.venv/bin/pytest tests services simulator -q --cov=contracts --cov=services \
		--cov=simulator --cov-branch --cov-report=term-missing \
		--cov-report=xml:coverage.xml --cov-fail-under=70

web-test:
	npm --prefix web test

web-lint:
	npm --prefix web run lint
	npm --prefix web run typecheck
	npm --prefix web run build

firmware-test:
	cmake -S firmware/host-tests -B firmware/host-tests/build
	cmake --build firmware/host-tests/build --parallel
	ctest --test-dir firmware/host-tests/build --output-on-failure

hardware-generate:
	.venv/bin/python scripts/generate_hardware_artifacts.py

hardware-check:
	.venv/bin/python scripts/generate_hardware_artifacts.py --check

reports:
	.venv/bin/python scripts/build_reports.py

report-check:
	.venv/bin/python scripts/verify_reports.py

license-inventory:
	.venv/bin/python scripts/check_dependency_licenses.py --write

license-check:
	.venv/bin/python scripts/check_dependency_licenses.py

hygiene:
	.venv/bin/python scripts/check_repository_hygiene.py

compose-smoke:
	.venv/bin/python scripts/compose_smoke.py

lint:
	.venv/bin/ruff format --check contracts services simulator scripts tests conftest.py
	.venv/bin/ruff check contracts services simulator scripts tests conftest.py
	.venv/bin/mypy contracts services simulator

check: lint coverage web-lint web-test firmware-test hardware-check report-check license-check hygiene
	IIOT_ENV_FILE=.env.example docker compose --env-file .env.example config --quiet

clean-demo:
	docker compose down --remove-orphans

reset-demo:
	@echo "Removing only the iiot-monitoring-demo containers and named volumes"
	docker compose down --volumes --remove-orphans
