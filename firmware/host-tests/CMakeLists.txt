# SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
# SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available
cmake_minimum_required(VERSION 3.22)
project(iiot_firmware_host_tests VERSION 0.1.0 LANGUAGES C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)

add_library(iiot_core STATIC ../shared/src/iiot_core.c ../shared/src/modbus_node.c)
target_include_directories(iiot_core PUBLIC ../shared/include)
target_compile_definitions(iiot_core PRIVATE _POSIX_C_SOURCE=200809L)
target_compile_options(iiot_core PRIVATE -Wall -Wextra -Wpedantic -Werror)

add_executable(iiot_core_tests test_core.c)
target_link_libraries(iiot_core_tests PRIVATE iiot_core m)
target_compile_options(iiot_core_tests PRIVATE -Wall -Wextra -Wpedantic -Werror)

enable_testing()
add_test(NAME iiot_core_tests COMMAND iiot_core_tests)

add_executable(modbus_node_tests test_modbus_node.c)
target_link_libraries(modbus_node_tests PRIVATE iiot_core m)
target_compile_options(modbus_node_tests PRIVATE -Wall -Wextra -Wpedantic -Werror)
add_test(NAME modbus_node_tests COMMAND modbus_node_tests)
