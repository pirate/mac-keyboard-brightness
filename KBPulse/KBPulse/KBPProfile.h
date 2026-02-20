//
//  KBPProfile.h
//  KBPulse
//
//  Created by EthanRDoesMC on 10/25/21.
//

#import <Cocoa/Cocoa.h>
#import "KBPAnimation.h"

NS_ASSUME_NONNULL_BEGIN

@interface KBPProfile : NSObject
#pragma mark - Metadata
@property NSString * name;
@property NSString * versionNumber;
@property (nullable) NSString * comment;
@property (nullable) NSString * author;
@property (nullable) NSString * homepage;
@property (nullable) NSString * previewImageURL;

#pragma mark - Animations
@property NSArray * animations; // array of KBPAnimations
-(NSNumber *)totalDuration; // in seconds, as a double
-(NSArray *)animationArray;

-(id)initWithFileURL:(NSURL *)filePath;
-(void)writeToFileURL:(NSURL *)filePath;

+(KBPProfile *)yawnProfile;
+(void)createYawnJSON;

// profile implementation

@end

NS_ASSUME_NONNULL_END
