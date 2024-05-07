import sounddevice as sd
from scipy.io.wavfile import write
import wavio as wv

freq = 44100

# Recording duration
duration = 30

# Start recorder with the given values 
# of duration and sample frequency
recording = sd.rec(int(duration * freq), 
				samplerate=freq, channels=2)

sd.wait()
write("recording0.wav", freq, recording)
 