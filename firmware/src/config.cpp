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
static const uint16_t DEFAULT_SLEEP_MINUTES = 15;
static const uint16_t DEFAULT_MQTT_PORT = 1883;

void configLoad()
{
    cfg = Config{};

    Preferences prefs;
    prefs.begin(NVS_NAMESPACE, true);
    prefs.getString("hostname", cfg.hostname, sizeof(cfg.hostname));
    prefs.getString("imageUrl", cfg.imageUrl, sizeof(cfg.imageUrl));
    cfg.sleepMinutes = prefs.getUShort("sleepMinutes", DEFAULT_SLEEP_MINUTES);
    prefs.getString("mqttHost", cfg.mqttHost, sizeof(cfg.mqttHost));
    cfg.mqttPort = prefs.getUShort("mqttPort", DEFAULT_MQTT_PORT);
    prefs.getString("mqttUser", cfg.mqttUser, sizeof(cfg.mqttUser));
    prefs.getString("mqttPassword", cfg.mqttPassword, sizeof(cfg.mqttPassword));
    prefs.getString("mqttName", cfg.mqttName, sizeof(cfg.mqttName));
    prefs.end();

    if (cfg.hostname[0] == '\0')
    {
        strlcpy(cfg.hostname, DEFAULT_HOSTNAME, sizeof(cfg.hostname));
    }
    if (cfg.mqttName[0] == '\0')
    {
        strlcpy(cfg.mqttName, cfg.hostname, sizeof(cfg.mqttName));
    }
    if (cfg.sleepMinutes == 0)
    {
        cfg.sleepMinutes = DEFAULT_SLEEP_MINUTES;
    }
    if (cfg.mqttPort == 0)
    {
        cfg.mqttPort = DEFAULT_MQTT_PORT;
    }
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

static void configSave()
{
    Preferences prefs;
    prefs.begin(NVS_NAMESPACE, false);
    prefs.putString("hostname", cfg.hostname);
    prefs.putString("imageUrl", cfg.imageUrl);
    prefs.putUShort("sleepMinutes", cfg.sleepMinutes);
    prefs.putString("mqttHost", cfg.mqttHost);
    prefs.putUShort("mqttPort", cfg.mqttPort);
    prefs.putString("mqttUser", cfg.mqttUser);
    prefs.putString("mqttPassword", cfg.mqttPassword);
    prefs.putString("mqttName", cfg.mqttName);
    prefs.end();
}

void configPortal()
{
    Serial.println("[CONFIG] Starting the setup portal");
    displaySetupScreen();

    char sleepMinutes[8];
    char mqttPort[8];
    snprintf(sleepMinutes, sizeof(sleepMinutes), "%u", cfg.sleepMinutes);
    snprintf(mqttPort, sizeof(mqttPort), "%u", cfg.mqttPort);

    // The fifth argument is injected into the <input> tag as extra attributes, so an empty
    // field shows a worked example rather than nothing. A placeholder is only a hint: it is
    // never submitted, so leaving a field untouched still stores an empty value.
    WiFiManagerParameter pHostname("hostname", "Hostname", cfg.hostname, sizeof(cfg.hostname) - 1);
    WiFiManagerParameter pImageUrl("image_url", "Image URL (GET, PNG)", cfg.imageUrl, sizeof(cfg.imageUrl) - 1,
                                   " placeholder=\"http://zimaboard.lan:10825/render/home.png\"");
    WiFiManagerParameter pSleep("sleep_minutes", "Sleep minutes", sleepMinutes, sizeof(sleepMinutes) - 1);
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
    wm.addParameter(&pSleep);
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
    cfg.sleepMinutes = (uint16_t)atoi(pSleep.getValue());
    strlcpy(cfg.mqttHost, pMqttHost.getValue(), sizeof(cfg.mqttHost));
    cfg.mqttPort = (uint16_t)atoi(pMqttPort.getValue());
    strlcpy(cfg.mqttUser, pMqttUser.getValue(), sizeof(cfg.mqttUser));
    strlcpy(cfg.mqttPassword, pMqttPassword.getValue(), sizeof(cfg.mqttPassword));
    strlcpy(cfg.mqttName, pMqttName.getValue(), sizeof(cfg.mqttName));

    if (cfg.hostname[0] == '\0')
    {
        strlcpy(cfg.hostname, DEFAULT_HOSTNAME, sizeof(cfg.hostname));
    }
    if (cfg.sleepMinutes == 0)
    {
        cfg.sleepMinutes = DEFAULT_SLEEP_MINUTES;
    }
    if (cfg.mqttPort == 0)
    {
        cfg.mqttPort = DEFAULT_MQTT_PORT;
    }

    configSave();
}
