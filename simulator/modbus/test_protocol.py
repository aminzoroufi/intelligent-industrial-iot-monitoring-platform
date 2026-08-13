# SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
# SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available
from __future__ import annotations

import os
import pty
import threading
import tty

from simulator.modbus.protocol import DeterministicNode, Scenario, crc16, read_request
from simulator.modbus.pty_node import serve_once


def test_golden_read_frame_matches_c_fixture() -> None:
    request = read_request()
    assert request == bytes([1, 3, 0, 0, 0, 8, 68, 12])
    response = DeterministicNode().handle(request)
    assert response == bytes(
        [1, 3, 16, 1, 0, 73, 73, 0, 1, 0, 1, 0, 0, 0, 0, 16, 154, 8, 0, 164, 10]
    )


def test_timeout_bad_crc_and_illegal_address_are_deterministic() -> None:
    request = read_request()
    assert DeterministicNode(scenario=Scenario.TIMEOUT).handle(request) is None
    corrupt = DeterministicNode(scenario=Scenario.BAD_CRC).handle(request)
    assert corrupt is not None
    assert crc16(corrupt[:-2]) != int.from_bytes(corrupt[-2:], "little")
    exception = DeterministicNode(scenario=Scenario.ILLEGAL_ADDRESS).handle(request)
    assert exception is not None
    assert exception[1:3] == bytes([0x83, 0x02])


def test_stale_register_scenario_freezes_previous_values() -> None:
    node = DeterministicNode(scenario=Scenario.STALE)
    first = node.handle(read_request(first=6, quantity=2))
    node.temperature_centi_c = 9000
    node.adc_raw = 4095
    second = node.handle(read_request(first=6, quantity=2))
    assert first == second


def test_bad_request_crc_is_silently_ignored_and_counted() -> None:
    node = DeterministicNode()
    request = bytearray(read_request())
    request[-1] ^= 1
    assert node.handle(bytes(request)) is None
    assert node.crc_error_count == 1


def test_pseudo_terminal_pair_round_trip() -> None:
    master_fd, slave_fd = pty.openpty()
    tty.setraw(master_fd)
    tty.setraw(slave_fd)
    node = DeterministicNode()
    worker = threading.Thread(target=serve_once, args=(master_fd, node), daemon=True)
    worker.start()
    try:
        os.write(slave_fd, read_request())
        response = os.read(slave_fd, 64)
        worker.join(timeout=1.0)
        assert not worker.is_alive()
        assert response == node.handle(read_request())
    finally:
        os.close(master_fd)
        os.close(slave_fd)
