# ADR 0001: ESP-IDF for the edge gateway

Status: accepted — 2026-08-11

ESP-IDF is selected for the ESP32 gateway because it exposes FreeRTOS tasks,
hardware timers, interrupts, NVS, watchdogs, networking, and build-time target
configuration without concentrating the system in an Arduino loop. Sensor,
queue, threshold, and serialization logic will remain behind C interfaces so it
can run in host tests. The cost is greater setup complexity and target-specific
build tooling, which is justified by the real-time and fault-handling scope.

