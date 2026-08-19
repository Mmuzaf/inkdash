// Telemetry, settings and Home Assistant MQTT discovery.
//
// The device sleeps between refreshes, so it has no useful notion of being
// "online" and publishes no availability topic: a last will would mark it
// unavailable for the entire sleep window. Every sensor carries expire_after
// instead, which turns a genuinely missed refresh into an unknown state while
// tolerating the normal sleep cycle.
//
// Settings go the other way and carry no expire_after, because a value the user
// typed has to stay visible for as long as the panel sleeps.

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
    const uint32_t expireAfter = (uint32_t)(cfg.wakeupEverySeconds * EXPIRE_AFTER_CYCLES);
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

// --- Settings -------------------------------------------------------------
//
// A bare scalar per setting, which is what the Home Assistant number and text
// platforms speak. Only these two: the hostname decides the topics the messages
// arrive on, and a broker setting cannot be corrected over that same broker.

enum SettingKind
{
    SETTING_NUMBER,
    SETTING_TEXT,
};

struct SettingSpec
{
    const char *key;
    const char *name;
    const char *icon;
    SettingKind kind;
};

static const SettingSpec SETTINGS[] = {
    {"wakeup_every_seconds", "Wakeup every", "mdi:timer-sand", SETTING_NUMBER},
    {"image_url", "Image URL", "mdi:link-variant", SETTING_TEXT},
};
static const size_t SETTINGS_COUNT = sizeof(SETTINGS) / sizeof(SETTINGS[0]);

// Home Assistant drops a text entity above 255 silently. Advertising the real
// slot size stays under that and rejects an over-long URL as it is typed.
static const uint16_t IMAGE_URL_MAX = sizeof(cfg.imageUrl) - 1;

static void settingStateTopic(char *out, size_t size, const char *key)
{
    snprintf(out, size, "inkdash/%s/config/%s/state", nodeId, key);
}

static void settingCommandTopic(char *out, size_t size, const char *key)
{
    snprintf(out, size, "inkdash/%s/config/%s/set", nodeId, key);
}

static void publishSettingState(const SettingSpec &spec)
{
    char topic[128];
    settingStateTopic(topic, sizeof(topic), spec.key);

    char payload[sizeof(cfg.imageUrl)];
    if (spec.kind == SETTING_NUMBER)
    {
        snprintf(payload, sizeof(payload), "%u", (unsigned)cfg.wakeupEverySeconds);
    }
    else
    {
        strlcpy(payload, cfg.imageUrl, sizeof(payload));
    }

    Serial.printf("[MQTT] %s %s\n", topic, payload);
    client.publish(topic, payload, true);
}

static bool applyWakeupEverySeconds(const char *value)
{
    char *end = nullptr;
    const unsigned long parsed = strtoul(value, &end, 10);
    if (end == value || *end != '\0' || parsed == 0)
    {
        Serial.printf("[MQTT] Ignoring wakeup_every_seconds: %s\n", value);
        return false;
    }

    const uint32_t seconds = configClampWakeup((uint32_t)parsed);
    if (seconds == cfg.wakeupEverySeconds)
    {
        return false;
    }
    cfg.wakeupEverySeconds = seconds;
    Serial.printf("[MQTT] wakeup_every_seconds is now %u\n", (unsigned)seconds);
    return true;
}

static bool applyImageUrl(const char *value)
{
    // https would fail on every wake with nothing on the panel to say why.
    if (strncmp(value, "http://", 7) != 0 || strlen(value) >= sizeof(cfg.imageUrl))
    {
        Serial.printf("[MQTT] Ignoring image_url: %s\n", value);
        return false;
    }
    if (strcmp(value, cfg.imageUrl) == 0)
    {
        return false;
    }

    strlcpy(cfg.imageUrl, value, sizeof(cfg.imageUrl));
    // The cached ETag is the old dashboard's, so the new one would 304 and never draw.
    fetchDropEtag();
    Serial.printf("[MQTT] image_url is now %s\n", cfg.imageUrl);
    return true;
}

static void handleSetting(const SettingSpec &spec, const char *commandTopic, const uint8_t *payload,
                          unsigned int length)
{
    // How a retained command is cleared, not a value to store.
    if (length == 0)
    {
        return;
    }

    if (portalSaveBoot)
    {
        // Anything retained here predates what was just typed into the portal.
        Serial.printf("[MQTT] Portal save, dropping retained %s\n", spec.key);
        client.publish(commandTopic, "", true);
        return;
    }

    char value[sizeof(cfg.imageUrl)];
    if (length >= sizeof(value))
    {
        Serial.printf("[MQTT] %s payload is too long, %u bytes\n", spec.key, length);
        return;
    }
    memcpy(value, payload, length);
    value[length] = '\0';

    const bool changed =
        spec.kind == SETTING_NUMBER ? applyWakeupEverySeconds(value) : applyImageUrl(value);
    if (changed)
    {
        // Only on a change: Home Assistant replays retained commands on every
        // reconnect, and flash wears out.
        configSave();
    }
}

static void onCommand(char *topic, uint8_t *payload, unsigned int length)
{
    char expected[128];
    for (const SettingSpec &spec : SETTINGS)
    {
        settingCommandTopic(expected, sizeof(expected), spec.key);
        if (strcmp(topic, expected) == 0)
        {
            handleSetting(spec, expected, payload, length);
            return;
        }
    }
}

static void subscribeSettings()
{
    char topic[128];
    for (const SettingSpec &spec : SETTINGS)
    {
        settingCommandTopic(topic, sizeof(topic), spec.key);
        if (!client.subscribe(topic))
        {
            Serial.printf("[MQTT] Subscribe failed for %s\n", spec.key);
        }
    }
}

static void publishSettingsDiscovery()
{
    char topic[160];
    char payload[MQTT_BUFFER_SIZE];

    for (const SettingSpec &spec : SETTINGS)
    {
        JsonDocument doc;
        char uniqueId[sizeof(nodeId) + 48];
        char state[128];
        char command[128];
        snprintf(uniqueId, sizeof(uniqueId), "inkdash_%s_cfg_%s", nodeId, spec.key);
        settingStateTopic(state, sizeof(state), spec.key);
        settingCommandTopic(command, sizeof(command), spec.key);

        doc["name"] = spec.name;
        doc["unique_id"] = uniqueId;
        doc["icon"] = spec.icon;
        doc["state_topic"] = state;
        doc["command_topic"] = command;
        doc["entity_category"] = "config";
        // Retained, or a change made while the panel sleeps never reaches it.
        doc["retain"] = true;
        // Optimistic, because the state echo cannot arrive until the next wake.
        doc["optimistic"] = true;

        if (spec.kind == SETTING_NUMBER)
        {
            doc["min"] = WAKEUP_EVERY_SECONDS_MIN;
            doc["max"] = WAKEUP_EVERY_SECONDS_MAX;
            doc["step"] = 1;
            doc["mode"] = "box";
            doc["unit_of_measurement"] = "s";
        }
        else
        {
            doc["min"] = 0;
            doc["max"] = IMAGE_URL_MAX;
            doc["mode"] = "text";
        }
        addDevice(doc);

        const size_t length = serializeJson(doc, payload, sizeof(payload));
        snprintf(topic, sizeof(topic), "%s/%s/%s/cfg_%s/config", DISCOVERY_PREFIX,
                 spec.kind == SETTING_NUMBER ? "number" : "text", nodeId, spec.key);
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
    client.setCallback(onCommand);
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

    // Only subscribe here. Retained commands are read at the end of the cycle,
    // where the wait costs nothing: see mqttEnd().
    subscribeSettings();

    publishDiscovery();
    publishSettingsDiscovery();
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

    for (size_t i = 0; i < SETTINGS_COUNT + 1; i++)
    {
        client.loop();
    }

    for (const SettingSpec &spec : SETTINGS)
    {
        publishSettingState(spec);
    }

    client.disconnect();
    connected = false;
}
