# SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
# SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available

from services.api.app.live import bearer_subprotocol_token, websocket_origin_is_allowed


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


def test_websocket_origin_requires_exact_match_when_present() -> None:
    allowed = ["http://localhost:3000", "http://127.0.0.1:3000"]
    assert websocket_origin_is_allowed(None, allowed)
    assert websocket_origin_is_allowed("http://localhost:3000", allowed)
    assert websocket_origin_is_allowed("http://127.0.0.1:3000", allowed)
    assert not websocket_origin_is_allowed("http://attacker.invalid", allowed)
    assert not websocket_origin_is_allowed("http://localhost:3000.attacker.invalid", allowed)
