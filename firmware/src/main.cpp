// The wake cycle.
//
// Deep sleep restarts the program every time, so the whole cycle lives in
// setup() and loop() stays empty. Nothing is retried in a loop here: a failed
// cycle sleeps and tries again, and e-paper keeps showing the last dashboard in
// the meantime.

#include "inkdash.h"

#include <WiFi.h>
#include <esp_sleep.h>

Inkplate display(INKPLATE_3BIT);

RTC_DATA_ATTR static uint32_t bootCount = 0;

// Consecutive failed cycles, kept across deep sleep to drive the retry backoff
// and reset by a success or a button press.
RTC_DATA_ATTR static uint32_t failureCount = 0;

static const uint64_t MICROSECONDS_PER_SECOND = 1000ULL * 1000ULL;

// A renderer that is restarting, or a router that has not finished booting, is
// usually back within a minute, so the first retry is quick and each further
// failure doubles the wait.
static const uint32_t BACKOFF_FIRST_SECONDS = 60;

// A single LiPo cell, flat below 3.4V and full at 4.2V. Linear is wrong in
// detail but honest enough for a battery icon.
static const double BATTERY_EMPTY_VOLTS = 3.4;
static const double BATTERY_FULL_VOLTS = 4.2;

static const char *wakeReason()
{
    switch (esp_sleep_get_wakeup_cause())
    {
    case ESP_SLEEP_WAKEUP_TIMER:
        return "timer";
    case ESP_SLEEP_WAKEUP_EXT0:
        return "button";
    default:
        return "power_on";
    }
}

static int batteryPercent(double volts)
{
    const double fraction = (volts - BATTERY_EMPTY_VOLTS) / (BATTERY_FULL_VOLTS - BATTERY_EMPTY_VOLTS);
    return constrain((int)lround(fraction * 100.0), 0, 100);
}

// The configured refresh interval is the ceiling as well as the healthy value:
// a failing device retries sooner than a working one, never later. Doubling in
// a loop rather than shifting keeps the arithmetic safe once failureCount grows
// large enough that a shift would overflow.
static uint32_t nextSleepSeconds()
{
    if (failureCount == 0)
    {
        return cfg.wakeupEverySeconds;
    }

    uint32_t seconds = BACKOFF_FIRST_SECONDS;
    for (uint32_t i = 1; i < failureCount && seconds < cfg.wakeupEverySeconds; i++)
    {
        seconds *= 2;
    }
    return min(seconds, cfg.wakeupEverySeconds);
}

// Whole minutes read better on a panel a metre away.
static void formatDuration(char *out, size_t size, uint32_t seconds)
{
    if (seconds >= 60 && seconds % 60 == 0)
    {
        snprintf(out, size, "%u min", (unsigned)(seconds / 60));
        return;
    }
    snprintf(out, size, "%u s", (unsigned)seconds);
}

// Every failure path ends here: count the attempt, say so on the panel, and let
// the caller sleep for whatever the backoff now works out to.
static void reportFailure(const char *problem)
{
    failureCount++;

    char retry[16];
    formatDuration(retry, sizeof(retry), nextSleepSeconds());

    char message[160];
    snprintf(message, sizeof(message), "%s (attempt %u, retry in %s)", problem, (unsigned)failureCount, retry);
    displayBanner(message);
}

static void deepSleep()
{
    const uint32_t seconds = nextSleepSeconds();
    Serial.printf("[MAIN] Sleeping for %u seconds\n", (unsigned)seconds);
    Serial.flush();

    esp_sleep_enable_timer_wakeup((uint64_t)seconds * MICROSECONDS_PER_SECOND);
    esp_sleep_enable_ext0_wakeup(WAKE_BUTTON_PIN, LOW);
    esp_deep_sleep_start();
}

// Returns what to report as the refresh status.
static const char *refreshDashboard()
{
    uint8_t *body = nullptr;
    size_t length = 0;

    switch (fetchImage(&body, &length))
    {
    case FETCH_UNCHANGED:
        failureCount = 0;
        return "unchanged";

    case FETCH_UPDATED: {
        const bool drawn = displayImage(body, length);
        free(body);
        if (!drawn)
        {
            reportFailure("Dashboard image could not be decoded.");
            return "decode_failed";
        }
        // Only now: a decode failure must not be masked by a 304 next time.
        fetchKeepEtag();
        failureCount = 0;
        return "updated";
    }

    case FETCH_FAILED:
    default:
        reportFailure("Dashboard download failed. Check the image URL.");
        return "download_failed";
    }
}

void setup()
{
    Serial.begin(115200);
    bootCount++;

    displayBegin();
    configLoad();
    portalSaveBoot = configConsumePortalSaved();

    Serial.printf("\n[MAIN] inkdash %s, boot %u, woken by %s\n", INKDASH_VERSION, bootCount, wakeReason());

    // Waking on the button is already a forced refresh, since the cycle runs
    // immediately. Clearing the counter as well means the press also abandons an
    // escalated backoff: if this attempt fails it waits the short first interval
    // again rather than the full refresh interval.
    if (esp_sleep_get_wakeup_cause() == ESP_SLEEP_WAKEUP_EXT0)
    {
        failureCount = 0;
    }

    // The button check happens after display.begin() so a short press to force
    // a refresh has had time to be released; only a held button means setup.
    if (!configComplete() || wakeButtonHeld())
    {
        configPortal();
        if (configComplete())
        {
            ESP.restart();
        }
        // Nothing was configured. Sleep rather than reopening the portal
        // immediately, which would flatten the battery in an afternoon.
        deepSleep();
    }

    // The panel sensors are read before the network work so the values
    // published describe this cycle rather than the previous one.
    Telemetry telemetry = {};
    telemetry.batteryVolts = display.readBattery();
    telemetry.batteryPercent = batteryPercent(telemetry.batteryVolts);
    telemetry.temperatureC = display.readTemperature();
    telemetry.bootCount = bootCount;
    telemetry.bootReason = wakeReason();

    if (!wifiConnect())
    {
        // The banner names the way out, because a wrong password looks exactly
        // like a router that is briefly down and the device cannot tell them
        // apart: both just sleep and try again.
        reportFailure("Wi-Fi unavailable. Hold the wake button at boot for setup.");
        deepSleep();
    }
    telemetry.rssi = WiFi.RSSI();

    mqttBegin();
    mqttPublishTelemetry(telemetry);

    mqttPublishRefresh(refreshDashboard());

    mqttEnd();
    wifiDisconnect();
    deepSleep();
}

void loop()
{
    // Unreachable: the cycle ends in deep sleep, which restarts from setup().
}
