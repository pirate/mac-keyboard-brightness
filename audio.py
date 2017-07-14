try:
    import pyaudio
    import audioop
except ImportError:
    print('Missing pyaudio, run:'
          '    pip3 install --upgrade pyaudio audioop')
    raise

from time import sleep
from subprocess import run

CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 2
RATE = 44100
RECORD_SECONDS = 5
WAVE_OUTPUT_FILENAME = "output.wav"
POLL_SPEED = 0.001

def get_mic(p):
    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK)
    return stream


def runloop(stream):
    while True:
        data = stream.read(CHUNK)
        rms = audioop.rms(data, 2)         # here's where you calculate the volume
        level = rms / 20000
        run(['./kbrightness', str(level)])
        sleep(POLL_SPEED)


if __name__ == '__main__':
    print('[+] Starting...')
    p = pyaudio.PyAudio()
    stream = get_mic(p)
    try:
        runloop(stream)
    except (KeyboardInterrupt, Exception):
        stream.stop_stream()
        stream.close()
        p.terminate()
        print('[X] Stopped.')
