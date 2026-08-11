# SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
# SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available
"""Idempotently seed the explicitly local demonstration identity and asset."""

from __future__ import annotations

from sqlalchemy import select

from services.api.app.database import SessionLocal
from services.api.app.models import Device, ThresholdConfig, User
from services.api.app.security import hash_password
from services.api.app.settings import get_settings


def seed() -> None:
    settings = get_settings()
    if settings.environment not in {"development", "test"}:
        raise RuntimeError("demo seeding is restricted to development and test environments")

    with SessionLocal() as session:
        user = session.scalar(select(User).where(User.username == settings.demo_admin_username))
        if user is None:
            session.add(
                User(
                    username=settings.demo_admin_username,
                    password_hash=hash_password(settings.demo_admin_password.get_secret_value()),
                    role="admin",
                )
            )
        device = session.get(Device, "motor-01")
        if device is None:
            session.add(
                Device(
                    id="motor-01",
                    site_id="workshop-demo",
                    display_name="Workshop demo motor",
                    asset_class="dc-motor",
                    simulated=True,
                )
            )
        if session.get(ThresholdConfig, "motor-01") is None:
            session.add(ThresholdConfig(device_id="motor-01"))
        session.commit()


if __name__ == "__main__":
    seed()
