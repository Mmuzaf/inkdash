// Settings storage and the WiFi captive portal.
//
// Nothing is compiled in: the device is configured once through a portal and
// keeps its settings in NVS, so the firmware binary carries no credentials and
// the same build runs on every device.

#include "inkdash.h"

#include <Preferences.h>
#include <WiFiManager.h>

Config cfg;

const char *SETUP_AP_NAME = "Inkdash-Setup";

static const char *NVS_NAMESPACE = "inkdash";
static const uint16_t PORTAL_TIMEOUT_SECONDS = 15 * 60;

static const char *DEFAULT_HOSTNAME = "inkdash";
static const uint16_t DEFAULT_MQTT_PORT = 1883;

// NVS caps a key at 15 characters
static const char *KEY_HOSTNAME = "hostname";
static const char *KEY_IMAGE_URL = "imageUrl";
static const char *KEY_WAKEUP_EVERY = "wakeupEvery";
static const char *KEY_MQTT_HOST = "mqttHost";
static const char *KEY_MQTT_PORT = "mqttPort";
static const char *KEY_MQTT_USER = "mqttUser";
static const char *KEY_MQTT_PASSWORD = "mqttPassword";
static const char *KEY_MQTT_NAME = "mqttName";
static const char *KEY_PORTAL_SAVED = "portalSaved";

const uint32_t WAKEUP_EVERY_SECONDS_MIN = 1;
const uint32_t WAKEUP_EVERY_SECONDS_MAX = 24 * 60 * 60;
const uint32_t WAKEUP_EVERY_SECONDS_DEFAULT = 15 * 60;

bool portalSaveBoot = false;

void configLoad()
{
    cfg = Config{};

    Preferences prefs;
    prefs.begin(NVS_NAMESPACE, true);
    prefs.getString(KEY_HOSTNAME, cfg.hostname, sizeof(cfg.hostname));
    prefs.getString(KEY_IMAGE_URL, cfg.imageUrl, sizeof(cfg.imageUrl));
    cfg.wakeupEverySeconds = prefs.getUInt(KEY_WAKEUP_EVERY, 0);
    prefs.getString(KEY_MQTT_HOST, cfg.mqttHost, sizeof(cfg.mqttHost));
    cfg.mqttPort = prefs.getUShort(KEY_MQTT_PORT, DEFAULT_MQTT_PORT);
    prefs.getString(KEY_MQTT_USER, cfg.mqttUser, sizeof(cfg.mqttUser));
    prefs.getString(KEY_MQTT_PASSWORD, cfg.mqttPassword, sizeof(cfg.mqttPassword));
    prefs.getString(KEY_MQTT_NAME, cfg.mqttName, sizeof(cfg.mqttName));
    prefs.end();

    if (cfg.hostname[0] == '\0')
    {
        strlcpy(cfg.hostname, DEFAULT_HOSTNAME, sizeof(cfg.hostname));
    }
    if (cfg.mqttName[0] == '\0')
    {
        strlcpy(cfg.mqttName, cfg.hostname, sizeof(cfg.mqttName));
    }
    cfg.wakeupEverySeconds = configClampWakeup(cfg.wakeupEverySeconds);
    if (cfg.mqttPort == 0)
    {
        cfg.mqttPort = DEFAULT_MQTT_PORT;
    }
}

// Zero means unset, so it becomes the default rather than the minimum.
uint32_t configClampWakeup(uint32_t seconds)
{
    if (seconds == 0)
    {
        return WAKEUP_EVERY_SECONDS_DEFAULT;
    }
    if (seconds < WAKEUP_EVERY_SECONDS_MIN)
    {
        return WAKEUP_EVERY_SECONDS_MIN;
    }
    if (seconds > WAKEUP_EVERY_SECONDS_MAX)
    {
        return WAKEUP_EVERY_SECONDS_MAX;
    }
    return seconds;
}

// MQTT is optional; without an image URL there is nothing for the device to do.
// The WiFi credentials themselves live in the ESP32's own NVS, written by
// WiFiManager, and are only known to be good once an association is attempted.
bool configComplete()
{
    return cfg.imageUrl[0] != '\0';
}

bool wakeButtonHeld()
{
    pinMode(WAKE_BUTTON_PIN, INPUT);
    return digitalRead(WAKE_BUTTON_PIN) == LOW;
}

void configSave()
{
    Preferences prefs;
    prefs.begin(NVS_NAMESPACE, false);
    prefs.putString(KEY_HOSTNAME, cfg.hostname);
    prefs.putString(KEY_IMAGE_URL, cfg.imageUrl);
    prefs.putUInt(KEY_WAKEUP_EVERY, cfg.wakeupEverySeconds);
    prefs.putString(KEY_MQTT_HOST, cfg.mqttHost);
    prefs.putUShort(KEY_MQTT_PORT, cfg.mqttPort);
    prefs.putString(KEY_MQTT_USER, cfg.mqttUser);
    prefs.putString(KEY_MQTT_PASSWORD, cfg.mqttPassword);
    prefs.putString(KEY_MQTT_NAME, cfg.mqttName);
    prefs.end();
}

void configSetPortalSaved()
{
    Preferences prefs;
    prefs.begin(NVS_NAMESPACE, false);
    prefs.putBool(KEY_PORTAL_SAVED, true);
    prefs.end();
}

bool configConsumePortalSaved()
{
    Preferences prefs;
    prefs.begin(NVS_NAMESPACE, false);
    const bool saved = prefs.getBool(KEY_PORTAL_SAVED, false);
    if (saved)
    {
        prefs.remove(KEY_PORTAL_SAVED);
    }
    prefs.end();
    return saved;
}

void configPortal()
{
    Serial.println("[CONFIG] Starting the setup portal");
    displaySetupScreen();

    char wakeupEverySeconds[8];
    char mqttPort[8];
    snprintf(wakeupEverySeconds, sizeof(wakeupEverySeconds), "%u", (unsigned)cfg.wakeupEverySeconds);
    snprintf(mqttPort, sizeof(mqttPort), "%u", cfg.mqttPort);

    // The fifth argument is injected into the <input> tag as extra attributes, so an empty
    // field shows a worked example rather than nothing. A placeholder is only a hint: it is
    // never submitted, so leaving a field untouched still stores an empty value.
    WiFiManagerParameter pHostname("hostname", "Hostname", cfg.hostname, sizeof(cfg.hostname) - 1);
    WiFiManagerParameter pImageUrl("image_url", "Image URL (GET, PNG)", cfg.imageUrl, sizeof(cfg.imageUrl) - 1,
                                   " placeholder=\"http://zimaboard.lan:10825/render/home.png\"");
    WiFiManagerParameter pWakeup("wakeup_every_seconds", "Wakeup every seconds", wakeupEverySeconds,
                                 sizeof(wakeupEverySeconds) - 1);
    WiFiManagerParameter pMqttHost("mqtt_host", "MQTT host (blank disables)", cfg.mqttHost, sizeof(cfg.mqttHost) - 1,
                                   " placeholder=\"zimaboard.lan\"");
    WiFiManagerParameter pMqttPort("mqtt_port", "MQTT port", mqttPort, sizeof(mqttPort) - 1);
    WiFiManagerParameter pMqttUser("mqtt_user", "MQTT user", cfg.mqttUser, sizeof(cfg.mqttUser) - 1);
    WiFiManagerParameter pMqttPassword("mqtt_password", "MQTT password", cfg.mqttPassword,
                                       sizeof(cfg.mqttPassword) - 1);
    WiFiManagerParameter pMqttName("mqtt_name", "Home Assistant device name", cfg.mqttName, sizeof(cfg.mqttName) - 1);

    WiFiManager wm;
    wm.addParameter(&pHostname);
    wm.addParameter(&pImageUrl);
    wm.addParameter(&pWakeup);
    wm.addParameter(&pMqttHost);
    wm.addParameter(&pMqttPort);
    wm.addParameter(&pMqttUser);
    wm.addParameter(&pMqttPassword);
    wm.addParameter(&pMqttName);

    wm.setConfigPortalTimeout(PORTAL_TIMEOUT_SECONDS);
    // Save the parameters even when the entered WiFi credentials turn out to be
    // wrong, so a typo in the password does not discard the rest of the form.
    wm.setBreakAfterConfig(true);
    wm.setSaveConnectTimeout(20);

    bool connected = wm.startConfigPortal(SETUP_AP_NAME);
    Serial.printf("[CONFIG] Portal closed, WiFi %s\n", connected ? "connected" : "not connected");

    strlcpy(cfg.hostname, pHostname.getValue(), sizeof(cfg.hostname));
    strlcpy(cfg.imageUrl, pImageUrl.getValue(), sizeof(cfg.imageUrl));
    cfg.wakeupEverySeconds = configClampWakeup((uint32_t)strtoul(pWakeup.getValue(), nullptr, 10));
    strlcpy(cfg.mqttHost, pMqttHost.getValue(), sizeof(cfg.mqttHost));
    cfg.mqttPort = (uint16_t)atoi(pMqttPort.getValue());
    strlcpy(cfg.mqttUser, pMqttUser.getValue(), sizeof(cfg.mqttUser));
    strlcpy(cfg.mqttPassword, pMqttPassword.getValue(), sizeof(cfg.mqttPassword));
    strlcpy(cfg.mqttName, pMqttName.getValue(), sizeof(cfg.mqttName));

    if (cfg.hostname[0] == '\0')
    {
        strlcpy(cfg.hostname, DEFAULT_HOSTNAME, sizeof(cfg.hostname));
    }
    if (cfg.mqttPort == 0)
    {
        cfg.mqttPort = DEFAULT_MQTT_PORT;
    }

    configSave();
    // So a retained MQTT setting does not undo what was just typed.
    configSetPortalSaved();
}
