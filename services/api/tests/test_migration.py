# SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
# SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from services.api.app.settings import get_settings


def test_baseline_migration_upgrade_and_downgrade(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    database_path = tmp_path / "migration.db"
    monkeypatch.setenv("IIOT_DATABASE_URL", f"sqlite+pysqlite:///{database_path}")
    get_settings.cache_clear()
    config = Config("alembic.ini")

    command.upgrade(config, "head")
    engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    tables = set(inspect(engine).get_table_names())
    assert {
        "devices",
        "telemetry",
        "users",
        "audit_events",
        "anomaly_models",
    }.issubset(tables)

    command.downgrade(config, "base")
    assert set(inspect(engine).get_table_names()) == {"alembic_version"}
    engine.dispose()
    get_settings.cache_clear()
