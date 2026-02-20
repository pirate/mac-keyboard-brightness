//
//  KBPPulseManager.m
//  KBPulse
//
//  Created by EthanRDoesMC on 10/20/21.
//

#import "KBPPulseManager.h"
#import "KBPAnimator.h"

@interface KBPPulseManager()
+(void)loadPrivateFrameworks;
+(void)modifyBacklightSettings;
+(void)showBezel;
@end

@implementation KBPPulseManager

+ (id)sharedInstance {
    static KBPPulseManager *sharedInstance = nil;
    static dispatch_once_t onceToken;
    dispatch_once(&onceToken, ^{
        sharedInstance = [[self alloc] init];
    });
    return sharedInstance;
}

+(void)loadPrivateFrameworks {
    printf("Loading private frameworks\n");
    printf("CoreBrightness: %hhd\n",[[NSBundle bundleWithPath:@"/System/Library/PrivateFrameworks/CoreBrightness.framework"] load]);
    [KBPPulseManager.sharedInstance setBrightnessClient:[[NSClassFromString(@"KeyboardBrightnessClient") alloc] init]];
    printf("OSD: %hhd\n",[[NSBundle bundleWithPath:@"/System/Library/PrivateFrameworks/OSD.framework"] load]);
}

+(void)modifyBacklightSettings {
    printf("Disabling idle-dimming and auto-brightness\n");
    [KBPPulseManager.brightnessClient setIdleDimTime:0 forKeyboard:1];
    [KBPPulseManager.brightnessClient enableAutoBrightness:false forKeyboard:1];
}

+(void)showBezel {
    [[NSClassFromString(@"OSDManager") sharedManager] showImage:11 onDisplayID:1 priority:1 msecUntilFade:1000 withText:@"KBPulse"];
}

+(void)configure {
    [self loadPrivateFrameworks];
    [self modifyBacklightSettings];
    [self showBezel];
}

+(KeyboardBrightnessClient *)brightnessClient {
    return [KBPPulseManager.sharedInstance brightnessClient];
}

+(NSString *)configurationFile {
    NSString * configuration = @"Yawn";
    if ([NSProcessInfo.processInfo arguments][1]) {
        configuration = [NSString stringWithFormat:@"/KBPulse/%@.json", NSProcessInfo.processInfo.arguments[1] ];
    }
    return configuration;
}

- (id)init {
    if (self = [super init]) {
        self.paused = false;
    }
    return self;
}

@end
