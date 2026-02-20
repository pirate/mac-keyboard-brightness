//
//  KBPProfile.m
//  KBPulse
//
//  Created by EthanRDoesMC on 10/25/21.
//

#import "KBPProfile.h"

@implementation KBPProfile

-(NSNumber *)totalDuration {
    NSInteger duration = 0;
    for (KBPAnimation * animation in _animations) {
        duration += animation.totalDuration.intValue;
    }
    return @(duration/1000);
}

-(id)initWithFileURL:(NSURL *)filePath {
    self = [super init];
    if (self) {
        NSDictionary * profile = [NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfURL:filePath] options:NSJSONReadingMutableLeaves error:nil];
        _name = profile[@"Name"] ?: @"";
        _versionNumber = profile[@"Version"] ?: @"";
        _comment = profile[@"Description"] ?: @"";
        _author = profile[@"Author"] ?: @"";
        _homepage = profile[@"Homepage"] ?: @"";
        _previewImageURL = profile[@"Preview Image URL"] ?: @"";
        NSMutableArray * animationArray = [NSMutableArray new];
        for (NSDictionary * animation in profile[@"Animations"]) {
            [animationArray addObject:[[KBPAnimation alloc] initWithDictionary:animation]];
        }
        _animations = animationArray;
    }
    return self;
}

-(void)writeToFileURL:(NSURL *)filePath {
    NSDictionary * profile = @{ @"Name":_name, @"Version":_versionNumber, @"Description":_comment, @"Author":_author, @"Homepage":_homepage, @"Preview Image URL":_previewImageURL, @"Animations":[self animationArray] };
    [[NSJSONSerialization dataWithJSONObject:profile options:NSJSONWritingPrettyPrinted error:nil] writeToURL:filePath options:NSDataWritingAtomic error:nil];
}

-(NSArray *)animationArray {
    NSMutableArray * m_animations = [NSMutableArray new];
    for (KBPAnimation * animation in _animations) {
        [m_animations addObject:[animation animationDictionary]];
    }
    return m_animations;
}

+(KBPProfile *)yawnProfile {
    KBPProfile * slowFadeProfile = [KBPProfile new];
    slowFadeProfile.name = @"Yawn (default)";
    slowFadeProfile.versionNumber = @"1.0.0";
    slowFadeProfile.comment = @"A calm, breath-like animation that somewhat resembles the sleep indicator on older MacBooks.";
    slowFadeProfile.author = @"EthanRDoesMC";
    slowFadeProfile.homepage = @"https://ethanrdoesmc.com/";
    slowFadeProfile.previewImageURL = @" ";

    KBPAnimation * fadeInAnimation = [KBPAnimation new];
    fadeInAnimation.name = @"Fade In";
    fadeInAnimation.comment = @"Fades the keyboard to full brightness";
    fadeInAnimation.brightness = [NSNumber numberWithInteger:1];
    fadeInAnimation.fadeDuration = [NSNumber numberWithInteger:2500];
    fadeInAnimation.delay = [NSNumber numberWithInteger:0];

    KBPAnimation * fadeOutAnimation = [KBPAnimation new];
    fadeOutAnimation.name = @"Fade Out";
    fadeOutAnimation.comment = @"Fades the keyboard to off";
    fadeOutAnimation.brightness = [NSNumber numberWithInteger:0];
    fadeOutAnimation.fadeDuration = [NSNumber numberWithInteger:2500];
    fadeOutAnimation.delay = [NSNumber numberWithInteger:0];

    slowFadeProfile.animations = @[ fadeInAnimation, fadeOutAnimation, /*delayAnimation*/ ];
    return slowFadeProfile;
}

+(void)createYawnJSON {
    KBPProfile * slowFadeProfile = [KBPProfile yawnProfile];
    [NSFileManager.defaultManager createDirectoryAtURL:[[NSFileManager.defaultManager URLsForDirectory:NSDocumentDirectory inDomains:NSUserDomainMask][0] URLByAppendingPathComponent:@"/KBPulse/"] withIntermediateDirectories:true attributes:nil error:nil];
    [slowFadeProfile writeToFileURL:[[NSFileManager.defaultManager URLsForDirectory:NSDocumentDirectory inDomains:NSUserDomainMask][0] URLByAppendingPathComponent:@"/KBPulse/Yawn.json"]];
}

@end
