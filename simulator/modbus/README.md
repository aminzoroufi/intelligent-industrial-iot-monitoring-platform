# Modbus RTU pseudo-terminal simulator

The simulator exposes the version-1 STM32 register contract through a POSIX
pseudo-terminal pair. The printed slave path can be opened by a host Modbus
master at 115200 baud, 8 data bits, even parity, and 1 stop bit.

```sh
python -m simulator.modbus.pty_node --scenario normal
python -m simulator.modbus.pty_node --scenario timeout
python -m simulator.modbus.pty_node --scenario bad-crc
python -m simulator.modbus.pty_node --scenario illegal-address
python -m simulator.modbus.pty_node --scenario stale
```

The protocol model is deterministic and its first-eight-register response is
the same golden byte frame asserted by the shared C tests. A pseudo-terminal
models byte transport only; it cannot verify MAX3485 voltage levels, driver
enable timing, line bias, termination, common-mode range, reflections, or EMC.
