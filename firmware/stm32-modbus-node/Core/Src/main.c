/*
 * SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
 * SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available
 */
#include "main.h"

#include "modbus_node.h"

#include <stdbool.h>
#include <string.h>

#define CONFIG_FLASH_ADDRESS UINT32_C(0x0800fc00)
#define CONFIG_FLASH_PAGE_SIZE 1024U
#define RX_BUFFER_SIZE 64U
#define FAULT_ADC_RANGE (UINT16_C(1) << 1U)
#define FAULT_SAMPLE_STALE (UINT16_C(1) << 2U)
#define FAULT_UART (UINT16_C(1) << 3U)

ADC_HandleTypeDef hadc1;
TIM_HandleTypeDef htim3;
UART_HandleTypeDef huart2;
IWDG_HandleTypeDef hiwdg;

static modbus_node_t node;
static uint8_t receive_buffer[RX_BUFFER_SIZE];
static volatile uint16_t received_length;
static volatile bool frame_ready;
static volatile bool sample_due;
static uint32_t last_sample_ms;
static uint32_t reset_count;
static uint16_t runtime_faults;

static void SystemClock_Config(void);
static void MX_GPIO_Init(void);
static void MX_ADC1_Init(void);
static void MX_TIM3_Init(void);
static void MX_USART2_UART_Init(void);
static void MX_IWDG_Init(void);

static uint32_t load_reset_count(void) {
#ifdef IIOT_WOKWI
    return 1U;
#else
    HAL_PWR_EnableBkUpAccess();
    __HAL_RCC_BKP_CLK_ENABLE();
    if (BKP->DR1 != UINT16_C(0x4949)) {
        BKP->DR1 = UINT16_C(0x4949);
        BKP->DR2 = 1U;
    } else if (BKP->DR2 != UINT16_MAX) {
        ++BKP->DR2;
    }
    return BKP->DR2;
#endif
}

static bool persist_config(const modbus_node_config_t *config, void *context) {
    (void)context;
    FLASH_EraseInitTypeDef erase = {
        .TypeErase = FLASH_TYPEERASE_PAGES,
        .PageAddress = CONFIG_FLASH_ADDRESS,
        .NbPages = 1U,
    };
    uint32_t page_error = 0U;
    if (HAL_FLASH_Unlock() != HAL_OK) {
        return false;
    }
    bool success = HAL_FLASHEx_Erase(&erase, &page_error) == HAL_OK;
    for (size_t offset = 0U; success && offset < sizeof(*config); offset += 2U) {
        uint16_t value = UINT16_MAX;
        const size_t remaining = sizeof(*config) - offset;
        memcpy(&value, (const uint8_t *)config + offset, remaining >= 2U ? 2U : 1U);
        success = HAL_FLASH_Program(FLASH_TYPEPROGRAM_HALFWORD,
                                    CONFIG_FLASH_ADDRESS + (uint32_t)offset, value) == HAL_OK;
    }
    (void)HAL_FLASH_Lock();
    return success &&
           memcmp((const void *)CONFIG_FLASH_ADDRESS, config, sizeof(*config)) == 0;
}

static void sample_fixture(void) {
    uint16_t adc_raw = 0U;
    modbus_sensor_status_t status = MODBUS_SENSOR_OK;
    uint16_t faults = runtime_faults;
    if (HAL_ADC_Start(&hadc1) != HAL_OK ||
        HAL_ADC_PollForConversion(&hadc1, 2U) != HAL_OK) {
        status = MODBUS_SENSOR_ADC_ERROR;
        faults |= FAULT_ADC_RANGE;
    } else {
        adc_raw = (uint16_t)HAL_ADC_GetValue(&hadc1);
        if (adc_raw < 10U || adc_raw > 4085U) {
            status = MODBUS_SENSOR_OUT_OF_RANGE;
            faults |= FAULT_ADC_RANGE;
        } else {
            faults &= (uint16_t)~FAULT_ADC_RANGE;
        }
    }
    (void)HAL_ADC_Stop(&hadc1);
    const int32_t uncalibrated = 2000 + ((int32_t)adc_raw * 8000) / 4095;
    int32_t calibrated = uncalibrated + node.config.calibration_offset_centi_c;
    calibrated = (calibrated * node.config.calibration_gain_q15) / 32768;
    if (calibrated < -4000 || calibrated > 12500) {
        status = MODBUS_SENSOR_OUT_OF_RANGE;
        faults |= FAULT_ADC_RANGE;
    }
    runtime_faults = faults;
    last_sample_ms = HAL_GetTick();
    modbus_node_set_measurement(&node, adc_raw, (int16_t)calibrated, status, faults,
                                HAL_GetTick(), reset_count);
}

static void transmit_response(const uint8_t *response, size_t length) {
    HAL_GPIO_WritePin(RS485_DE_GPIO_Port, RS485_DE_Pin, GPIO_PIN_SET);
    for (volatile uint32_t delay = 0U; delay < 32U; ++delay) {
        __NOP();
    }
    if (HAL_UART_Transmit(&huart2, response, (uint16_t)length, 50U) != HAL_OK) {
        runtime_faults |= FAULT_UART;
    }
    while (__HAL_UART_GET_FLAG(&huart2, UART_FLAG_TC) == RESET) {
    }
    HAL_GPIO_WritePin(RS485_DE_GPIO_Port, RS485_DE_Pin, GPIO_PIN_RESET);
}

int main(void) {
    HAL_Init();
    SystemClock_Config();
    MX_GPIO_Init();
    MX_ADC1_Init();
    MX_TIM3_Init();
    MX_USART2_UART_Init();
    MX_IWDG_Init();
    (void)HAL_ADCEx_Calibration_Start(&hadc1);
    reset_count = load_reset_count();

    const modbus_node_config_t *stored =
        (const modbus_node_config_t *)CONFIG_FLASH_ADDRESS;
    modbus_node_init(&node, stored, persist_config, NULL);
    if (!modbus_node_config_validate(stored)) {
        (void)persist_config(&node.config, NULL);
    }
    HAL_GPIO_WritePin(RS485_DE_GPIO_Port, RS485_DE_Pin, GPIO_PIN_RESET);
    if (HAL_UARTEx_ReceiveToIdle_IT(&huart2, receive_buffer, sizeof(receive_buffer)) != HAL_OK ||
        HAL_TIM_Base_Start_IT(&htim3) != HAL_OK) {
        Error_Handler();
    }
    sample_due = true;

    for (;;) {
        if (sample_due) {
            sample_due = false;
            sample_fixture();
        }
        if (HAL_GetTick() - last_sample_ms > 500U) {
            runtime_faults |= FAULT_SAMPLE_STALE;
            modbus_node_set_measurement(&node, node.adc_raw, node.temperature_centi_c,
                                        MODBUS_SENSOR_STALE, runtime_faults, HAL_GetTick(),
                                        reset_count);
        } else {
            runtime_faults &= (uint16_t)~FAULT_SAMPLE_STALE;
        }
        if (frame_ready) {
            uint8_t request[RX_BUFFER_SIZE];
            uint16_t length = 0U;
            __disable_irq();
            length = received_length;
            memcpy(request, receive_buffer, length);
            frame_ready = false;
            __enable_irq();
            (void)HAL_UARTEx_ReceiveToIdle_IT(&huart2, receive_buffer,
                                              sizeof(receive_buffer));
            uint8_t response[MODBUS_NODE_MAX_RESPONSE];
            size_t response_length = 0U;
            if (modbus_node_handle_request(&node, request, length, response, sizeof(response),
                                           &response_length) == MODBUS_NODE_RESPONSE) {
                transmit_response(response, response_length);
            }
        }
#ifndef IIOT_WOKWI
        (void)HAL_IWDG_Refresh(&hiwdg);
#endif
        HAL_GPIO_WritePin(STATUS_LED_GPIO_Port, STATUS_LED_Pin,
                          runtime_faults == 0U ? GPIO_PIN_SET : GPIO_PIN_RESET);
    }
}

void HAL_UARTEx_RxEventCallback(UART_HandleTypeDef *uart, uint16_t size) {
    if (uart->Instance != USART2) {
        return;
    }
    if (size == 8U && !frame_ready) {
        received_length = size;
        frame_ready = true;
    } else {
        runtime_faults |= FAULT_UART;
        (void)HAL_UARTEx_ReceiveToIdle_IT(&huart2, receive_buffer,
                                          sizeof(receive_buffer));
    }
}

void HAL_UART_ErrorCallback(UART_HandleTypeDef *uart) {
    if (uart->Instance == USART2) {
        runtime_faults |= FAULT_UART;
        (void)HAL_UARTEx_ReceiveToIdle_IT(&huart2, receive_buffer, sizeof(receive_buffer));
    }
}

void HAL_TIM_PeriodElapsedCallback(TIM_HandleTypeDef *timer) {
    if (timer->Instance == TIM3) {
        sample_due = true;
    }
}

static void SystemClock_Config(void) {
    RCC_OscInitTypeDef oscillator = {
        .OscillatorType = RCC_OSCILLATORTYPE_HSE,
        .HSEState = RCC_HSE_ON,
        .HSEPredivValue = RCC_HSE_PREDIV_DIV1,
        .HSIState = RCC_HSI_ON,
        .PLL.PLLState = RCC_PLL_ON,
        .PLL.PLLSource = RCC_PLLSOURCE_HSE,
        .PLL.PLLMUL = RCC_PLL_MUL9,
    };
    if (HAL_RCC_OscConfig(&oscillator) != HAL_OK) {
        Error_Handler();
    }
    RCC_ClkInitTypeDef clocks = {
        .ClockType = RCC_CLOCKTYPE_HCLK | RCC_CLOCKTYPE_SYSCLK | RCC_CLOCKTYPE_PCLK1 |
                     RCC_CLOCKTYPE_PCLK2,
        .SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK,
        .AHBCLKDivider = RCC_SYSCLK_DIV1,
        .APB1CLKDivider = RCC_HCLK_DIV2,
        .APB2CLKDivider = RCC_HCLK_DIV1,
    };
    if (HAL_RCC_ClockConfig(&clocks, FLASH_LATENCY_2) != HAL_OK) {
        Error_Handler();
    }
    RCC_PeriphCLKInitTypeDef peripheral_clock = {
        .PeriphClockSelection = RCC_PERIPHCLK_ADC,
        .AdcClockSelection = RCC_ADCPCLK2_DIV6,
    };
    if (HAL_RCCEx_PeriphCLKConfig(&peripheral_clock) != HAL_OK) {
        Error_Handler();
    }
}

static void MX_GPIO_Init(void) {
    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_GPIOB_CLK_ENABLE();
    __HAL_RCC_GPIOC_CLK_ENABLE();
    HAL_GPIO_WritePin(GPIOB, RS485_DE_Pin, GPIO_PIN_RESET);
    GPIO_InitTypeDef output = {
        .Pin = RS485_DE_Pin,
        .Mode = GPIO_MODE_OUTPUT_PP,
        .Speed = GPIO_SPEED_FREQ_HIGH,
    };
    HAL_GPIO_Init(GPIOB, &output);
    output.Pin = STATUS_LED_Pin;
    output.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(GPIOC, &output);
    GPIO_InitTypeDef analog = {.Pin = GPIO_PIN_0, .Mode = GPIO_MODE_ANALOG};
    HAL_GPIO_Init(GPIOA, &analog);
    GPIO_InitTypeDef uart_tx = {
        .Pin = GPIO_PIN_2,
        .Mode = GPIO_MODE_AF_PP,
        .Speed = GPIO_SPEED_FREQ_HIGH,
    };
    HAL_GPIO_Init(GPIOA, &uart_tx);
    GPIO_InitTypeDef uart_rx = {.Pin = GPIO_PIN_3, .Mode = GPIO_MODE_INPUT};
    HAL_GPIO_Init(GPIOA, &uart_rx);
}

static void MX_ADC1_Init(void) {
    __HAL_RCC_ADC1_CLK_ENABLE();
    hadc1.Instance = ADC1;
    hadc1.Init.ScanConvMode = ADC_SCAN_DISABLE;
    hadc1.Init.ContinuousConvMode = DISABLE;
    hadc1.Init.DiscontinuousConvMode = DISABLE;
    hadc1.Init.ExternalTrigConv = ADC_SOFTWARE_START;
    hadc1.Init.DataAlign = ADC_DATAALIGN_RIGHT;
    hadc1.Init.NbrOfConversion = 1U;
    if (HAL_ADC_Init(&hadc1) != HAL_OK) {
        Error_Handler();
    }
    ADC_ChannelConfTypeDef channel = {
        .Channel = ADC_CHANNEL_0,
        .Rank = ADC_REGULAR_RANK_1,
        .SamplingTime = ADC_SAMPLETIME_55CYCLES_5,
    };
    if (HAL_ADC_ConfigChannel(&hadc1, &channel) != HAL_OK) {
        Error_Handler();
    }
}

static void MX_TIM3_Init(void) {
    __HAL_RCC_TIM3_CLK_ENABLE();
    htim3.Instance = TIM3;
    htim3.Init.Prescaler = 7200U - 1U;
    htim3.Init.CounterMode = TIM_COUNTERMODE_UP;
    htim3.Init.Period = 1000U - 1U;
    htim3.Init.ClockDivision = TIM_CLOCKDIVISION_DIV1;
    htim3.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_DISABLE;
    if (HAL_TIM_Base_Init(&htim3) != HAL_OK) {
        Error_Handler();
    }
    HAL_NVIC_SetPriority(TIM3_IRQn, 3U, 0U);
    HAL_NVIC_EnableIRQ(TIM3_IRQn);
}

static void MX_USART2_UART_Init(void) {
    __HAL_RCC_USART2_CLK_ENABLE();
    huart2.Instance = USART2;
    huart2.Init.BaudRate = 115200U;
    huart2.Init.WordLength = UART_WORDLENGTH_9B;
    huart2.Init.StopBits = UART_STOPBITS_1;
    huart2.Init.Parity = UART_PARITY_EVEN;
    huart2.Init.Mode = UART_MODE_TX_RX;
    huart2.Init.HwFlowCtl = UART_HWCONTROL_NONE;
    huart2.Init.OverSampling = UART_OVERSAMPLING_16;
    if (HAL_UART_Init(&huart2) != HAL_OK) {
        Error_Handler();
    }
    HAL_NVIC_SetPriority(USART2_IRQn, 2U, 0U);
    HAL_NVIC_EnableIRQ(USART2_IRQn);
}

static void MX_IWDG_Init(void) {
#ifndef IIOT_WOKWI
    hiwdg.Instance = IWDG;
    hiwdg.Init.Prescaler = IWDG_PRESCALER_64;
    hiwdg.Init.Reload = 1250U;
    if (HAL_IWDG_Init(&hiwdg) != HAL_OK) {
        Error_Handler();
    }
#endif
}

void Error_Handler(void) {
    __disable_irq();
    HAL_GPIO_WritePin(STATUS_LED_GPIO_Port, STATUS_LED_Pin, GPIO_PIN_RESET);
    for (;;) {
    }
}
