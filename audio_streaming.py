import pyaudio
import requests
from threading import Thread
import time
from queue import Queue
import subprocess

def stream_and_play_audio_optimized(url):
    chunk_size = 64 * 1024  # Smaller chunks for low bandwidth
    buffer = Queue(maxsize=5)  # Reduce buffer size for memory efficiency
    is_downloading = True

    def decode_audio_with_ffmpeg(input_data):
        process = subprocess.Popen(
            ['ffmpeg', '-i', 'pipe:0', '-f', 's16le', '-ar', '22050', '-ac', '1', 'pipe:1'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL
        )
        pcm_data, _ = process.communicate(input_data)
        return pcm_data

    def download_audio():
        nonlocal is_downloading
        response = requests.get(url, stream=True)
        audio_buffer = b""

        for chunk in response.iter_content(chunk_size=chunk_size):
            if chunk:
                audio_buffer += chunk

                if len(audio_buffer) > chunk_size * 2:  # Buffer 2 chunks before decoding
                    pcm_data = decode_audio_with_ffmpeg(audio_buffer)
                    buffer.put(pcm_data)
                    audio_buffer = b""

        # Decode remaining data
        if audio_buffer:
            pcm_data = decode_audio_with_ffmpeg(audio_buffer)
            buffer.put(pcm_data)

        is_downloading = False

    def play_audio():
        audio = pyaudio.PyAudio()
        stream = audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=22050,
            output=True,
        )

        while is_downloading or not buffer.empty():
            if not buffer.empty():
                chunk = buffer.get()
                stream.write(chunk)
            else:
                time.sleep(0.1)

        stream.stop_stream()
        stream.close()
        audio.terminate()

    download_thread = Thread(target=download_audio)
    play_thread = Thread(target=play_audio)
    download_thread.start()
    play_thread.start()
    download_thread.join()
    play_thread.join()


# Example usage
audio_url = "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"
stream_and_play_audio_optimized(audio_url)
