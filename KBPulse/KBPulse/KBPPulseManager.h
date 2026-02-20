//
//  KBPPulseManager.h
//  KBPulse
//
//  Created by EthanRDoesMC on 10/20/21.
//

#import <Foundation/Foundation.h>
#import "KeyboardBrightnessClient.h"
#import "OSDManager.h"

NS_ASSUME_NONNULL_BEGIN

@interface KBPPulseManager : NSObject
@property(nonatomic,strong) KeyboardBrightnessClient * brightnessClient;
@property(atomic,readwrite) BOOL paused;
+(id)sharedInstance;
+(void)configure;
+(KeyboardBrightnessClient *)brightnessClient;
+(NSString *)configurationFile;
@end

NS_ASSUME_NONNULL_END
