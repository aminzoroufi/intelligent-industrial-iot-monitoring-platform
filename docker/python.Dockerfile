# SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
# SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available

FROM python:3.14.6-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN addgroup --system app && adduser --system --ingroup app --home /app app

WORKDIR /app
COPY --chown=app:app . /app
RUN python -m pip install --root-user-action=ignore --no-cache-dir \
      -r requirements/runtime.lock

USER app
