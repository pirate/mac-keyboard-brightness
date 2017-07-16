try:
    from subprocess import run
except ImportError:
    print('You must run this program with python3 not python2:\n'
          '    brew install python3')
    raise

try:
    import pyaudio
    import audioop
except ImportError:
    print('Missing pyaudio, run:\n'
          '    pip3 install --upgrade pyaudio audioop')
    raise


CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
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
