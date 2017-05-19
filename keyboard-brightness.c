/*
    Set Mac Keyboard Backlight Brightness

    Usage:
        gcc -std=c99 -o kbrightness keyboard-brightness.c -framework IOKit -framework ApplicationServices
        ./kbrightness 0.8
*/

enum {
  kGetSensorReadingID = 0,  // getSensorReading(int *, int *)
  kGetLEDBrightnessID = 1,  // getLEDBrightness(int, int *)
  kSetLEDBrightnessID = 2,  // setLEDBrightness(int, int, int *)
  kSetLEDFadeID = 3,        // setLEDFade(int, int, int, int *)
};

#include <mach/mach.h>
#include <IOKit/IOKitLib.h>
#include <CoreFoundation/CoreFoundation.h>

static io_connect_t dataPort = 0;

io_connect_t getDataPort(void) {
    kern_return_t     kr;
    io_service_t      serviceObject;

    if (dataPort) return dataPort;

    // Look up a registered IOService object whose class is AppleLMUController
    serviceObject = IOServiceGetMatchingService(kIOMasterPortDefault, IOServiceMatching("AppleLMUController"));

    if (!serviceObject) {
        printf("Failed to connect to AppleLMUController\n");
        return 0;
    }

    // Create a connection to the IOService object
    kr = IOServiceOpen(serviceObject, mach_task_self(), 0, &dataPort);
    IOObjectRelease(serviceObject);

    if (kr != KERN_SUCCESS) {
        printf("Failed to open IoService object\n");
        return 0;
    }
    return dataPort;
}

float getKeyboardBrightness(void) {
    float f;
    kern_return_t kr;

    uint64_t inputCount = 1;
    uint64_t inputValues[1] = {0};

    uint32_t outputCount = 1;
    uint64_t outputValues[1];

    uint32_t out_brightness;

    kr = IOConnectCallScalarMethod(
        getDataPort(),
        kGetLEDBrightnessID,
        inputValues,
        inputCount,
        outputValues,
        &outputCount
    );

    out_brightness = outputValues[0];

    if (kr != KERN_SUCCESS) {
        printf("getKeyboardBrightness() error\n");
        return 0;
    }

    f = out_brightness;
    f /= 0xfff;
    return (float)f;
}

void setKeyboardBrightness(float in) {
    kern_return_t kr;

    uint64_t inputCount  = 2;
    uint64_t inputValues[2];
    uint64_t in_unknown = 0;
    uint64_t in_brightness = in * 0xfff;

    inputValues[0] = in_unknown;
    inputValues[1] = in_brightness;

    uint32_t outputCount = 1;
    uint64_t outputValues[1];

    uint32_t out_brightness;

    kr = IOConnectCallScalarMethod(
        getDataPort(),
        kSetLEDBrightnessID,
        inputValues,
        inputCount,
        outputValues,
        &outputCount
    );

    out_brightness = outputValues[0];

    if (kr != KERN_SUCCESS) {
        printf("setKeyboardBrightness() error\n");
        return;
    }
}


int main(int argc, char **argv) {
    // ./kbrightness 0.523
    float brightness;
    if (argc > 1 && sscanf(argv[1], "%f", &brightness) == 1) {
        setKeyboardBrightness(brightness);
    } else {
        printf("%f", getKeyboardBrightness());
    }
    exit(0);
}
