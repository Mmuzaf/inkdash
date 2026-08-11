// Telemetry and Home Assistant MQTT discovery.
//
// The device sleeps between refreshes, so it has no useful notion of being
// "online" and publishes no availability topic: a last will would mark it
// unavailable for the entire sleep window. Every entity carries expire_after
// instead, which turns a genuinely missed refresh into an unknown state while
// tolerating the normal sleep cycle.

#include "inkdash.h"

#include <ArduinoJson.h>
#include <PubSubClient.h>
#include <WiFi.h>

// Discovery payloads are a few hundred bytes; PubSubClient's 256 byte default
// would silently drop them.
static const uint16_t MQTT_BUFFER_SIZE = 1024;

static const uint16_t MQTT_SOCKET_TIMEOUT_SECONDS = 5;

// Two and a half sleep cycles: one late refresh is normal, two in a row is not.
static const float EXPIRE_AFTER_CYCLES = 2.5f;

static const char *DISCOVERY_PREFIX = "homeassistant";

static WiFiClient wifiClient;
static PubSubClient client(wifiClient);

static char nodeId[sizeof(cfg.hostname)];
static char stateTopic[96];
static char refreshTopic[96];
static bool connected = false;

struct SensorSpec
{
    const char *key;
    const char *name;
    const char *deviceClass;
    const char *unit;
    const char *stateClass;
    const char *valueTemplate;
    bool diagnostic;
    // The refresh outcome is only known after the image has been drawn, while
    // the rest is published before the download so it survives a failure.
    bool fromRefreshTopic;
};

static const SensorSpec SENSORS[] = {
    {"battery", "Battery", "battery", "%", "measurement", "{{ value_json.battery }}", false, false},
    {"voltage", "Battery voltage", "voltage", "V", "measurement", "{{ value_json.voltage }}", true, false},
    {"wifi_signal", "WiFi signal", "signal_strength", "dBm", "measurement", "{{ value_json.rssi }}", true, false},
    {"temperature", "Temperature", "temperature", "\u00b0C", "measurement", "{{ value_json.temperature }}", false,
     false},
    {"boot_count", "Boot count", nullptr, nullptr, "total_increasing", "{{ value_json.boot_count }}", true, false},
    {"boot_reason", "Boot reason", nullptr, nullptr, nullptr, "{{ value_json.boot_reason }}", true, false},
    {"refresh_status", "Refresh status", nullptr, nullptr, nullptr, nullptr, true, true},
};

// Topic segments allow a narrow character set, and the hostname does not.
static void buildNodeId()
{
    size_t out = 0;
    for (size_t i = 0; cfg.hostname[i] != '\0' && out < sizeof(nodeId) - 1; i++)
    {
        const char c = cfg.hostname[i];
        nodeId[out++] = isalnum((unsigned char)c) ? tolower(c) : '_';
    }
    nodeId[out] = '\0';
}

static void addDevice(JsonDocument &doc)
{
    JsonObject device = doc["device"].to<JsonObject>();
    char identifier[sizeof(nodeId) + 8];
    snprintf(identifier, sizeof(identifier), "inkdash_%s", nodeId);
    device["identifiers"][0] = identifier;
    device["name"] = cfg.mqttName;
    device["manufacturer"] = "Soldered";
    device["model"] = "Inkplate 10";
    device["sw_version"] = INKDASH_VERSION;
    // The dashboard the device is showing, which is the only web page involved.
    device["configuration_url"] = cfg.imageUrl;
}

static void publishDiscovery()
{
    const uint32_t expireAfter = (uint32_t)(cfg.sleepMinutes * 60 * EXPIRE_AFTER_CYCLES);
    char topic[160];
    char payload[MQTT_BUFFER_SIZE];

    for (const SensorSpec &spec : SENSORS)
    {
        JsonDocument doc;
        char uniqueId[sizeof(nodeId) + 40];
        snprintf(uniqueId, sizeof(uniqueId), "inkdash_%s_%s", nodeId, spec.key);

        doc["name"] = spec.name;
        doc["unique_id"] = uniqueId;
        doc["state_topic"] = spec.fromRefreshTopic ? refreshTopic : stateTopic;
        if (spec.valueTemplate != nullptr)
        {
            doc["value_template"] = spec.valueTemplate;
        }
        if (spec.deviceClass != nullptr)
        {
            doc["device_class"] = spec.deviceClass;
        }
        if (spec.unit != nullptr)
        {
            doc["unit_of_measurement"] = spec.unit;
        }
        if (spec.stateClass != nullptr)
        {
            doc["state_class"] = spec.stateClass;
        }
        if (spec.diagnostic)
        {
            doc["entity_category"] = "diagnostic";
        }
        doc["expire_after"] = expireAfter;
        addDevice(doc);

        const size_t length = serializeJson(doc, payload, sizeof(payload));
        snprintf(topic, sizeof(topic), "%s/sensor/%s/%s/config", DISCOVERY_PREFIX, nodeId, spec.key);
        if (!client.publish(topic, (const uint8_t *)payload, length, true))
        {
            Serial.printf("[MQTT] Discovery publish failed for %s\n", spec.key);
        }
    }
}

bool mqttBegin()
{
    connected = false;
    if (cfg.mqttHost[0] == '\0')
    {
        Serial.println("[MQTT] No broker configured");
        return false;
    }

    buildNodeId();
    snprintf(stateTopic, sizeof(stateTopic), "inkdash/%s/state", nodeId);
    snprintf(refreshTopic, sizeof(refreshTopic), "inkdash/%s/refresh", nodeId);

    client.setServer(cfg.mqttHost, cfg.mqttPort);
    client.setBufferSize(MQTT_BUFFER_SIZE);
    // Telemetry is the least important part of the cycle. An unreachable broker
    // should not keep the radio on long enough to matter to the battery.
    client.setSocketTimeout(MQTT_SOCKET_TIMEOUT_SECONDS);

    // Two devices can share a hostname; they cannot share a MAC, and a
    // duplicate client id would make the broker disconnect them in turn.
    uint8_t mac[6];
    WiFi.macAddress(mac);
    char clientId[sizeof(nodeId) + 24];
    snprintf(clientId, sizeof(clientId), "inkdash-%s-%02x%02x%02x", nodeId, mac[3], mac[4], mac[5]);

    const bool ok = cfg.mqttUser[0] != '\0'
                        ? client.connect(clientId, cfg.mqttUser, cfg.mqttPassword)
                        : client.connect(clientId);
    if (!ok)
    {
        Serial.printf("[MQTT] Connection to %s:%u failed, state %d\n", cfg.mqttHost, cfg.mqttPort, client.state());
        return false;
    }

    Serial.printf("[MQTT] Connected to %s:%u\n", cfg.mqttHost, cfg.mqttPort);
    connected = true;
    publishDiscovery();
    return true;
}

void mqttPublishTelemetry(const Telemetry &telemetry)
{
    if (!connected)
    {
        return;
    }

    JsonDocument doc;
    doc["battery"] = telemetry.batteryPercent;
    doc["voltage"] = serialized(String(telemetry.batteryVolts, 2));
    doc["temperature"] = telemetry.temperatureC;
    doc["rssi"] = telemetry.rssi;
    doc["boot_count"] = telemetry.bootCount;
    doc["boot_reason"] = telemetry.bootReason;
    doc["ip"] = WiFi.localIP().toString();
    doc["version"] = INKDASH_VERSION;

    char payload[MQTT_BUFFER_SIZE];
    const size_t length = serializeJson(doc, payload, sizeof(payload));
    Serial.printf("[MQTT] %s %s\n", stateTopic, payload);
    client.publish(stateTopic, (const uint8_t *)payload, length, true);
}

void mqttPublishRefresh(const char *status)
{
    if (!connected)
    {
        return;
    }
    Serial.printf("[MQTT] %s %s\n", refreshTopic, status);
    client.publish(refreshTopic, status, true);
}

void mqttEnd()
{
    if (!connected)
    {
        return;
    }
    client.loop();
    client.disconnect();
    connected = false;
}
