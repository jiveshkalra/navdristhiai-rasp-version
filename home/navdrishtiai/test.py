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

class ContinuousAudioRecorder:
    def __init__(self, channels=2, rate=44100, chunk=1024, sample_format=pyaudio.paInt16):
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
 
# def stream_and_play_audio_optimized(url):
#     chunk_size = 6 * 1024  # Smaller chunks for low bandwidth
#     buffer = Queue(maxsize=8)  # Reduce buffer size for memory efficiency
#     is_downloading = True

#     def decode_audio_with_ffmpeg(input_data):
#         process = subprocess.Popen(
#             ['ffmpeg', '-i', 'pipe:0', '-f', 's16le',
#                 '-ar', '22050', '-ac', '1', 'pipe:1'],
#             stdin=subprocess.PIPE,
#             stdout=subprocess.PIPE,
#             stderr=subprocess.DEVNULL
#         )
#         pcm_data, _ = process.communicate(input_data)
#         return pcm_data

#     def download_audio():
#         nonlocal is_downloading
#         response = requests.get(url, stream=True)
#         audio_buffer = b""

#         for chunk in response.iter_content(chunk_size=chunk_size):
#             if chunk:
#                 audio_buffer += chunk

#                 if len(audio_buffer) > chunk_size *2:  # Buffer 2 chunks before decoding
#                     pcm_data = decode_audio_with_ffmpeg(audio_buffer)
#                     buffer.put(pcm_data)
#                     audio_buffer = b""

#         # Decode remaining data
#         if audio_buffer:
#             pcm_data = decode_audio_with_ffmpeg(audio_buffer)
#             buffer.put(pcm_data)

#         is_downloading = False

#     def play_audio():
#         audio = pyaudio.PyAudio()
#         stream = audio.open(
#             format=pyaudio.paInt16,
#             channels=1,
#             rate=22050,
#             output=True,
#         )

#         while is_downloading or not buffer.empty():
#             if not buffer.empty():
#                 chunk = buffer.get()
#                 stream.write(chunk)
#             else:
#                 time.sleep(0.1)

#         stream.stop_stream()
#         stream.close()
#         audio.terminate()

#     download_thread = Thread(target=download_audio)
#     play_thread = Thread(target=play_audio)
#     download_thread.start()
#     play_thread.start()
#     download_thread.join()
#     play_thread.join()


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

 
# Function to ensure an intro message file exists and plays it


# Function to ensure a listening message file exists


def play_intro_async(audio_file_player):
    def play():
        intro_file = "intro.mp3"
        if not os.path.exists(intro_file):
            print("Intro file does not exist, generating TTS audio.")
            intro_text = "Hi, I am NavDrishtiAI, here to assist you with all your visual needs!"
            fetch_tts_audio(intro_text, intro_file, to_download=True)
        else:
            print("Intro file already exists.")
        audio_file_player.play_audio(intro_file)
    threading.Thread(target=play, daemon=True).start()

def play_listening_async(audio_file_player):
    def play():
        listening_file = "listening.mp3"
        if not os.path.exists(listening_file):
            print("Listening file does not exist, generating TTS audio.")
            listening_text = "Listening..."
            fetch_tts_audio(listening_text, listening_file, to_download=True)
        audio_file_player.play_audio(listening_file)

    threading.Thread(target=play, daemon=True).start()

def play_processing_async(audio_file_player):
    def play():
        processing_file = "processing.mp3"
        if not os.path.exists(processing_file):
            print("Processing file does not exist, generating TTS audio.")
            processing_text = "Processing..."
            fetch_tts_audio(processing_text, processing_file, to_download=True)
        audio_file_player.play_audio(processing_file)

    threading.Thread(target=play, daemon=True).start()

def play_unable_to_answer(audio_file_player):
    unable_to_answer_file = "unable_to_answer.mp3"
    if not os.path.exists(unable_to_answer_file):
        print("Unable to answer file does not exist, generating TTS audio.")
        unable_to_answer_text = "I am sorry but I am unable to answer your question at the moment. Please try again later."
        fetch_tts_audio(unable_to_answer_text, unable_to_answer_file, to_download=True)
    audio_file_player.play_audio(unable_to_answer_file)

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

# TTS function to fetch audio from RapidAPI
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


def do_complete_run(client,recorder,audio_url_player,audio_file_player):
    # Record start time for the entire process
    total_start_time = time.time() 
    # Step 1: Record audio continuously
    play_listening_async(audio_file_player)
    start_time = time.time()
    audio_file = recorder.record_audio_continuous()
    end_time = time.time()
    print(f"Audio recorded in {end_time - start_time:.2f} seconds.")

    # Step 2: Take a picture
    start_time = time.time()
    image_path = take_pic()
    end_time = time.time()
    print(f"Image saved at {image_path} in {end_time - start_time:.2f} seconds.")
    
    play_processing_async(audio_file_player)

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
        play_unable_to_answer()
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
    play_intro_async(audio_file_player) 

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
