/*
 * SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
 * SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available
 */
#include "gateway_platform.h"

#include "sensor_drivers.h"

#include <stdio.h>
#include <string.h>
#include <time.h>

#include "driver/gpio.h"
#include "esp_check.h"
#include "esp_event.h"
#include "esp_log.h"
#include "esp_mac.h"
#include "esp_netif.h"
#include "esp_netif_sntp.h"
#include "esp_random.h"
#include "esp_system.h"
#include "esp_timer.h"
#include "esp_wifi.h"
#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "mqtt_client.h"
#include "nvs.h"
#include "nvs_flash.h"

#define WIFI_CONNECTED_BIT BIT0
#define MQTT_CONNECTED_BIT BIT1
#define SEQUENCE_RESERVATION 256U

typedef struct {
    uint32_t magic;
    uint32_t generation;
    uint32_t dropped;
    uint8_t head;
    uint8_t count;
    uint8_t capacity;
    uint8_t reserved;
    uint32_t checksum;
} queue_metadata_t;

typedef struct {
    uint32_t magic;
    uint32_t previous_generation;
    iiot_telemetry_t telemetry;
    uint32_t checksum;
} pending_enqueue_t;

static const char *const TAG = "platform";
static nvs_handle_t storage;
static sensor_context_t sensors;
static EventGroupHandle_t network_events;
static esp_mqtt_client_handle_t mqtt_client;
static gateway_command_handler_t command_handler;
static iiot_config_t active_config;
static char broker_uri[176];
static char command_topic[IIOT_TOPIC_MAX];
static char availability_lwt[256];
static char availability_online[256];
static bool relay_on;
static uint64_t sequence_next;
static uint64_t sequence_end;
static SemaphoreHandle_t sequence_mutex;
static uint32_t queue_generation;

static void slot_key(uint8_t slot, char key[8]);

static bool save_queue_metadata(const iiot_offline_queue_t *queue) {
    queue_metadata_t metadata;
    memset(&metadata, 0, sizeof(metadata));
    metadata.magic = UINT32_C(0x51554555);
    metadata.generation = queue_generation;
    metadata.dropped = queue->dropped_message_count;
    metadata.head = queue->head;
    metadata.count = queue->count;
    metadata.capacity = queue->capacity;
    metadata.checksum = iiot_crc32(&metadata, offsetof(queue_metadata_t, checksum));
    return nvs_set_blob(storage, "queue_meta", &metadata, sizeof(metadata)) == ESP_OK &&
           nvs_commit(storage) == ESP_OK;
}

static bool erase_pending_enqueue(void) {
    const esp_err_t result = nvs_erase_key(storage, "q_pending");
    return (result == ESP_OK || result == ESP_ERR_NVS_NOT_FOUND) &&
           nvs_commit(storage) == ESP_OK;
}

static bool save_pending_enqueue(const iiot_telemetry_t *telemetry) {
    pending_enqueue_t pending;
    memset(&pending, 0, sizeof(pending));
    pending.magic = UINT32_C(0x51504e44);
    pending.previous_generation = queue_generation;
    pending.telemetry = *telemetry;
    pending.checksum = iiot_crc32(&pending, offsetof(pending_enqueue_t, checksum));
    return nvs_set_blob(storage, "q_pending", &pending, sizeof(pending)) == ESP_OK &&
           nvs_commit(storage) == ESP_OK;
}

static bool persist_enqueued_record(iiot_offline_queue_t *queue,
                                    const iiot_telemetry_t *telemetry) {
    const uint8_t slot = queue->count == queue->capacity
                             ? queue->head
                             : (uint8_t)((queue->head + queue->count) % queue->capacity);
    char key[8];
    slot_key(slot, key);
    if (nvs_set_blob(storage, key, telemetry, sizeof(*telemetry)) != ESP_OK) {
        return false;
    }
    (void)iiot_offline_queue_push(queue, telemetry);
    ++queue_generation;
    return save_queue_metadata(queue);
}

static void slot_key(uint8_t slot, char key[8]) {
    (void)snprintf(key, 8U, "q%02u", (unsigned)slot);
}

static void relay_gpio(bool enabled) {
    relay_on = enabled;
    (void)gpio_set_level(IIOT_RELAY_GPIO, enabled ? 1U : 0U);
}

static void network_event(void *argument, esp_event_base_t base, int32_t event_id,
                          void *event_data) {
    (void)argument;
    if (base == WIFI_EVENT && event_id == WIFI_EVENT_STA_DISCONNECTED) {
        xEventGroupClearBits(network_events, WIFI_CONNECTED_BIT | MQTT_CONNECTED_BIT);
        relay_gpio(false);
        ESP_LOGW(TAG, "code=WIFI_DISCONNECTED relay=off");
    } else if (base == IP_EVENT && event_id == IP_EVENT_STA_GOT_IP) {
        xEventGroupSetBits(network_events, WIFI_CONNECTED_BIT);
        ESP_LOGI(TAG, "code=WIFI_CONNECTED");
    } else if (base == MQTT_EVENTS && event_id == MQTT_EVENT_CONNECTED) {
        xEventGroupSetBits(network_events, MQTT_CONNECTED_BIT);
        (void)esp_mqtt_client_subscribe(mqtt_client, command_topic, 1);
        (void)gateway_mqtt_publish("availability", availability_online, 1, true);
        ESP_LOGI(TAG, "code=MQTT_CONNECTED");
    } else if (base == MQTT_EVENTS && event_id == MQTT_EVENT_DISCONNECTED) {
        xEventGroupClearBits(network_events, MQTT_CONNECTED_BIT);
        relay_gpio(false);
        ESP_LOGW(TAG, "code=MQTT_DISCONNECTED relay=off");
    } else if (base == MQTT_EVENTS && event_id == MQTT_EVENT_DATA) {
        const esp_mqtt_event_handle_t event = event_data;
        if (event->topic_len == (int)strlen(command_topic) &&
            memcmp(event->topic, command_topic, (size_t)event->topic_len) == 0 &&
            event->data_len > 0 && event->data_len < 2048 && command_handler != NULL) {
            command_handler(event->data, (size_t)event->data_len);
        }
    }
}

esp_err_t gateway_platform_init(void) {
    const gpio_config_t outputs = {
        .pin_bit_mask = (UINT64_C(1) << IIOT_RELAY_GPIO) |
                        (UINT64_C(1) << IIOT_STATUS_LED_GPIO),
        .mode = GPIO_MODE_OUTPUT,
    };
    ESP_ERROR_CHECK(gpio_config(&outputs));
    gateway_relay_force_off();
    (void)gpio_set_level(IIOT_STATUS_LED_GPIO, 0U);
    const gpio_config_t provision_button = {
        .pin_bit_mask = UINT64_C(1) << IIOT_PROVISION_GPIO,
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_ENABLE,
    };
    ESP_ERROR_CHECK(gpio_config(&provision_button));

    esp_err_t result = nvs_flash_init();
    if (result == ESP_ERR_NVS_NO_FREE_PAGES || result == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        result = nvs_flash_init();
    }
    if (result != ESP_OK) {
        return result;
    }
    ESP_RETURN_ON_ERROR(nvs_open("iiot", NVS_READWRITE, &storage), TAG, "open NVS");
    sequence_mutex = xSemaphoreCreateMutex();
    if (sequence_mutex == NULL) {
        return ESP_ERR_NO_MEM;
    }
    uint32_t boots = 0U;
    (void)nvs_get_u32(storage, "reset_count", &boots);
    ++boots;
    (void)nvs_set_u32(storage, "reset_count", boots);
    (void)nvs_commit(storage);
    return ESP_OK;
}

void gateway_relay_force_off(void) { relay_gpio(false); }

void gateway_relay_set(bool enabled) { relay_gpio(enabled); }

bool gateway_relay_is_on(void) { return relay_on; }

bool gateway_factory_reset_requested(void) {
    if (gpio_get_level(IIOT_PROVISION_GPIO) != 0) {
        return false;
    }
    ESP_LOGW(TAG, "code=FACTORY_RESET_ARMED hold_ms=10000");
    for (uint32_t elapsed = 0U; elapsed < 10000U; elapsed += 50U) {
        if (gpio_get_level(IIOT_PROVISION_GPIO) != 0) {
            ESP_LOGI(TAG, "code=FACTORY_RESET_CANCELLED");
            return false;
        }
        vTaskDelay(pdMS_TO_TICKS(50));
    }
    return true;
}

uint32_t gateway_reset_count(void) {
    uint32_t count = 0U;
    (void)nvs_get_u32(storage, "reset_count", &count);
    return count;
}

const char *gateway_reset_reason(void) {
    switch (esp_reset_reason()) {
        case ESP_RST_POWERON:
            return "power_on";
        case ESP_RST_SW:
            return "software";
        case ESP_RST_PANIC:
            return "panic";
        case ESP_RST_INT_WDT:
            return "interrupt_watchdog";
        case ESP_RST_TASK_WDT:
            return "task_watchdog";
        case ESP_RST_WDT:
            return "watchdog";
        case ESP_RST_BROWNOUT:
            return "brownout";
        default:
            return "other";
    }
}

bool gateway_config_load(iiot_config_t *config, bool *used_fallback) {
    size_t length = sizeof(*config);
    const esp_err_t result = nvs_get_blob(storage, "config", config, &length);
    if (result == ESP_ERR_NVS_NOT_FOUND) {
        iiot_config_defaults(config);
        *used_fallback = false;
        return true;
    }
    if (result == ESP_OK && length == sizeof(iiot_config_v0_t)) {
        iiot_config_v0_t legacy;
        length = sizeof(legacy);
        if (nvs_get_blob(storage, "config", &legacy, &length) == ESP_OK &&
            iiot_config_migrate_v0(&legacy, config) && gateway_config_save(config)) {
            *used_fallback = false;
            ESP_LOGW(TAG, "code=CONFIG_MIGRATED from=0 to=1");
            return true;
        }
    }
    if (result != ESP_OK || length != sizeof(*config) ||
        !iiot_config_validate(config, NULL, 0U)) {
        iiot_config_defaults(config);
        *used_fallback = true;
        return false;
    }
    *used_fallback = false;
    return true;
}

bool gateway_config_save(const iiot_config_t *config) {
    iiot_config_t candidate = *config;
    ++candidate.generation;
    iiot_config_finalize(&candidate);
    if (!iiot_config_validate(&candidate, NULL, 0U)) {
        return false;
    }
    return nvs_set_blob(storage, "config", &candidate, sizeof(candidate)) == ESP_OK &&
           nvs_commit(storage) == ESP_OK;
}

void gateway_config_erase(void) {
    gateway_relay_force_off();
    (void)nvs_erase_all(storage);
    (void)nvs_commit(storage);
}

bool gateway_is_provisioned(const iiot_config_t *config) {
    return config->wifi_ssid[0] != '\0' && config->mqtt_host[0] != '\0';
}

bool gateway_offline_load(iiot_offline_queue_t *queue, uint8_t capacity) {
    queue_metadata_t metadata = {0};
    size_t length = sizeof(metadata);
    if (nvs_get_blob(storage, "queue_meta", &metadata, &length) != ESP_OK ||
        length != sizeof(metadata) || metadata.magic != UINT32_C(0x51554555) ||
        metadata.checksum != iiot_crc32(&metadata, offsetof(queue_metadata_t, checksum)) ||
        metadata.capacity == 0U || metadata.capacity > IIOT_OFFLINE_CAPACITY_MAX ||
        metadata.count > metadata.capacity || metadata.head >= metadata.capacity) {
        iiot_offline_queue_init(queue, capacity);
        queue_generation = 0U;
        if (!save_queue_metadata(queue)) {
            return false;
        }
    } else {
        iiot_offline_queue_init(queue, metadata.capacity);
        queue->head = metadata.head;
        queue->count = metadata.count;
        queue->dropped_message_count = metadata.dropped;
        queue_generation = metadata.generation;
        for (uint8_t offset = 0U; offset < queue->count; ++offset) {
            const uint8_t slot = (uint8_t)((queue->head + offset) % queue->capacity);
            char key[8];
            slot_key(slot, key);
            length = sizeof(queue->records[slot]);
            if (nvs_get_blob(storage, key, &queue->records[slot], &length) != ESP_OK ||
                length != sizeof(queue->records[slot])) {
                iiot_offline_queue_init(queue, capacity);
                queue_generation = 0U;
                return save_queue_metadata(queue) && erase_pending_enqueue();
            }
        }
    }

    pending_enqueue_t pending;
    length = sizeof(pending);
    const esp_err_t pending_result = nvs_get_blob(storage, "q_pending", &pending, &length);
    if (pending_result == ESP_ERR_NVS_NOT_FOUND) {
        return true;
    }
    if (pending_result != ESP_OK || length != sizeof(pending) ||
        pending.magic != UINT32_C(0x51504e44) ||
        pending.checksum != iiot_crc32(&pending, offsetof(pending_enqueue_t, checksum))) {
        ESP_LOGE(TAG, "code=OFFLINE_QUEUE_JOURNAL_INVALID");
        return erase_pending_enqueue();
    }
    if (queue_generation == pending.previous_generation) {
        if (!persist_enqueued_record(queue, &pending.telemetry)) {
            return false;
        }
        ESP_LOGW(TAG, "code=OFFLINE_QUEUE_JOURNAL_RECOVERED generation=%lu",
                 (unsigned long)queue_generation);
    } else if (queue_generation != pending.previous_generation + 1U) {
        ESP_LOGE(TAG, "code=OFFLINE_QUEUE_JOURNAL_GENERATION_MISMATCH");
        return false;
    }
    return erase_pending_enqueue();
}

bool gateway_offline_push(iiot_offline_queue_t *queue,
                          const iiot_telemetry_t *telemetry) {
    const uint32_t dropped_before = queue->dropped_message_count;
    if (!save_pending_enqueue(telemetry) || !persist_enqueued_record(queue, telemetry) ||
        !erase_pending_enqueue()) {
        ESP_LOGE(TAG, "code=OFFLINE_QUEUE_PERSIST_FAILED");
        return false;
    }
    if (queue->dropped_message_count != dropped_before) {
        ESP_LOGW(TAG, "code=OFFLINE_QUEUE_DROPPED_OLDEST dropped=%lu",
                 (unsigned long)queue->dropped_message_count);
    }
    return true;
}

bool gateway_offline_pop(iiot_offline_queue_t *queue, iiot_telemetry_t *telemetry) {
    if (queue->count == 0U) {
        return false;
    }
    const uint8_t slot = queue->head;
    const uint8_t previous_head = queue->head;
    if (!iiot_offline_queue_pop(queue, telemetry)) {
        return false;
    }
    ++queue_generation;
    if (!save_queue_metadata(queue)) {
        --queue_generation;
        queue->head = previous_head;
        ++queue->count;
        return false;
    }
    char key[8];
    slot_key(slot, key);
    (void)nvs_erase_key(storage, key);
    return nvs_commit(storage) == ESP_OK;
}

uint64_t gateway_next_sequence(void) {
    xSemaphoreTake(sequence_mutex, portMAX_DELAY);
    if (sequence_next == 0U || sequence_next > sequence_end) {
        uint64_t high_water = 0U;
        (void)nvs_get_u64(storage, "sequence_hi", &high_water);
        sequence_next = high_water + 1U;
        sequence_end = high_water + SEQUENCE_RESERVATION;
        ESP_ERROR_CHECK(nvs_set_u64(storage, "sequence_hi", sequence_end));
        ESP_ERROR_CHECK(nvs_commit(storage));
    }
    const uint64_t result = sequence_next++;
    xSemaphoreGive(sequence_mutex);
    return result;
}

esp_err_t gateway_sensors_init(void) { return sensor_drivers_init(&sensors); }

gateway_sample_t gateway_sensors_read(void) { return sensor_drivers_read(&sensors); }

const char *gateway_modbus_status(void) { return sensor_drivers_modbus_status(); }

esp_err_t gateway_network_start(const iiot_config_t *config,
                                gateway_command_handler_t handler) {
    active_config = *config;
    command_handler = handler;
    network_events = xEventGroupCreate();
    if (network_events == NULL) {
        return ESP_ERR_NO_MEM;
    }
    ESP_RETURN_ON_ERROR(esp_netif_init(), TAG, "network interface");
    ESP_RETURN_ON_ERROR(esp_event_loop_create_default(), TAG, "event loop");
    (void)esp_netif_create_default_wifi_sta();
    const esp_sntp_config_t time_configuration =
        ESP_NETIF_SNTP_DEFAULT_CONFIG("pool.ntp.org");
    ESP_RETURN_ON_ERROR(esp_netif_sntp_init(&time_configuration), TAG, "SNTP init");
    const wifi_init_config_t wifi_initialization = WIFI_INIT_CONFIG_DEFAULT();
    ESP_RETURN_ON_ERROR(esp_wifi_init(&wifi_initialization), TAG, "Wi-Fi init");
    ESP_RETURN_ON_ERROR(esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID, network_event,
                                                   NULL),
                        TAG, "Wi-Fi event");
    ESP_RETURN_ON_ERROR(
        esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP, network_event, NULL), TAG,
        "IP event");
    wifi_config_t wifi = {0};
    (void)snprintf((char *)wifi.sta.ssid, sizeof(wifi.sta.ssid), "%s", config->wifi_ssid);
    (void)snprintf((char *)wifi.sta.password, sizeof(wifi.sta.password), "%s",
                   config->wifi_password);
    wifi.sta.threshold.authmode = WIFI_AUTH_OPEN;
    wifi.sta.pmf_cfg.capable = true;
    wifi.sta.pmf_cfg.required = false;
    ESP_RETURN_ON_ERROR(esp_wifi_set_mode(WIFI_MODE_STA), TAG, "Wi-Fi mode");
    ESP_RETURN_ON_ERROR(esp_wifi_set_config(WIFI_IF_STA, &wifi), TAG, "Wi-Fi config");
    ESP_RETURN_ON_ERROR(esp_wifi_start(), TAG, "Wi-Fi start");

    if (!iiot_make_topic(command_topic, sizeof(command_topic), config->site_id,
                         config->device_id, "commands")) {
        return ESP_ERR_INVALID_ARG;
    }
    char availability_topic[IIOT_TOPIC_MAX];
    if (!iiot_make_topic(availability_topic, sizeof(availability_topic), config->site_id,
                         config->device_id, "availability")) {
        return ESP_ERR_INVALID_ARG;
    }
    (void)snprintf(broker_uri, sizeof(broker_uri), "mqtt://%s:%u", config->mqtt_host,
                   (unsigned)config->mqtt_port);
    (void)snprintf(availability_lwt, sizeof(availability_lwt),
                   "{\"schema_version\":1,\"site_id\":\"%s\",\"device_id\":\"%s\","
                   "\"status\":\"offline\",\"reason\":\"broker_lwt\"}",
                   config->site_id, config->device_id);
    (void)snprintf(availability_online, sizeof(availability_online),
                   "{\"schema_version\":1,\"site_id\":\"%s\",\"device_id\":\"%s\","
                   "\"status\":\"online\",\"reason\":\"boot\"}",
                   config->site_id, config->device_id);
    const esp_mqtt_client_config_t mqtt_configuration = {
        .broker.address.uri = broker_uri,
        .session.protocol_ver = MQTT_PROTOCOL_V_5,
        .session.keepalive = 30,
        .session.last_will.topic = availability_topic,
        .session.last_will.msg = availability_lwt,
        .session.last_will.msg_len = 0,
        .session.last_will.qos = 1,
        .session.last_will.retain = true,
        .network.reconnect_timeout_ms = 5000,
        .task.stack_size = 6144,
    };
    mqtt_client = esp_mqtt_client_init(&mqtt_configuration);
    if (mqtt_client == NULL) {
        return ESP_ERR_NO_MEM;
    }
    ESP_RETURN_ON_ERROR(esp_mqtt_client_register_event(mqtt_client, ESP_EVENT_ANY_ID,
                                                        network_event, NULL),
                        TAG, "MQTT event");
    return esp_mqtt_client_start(mqtt_client);
}

bool gateway_mqtt_connected(void) {
    return network_events != NULL &&
           (xEventGroupGetBits(network_events) & MQTT_CONNECTED_BIT) != 0U;
}

bool gateway_mqtt_publish(const char *suffix, const char *payload, int qos, bool retained) {
    if (mqtt_client == NULL || !gateway_mqtt_connected()) {
        return false;
    }
    char topic[IIOT_TOPIC_MAX];
    if (!iiot_make_topic(topic, sizeof(topic), active_config.site_id, active_config.device_id,
                         suffix)) {
        return false;
    }
    return esp_mqtt_client_publish(mqtt_client, topic, payload, 0, qos, retained ? 1 : 0) >= 0;
}

int gateway_wifi_rssi_dbm(void) {
    wifi_ap_record_t record;
    return esp_wifi_sta_get_ap_info(&record) == ESP_OK ? record.rssi : -127;
}

uint64_t gateway_uptime_ms(void) { return (uint64_t)(esp_timer_get_time() / 1000); }

bool gateway_utc_now(char *output, size_t output_size) {
    const time_t now = time(NULL);
    if (now < 1735689600) {
        if (output_size > 0U) {
            output[0] = '\0';
        }
        return false;
    }
    struct tm utc;
    if (gmtime_r(&now, &utc) == NULL) {
        return false;
    }
    return strftime(output, output_size, "%Y-%m-%dT%H:%M:%SZ", &utc) > 0U;
}

void gateway_make_uuid(char output[37]) {
    uint8_t bytes[16];
    esp_fill_random(bytes, sizeof(bytes));
    bytes[6] = (uint8_t)((bytes[6] & 0x0fU) | 0x40U);
    bytes[8] = (uint8_t)((bytes[8] & 0x3fU) | 0x80U);
    (void)snprintf(output, 37U,
                   "%02x%02x%02x%02x-%02x%02x-%02x%02x-%02x%02x-"
                   "%02x%02x%02x%02x%02x%02x",
                   bytes[0], bytes[1], bytes[2], bytes[3], bytes[4], bytes[5], bytes[6],
                   bytes[7], bytes[8], bytes[9], bytes[10], bytes[11], bytes[12], bytes[13],
                   bytes[14], bytes[15]);
}

void gateway_network_wait_and_reconnect(void) {
    uint8_t attempt = 0U;
    for (;;) {
        const EventBits_t bits = xEventGroupGetBits(network_events);
        if ((bits & WIFI_CONNECTED_BIT) == 0U) {
            (void)esp_wifi_connect();
            const uint32_t delay_ms = iiot_reconnect_delay_ms(attempt, esp_random());
            ESP_LOGW(TAG, "code=WIFI_RECONNECT attempt=%u delay_ms=%lu", (unsigned)attempt,
                     (unsigned long)delay_ms);
            vTaskDelay(pdMS_TO_TICKS(delay_ms));
            if (attempt < UINT8_MAX) {
                ++attempt;
            }
        } else {
            attempt = 0U;
            vTaskDelay(pdMS_TO_TICKS(1000));
        }
    }
}
