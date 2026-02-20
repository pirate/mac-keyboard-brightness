//
//  KBPAnimator.h
//  KBPulse
//
//  Created by EthanRDoesMC on 10/20/21.
//

#import <Foundation/Foundation.h>

NS_ASSUME_NONNULL_BEGIN

@interface KBPAnimator : NSObject
+(void)setBrightness:(float)brightness withDuration:(int)duration;
+(void)brightenWithDuration:(int)duration;
+(void)dimWithDuration:(int)duration;
+(float)currentBrightness;
+(BOOL)isBright;
@end

NS_ASSUME_NONNULL_END
