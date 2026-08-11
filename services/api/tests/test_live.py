# SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
# SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available

from services.api.app.live import bearer_subprotocol_token


def test_bearer_subprotocol_extracts_token_without_url_credentials() -> None:
    assert bearer_subprotocol_token("bearer, header.payload.signature") == (
        "header.payload.signature"
    )
    assert bearer_subprotocol_token("Bearer, header.payload.signature") == (
        "header.payload.signature"
    )


def test_bearer_subprotocol_rejects_malformed_headers() -> None:
    assert bearer_subprotocol_token(None) is None
    assert bearer_subprotocol_token("header.payload.signature") is None
    assert bearer_subprotocol_token("basic, header.payload.signature") is None
    assert bearer_subprotocol_token("bearer, ") is None
    assert bearer_subprotocol_token("bearer, one, two") is None
