from picamera2 import Picamera2
from threading import Thread
import RPi.GPIO as GPIO
from queue import Queue
from io import BytesIO
from groq import Groq
from PIL import Image
# from gtts import gTTS
import subprocess
import threading
import requests
import pyaudio
import base64
import time
import wave
import os
import re

# Function definitions


## Image Functions
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def take_pic():
    timestamp = int(time.time())
    image_path = f'pics/{str(timestamp)}.jpg'
    picam2.capture_file(f'pics/{str(timestamp)}.jpg')
    
    # Rotate the captured image by 180°
    with Image.open(image_path) as img:
        rotated_image = img.rotate(180)
        rotated_image.save(image_path)

    return image_path 

## AI Functions

# VLM
def call_groq_vlm(image_path, query, client):
    base64_image = encode_image(image_path)
    completion = client.chat.completions.create(
        model="llama-3.2-11b-vision-preview",
        messages=[
            {"role": "assistant", "content": "Hi I am NavDrishtiAI, your personal visual image assistant , you can provide me image of your surroundings and I will give you concise descriptions or answer your questions based on that image."},
            {"role": "user", "content": [
                {"type": "text",
                 "text": f"Hi NavDrishtiAI, I have attached an image of what is in front of me, based on this image answer the following question: {query}. keep it short , simple and concise(under 200 letters), talk straight to point and avoid any unnecessary details and always be willing to help me with any other questions I may have."},
                {"type": "image_url", 
                 "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}]},
            {"role": "assistant", "content": "Sure I'll be glad to help in anyway I can. Based on the image provided here is a brief answer to your query, "}
        ],
        temperature=1,
        max_tokens=125,
        top_p=1,
        stream=False,
        stop=None,
    )
    return completion.choices[0].message.content

# Speech To Text
def run_whisper(filename):
    with open(filename, "rb") as file:
        transcription = client.audio.transcriptions.create(
            file=(filename, file.read()),
            model="whisper-large-v3-turbo",
            response_format="json",
            language="en",
            temperature=0.0
        )
        return transcription.text

# TTS
def fetch_tts_audio(text, filename, to_download=False):
    url = "https://text-to-speech-ai-tts-api.p.rapidapi.com/"
    querystring = {
        "text": text,
        "language": "en-IN",
        "voice": "en-IN-NeerjaNeural"
    }
    headers = { 
        "x-rapidapi-key": "003d07f7a3msh14a688b8db48422p1d893cjsne4055fd63ac2", ## Jivesh 4 API KEY
        #"x-rapidapi-key": "df51034d02msh737ed9ba2028b79p146d5ajsn90b7c1651d8c", ## Jivesh 9 API KEY 

        "x-rapidapi-host": "text-to-speech-ai-tts-api.p.rapidapi.com"
    }
    response = requests.get(url, headers=headers, params=querystring)
    if response.status_code == 200:
        data = response.json()
        if data.get("error") == "false":
            download_url = data.get("download_url")
            if to_download:
                audio_response = requests.get(download_url)
                with open(filename, 'wb') as audio_file:
                    audio_file.write(audio_response.content)
                print(
                    f"TTS audio for '{text}' downloaded successfully as {filename}.")
                return filename
            else:
                return download_url
        else:
            print("Error in TTS generation:", data.get("message"))
            return None
    else:
        print("TTS API request failed with status:", response.status_code)
        return None

## Audio Functions

# Continuous Audio Recorder
class ContinuousAudioRecorder:
    def __init__(self, channels=2, rate=22050, chunk=1024, sample_format=pyaudio.paInt16):
        self.channels = channels
        self.rate = rate
        self.chunk = chunk
        self.sample_format = sample_format

        self.p = pyaudio.PyAudio()
        self.stream = self.p.open(
            format=self.sample_format,
            channels=self.channels,
            rate=self.rate,
            input=True,
            frames_per_buffer=self.chunk,
        )
        print("Audio recorder initialized.")

    def record_audio_continuous(self, input_pin, filename="output.wav", post_record_buffer=1.5):
        frames = []
        print("Recording...")

        # Record while the GPIO input pin is HIGH
        while GPIO.input(input_pin) == GPIO.HIGH:
            data = self.stream.read(self.chunk)
            frames.append(data)

        # Record additional buffer after input goes LOW
        end_time = time.time() + post_record_buffer
        while time.time() < end_time:
            data = self.stream.read(self.chunk)
            frames.append(data)

        print("Recording finished.")

        # Save audio to file
        with wave.open(filename, 'wb') as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(self.p.get_sample_size(self.sample_format))
            wf.setframerate(self.rate)
            wf.writeframes(b''.join(frames))

        return filename

    def close(self):
        self.stream.stop_stream()
        self.stream.close()
        self.p.terminate()
        print("Audio recorder closed.")

# Audio From URL Player
class PersistentAudioURLPlayer:
    def __init__(self, rate=22050, channels=1):
        self.audio = pyaudio.PyAudio()
        self.stream = self.audio.open(
            format=pyaudio.paInt16,
            channels=channels,
            rate=rate,
            output=True,
        )
        self.buffer = Queue(maxsize=4)  # Allow buffering of multiple chunks
        self.is_playing = True
        self.play_thread = Thread(target=self._play_audio)
        self.play_thread.start()

    def _play_audio(self):
        while self.is_playing or not self.buffer.empty():
            if not self.buffer.empty():
                chunk = self.buffer.get()
                self.stream.write(chunk)
            else:
                time.sleep(0.025)  # Avoid busy-waiting
    
    def write(self, chunk):
        self.buffer.put(chunk)

    def close(self):
        self.is_playing = False
        self.play_thread.join()
        self.stream.stop_stream()
        self.stream.close()
        self.audio.terminate()

# Audio File Player
class PersistentAudioFILEPlayer:

    def __init__(self):
        self.audio = pyaudio.PyAudio()
        self.stream = None
        print("Audio player initialized.")

    def play_audio(self, audio_path):
        # Open the audio file
        with wave.open(audio_path, 'rb') as wf:
            if not self.stream:
                # Initialize the audio stream if not already open
                self.stream = self.audio.open(
                    format=self.audio.get_format_from_width(wf.getsampwidth()),
                    channels=wf.getnchannels(),
                    rate=wf.getframerate(),
                    output=True,
                )

            print(f"Playing audio: {audio_path}")
            # Read and play audio data in chunks
            chunk = 1024
            data = wf.readframes(chunk)
            while data:
                self.stream.write(data)
                data = wf.readframes(chunk)

    def close(self):
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            print("Audio stream closed.")
        self.audio.terminate()
        print("Audio player terminated.")

def decode_audio_with_ffmpeg(input_data):
    process = subprocess.Popen(
        ['ffmpeg', '-i', 'pipe:0', '-f', 's16le', '-ar', '22050', '-ac', '1', 'pipe:1'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL
    )
    pcm_data, _ = process.communicate(input_data)
    return pcm_data

# Stream and Play Audio
def stream_and_play_audio_optimized(url, player):

    chunk_size = 6 * 1024  # Smaller chunks for low bandwidth

    def download_audio():
        response = requests.get(url, stream=True)
        audio_buffer = b""

        for chunk in response.iter_content(chunk_size=chunk_size):
            if chunk:
                audio_buffer += chunk

                if len(audio_buffer) > chunk_size * 2:  # Buffer 2 chunks before decoding
                    pcm_data = decode_audio_with_ffmpeg(audio_buffer)
                    player.write(pcm_data)
                    audio_buffer = b""

        # Decode and play remaining data
        if audio_buffer:
            pcm_data = decode_audio_with_ffmpeg(audio_buffer)
            player.write(pcm_data)

    download_thread = Thread(target=download_audio)
    download_thread.start()
    download_thread.join()

# Playing/ caching small audio files
def play_small_audio_async(audio_file_player, file_path, tts_text):
    """
    Plays audio asynchronously. If the audio file does not exist, it generates it using TTS.
    
    Args:
        audio_file_player: The audio playback object.
        file_path (str): The file path to check or store the audio file.
        tts_text (str): The text to synthesize into speech if the file does not exist.
    """
    def play():
        if not os.path.exists(file_path):
            print(f"{file_path} does not exist, generating TTS audio.")
            fetch_tts_audio(tts_text, file_path, to_download=True)
        else:
            print(f"{file_path} already exists.")
        audio_file_player.play_audio(file_path)
    threading.Thread(target=play, daemon=True).start()
 

## Misc.
def preprocess_text_for_tts(text):
    # Remove non-ASCII characters and limit length
    # Removes non-ASCII characters
    clean_text = re.sub(r'[^\x00-\x7F]+', ' ', text)
    clean_text = clean_text.replace("•", " ")
    clean_text = clean_text.replace("-", " ")
    clean_text = clean_text.replace(" or ", ",")
    # Removes non-ASCII characters
    clean_text = clean_text.replace("°", " degrees")
    return clean_text[:1000]  # Limits to 200 characters for API compatibility


# Main function
def do_complete_run(client,recorder,audio_url_player,audio_file_player):
    # Record start time for the entire process
    total_start_time = time.time() 
    # Step 1: Record audio continuously
    
    play_small_audio_async(audio_file_player, "listening.mp3", "Listening...")
    start_time = time.time()
    audio_file = recorder.record_audio_continuous()
    end_time = time.time()
    print(f"Audio recorded in {end_time - start_time:.2f} seconds.")

    # Step 2: Take a picture
    start_time = time.time()
    image_path = take_pic()
    end_time = time.time()
    print(f"Image saved at {image_path} in {end_time - start_time:.2f} seconds.")
    
    play_small_audio_async(audio_file_player, "processing.mp3", "Processing...")

    # Step 3: Run Whisper for transcription
    start_time = time.time()
    transcription_text = run_whisper(audio_file)
    end_time = time.time()
    print(f"Transcription completed in {end_time - start_time:.2f} seconds.")
    print(f"Transcription: {transcription_text}")

    # Step 4: Call VLM with the image and transcription
    start_time = time.time()
    vlm_response = call_groq_vlm(image_path, transcription_text, client)
    end_time = time.time()
    print(f"VLM Response received in {end_time - start_time:.2f} seconds.")
    print(f"VLM Response: {vlm_response}")

    # Step 5: Preprocess text for TTS
    start_time = time.time()
    tts_text = preprocess_text_for_tts(vlm_response)
    end_time = time.time()
    print(f"TTS text preprocessing completed in {end_time - start_time:.2f} seconds.")
    print(f"TTS Text: {tts_text}")

    # Step 6: Fetch TTS audio from RapidAPI
    start_time = time.time()
    tts_audio_url = fetch_tts_audio(tts_text, 'vlm_response.mp3', to_download=False)

    if tts_audio_url:
        # Step 7: Stream and play the TTS audio
        start_time = time.time()
        stream_and_play_audio_optimized(tts_audio_url,audio_url_player)
        end_time = time.time()
        print(f"TTS audio played in {end_time - start_time:.2f} seconds.")
    else:
        play_small_audio_async(audio_file_player, "unable_to_answer.mp3", "I am sorry but I am unable to answer your question at the moment. Please try again later.")
        print("Failed to fetch or play TTS audio.")

    end_time = time.time()
    print(f"TTS audio fetch completed in {end_time - start_time:.2f} seconds.")
    # Final print of total time taken
    total_end_time = time.time()
    print(f"Total time for do_complete_run: {total_end_time - total_start_time:.2f} seconds.") 
    print("do_complete_run completed successfully.")

    # if tts_audio_path:
    # Step 6: Play the audio
    #   play_audio(tts_audio_path)
    # Optionally, clean up the audio file after playing
    #  os.remove(tts_audio_path)
    # else:
    #   print("Failed to fetch or play TTS audio.")
    # stream_and_play_tts(text, language="en-US", voice="en-US-AriaNeural")


# Main loop
try: 
    audio_file_player = PersistentAudioFILEPlayer()
    play_small_audio_async(audio_file_player, "intro.mp3", "Hi, I am NavDrishtiAI, here to assist you with all your visual needs!")


    # Set up GPIO
    GPIO.setmode(GPIO.BCM)
    input_pin = 4
    GPIO.setup(input_pin, GPIO.IN)

    # Initialize Camera
    picam2 = Picamera2()
    picam2.start()
    time.sleep(1)

    # Initialize Groq client
    groq_api_key = "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"
    client = Groq(api_key=groq_api_key)
    recorder = ContinuousAudioRecorder() 
    audio_url_player = PersistentAudioURLPlayer()
    print("Monitoring GPIO for input...")
    while True:
        if GPIO.input(input_pin) == GPIO.HIGH:

            do_complete_run(client,recorder,audio_url_player,audio_file_player)
        time.sleep(0.5)  # Small delay to reduce CPU usage
finally:
    audio_url_player.close()
    recorder.close()
    GPIO.cleanup()
