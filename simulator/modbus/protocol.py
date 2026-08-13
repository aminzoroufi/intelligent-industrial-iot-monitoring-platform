# SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
# SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available
"""Small deterministic model of the versioned STM32 Modbus register contract."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

REGISTER_COUNT = 18


class Scenario(StrEnum):
    NORMAL = "normal"
    TIMEOUT = "timeout"
    BAD_CRC = "bad-crc"
    ILLEGAL_ADDRESS = "illegal-address"
    STALE = "stale"


def crc16(data: bytes) -> int:
    crc = 0xFFFF
    for value in data:
        crc ^= value
        for _ in range(8):
            crc = ((crc >> 1) ^ 0xA001) if crc & 1 else crc >> 1
    return crc


def with_crc(payload: bytes) -> bytes:
    checksum = crc16(payload)
    return payload + checksum.to_bytes(2, "little")


def read_request(node_address: int = 1, first: int = 0, quantity: int = 8) -> bytes:
    return with_crc(
        bytes(
            [
                node_address,
                0x03,
                first >> 8,
                first & 0xFF,
                quantity >> 8,
                quantity & 0xFF,
            ]
        )
    )


@dataclass
class DeterministicNode:
    node_address: int = 1
    scenario: Scenario = Scenario.NORMAL
    temperature_centi_c: int = 4250
    adc_raw: int = 2048
    sensor_status: int = 0
    fault_flags: int = 0
    uptime_ms: int = 120_000
    reset_count: int = 3
    crc_error_count: int = 0
    exception_count: int = 0
    config_generation: int = 1
    calibration_offset_centi_c: int = 0
    calibration_gain_q15: int = 32_768
    _stale_registers: list[int] | None = field(default=None, init=False, repr=False)

    def registers(self) -> list[int]:
        current = [
            0x0100,
            0x4949,
            self.node_address,
            0x0001,
            self.sensor_status,
            self.fault_flags,
            self.temperature_centi_c & 0xFFFF,
            self.adc_raw,
            (self.uptime_ms >> 16) & 0xFFFF,
            self.uptime_ms & 0xFFFF,
            (self.reset_count >> 16) & 0xFFFF,
            self.reset_count & 0xFFFF,
            self.crc_error_count & 0xFFFF,
            self.exception_count & 0xFFFF,
            (self.config_generation >> 16) & 0xFFFF,
            self.config_generation & 0xFFFF,
            self.calibration_offset_centi_c & 0xFFFF,
            self.calibration_gain_q15,
        ]
        if self.scenario is Scenario.STALE:
            if self._stale_registers is None:
                self._stale_registers = current
            return self._stale_registers.copy()
        self._stale_registers = None
        return current

    def _exception(self, function: int, code: int) -> bytes:
        self.exception_count += 1
        return with_crc(bytes([self.node_address, function | 0x80, code]))

    def handle(self, frame: bytes) -> bytes | None:
        if self.scenario is Scenario.TIMEOUT:
            return None
        if len(frame) != 8 or crc16(frame[:-2]) != int.from_bytes(frame[-2:], "little"):
            self.crc_error_count += 1
            return None
        if frame[0] != self.node_address:
            return None
        function = frame[1]
        if self.scenario is Scenario.ILLEGAL_ADDRESS:
            response = self._exception(function, 0x02)
        elif function == 0x03:
            first = int.from_bytes(frame[2:4], "big")
            quantity = int.from_bytes(frame[4:6], "big")
            if quantity < 1 or quantity > REGISTER_COUNT:
                response = self._exception(function, 0x03)
            elif first >= REGISTER_COUNT or first + quantity > REGISTER_COUNT:
                response = self._exception(function, 0x02)
            else:
                values = self.registers()[first : first + quantity]
                data = b"".join(value.to_bytes(2, "big") for value in values)
                response = with_crc(bytes([self.node_address, function, len(data)]) + data)
        else:
            response = self._exception(function, 0x01)
        if self.scenario is Scenario.BAD_CRC:
            return response[:-1] + bytes([response[-1] ^ 0x01])
        return response
