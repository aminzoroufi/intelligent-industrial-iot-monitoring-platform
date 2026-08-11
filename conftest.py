# SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
# SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available

from __future__ import annotations

import os
from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("IIOT_JWT_SECRET", "test-jwt-secret-with-at-least-32-characters")
os.environ.setdefault("IIOT_INGEST_TOKEN", "test-ingest-token-with-at-least-32-characters")
os.environ.setdefault("IIOT_DEMO_ADMIN_PASSWORD", "local-test-password")

from services.api.app.database import Base
from services.api.app.models import Device, User
from services.api.app.security import hash_password


@pytest.fixture
def session_factory() -> Generator[sessionmaker[Session], None, None]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        session.add(
            User(
                username="demo-admin",
                password_hash=hash_password("local-test-password"),
                role="admin",
            )
        )
        session.add(
            Device(
                id="motor-01",
                site_id="workshop-demo",
                display_name="Workshop demo motor",
                simulated=True,
            )
        )
        session.commit()
    yield factory
    Base.metadata.drop_all(engine)
    engine.dispose()
