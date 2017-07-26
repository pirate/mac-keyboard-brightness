/*
    Set Mac Display Backlight Brightness

    Usage:
        gcc -std=c99 -o dbrightness display-brightness.c -framework IOKit -framework ApplicationServices
        ./dbrightness 0.8
*/

#include <IOKit/graphics/IOGraphicsLib.h>
#include <ApplicationServices/ApplicationServices.h>

// According to: https://stackoverflow.com/questions/20025868/cgdisplayioserviceport-is-deprecated-in-os-x-10-9-how-to-replace
// ...CGDisplayIOServicePort is deprecated. However, the discussion from: https://github.com/glfw/glfw/blob/e0a6772e5e4c672179fc69a90bcda3369792ed1f/src/cocoa_monitor.m
// ...suggests that GLFW's cocoa_monitor offers the implementation we need. Eun's solution appears to work well. It is pasted below.

// Returns the io_service_t corresponding to a CG display ID, or 0 on failure.
// The io_service_t should be released with IOObjectRelease when not needed.
//
static io_service_t IOServicePortFromCGDisplayID(CGDirectDisplayID displayID)
{
    io_iterator_t iter;
    io_service_t serv, servicePort = 0;

    CFMutableDictionaryRef matching = IOServiceMatching("IODisplayConnect");

    // releases matching for us
    kern_return_t err = IOServiceGetMatchingServices(kIOMasterPortDefault,
		                                     matching,
						     &iter);
    if ( err )
        return 0;

    while ( (serv = IOIteratorNext(iter)) != 0 )
    {
        CFDictionaryRef displayInfo;
        CFNumberRef vendorIDRef;
        CFNumberRef productIDRef;
        CFNumberRef serialNumberRef;

        displayInfo = IODisplayCreateInfoDictionary( serv, kIODisplayOnlyPreferredName );

        Boolean success;
        success =  CFDictionaryGetValueIfPresent( displayInfo, CFSTR(kDisplayVendorID),  (const void**) & vendorIDRef );
        success &= CFDictionaryGetValueIfPresent( displayInfo, CFSTR(kDisplayProductID), (const void**) & productIDRef );

        if ( !success )
        {
            CFRelease(displayInfo);
            continue;
        }

        SInt32 vendorID;
        CFNumberGetValue( vendorIDRef, kCFNumberSInt32Type, &vendorID );
        SInt32 productID;
        CFNumberGetValue( productIDRef, kCFNumberSInt32Type, &productID );

        // If a serial number is found, use it.
        // Otherwise serial number will be nil (= 0) which will match with the output of 'CGDisplaySerialNumber'
        SInt32 serialNumber = 0;
        if ( CFDictionaryGetValueIfPresent(displayInfo, CFSTR(kDisplaySerialNumber), (const void**) & serialNumberRef) )
        {
            CFNumberGetValue( serialNumberRef, kCFNumberSInt32Type, &serialNumber );
        }

        // If the vendor and product id along with the serial don't match
        // then we are not looking at the correct monitor.
        // NOTE: The serial number is important in cases where two monitors
        //       are the exact same.
        if( CGDisplayVendorNumber(displayID) != vendorID ||
            CGDisplayModelNumber(displayID)  != productID ||
            CGDisplaySerialNumber(displayID) != serialNumber )
        {
            CFRelease(displayInfo);
            continue;
        }

        servicePort = serv;
        CFRelease(displayInfo);
        break;
    }

    IOObjectRelease(iter);
    return servicePort;
}

float getDisplayBrightness(void) {
  CGDisplayErr      dErr;
  io_service_t      service;
  CGDirectDisplayID targetDisplay;

  CFStringRef key = CFSTR(kIODisplayBrightnessKey);
  float brightness = HUGE_VALF;

  targetDisplay = CGMainDisplayID();
  service = IOServicePortFromCGDisplayID(targetDisplay);

  dErr = IODisplayGetFloatParameter(service, kNilOptions, key, &brightness);

  return brightness;
}

void setDisplayBrightness(float brightness) {
  CGDisplayErr      dErr;
  io_service_t      service;
  CGDirectDisplayID targetDisplay;
  CFStringRef key = CFSTR(kIODisplayBrightnessKey);

  targetDisplay = CGMainDisplayID();
  service = IOServicePortFromCGDisplayID(targetDisplay);

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
