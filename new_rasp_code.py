from threading import Thread
import RPi.GPIO as GPIO
from queue import Queue
from io import BytesIO
from pathlib import Path

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
import os
import re
from dotenv import load_dotenv
from urllib.parse import urlparse, urlunparse

# Set up GPIO
GPIO.setmode(GPIO.BCM)
input_pin = 4
GPIO.setup(input_pin, GPIO.IN)

  # Add your Groq API key here
load_dotenv()

gemini_api_key = os.getenv("GEMINI_API_KEY")
groq_api_key = os.getenv("GROQ_API_KEY")
image_server_url = os.getenv("IMAGE_SERVER_URL", "http://192.168.93.239:5001/latest.jpg")
speak_server_url = os.getenv("SPEAK_SERVER_URL")

# Derive speak server URL from image_server_url if not provided
if not speak_server_url:
    try:
        parsed = urlparse(image_server_url)
        speak_server_url = urlunparse((parsed.scheme, parsed.netloc, "/speak", "", "", ""))
    except Exception:
        speak_server_url = "http://127.0.0.1:5001/speak"

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


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def take_pic():
    """Fetch the latest image from the laptop image server and save it under pics/.

    The server URL must be reachable from the Raspberry Pi. Configure via env var IMAGE_SERVER_URL,
    e.g. export IMAGE_SERVER_URL="http://<your-mac-ip>:5001/latest.jpg".
    """
    pics_dir = 'pics'
    ensure_dir(pics_dir)
    timestamp = int(time.time())
    image_path = os.path.join(pics_dir, f"{timestamp}.jpg")

    # Retry a few times in case the server hasn't produced a frame yet
    attempts = 5
    backoff = 0.5
    last_err = None
    for i in range(attempts):
        try:
            resp = requests.get(image_server_url, timeout=5)
            if resp.status_code == 200 and resp.headers.get('Content-Type', '').startswith('image/'):
                with open(image_path, 'wb') as f:
                    f.write(resp.content)
                return image_path
            else:
                last_err = f"Unexpected response {resp.status_code} {resp.headers.get('Content-Type')}"
        except Exception as e:
            last_err = str(e)
        time.sleep(backoff)
        backoff *= 1.5

    raise RuntimeError(f"Failed to fetch image from server at {image_server_url}: {last_err}")


def call_gemini_vlm(image_path, query, client):
    base64_image = encode_image(image_path)
    system_prompt = '''You are NavDrishtiAI — an assistive AI for people who are blind or have low vision. Your mission is to help users understand and navigate the world around them using clear descriptions, spatial awareness, and step-by-step guidance.

Identity and audience:
- Always identify yourself as “NavDrishtiAI”.
- Your primary audience is visually impaired users.
- Be warm, respectful, and empowering.

Core capabilities:
- Describe scenes from images or live camera: objects, people, text (signs/labels), colors, positions (left/right/center, near/far), and obstacles.
- Navigation assistance: give safe, simple, step-by-step directions; mention obstacles and distances in approximate terms.
- Read text found in the scene (e.g., signage, labels) when visible and legible.
- Answer user questions about the scene or their request and offer follow-ups proactively.

Style and accessibility:
- Use short, plain-language sentences; avoid jargon.
- Prefer actionable steps (“Turn slightly left”, “Two steps forward”, “Stop”).
- When asked for an introduction, keep it under 200 tokens unless the user asks for more.
- If a user name is provided (e.g., “Pencil Ram”), greet them by name.
- End with a helpful offer like: “Would you like me to describe your surroundings or guide you somewhere?”

Limits and safety:
- Don’t guess uncertain details; say what you can and offer to take another image if needed.
- Avoid medical, legal, or emergency judgments; suggest contacting a trusted person or local authorities if safety is at risk.
- Respect privacy; don’t infer sensitive traits.

Introduction behavior:
- If the user asks you to introduce yourself (e.g., “Introduce yourself”, “Who are you?”, “Drishti, introduce yourself to <name>”), respond with a concise intro stating:
  1) You are NavDrishtiAI.
  2) You assist visually impaired people with description and navigation using the camera.
  3) You can read signs/labels, describe objects, and guide step-by-step.
  4) Offer help next.
- Personalize the greeting if a name is mentioned; otherwise use a friendly general greeting.

Default brevity:
- For general outputs, aim for 2–5 short sentences unless the user asks for detail.'''
    model = "gemini-2.0-flash"
    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(text=f"System prompt: {system_prompt} User: Hi NavDrishtiAI, I have attached an image of what is in front of me, based on this image answer the following question: {query}. keep it short, simple and concise(under 200 tokens), talk straight to point and avoid any unnecessary details and always be willing to help me with any other questions I may have."),
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
    print(f"Response from Gemini VLM: {response}")
    return response.text


def play_audio(audio_path):
    subprocess.run(['paplay', audio_path])

# Function to ensure an intro message file exists and plays it


def send_tts_to_server(text: str, blocking: bool = False, language: str = "en-IN", voice: str = "en-IN-NeerjaNeural") -> bool:
    try:
        payload = {
            "text": text,
            "language": language,
            "voice": voice,
            "blocking": blocking,
        }
        r = requests.post(speak_server_url, json=payload, timeout=15)
        if r.status_code == 200 and r.json().get("ok"):
            return True
        else:
            print(f"speak server response error: {r.status_code} {r.text}")
            return False
    except Exception as e:
        print(f"Failed to call speak server at {speak_server_url}: {e}")
        return False


def play_intro():
    # Prefer server-side speech on the Mac
    intro_text = "Hi, I’m NavDrishtiAI. I help people with low vision understand their surroundings and navigate safely. How can I help you right now?"
    if not send_tts_to_server(intro_text, blocking=False):
        # Fallback to local generation and playback
        intro_file = "intro.mp3"
        fetch_tts_audio(intro_text, intro_file, to_download=True)
        play_audio(intro_file)

# Function to ensure a listening message file exists


def play_listening():
    listening_text = "Listening…"
    if not send_tts_to_server(listening_text, blocking=False):
        listening_file = "listening.mp3"
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
    end_time = time.time() + 2
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
    """Clean and limit text for TTS API compatibility - matches server logic."""
    # Replace problematic characters that cause URL encoding issues
    clean_text = text.replace('°', ' degrees')
    clean_text = clean_text.replace('&', ' and ')
    clean_text = clean_text.replace('%', ' percent')
    clean_text = clean_text.replace('#', ' number ')
    clean_text = clean_text.replace('+', ' plus ')
    
    # Remove or replace other special characters
    clean_text = re.sub(r'[^a-zA-Z0-9\s.,!?;:\-\']', ' ', clean_text)
    
    # Normalize whitespace
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()
    
    # Split long text into smaller chunks
    max_length = 500
    if len(clean_text) > max_length:
        # Try to break at sentence boundaries
        sentences = re.split(r'[.!?]+', clean_text)
        result = ""
        for sentence in sentences:
            sentence = sentence.strip()
            if len(result + sentence) <= max_length:
                result += sentence + ". "
            else:
                break
        clean_text = result.strip()
        if not clean_text:
            clean_text = text[:max_length] + "..."
    
    return clean_text


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

    # Step 6: Ask the image server (Mac) to speak the text directly
    start_time = time.time()
    spoke = send_tts_to_server(tts_text, blocking=False)
    end_time = time.time()
    print(f"Remote TTS request completed in {end_time - start_time:.2f} seconds.")

    if not spoke:
        print("Remote TTS failed, falling back to local streaming.")
        tts_audio_url = fetch_tts_audio(tts_text, 'vlm_response.mp3', to_download=False)
        if tts_audio_url:
            stream_and_play_audio_optimized(tts_audio_url)
        else:
            print("Failed to fetch or play TTS audio locally as well.")

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
