// Everything that puts pixels on the panel.
//
// Two update paths are used deliberately. The dashboard is a full 3-bit
// refresh, because the renderer produces a grayscale image. Status text is a
// 1-bit partial update, which only drives the pixels inside the banner and
// therefore leaves the rest of the dashboard on the panel untouched.

#include "inkdash.h"

#include <qrcode.h>

// The framebuffer is empty after deep sleep while the panel still physically
// shows the last dashboard. Forcing the partial update keeps the library from
// "helpfully" doing a full refresh, which would wipe that image.
static const bool FORCE_PARTIAL = true;

static const int BANNER_MARGIN = 8;
static const int BANNER_PADDING = 6;
static const int BANNER_TEXT_SIZE = 2;

// The built-in font is 6x8 before scaling.
static const int BANNER_CHAR_WIDTH = 6 * BANNER_TEXT_SIZE;
static const int BANNER_CHAR_HEIGHT = 8 * BANNER_TEXT_SIZE;
static const int BANNER_WIDTH = E_INK_WIDTH - BANNER_MARGIN * 2;
static const int BANNER_HEIGHT = BANNER_CHAR_HEIGHT + BANNER_PADDING * 2;
static const int BANNER_TOP = E_INK_HEIGHT - BANNER_MARGIN - BANNER_HEIGHT;
static const size_t BANNER_MAX_CHARS = (BANNER_WIDTH - BANNER_PADDING * 2) / BANNER_CHAR_WIDTH;

void displayBegin()
{
    display.begin();
}

bool displayImage(uint8_t *body, size_t length)
{
    display.selectDisplayMode(INKPLATE_3BIT);
    display.clearDisplay();

    // Dithering stays off: the renderer already quantizes to the panel's eight
    // gray levels, and dithering only smears the small terminal font.
    if (!display.image.drawPngFromBuffer(body, length, 0, 0, false, false))
    {
        Serial.println("[DISPLAY] PNG decode failed");
        return false;
    }

    display.display();
    return true;
}

// Two passes: begin() zeroes the library's copy of the panel, so it only ever paints pixels
// black and a single pass skips the white lettering. Blacking the strip first syncs that
// copy, and erases the previous banner, which is why the strip is a fixed rectangle.
void displayBanner(const char *message)
{
    Serial.printf("[DISPLAY] %s\n", message);

    display.selectDisplayMode(INKPLATE_1BIT);
    display.setFont(NULL);
    display.setTextSize(BANNER_TEXT_SIZE);
    // Wrapped text would land outside the strip, where nothing ever erases it.
    display.setTextWrap(false);

    display.clearDisplay();
    display.fillRect(BANNER_MARGIN, BANNER_TOP, BANNER_WIDTH, BANNER_HEIGHT, BLACK);
    display.partialUpdate(FORCE_PARTIAL);

    char text[BANNER_MAX_CHARS + 1];
    strlcpy(text, message, sizeof(text));

    display.clearDisplay();
    display.fillRect(BANNER_MARGIN, BANNER_TOP, BANNER_WIDTH, BANNER_HEIGHT, BLACK);
    display.setTextColor(WHITE, BLACK);
    display.setCursor(BANNER_MARGIN + BANNER_PADDING, BANNER_TOP + BANNER_PADDING);
    display.print(text);
    display.partialUpdate(FORCE_PARTIAL);

    // The banner now covers part of the dashboard, so the panel no longer shows
    // what the cached ETag claims it does. Dropping the ETag here rather than at
    // each call site means a 304 can never leave this message stranded on screen
    // until the dashboard content happens to change.
    fetchDropEtag();
}

static void drawQrCode(const char *text, int originX, int originY, int scale)
{
    // Version 4 holds 46 bytes at medium error correction, comfortably more
    // than the WiFi join string needs.
    QRCode qrcode;
    uint8_t data[qrcode_getBufferSize(4)];
    qrcode_initText(&qrcode, data, 4, ECC_MEDIUM, text);

    for (uint8_t y = 0; y < qrcode.size; y++)
    {
        for (uint8_t x = 0; x < qrcode.size; x++)
        {
            if (qrcode_getModule(&qrcode, x, y))
            {
                display.fillRect(originX + x * scale, originY + y * scale, scale, scale, BLACK);
            }
        }
    }
}

void displaySetupScreen()
{
    char joinText[64];
    snprintf(joinText, sizeof(joinText), "WIFI:S:%s;T:nopass;;", SETUP_AP_NAME);

    display.selectDisplayMode(INKPLATE_1BIT);
    display.clearDisplay();
    display.setFont(NULL);
    display.setTextColor(BLACK, WHITE);

    display.setTextSize(6);
    display.setCursor(60, 90);
    display.print("inkdash setup");

    // Every line is kept short enough to clear the QR code in the lower right.
    display.setTextSize(3);
    display.setCursor(60, 210);
    display.printf("1. Join the Wi-Fi network %s", SETUP_AP_NAME);
    display.setCursor(60, 260);
    display.print("2. A setup page should open by itself,");
    display.setCursor(60, 305);
    display.print("   otherwise browse to http://192.168.4.1");

    display.setTextSize(2);
    display.setCursor(60, 380);
    display.print("Choose \"Configure WiFi\", pick your home network");
    display.setCursor(60, 408);
    display.print("from the list and enter its password. Set the");
    display.setCursor(60, 436);
    display.print("dashboard image URL on the same page, then save.");

    display.setTextSize(2);
    display.setCursor(60, 500);
    display.print("The portal closes after 15 minutes. Hold the wake");
    display.setCursor(60, 528);
    display.print("button while booting to reopen it.");

    const int scale = 8;
    const int qrSize = 33 * scale;
    drawQrCode(joinText, E_INK_WIDTH - qrSize - 90, E_INK_HEIGHT - qrSize - 120, scale);

    display.setTextSize(2);
    display.setCursor(60, E_INK_HEIGHT - 40);
    display.printf("firmware %s", INKDASH_VERSION);

    display.display();
}
