/*
 * SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
 * SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available
 */
#include "main.h"
#include "stm32f1xx_it.h"

void SysTick_Handler(void) {
    HAL_IncTick();
    HAL_SYSTICK_IRQHandler();
}

void TIM3_IRQHandler(void) { HAL_TIM_IRQHandler(&htim3); }

void USART2_IRQHandler(void) { HAL_UART_IRQHandler(&huart2); }
