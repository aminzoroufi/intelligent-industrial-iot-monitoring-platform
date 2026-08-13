# SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
# SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available
"""Expose the deterministic Modbus RTU node through a POSIX pseudo-terminal pair."""

from __future__ import annotations

import argparse
import os
import pty
import select
import signal
import tty
from collections.abc import Sequence

from simulator.modbus.protocol import DeterministicNode, Scenario


def serve_once(master_fd: int, node: DeterministicNode, timeout_s: float = 1.0) -> bool:
    readable, _, _ = select.select([master_fd], [], [], timeout_s)
    if not readable:
        return False
    request = os.read(master_fd, 256)
    response = node.handle(request)
    if response is not None:
        os.write(master_fd, response)
    return True


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--scenario", type=Scenario, choices=list(Scenario), default=Scenario.NORMAL)
    value.add_argument("--address", type=int, choices=range(1, 248), default=1)
    return value


def main(argv: Sequence[str] | None = None) -> None:
    arguments = parser().parse_args(argv)
    master_fd, slave_fd = pty.openpty()
    tty.setraw(master_fd)
    tty.setraw(slave_fd)
    print(os.ttyname(slave_fd), flush=True)
    node = DeterministicNode(node_address=arguments.address, scenario=arguments.scenario)
    running = True

    def stop(_signum: int, _frame: object) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    try:
        while running:
            serve_once(master_fd, node, timeout_s=0.25)
    finally:
        os.close(master_fd)
        os.close(slave_fd)


if __name__ == "__main__":
    main()
