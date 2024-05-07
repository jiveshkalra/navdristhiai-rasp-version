# Making a Virtual assistant that contacts the backend server at the serverURL 
# It is function is out to help visually imapired , it takes input from mic and camera at same time and then it sends it to the backend.  
# it performs 4-5 functions
# 1. in a while true loop, it continously takes user input from mic , this is sent to the backend in form of an AudioBlob 
# 

import sounddevice as sd
import io
import wave
from scipy.io.wavfile import write
import wavio as wv
import requests
import base64 
from gtts import gTTS
# serverURL = "https://herring-notable-physically.ngrok-free.app/"

serverURL = "127.0.0.1"
mode = "question"

audio_record_freq = 44100
audio_record_duration = 10


def convert_audio_to_blob(audio_file_path): 
  with wave.open(audio_file_path, "rb") as f:
    audio_data = f.readframes(f.getnframes()) 
  blob = io.BytesIO(audio_data) 
  return blob 

def record_audio():
    """Records audio from the microphone for the specified duration."""

    recording = sd.rec(int(audio_record_duration * audio_record_freq),
                       samplerate=audio_record_freq, channels=2)
    sd.wait()

    write("recording0.wav", audio_record_freq, recording)
 
def send_data():
    audio_file_path = "recording0.wav"
    audio_blob = convert_audio_to_blob(audio_file_path)
    files = {'file': open('img.png', 'rb')}

    data = {"audioBlob":audio_blob }
    response = requests.post(serverURL, data = data , files=files )
    if response.status_code == 200:
        print("Audio sent successfully. Server response:", response.json())
    else:
        print("Error sending audio:", response.status_code, response.text)


def take_input():
    record_audio()
    send_data()


def analyze_image(file_path = "img.png",mode=mode):
    with open(file_path, 'rb') as image_file:
        image_data = image_file.read()
        image_base64 = base64.b64encode(image_data).decode('utf-8')
        image_url = f"data:image/jpeg;base64,{image_base64}"
    formdata = {
        'image': image_url ,
        "prompt": "Give me the description of what is in front of me in as much details as possible",
        "mode":mode,
        } 
    
    response = requests.post(f"{serverURL}/process_image", data=formdata)
    data = response.json() 
    return data.to_play

take_input()