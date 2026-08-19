// Shared declarations for the inkdash Inkplate firmware.
//
// The device is a display appliance: it wakes, reports telemetry, downloads a
// PNG rendered by the server and goes back to sleep. No dashboard logic lives
// here, so a layout change never requires reflashing.

#pragma once

#include <Arduino.h>
#include <Inkplate.h>

// The wake button on Inkplate 10 pulls GPIO 36 low. It is input-only, so the
// pull-up is the one on the board.
#define WAKE_BUTTON_PIN GPIO_NUM_36

#ifndef INKDASH_VERSION
#define INKDASH_VERSION "dev"
#endif

extern Inkplate display;

// Everything the user can set in the config portal. Persisted in NVS.
struct Config
{
    char hostname[32];
    char imageUrl[192];
    uint32_t wakeupEverySeconds;
    char mqttHost[64];
    uint16_t mqttPort;
    char mqttUser[32];
    char mqttPassword[64];
    char mqttName[32];
};

extern Config cfg;

// This boot follows a portal save, so retained MQTT settings are stale.
extern bool portalSaveBoot;

// --- config.cpp ---

extern const char *SETUP_AP_NAME;

extern const uint32_t WAKEUP_EVERY_SECONDS_MIN;
extern const uint32_t WAKEUP_EVERY_SECONDS_MAX;
extern const uint32_t WAKEUP_EVERY_SECONDS_DEFAULT;

void configLoad();
bool configComplete();
bool wakeButtonHeld();
void configPortal();
uint32_t configClampWakeup(uint32_t seconds);
void configSave();
// One-shot flag, set before the portal reboots and consumed on the next boot.
void configSetPortalSaved();
bool configConsumePortalSaved();

// --- display.cpp ---

void displayBegin();
bool displayImage(uint8_t *body, size_t length);
// Drawn as a 1-bit partial update so the rest of the panel keeps the image it
// is already showing.
void displayBanner(const char *message);
void displaySetupScreen();

// --- net.cpp ---

enum FetchResult
{
    FETCH_UPDATED,
    FETCH_UNCHANGED,
    FETCH_FAILED,
};

bool wifiConnect();
void wifiDisconnect();
FetchResult fetchImage(uint8_t **body, size_t *length);
// Only called once the image has actually been drawn, so a decode failure is
// retried on the next wake instead of being masked by a 304.
void fetchKeepEtag();
// Forgets the cached ETag, forcing the next wake to fetch a full image rather
// than accept a 304.
void fetchDropEtag();

// --- mqtt.cpp ---

struct Telemetry
{
    double batteryVolts;
    int batteryPercent;
    int temperatureC;
    int rssi;
    uint32_t bootCount;
    const char *bootReason;
};

bool mqttBegin();
void mqttPublishTelemetry(const Telemetry &telemetry);
void mqttPublishRefresh(const char *status);
void mqttEnd();
