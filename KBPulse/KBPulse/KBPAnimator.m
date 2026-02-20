//
//  KBPAnimator.m
//  KBPulse
//
//  Created by EthanRDoesMC on 10/20/21.
//

#import "KBPAnimator.h"
#import "KBPPulseManager.h"

@implementation KBPAnimator

+(void)setBrightness:(float)brightness withDuration:(int)duration {
    [KBPPulseManager.brightnessClient setBrightness:brightness fadeSpeed:duration commit:true forKeyboard:1];
}

+(void)brightenWithDuration:(int)duration {
    [self setBrightness:1 withDuration:duration];
}

+(void)dimWithDuration:(int)duration {
    [self setBrightness:0 withDuration:duration];
}

+(float)currentBrightness {
    return [KBPPulseManager.brightnessClient brightnessForKeyboard:1];
}

+(BOOL)isBright {
    return self.currentBrightness == 1.0;
}

@end
