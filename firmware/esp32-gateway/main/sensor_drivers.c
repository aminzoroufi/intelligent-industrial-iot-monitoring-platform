/*
 * SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
 * SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available
 */
#include "sensor_drivers.h"

#include <math.h>
#include <stdio.h>
#include <string.h>

#include "driver/gpio.h"
#include "driver/uart.h"
#include "esp_check.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#define I2C_SDA_GPIO 21
#define I2C_SCL_GPIO 22
#define TMP117_ADDRESS 0x48
#define INA219_ADDRESS 0x40
#define SPI_MOSI_GPIO 23
#define SPI_MISO_GPIO 19
#define SPI_CLOCK_GPIO 18
#define ADXL345_CS_GPIO 5
#define ADXL345_DRDY_GPIO 34
#define RS485_UART UART_NUM_2
#define RS485_TX_GPIO 17
#define RS485_RX_GPIO 16
#define RS485_DE_GPIO 25

static const char *const TAG = "sensor";
static char modbus_status[16] = "disabled";

#if !CONFIG_IIOT_SIMULATION
static TaskHandle_t vibration_waiter;
static void IRAM_ATTR vibration_data_ready(void *argument) {
    (void)argument;
    BaseType_t task_woken = pdFALSE;
    if (vibration_waiter != NULL) {
        vTaskNotifyGiveFromISR(vibration_waiter, &task_woken);
        portYIELD_FROM_ISR(task_woken);
    }
}

static esp_err_t i2c_write_register(i2c_master_dev_handle_t device, uint8_t address,
                                    uint16_t value) {
    const uint8_t bytes[] = {address, (uint8_t)(value >> 8U), (uint8_t)value};
    return i2c_master_transmit(device, bytes, sizeof(bytes), 100);
}

static esp_err_t i2c_read_register(i2c_master_dev_handle_t device, uint8_t address,
                                   uint16_t *value) {
    uint8_t bytes[2];
    ESP_RETURN_ON_ERROR(i2c_master_transmit_receive(device, &address, 1U, bytes, sizeof(bytes),
                                                    100),
                        TAG, "i2c register read");
    *value = ((uint16_t)bytes[0] << 8U) | bytes[1];
    return ESP_OK;
}

static esp_err_t adxl_write(sensor_context_t *context, uint8_t address, uint8_t value) {
    uint8_t bytes[] = {address, value};
    spi_transaction_t transaction = {.length = 16U, .tx_buffer = bytes};
    return spi_device_polling_transmit(context->adxl345, &transaction);
}

static esp_err_t adxl_read_xyz(sensor_context_t *context, float *magnitude_mps2) {
    uint8_t transmit[7] = {0x80U | 0x40U | 0x32U};
    uint8_t receive[7] = {0};
    spi_transaction_t transaction = {
        .length = 56U,
        .tx_buffer = transmit,
        .rx_buffer = receive,
    };
    ESP_RETURN_ON_ERROR(spi_device_polling_transmit(context->adxl345, &transaction), TAG,
                        "ADXL345 read");
    const int16_t x = (int16_t)(((uint16_t)receive[2] << 8U) | receive[1]);
    const int16_t y = (int16_t)(((uint16_t)receive[4] << 8U) | receive[3]);
    const int16_t z = (int16_t)(((uint16_t)receive[6] << 8U) | receive[5]);
    const float scale_mps2 = 0.0382459F;
    const float x_value = x * scale_mps2;
    const float y_value = y * scale_mps2;
    const float z_value = z * scale_mps2;
    const float z_dynamic = z_value - copysignf(9.80665F, z_value);
    *magnitude_mps2 =
        sqrtf(x_value * x_value + y_value * y_value + z_dynamic * z_dynamic);
    return ESP_OK;
}

static uint16_t modbus_crc(const uint8_t *bytes, size_t length) {
    uint16_t crc = UINT16_C(0xffff);
    for (size_t index = 0; index < length; ++index) {
        crc ^= bytes[index];
        for (uint8_t bit = 0; bit < 8U; ++bit) {
            crc = (crc & 1U) != 0U ? (crc >> 1U) ^ UINT16_C(0xa001) : crc >> 1U;
        }
    }
    return crc;
}

static void modbus_poll_identity(void) {
    uint8_t request[] = {1U, 3U, 0U, 0U, 0U, 8U, 0U, 0U};
    const uint16_t request_crc = modbus_crc(request, 6U);
    request[6] = (uint8_t)request_crc;
    request[7] = (uint8_t)(request_crc >> 8U);
    (void)uart_flush_input(RS485_UART);
    if (uart_write_bytes(RS485_UART, request, sizeof(request)) != (int)sizeof(request) ||
        uart_wait_tx_done(RS485_UART, pdMS_TO_TICKS(20)) != ESP_OK) {
        (void)snprintf(modbus_status, sizeof(modbus_status), "timeout");
        return;
    }
    uint8_t response[32];
    const int received = uart_read_bytes(RS485_UART, response, sizeof(response),
                                         pdMS_TO_TICKS(80));
    if (received == 0) {
        (void)snprintf(modbus_status, sizeof(modbus_status), "timeout");
        return;
    }
    if (received < 5 || response[0] != 1U) {
        (void)snprintf(modbus_status, sizeof(modbus_status), "stale");
        return;
    }
    if ((response[1] & 0x80U) != 0U) {
        (void)snprintf(modbus_status, sizeof(modbus_status), "exception");
        return;
    }
    const uint16_t actual_crc = modbus_crc(response, (size_t)received - 2U);
    const uint16_t frame_crc = (uint16_t)response[received - 2] |
                               ((uint16_t)response[received - 1] << 8U);
    (void)snprintf(modbus_status, sizeof(modbus_status), "%s",
                   actual_crc == frame_crc ? "ok" : "crc_error");
}
#endif

esp_err_t sensor_drivers_init(sensor_context_t *context) {
    memset(context, 0, sizeof(*context));
#if CONFIG_IIOT_SIMULATION
    gpio_config_t button = {
        .pin_bit_mask = UINT64_C(1) << IIOT_PROVISION_GPIO,
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_ENABLE,
    };
    ESP_RETURN_ON_ERROR(gpio_config(&button), TAG, "simulation control GPIO");
    context->initialized = true;
    (void)snprintf(modbus_status, sizeof(modbus_status), "ok");
    ESP_LOGW(TAG, "code=SIMULATED_SENSOR_ADAPTER deterministic electrical model disabled");
    return ESP_OK;
#else
    const i2c_master_bus_config_t bus_config = {
        .i2c_port = I2C_NUM_0,
        .sda_io_num = I2C_SDA_GPIO,
        .scl_io_num = I2C_SCL_GPIO,
        .clk_source = I2C_CLK_SRC_DEFAULT,
        .glitch_ignore_cnt = 7,
        .flags.enable_internal_pullup = true,
    };
    ESP_RETURN_ON_ERROR(i2c_new_master_bus(&bus_config, &context->i2c_bus), TAG, "i2c bus");
    const i2c_device_config_t temp_config = {
        .dev_addr_length = I2C_ADDR_BIT_LEN_7,
        .device_address = TMP117_ADDRESS,
        .scl_speed_hz = 400000,
    };
    const i2c_device_config_t current_config = {
        .dev_addr_length = I2C_ADDR_BIT_LEN_7,
        .device_address = INA219_ADDRESS,
        .scl_speed_hz = 400000,
    };
    ESP_RETURN_ON_ERROR(i2c_master_bus_add_device(context->i2c_bus, &temp_config,
                                                   &context->tmp117),
                        TAG, "TMP117 attach");
    ESP_RETURN_ON_ERROR(i2c_master_bus_add_device(context->i2c_bus, &current_config,
                                                   &context->ina219),
                        TAG, "INA219 attach");
    ESP_RETURN_ON_ERROR(i2c_write_register(context->ina219, 0x00U, 0x399FU), TAG,
                        "INA219 configuration");
    ESP_RETURN_ON_ERROR(i2c_write_register(context->ina219, 0x05U, 4096U), TAG,
                        "INA219 calibration");

    const spi_bus_config_t spi_bus = {
        .mosi_io_num = SPI_MOSI_GPIO,
        .miso_io_num = SPI_MISO_GPIO,
        .sclk_io_num = SPI_CLOCK_GPIO,
        .quadwp_io_num = -1,
        .quadhd_io_num = -1,
        .max_transfer_sz = 8,
    };
    ESP_RETURN_ON_ERROR(spi_bus_initialize(SPI2_HOST, &spi_bus, SPI_DMA_DISABLED), TAG,
                        "spi bus");
    const spi_device_interface_config_t device = {
        .clock_speed_hz = 5000000,
        .mode = 3,
        .spics_io_num = ADXL345_CS_GPIO,
        .queue_size = 1,
    };
    ESP_RETURN_ON_ERROR(spi_bus_add_device(SPI2_HOST, &device, &context->adxl345), TAG,
                        "ADXL345 attach");
    ESP_RETURN_ON_ERROR(adxl_write(context, 0x31U, 0x08U), TAG, "ADXL345 data format");
    ESP_RETURN_ON_ERROR(adxl_write(context, 0x2CU, 0x0AU), TAG, "ADXL345 100 Hz rate");
    ESP_RETURN_ON_ERROR(adxl_write(context, 0x2EU, 0x80U), TAG, "ADXL345 data ready");
    ESP_RETURN_ON_ERROR(adxl_write(context, 0x2DU, 0x08U), TAG, "ADXL345 measurement mode");
    gpio_config_t interrupt_pin = {
        .pin_bit_mask = UINT64_C(1) << ADXL345_DRDY_GPIO,
        .mode = GPIO_MODE_INPUT,
        .intr_type = GPIO_INTR_POSEDGE,
    };
    ESP_RETURN_ON_ERROR(gpio_config(&interrupt_pin), TAG, "ADXL345 interrupt GPIO");
    const esp_err_t isr_result = gpio_install_isr_service(ESP_INTR_FLAG_IRAM);
    if (isr_result != ESP_OK && isr_result != ESP_ERR_INVALID_STATE) {
        return isr_result;
    }
    ESP_RETURN_ON_ERROR(gpio_isr_handler_add(ADXL345_DRDY_GPIO, vibration_data_ready, context),
                        TAG, "ADXL345 ISR");

    const uart_config_t uart_config = {
        .baud_rate = 115200,
        .data_bits = UART_DATA_8_BITS,
        .parity = UART_PARITY_EVEN,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
        .source_clk = UART_SCLK_DEFAULT,
    };
    ESP_RETURN_ON_ERROR(uart_driver_install(RS485_UART, 256, 0, 0, NULL, 0), TAG,
                        "RS485 UART driver");
    ESP_RETURN_ON_ERROR(uart_param_config(RS485_UART, &uart_config), TAG, "RS485 UART config");
    ESP_RETURN_ON_ERROR(uart_set_pin(RS485_UART, RS485_TX_GPIO, RS485_RX_GPIO, RS485_DE_GPIO,
                                     UART_PIN_NO_CHANGE),
                        TAG, "RS485 pins");
    ESP_RETURN_ON_ERROR(uart_set_mode(RS485_UART, UART_MODE_RS485_HALF_DUPLEX), TAG,
                        "RS485 half duplex");
    context->initialized = true;
    return ESP_OK;
#endif
}

#if CONFIG_IIOT_SIMULATION
static gateway_sample_t simulated_read(sensor_context_t *context) {
    static int previous_button = 1;
    const int button = gpio_get_level(IIOT_PROVISION_GPIO);
    if (previous_button == 1 && button == 0) {
        context->simulation_fault = (uint8_t)((context->simulation_fault + 1U) % 6U);
        ESP_LOGW(TAG, "code=SIMULATION_SCENARIO scenario=%u",
                 (unsigned)context->simulation_fault);
    }
    previous_button = button;
    const float phase = context->simulation_step * 0.12F;
    gateway_sample_t sample = {
        .temperature_c = 41.5F + 0.3F * sinf(phase * 0.1F),
        .current_a = 0.64F + 0.02F * sinf(phase),
        .vibration_mps2 = 1.1F * sinf(phase * 3.0F),
        .temperature_status = IIOT_SENSOR_GOOD,
        .current_status = IIOT_SENSOR_GOOD,
        .vibration_status = IIOT_SENSOR_GOOD,
    };
    if (context->simulation_fault == 1U) {
        sample.temperature_c += fminf(context->simulation_step * 0.025F, 45.0F);
    } else if (context->simulation_fault == 2U) {
        sample.vibration_mps2 *= 6.0F;
    } else if (context->simulation_fault == 3U) {
        sample.current_a += 1.35F;
    } else if (context->simulation_fault == 4U) {
        sample.temperature_c = NAN;
        sample.temperature_status = IIOT_SENSOR_DRIVER_ERROR;
    } else if (context->simulation_fault == 5U) {
        (void)snprintf(modbus_status, sizeof(modbus_status), "timeout");
    }
    if (context->simulation_fault != 5U) {
        (void)snprintf(modbus_status, sizeof(modbus_status), "ok");
    }
    ++context->simulation_step;
    return sample;
}
#endif

gateway_sample_t sensor_drivers_read(sensor_context_t *context) {
    if (!context->initialized) {
        return (gateway_sample_t){.temperature_c = NAN,
                                  .current_a = NAN,
                                  .vibration_mps2 = NAN,
                                  .temperature_status = IIOT_SENSOR_DRIVER_ERROR,
                                  .current_status = IIOT_SENSOR_DRIVER_ERROR,
                                  .vibration_status = IIOT_SENSOR_DRIVER_ERROR};
    }
#if CONFIG_IIOT_SIMULATION
    return simulated_read(context);
#else
    gateway_sample_t sample = {.temperature_status = IIOT_SENSOR_GOOD,
                               .current_status = IIOT_SENSOR_GOOD,
                               .vibration_status = IIOT_SENSOR_GOOD};
    uint16_t raw = 0U;
    if (i2c_read_register(context->tmp117, 0x00U, &raw) == ESP_OK) {
        sample.temperature_c = (int16_t)raw * 0.0078125F;
    } else {
        sample.temperature_c = NAN;
        sample.temperature_status = IIOT_SENSOR_DRIVER_ERROR;
    }
    if (i2c_read_register(context->ina219, 0x04U, &raw) == ESP_OK) {
        sample.current_a = (int16_t)raw * 0.0001F;
    } else {
        sample.current_a = NAN;
        sample.current_status = IIOT_SENSOR_DRIVER_ERROR;
    }
    vibration_waiter = xTaskGetCurrentTaskHandle();
    if (ulTaskNotifyTake(pdTRUE, pdMS_TO_TICKS(20)) == 0U ||
        adxl_read_xyz(context, &sample.vibration_mps2) != ESP_OK) {
        sample.vibration_mps2 = NAN;
        sample.vibration_status = IIOT_SENSOR_MISSING;
    }
    vibration_waiter = NULL;
    if (context->simulation_step++ % 10U == 0U) {
        modbus_poll_identity();
    }
    return sample;
#endif
}

const char *sensor_drivers_modbus_status(void) { return modbus_status; }
