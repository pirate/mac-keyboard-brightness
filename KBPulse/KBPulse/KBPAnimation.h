//
//  KBPAnimation.h
//  KBPulse
//
//  Created by EthanRDoesMC on 10/25/21.
//

#import <Cocoa/Cocoa.h>

NS_ASSUME_NONNULL_BEGIN

@interface KBPAnimation : NSObject
@property (nullable) NSString * name;
@property (nullable) NSString * comment;

@property NSNumber * brightness; // [0.0, 1.0]
@property NSNumber * fadeDuration; // in milliseconds
@property NSNumber * delay; // in milliseconds

-(NSNumber *)totalDuration;

-(NSDictionary *)animationDictionary;
-(id)initWithDictionary:(NSDictionary *)dictionary;


@end

NS_ASSUME_NONNULL_END
