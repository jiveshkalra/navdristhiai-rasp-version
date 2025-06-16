import time
import wave
import pyaudio
import requests
# from picamera2 import Picamera2

def record_audio(filename="test_audio.wav", record_seconds=5):
    chunk = 1024
    fmt = pyaudio.paInt16
    channels = 1
    rate = 44100
    p = pyaudio.PyAudio()
    stream = p.open(format=fmt, channels=channels,
                    rate=rate, input=True,
                    frames_per_buffer=chunk)
    print(f"Recording {record_seconds}s of audio...")
    frames = [stream.read(chunk) for _ in range(0, int(rate / chunk * record_seconds))]
    stream.stop_stream()
    stream.close()
    p.terminate()
    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(p.get_sample_size(fmt))
        wf.setframerate(rate)
        wf.writeframes(b''.join(frames))
    print(f"Saved audio to {filename}")
    return filename

def main():
    # 1. Capture image
    # picam2 = Picamera2()
    # picam2.start()
    # img_file = "test2.jpg"
    # picam2.capture_file(img_file)
    # print(f"Saved image to {img_file}")

    # 2. Record audio
    audio_file = record_audio()

    # 3. Upload image
    # base_url = 'https://herring-notable-physically.ngrok-free.app'
    # resp_img = requests.post(f"{base_url}/upload_image",
    #                          files={'image': open(img_file, 'rb')})
    # print("Image upload response:", resp_img.text)

    # 4. Upload audio
    resp_aud = requests.post(f"{base_url}/upload_audio",
                             files={'audio': open(audio_file, 'rb')})
    print("Audio upload response:", resp_aud.text)

if __name__ == "__main__":
    main()
