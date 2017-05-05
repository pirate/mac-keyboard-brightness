/*
    Set Mac Display Backlight Brightness

    Usage:
        gcc -std=c99 -o dbrightness display-brightness.c -framework IOKit -framework ApplicationServices
        ./dbrightness 0.8
*/

#include <IOKit/graphics/IOGraphicsLib.h>
#include <ApplicationServices/ApplicationServices.h>

float getDisplayBrightness(void)
{
  CGDisplayErr      dErr;
  io_service_t      service;
  CGDirectDisplayID targetDisplay;

  CFStringRef key = CFSTR(kIODisplayBrightnessKey);
  float brightness = HUGE_VALF;

  targetDisplay = CGMainDisplayID();
  service = CGDisplayIOServicePort(targetDisplay);

  dErr = IODisplayGetFloatParameter(service, kNilOptions, key, &brightness);

  return brightness;
}

void setDisplayBrightness(float brightness)
{
  CGDisplayErr      dErr;
  io_service_t      service;
  CGDirectDisplayID targetDisplay;
  CFStringRef key = CFSTR(kIODisplayBrightnessKey);

  targetDisplay = CGMainDisplayID();
  service = CGDisplayIOServicePort(targetDisplay);

  dErr = IODisplaySetFloatParameter(service, kNilOptions, key, brightness);

}


int main(int argc, char **argv) {
    // ./dbrightness 0.523
    float brightness;
    if (argc > 1 && sscanf(argv[1], "%f", &brightness) == 1) {
        setDisplayBrightness(brightness);
    } else {
        printf("%f", getDisplayBrightness());
    }
    exit(0);
}
