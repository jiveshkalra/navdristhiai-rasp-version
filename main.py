# code for a raspberry pi powered smart glasses that can describe the world to the visually impaired
# Core things are 
# 1. Mic and Camera input 
# 2. Text to speech(using GTTs) output through speakers

# Things to do 
# 1st step: Inputs
# 1. Function to take a picture
# 2. Function to image into base64 blob
# 3. Function to take the audio input of 30 seconds 

# 2nd step: Dealing with server
# 1. Sending the 30 sec Audio and picture(in blob) to the server 
# 2. Getting the response from the server 

# 3rd step: Output
# 1. Converting the response to speech (via gTTS)
# 2. Playing the response to the user through speakers





# Importing Libraries
import requests
import base64 
import os
import time
# from picamera import PiCamera 
from gtts import gTTS
import cv2
from playsound import playsound
import pyaudio
import wave 
# Setting up Server URL
serverURL = "https://herring-notable-physically.ngrok-free.app/"
mode = "question"
#  camera = PiCamera() # for pi

# Step 1: Inputs
# Function to take a picture
def takePicture():
    # Raspiberry method 
    
    # camera.start_preview()
    # camera.capture('/home/pi/Desktop/image.jpg')
    # camera.stop_preview()

    # Windows Method 
    
    cam = cv2.VideoCapture(0)
    result, image = cam.read()
    cv2.imwrite("img.png", image) 
    print("Picture taken")
    cam.release()
 
#  Function to image into base64 blob
def imageToBlob():
    with open("img.png", "rb") as img_file:
        my_string = base64.b64encode(img_file.read())
        return my_string

# Function to take the audio input of 30 seconds
def takeAudio():
    # Raspiberry method
    # os.system("arecord -D plughw:1,0 -f cd -c1 -r 48000 -d 30 -t wav audio.wav")
    # Windows method 

    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 44100
    RECORD_SECONDS = 5
    WAVE_OUTPUT_FILENAME = "output.wav"

    p = pyaudio.PyAudio()

    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK)

    print("* recording")

    frames = []

    for i in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
        data = stream.read(CHUNK)
        frames.append(data)

    print("* done recording")

    stream.stop_stream()
    stream.close()
    p.terminate()

    wf = wave.open(WAVE_OUTPUT_FILENAME, 'wb')
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(p.get_sample_size(FORMAT))
    wf.setframerate(RATE)
    wf.writeframes(b''.join(frames))
    wf.close() 
 

# Step 2: Dealing with server
# Sending the 30 sec Audio and picture(in blob) to the server
def sendToServer(audio, image):
    data = {
        "audio": audio,
        "image": image,
        "mode": mode
    }
    response = requests.post(serverURL, json = data)
    return response.json()

# Getting the response from the server
def getResponse():
    response = sendToServer(takeAudio(), imageToBlob())
    return response

# Step 3: Output
# Converting the response to speech (via gTTS)
def convertToSpeech(response):
    # Pi Method? 
    # os.system("gtts-cli " + response + " --output response.mp3")
    # os.system("mpg321 response.mp3")
    # Windows Method
    tts = gTTS(text=response, lang='en')
    tts.save("response.mp3")

# Playing the response to the user through speakers
def playResponse(path): 
    playsound(path)

# Main Function
def main():
    takePicture()
    response = getResponse()
    convertToSpeech(response)
    playResponse("response.mp3")