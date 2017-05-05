# Control Mac Keyboard Brightness: kbrightness & dbrightness
Programmatically set the keyboard & display brightness on macs with built-in backlit keyboards.

This was mostly copied from [@tcr's repo](https://github.com/tcr/macbook-brightness), 
just repackaged for ease of use.  I had trouble finding any other easy-to-use binary for controlling
keyboard brightness, so I made one.

![](https://nicksweeting.com/d/keyboard.gif)

## Usage

Pass a float between 0-1 to the command to set brightness, or no args to get the current brightness.

```bash
git clone https://github.com/pirate/mac-keyboard-brightness
cd mac-keyboard-brightness/

./kbrightness 0.85     # sets keyboard brightness to 85%
./kbrightness
# 0.286447

./dbrightness 0.42     # sets display brightness to 42%
./dbrightness
# 0.938477
```
You should be able to download the repo and use the binaries without needing to recompile anything (tested on macOS Sierra).

 - `kbrightness` manages the keyboard backlight brightness
 - `dbrightness` manages the display backlight brightness

## Why?

It's fun.  Here are some ideas:

 - make a bitbar menubar app to control keyboard brightness
 - make your keyboard lights flash for security alerts using [Security Growler](https://github.com/pirate/security-growler)
 - make your keyboard flash right before your display is about to sleep
 - make your keyboard flash on incoming email
 - make your keyboard flash to the beat of music
 - make your keyboard flash when your boss's iPhone comes within bluetooth range

## Advanced

If you want to write more advanced programs to update the brightness at higher frequencies
(e.g. to make your keyboard flash to music), you can use the C functions directly.

 - `setDisplayBrightness`, `setDisplayBrightness`
 - `setKeyboardBrightness`, `getKeyboardBrightness`
 - `getLightSensors`: get ambient light sensor values, see [@tcr's original repo](https://github.com/tcr/macbook-brightness/blob/master/displaybrightness.c#L54)

Compile each file individually with:

```bash
gcc -std=c99 -o kbrightness keyboard-brightness.c -framework IOKit -framework ApplicationServices
# OR
gcc -std=c99 -o dbrightness display-brightness.c -framework IOKit -framework ApplicationServices
```

## Links

- https://github.com/tcr/macbook-brightness (all of the code is copied from @tcr's, just separated by function)
- http://stackoverflow.com/questions/3239749/programmatically-change-mac-display-brightness
- https://web.archive.org/web/20110828210316/http://mattdanger.net:80/2008/12/adjust-mac-os-x-display-brightness-from-the-terminal/
- http://osxbook.com/book/bonus/chapter10/light/
- https://github.com/samnung/maclight/blob/master/lights_handle.cpp
- http://www.keindesign.de/stefan/Web/Sites/iWeb/Site/iSpazz.html
