from picamera2 import Picamera2
from threading import Thread
import RPi.GPIO as GPIO
from queue import Queue
from io import BytesIO
from google import genai
from google.genai import types
from groq import Groq
# from gtts import gTTS
import subprocess
import requests
import pyaudio
import base64
import time
import wave
from PIL import Image
import os
import re

# Set up GPIO
GPIO.setmode(GPIO.BCM)
input_pin = 4
GPIO.setup(input_pin, GPIO.IN)

# Initialize Camera
picam2 = Picamera2()
picam2.start()
time.sleep(1)

# Initialize both clients
gemini_api_key = "AIzaSyDbbNQwdUMWSZ-FQISlFhLQ1YXO5V50AVA"
groq_api_key = "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"  # Add your Groq API key here

gemini_client = genai.Client(api_key=gemini_api_key)
groq_client = Groq(api_key=groq_api_key)

# Function definitions


def stream_and_play_audio_optimized(url):
    chunk_size = 64 * 1024  # Smaller chunks for low bandwidth
    buffer = Queue(maxsize=5)  # Reduce buffer size for memory efficiency
    is_downloading = True

    def decode_audio_with_ffmpeg(input_data):
        process = subprocess.Popen(
            ['ffmpeg', '-i', 'pipe:0', '-f', 's16le',
                '-ar', '22050', '-ac', '1', 'pipe:1'],
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


def call_gemini_vlm(image_path, query, client):
    base64_image = encode_image(image_path)
    
    model = "gemini-2.5-flash-preview-05-20"
    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(text=f"Hi NavDrishtiAI, I have attached an image of what is in front of me, based on this image answer the following question: {query}. keep it short, simple and concise(under 200 letters), talk straight to point and avoid any unnecessary details and always be willing to help me with any other questions I may have."),
                types.Part.from_bytes(data=base64.b64decode(base64_image), mime_type="image/jpeg"),
            ],
        ),
    ]
    
    generate_content_config = types.GenerateContentConfig(
        response_mime_type="text/plain",
        max_output_tokens=125,
        temperature=1.0,
    )
    
    response = client.models.generate_content(
        model=model,
        contents=contents,
        config=generate_content_config,
    )
    
    return response.text


def play_audio(audio_path):
    subprocess.run(['paplay', audio_path])

# Function to ensure an intro message file exists and plays it


def play_intro():
    intro_file = "intro.mp3"
    if not os.path.exists(intro_file):
        print("Intro file does not exist, generating TTS audio.")
        intro_text = "Hi, I am NavDrishtiAI, here to assist you with all your visual needs!"
        fetch_tts_audio(intro_text, intro_file, to_download=True)
    else:
        print("Intro file already exists.")
    play_audio(intro_file)

# Function to ensure a listening message file exists


def play_listening():
    listening_file = "listening.mp3"
    if not os.path.exists(listening_file):
        print("Listening file does not exist, generating TTS audio.")
        listening_text = "Listening..."
        fetch_tts_audio(listening_text, listening_file, to_download=True)
    play_audio(listening_file)


def record_audio_continuous(filename="output.wav"):
    chunk = 1024
    sample_format = pyaudio.paInt16
    channels = 2
    fs = 44100
    p = pyaudio.PyAudio()
    stream = p.open(format=sample_format, channels=channels,
                    rate=fs, input=True, frames_per_buffer=chunk)
    frames = []

    print("Recording...")
    while GPIO.input(input_pin) == GPIO.HIGH:
        data = stream.read(chunk)
        frames.append(data)

    # Add a 5-second buffer after input goes low
    end_time = time.time() + 1.5
    while time.time() < end_time:
        data = stream.read(chunk)
        frames.append(data)

    print("Recording finished.")
    stream.stop_stream()
    stream.close()
    p.terminate()

    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(p.get_sample_size(sample_format))
        wf.setframerate(fs)
        wf.writeframes(b''.join(frames))

    return filename


def run_whisper(filename):
    with open(filename, "rb") as file:
        transcription = groq_client.audio.transcriptions.create(
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
        # Replace with your RapidAPI key
        "x-rapidapi-key": "003d07f7a3msh14a688b8db48422p1d893cjsne4055fd63ac2",
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
    # Removes non-ASCII characters
    clean_text = clean_text.replace("°", " degrees")
    return clean_text[:1000]  # Limits to 200 characters for API compatibility


def do_complete_run(groq_client, gemini_client):
    # Record start time for the entire process
    total_start_time = time.time()

    # Step 1: Record audio continuously
    start_time = time.time()
    audio_file = record_audio_continuous()
    end_time = time.time()
    print(f"Audio recorded in {end_time - start_time:.2f} seconds.")

    # Step 2: Take a picture
    start_time = time.time()
    image_path = take_pic()
    end_time = time.time()
    print(
        f"Image saved at {image_path} in {end_time - start_time:.2f} seconds.")

    # Step 3: Run Whisper for transcription
    start_time = time.time()
    transcription_text = run_whisper(audio_file)
    end_time = time.time()
    print(f"Transcription completed in {end_time - start_time:.2f} seconds.")
    print(f"Transcription: {transcription_text}")

    # Step 4: Call VLM with the image and transcription
    start_time = time.time()
    vlm_response = call_gemini_vlm(image_path, transcription_text, gemini_client)
    end_time = time.time()
    print(f"VLM Response received in {end_time - start_time:.2f} seconds.")
    print(f"VLM Response: {vlm_response}")

    # Step 5: Preprocess text for TTS
    start_time = time.time()
    tts_text = preprocess_text_for_tts(vlm_response)
    end_time = time.time()
    print(
        f"TTS text preprocessing completed in {end_time - start_time:.2f} seconds.")

    # Step 6: Fetch TTS audio from RapidAPI
    start_time = time.time()
    tts_audio_url = fetch_tts_audio(
        tts_text, 'vlm_response.mp3', to_download=False)
    end_time = time.time()
    print(f"TTS audio fetch completed in {end_time - start_time:.2f} seconds.")

    if tts_audio_url:
        # Step 7: Stream and play the TTS audio
        start_time = time.time()
        stream_and_play_audio_optimized(tts_audio_url)
        end_time = time.time()
        print(f"TTS audio played in {end_time - start_time:.2f} seconds.")
    else:
        print("Failed to fetch or play TTS audio.")

    # Final print of total time taken
    total_end_time = time.time()
    print(
        f"Total time for do_complete_run: {total_end_time - total_start_time:.2f} seconds.")

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
play_intro()
try:
    print("Monitoring GPIO for input...")
    while True:
        if GPIO.input(input_pin) == GPIO.HIGH:
            play_listening()

            do_complete_run(groq_client, gemini_client)
        time.sleep(0.5)  # Small delay to reduce CPU usage
finally:
    GPIO.cleanup()
