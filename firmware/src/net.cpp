// WiFi association and the image download.
//
// The renderer answers with an ETag and honours If-None-Match, so an unchanged
// dashboard costs one small request instead of a download plus a two second
// e-paper refresh. The ETag is kept in RTC memory, which survives deep sleep.

#include "inkdash.h"

#include <HTTPClient.h>
#include <WiFi.h>

static const uint32_t WIFI_TIMEOUT_MS = 20 * 1000;
static const uint32_t HTTP_TIMEOUT_MS = 15 * 1000;

// A grayscale PNG of the panel can never exceed its uncompressed size.
static const size_t MAX_IMAGE_BYTES = E_INK_WIDTH * E_INK_HEIGHT;

RTC_DATA_ATTR static char rtcEtag[96];
static char pendingEtag[sizeof(rtcEtag)];

bool wifiConnect()
{
    WiFi.mode(WIFI_STA);
    WiFi.setHostname(cfg.hostname);
    WiFi.setSleep(true);
    // No arguments: the credentials saved by the config portal are reused.
    WiFi.begin();

    const uint32_t start = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - start < WIFI_TIMEOUT_MS)
    {
        delay(50);
    }

    if (WiFi.status() != WL_CONNECTED)
    {
        Serial.println("[WIFI] Association failed");
        return false;
    }

    Serial.printf("[WIFI] Connected as %s in %lums, %ddBm\n", WiFi.localIP().toString().c_str(),
                  (unsigned long)(millis() - start), WiFi.RSSI());
    return true;
}

void wifiDisconnect()
{
    WiFi.disconnect(true);
    WiFi.mode(WIFI_OFF);
}

static bool readBody(HTTPClient &http, size_t expected, uint8_t *buffer)
{
    WiFiClient *stream = http.getStreamPtr();
    size_t received = 0;
    uint32_t lastProgress = millis();

    while (received < expected)
    {
        const int available = stream->available();
        if (available > 0)
        {
            const size_t wanted = min((size_t)available, expected - received);
            received += stream->readBytes(buffer + received, wanted);
            lastProgress = millis();
            continue;
        }

        if (!http.connected() || millis() - lastProgress > HTTP_TIMEOUT_MS)
        {
            break;
        }
        delay(10);
    }

    if (received != expected)
    {
        Serial.printf("[HTTP] Truncated body: %u of %u bytes\n", (unsigned)received, (unsigned)expected);
        return false;
    }
    return true;
}

FetchResult fetchImage(uint8_t **body, size_t *length)
{
    *body = nullptr;
    *length = 0;

    HTTPClient http;
    http.setConnectTimeout(HTTP_TIMEOUT_MS);
    http.setTimeout(HTTP_TIMEOUT_MS);
    http.setUserAgent("inkdash/" INKDASH_VERSION);
    if (!http.begin(cfg.imageUrl))
    {
        Serial.printf("[HTTP] Malformed URL: %s\n", cfg.imageUrl);
        return FETCH_FAILED;
    }

    const char *collected[] = {"ETag"};
    http.collectHeaders(collected, 1);
    if (rtcEtag[0] != '\0')
    {
        http.addHeader("If-None-Match", rtcEtag);
    }

    Serial.printf("[HTTP] GET %s\n", cfg.imageUrl);
    const int status = http.GET();

    if (status == HTTP_CODE_NOT_MODIFIED)
    {
        Serial.println("[HTTP] 304, the dashboard has not changed");
        http.end();
        return FETCH_UNCHANGED;
    }

    if (status != HTTP_CODE_OK)
    {
        Serial.printf("[HTTP] Unexpected status %d\n", status);
        http.end();
        return FETCH_FAILED;
    }

    const int contentLength = http.getSize();
    if (contentLength <= 0 || (size_t)contentLength > MAX_IMAGE_BYTES)
    {
        Serial.printf("[HTTP] Unusable Content-Length: %d\n", contentLength);
        http.end();
        return FETCH_FAILED;
    }

    uint8_t *buffer = (uint8_t *)ps_malloc(contentLength);
    if (buffer == nullptr)
    {
        Serial.printf("[HTTP] Cannot allocate %d bytes\n", contentLength);
        http.end();
        return FETCH_FAILED;
    }

    const bool complete = readBody(http, contentLength, buffer);
    strlcpy(pendingEtag, http.header("ETag").c_str(), sizeof(pendingEtag));
    http.end();

    if (!complete)
    {
        free(buffer);
        return FETCH_FAILED;
    }

    Serial.printf("[HTTP] Downloaded %d bytes\n", contentLength);
    *body = buffer;
    *length = contentLength;
    return FETCH_UPDATED;
}

void fetchKeepEtag()
{
    strlcpy(rtcEtag, pendingEtag, sizeof(rtcEtag));
}

void fetchDropEtag()
{
    rtcEtag[0] = '\0';
}
