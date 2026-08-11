#!/bin/sh
# SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
# SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available
set -eu

alembic upgrade head
python -m services.api.app.seed
exec uvicorn services.api.app.main:app --host 0.0.0.0 --port 8000

