# KBPulse Profiles

Profiles are implemented in .json for readability and simplicity. At the moment, *all* fields must be present. That's not a technical limitation -- I've just been really busy with college and haven't had the time to implement something to handle that. 

**For now, consider all fields as effectively required, but I am going to mark optional fields as such.**

Profiles correspond to `KBPProfile`, and the animations are `KBPAnimation`s.

## Top-Level
```objective-c
@interface KBPProfile
```

### Name
```json
"Name" : "Cool Profile",
```
```objective-c
@property NSString *name;
```
**Required**. Should generally match your file name, but you can add extra details here (i.e. `theme_slow.json` can have `Theme (slow)` for `Name`. It can technically be anything, but try not to be confusing to the user.

### Version
```json
"Version" : "1.0.0",
```
```objective-c
@property NSString *versionNumber;
```
**Required**. Try to use the MAJOR.MINOR.PATCH semantic versioning format.

### Description
```json
"Description" : "A short description of your profile in a calm fragment that makes a comparison at the end",
```
```objective-c
@property (nullable) NSString *comment;
```
*Optional*. You can put anything into the description, but I put extra effort into coming up with the "style" of the built-in profiles' descriptions. There's a formula:

> (A/an) (short adjective), (adverb comparison) animation that (comparison to something familiar).

If you want to follow this formula, remember to not make a complete sentence. Your description should be a sentence fragment, and more specifically, a subject (or noun) fragment. The description should describe the profile's attributes, not its actions.

### Author
```json
"Author" : "EthanRDoesMC",
```
```objective-c
@property (nullable) NSString *author;
```
*Optional but recommended*.

### Homepage
```json
"Homepage" : "https://github.com/EthanRDoesMC/KBPulse/",
```
```objective-c
@property (nullable) NSString *homepage;
```
*Optional*. Try not to use *your* homepage. Instead, try to link to the website (or GitHub repo/gist) *for the profile*.

### Preview Image URL
```json
"Preview Image URL" : "https://example.com/image.jpeg",
```
```objective-c
@property (nullable) NSString *previewImageURL;
```
*Optional*. Not a big priority, but should I implement a UI one day, it would be really nice if community profiles already had preview images.

## Animations
```json
"Animations" = [
    {
        ...
    },
    ...
],
```
    
```objective-c
@property NSArray *animations;

@interface KBPAnimation
```

### Name
Same as above, but optional. For your own reference.

### Description
Same as above, but optional. *This* description is for *your* reference, so you don't have to worry about making it nice.

### Brightness
```json
"Brightness" : 0.5,
```
```objective-c
@property NSNumber *brightness;
```
**Required**. Any `double` between and including 0.0 and 1.0. The brightness value that the backlight will be set to.

### Fade Duration
```json
"Fade Duration" : 2500,
```
```objective-c
@property NSNumber *fadeDuration;
```
**Required**. An integer in milliseconds for how long the brightness fade-in will take.

### Delay
```json
"Delay" : 2500,
```
```objective-c
@property NSNumber *delay;
```
**Required**. An integer in milliseconds that specifies how long KBPulse will wait *after* the current fade animation completes before starting the next animation.