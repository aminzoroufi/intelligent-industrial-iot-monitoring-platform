# SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
# SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available
"""Exercise the running Compose API from health through persisted telemetry."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

API_URL = os.getenv("IIOT_SMOKE_API_URL", "http://127.0.0.1:8000").rstrip("/")
WEB_URL = os.getenv("IIOT_SMOKE_WEB_URL", "http://127.0.0.1:3000").rstrip("/")
USERNAME = os.getenv("IIOT_DEMO_ADMIN_USERNAME", "demo-admin")
PASSWORD = os.getenv("IIOT_DEMO_ADMIN_PASSWORD", "local-demo-admin-password")
TIMEOUT_S = 120


def request_json(
    method: str, url: str, *, body: bytes | None = None, token: str | None = None
) -> Any:
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(  # noqa: S310 - URLs are configured HTTP endpoints.
        url, data=body, headers=headers, method=method
    )
    with urllib.request.urlopen(request, timeout=5) as response:  # noqa: S310
        return json.load(response)


def wait_for_stack() -> str:
    deadline = time.monotonic() + TIMEOUT_S
    last_error = "not attempted"
    while time.monotonic() < deadline:
        try:
            health = request_json("GET", f"{API_URL}/healthz")
            if health.get("status") != "ok":
                raise ValueError(f"unexpected health response: {health}")
            with urllib.request.urlopen(f"{WEB_URL}/api/health", timeout=5) as response:  # noqa: S310
                if response.status != 200:
                    raise ValueError(f"dashboard health returned {response.status}")
            login_body = urllib.parse.urlencode(
                {"username": USERNAME, "password": PASSWORD}
            ).encode()
            login = request_json("POST", f"{API_URL}/api/v1/auth/token", body=login_body)
            token = login["access_token"]
            devices = request_json("GET", f"{API_URL}/api/v1/devices", token=token)
            if not any(device.get("id") == "motor-01" for device in devices):
                raise ValueError("seeded motor-01 is absent")
            telemetry = request_json(
                "GET",
                f"{API_URL}/api/v1/devices/motor-01/telemetry?limit=5",
                token=token,
            )
            if not telemetry.get("items"):
                raise ValueError("simulated gateway telemetry has not been persisted yet")
            return token
        except (KeyError, TypeError, ValueError, urllib.error.URLError) as error:
            last_error = str(error)
            time.sleep(2)
    raise TimeoutError(f"Compose smoke did not become ready: {last_error}")


def main() -> None:
    wait_for_stack()
    print("Compose smoke passed: API, web, auth, seeded device, MQTT ingestion, and PostgreSQL")


if __name__ == "__main__":
    main()
