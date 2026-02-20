//
//  main.m
//  KBPulse
//
//  Created by EthanRDoesMC on 10/20/21.
//

#import <Foundation/Foundation.h>
#import <Cocoa/Cocoa.h>
#import <math.h>
#import <stdlib.h>
#import <string.h>
#import "KBPPulseManager.h"
#import "KBPAnimator.h"
#import "KBPProfile.h"

static void printUsage(void) {
    printf("Usage:\n");
    printf("  KBPulse [ThemeName]\n");
    printf("  KBPulse --stdin-intensity [--fade-ms <milliseconds>]\n");
}

static float clamp01(float value) {
    if (value < 0.0f) {
        return 0.0f;
    }
    if (value > 1.0f) {
        return 1.0f;
    }
    return value;
}

static int runStdinIntensityMode(int fadeMs) {
    @autoreleasepool {
        printf("KBPulse by EthanRDoesMC\n");
        [KBPPulseManager configure];
        printf("Streaming keyboard intensity from stdin. Press ctrl-c to stop.\n");

        char line[256];
        while (fgets(line, sizeof(line), stdin)) {
            if (strncmp(line, "quit", 4) == 0 || strncmp(line, "exit", 4) == 0) {
                break;
            }

            char *end = NULL;
            float level = strtof(line, &end);
            if (end == line || isnan(level) || isinf(level)) {
                continue;
            }

            [KBPAnimator setBrightness:clamp01(level) withDuration:fadeMs];
        }

        [KBPAnimator setBrightness:0.0f withDuration:fadeMs];
    }

    return 0;
}

int main(int argc, const char * argv[]) {
    BOOL stdinMode = NO;
    int fadeMs = 20;
    NSString * _Nullable profileName = nil;

    for (int i = 1; i < argc; i++) {
        const char *arg = argv[i];

        if (strcmp(arg, "--stdin-intensity") == 0) {
            stdinMode = YES;
            continue;
        }

        if (strcmp(arg, "--fade-ms") == 0) {
            if (i + 1 >= argc) {
                fprintf(stderr, "Missing value for --fade-ms\n");
                printUsage();
                return 1;
            }
            fadeMs = MAX(0, atoi(argv[++i]));
            continue;
        }

        if (strcmp(arg, "-h") == 0 || strcmp(arg, "--help") == 0) {
            printUsage();
            return 0;
        }

        if (arg[0] == '-') {
            fprintf(stderr, "Unknown option: %s\n", arg);
            printUsage();
            return 1;
        }

        if (profileName == nil) {
            profileName = [NSString stringWithUTF8String:arg];
        } else {
            fprintf(stderr, "Ignoring extra argument: %s\n", arg);
        }
    }

    if (stdinMode) {
        return runStdinIntensityMode(fadeMs);
    }

    @autoreleasepool {
        printf("KBPulse by EthanRDoesMC\n");
        [KBPPulseManager configure];
        printf("Animating keyboard. Press ctrl-c or close terminal to stop.\n");

        [KBPProfile createYawnJSON];
        NSString *resolvedProfileName = profileName ?: @"Yawn";
        NSURL *documents = [NSFileManager.defaultManager URLsForDirectory:NSDocumentDirectory inDomains:NSUserDomainMask][0];
        NSURL *profileURL = [documents URLByAppendingPathComponent:[NSString stringWithFormat:@"KBPulse/%@.json", resolvedProfileName]];
        KBPProfile *myProfile = [[KBPProfile alloc] initWithFileURL:profileURL];

        [NSTimer scheduledTimerWithTimeInterval:[myProfile totalDuration].doubleValue repeats:true block:^(NSTimer * _Nonnull timer) {
            for (KBPAnimation * animation in myProfile.animations) {
                [KBPAnimator setBrightness:animation.brightness.floatValue withDuration:animation.fadeDuration.intValue];
                [NSThread sleepForTimeInterval:(animation.totalDuration.doubleValue)/1000];

            }
        }];
    }
    [[NSRunLoop currentRunLoop] run];
    return 0;
}
