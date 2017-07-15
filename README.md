# Control Mac Keyboard Brightness: kbrightness & dbrightness
Programmatically flash the keyboard lights and control display brightness on Macs.

This was inspired by [@tcr's repo](https://github.com/tcr/macbook-brightness).
I had trouble finding any other easy-to-use binary for controlling keyboard brightness, so I made one.

![Flashing keyboard](https://nicksweeting.com/d/keyboard.gif) ![Flashing display](https://nicksweeting.com/d/display.gif)

## Usage

 - `blink` is a shortcut to flash the keyboard lights [n] times for [t] seconds each time
 - `kbrightness` manages the keyboard backlight brightness
 - `dbrightness` manages the display backlight brightness
 - `python3 audio.py` flash the keyboard based on the audio input from your mic, makes it flash to the beat of music

Use blink in your shell scripts to alert you when things have succeeded or failed.
e.g. `wget https://example.com/large-file.mp4 && blink 2` or `./tests.py || blink 3 1`

```bash
git clone https://github.com/pirate/mac-keyboard-brightness
cd mac-keyboard-brightness/

./kbrightness          # gets current keyboard brightness
# 0.286447
./kbrightness 0.85     # sets keyboard brightness to 85%

./dbrightness          # gets current display brightness
# 0.938477
./dbrightness 0.42     # sets display brightness to 42%
=======

./blink                # flash the keyboard lights once (good for subtle alerts, e.g. git pull && blink 2)
./blink 2              # flash the keyboard lights twice
./blink 10 0.1         # flash the keyboard lights 10 times, for 0.1 seconds each time
./blink 1000 0.01      # turn your keyboard into a disco strobe

=======

pip3 install --upgrade pyaudio audioop
python3 audio.py       # flash your keyboard to the beat of the music! (uses mic input)
```
You should be able to download the repo and use the binaries without needing to recompile anything (tested on macOS Sierra).

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

 - `setDisplayBrightness`, `getDisplayBrightness`
 - `setKeyboardBrightness`, `getKeyboardBrightness`
 - `getLightSensors`: get ambient light sensor values, see [@tcr's original repo](https://github.com/tcr/macbook-brightness/blob/master/displaybrightness.c#L54)

Compile each file individually with:

```bash
gcc -std=c99 -o kbrightness keyboard-brightness.c -framework IOKit -framework ApplicationServices
# OR
gcc -std=c99 -o dbrightness display-brightness.c -framework IOKit -framework ApplicationServices
```

## Links

- https://github.com/tcr/macbook-brightness (the core brightness code is copied from @tcr's, but separated into two cli utils)
- http://stackoverflow.com/questions/3239749/programmatically-change-mac-display-brightness
- https://web.archive.org/web/20110828210316/http://mattdanger.net:80/2008/12/adjust-mac-os-x-display-brightness-from-the-terminal/
- http://osxbook.com/book/bonus/chapter10/light/
- https://github.com/samnung/maclight/blob/master/lights_handle.cpp
- http://www.keindesign.de/stefan/Web/Sites/iWeb/Site/iSpazz.html
- https://github.com/bhoeting/DiscoKeyboard
