from groq import Groq 
from picamera2 import Picamera2
import subprocess

import requests
import base64
import json
import time


# Function to encode the image
def encode_image(image_path):
  with open(image_path, "rb") as image_file:
    return base64.b64encode(image_file.read()).decode('utf-8')

def take_pic():    
    timestamp = int(time.time())
    picam2.capture_file(f'pics/{str(timestamp)}.jpg')  
    return f'pics/{str(timestamp)}.jpg'    

def call_groq(image_path,query,client): 
    
    base64_image = encode_image(image_path)

    completion = client.chat.completions.create(
        model="llama-3.2-11b-vision-preview",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"I have attached an image of what is in front of me, based on this image answer the following question: {query}"
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url":  f"data:image/jpeg;base64,{base64_image}",
                        }
                    }
                ]
            },
            {
                "role": "assistant",
                "content": "Sure I'll be glad to help in anyway I can. Based on the image provided, "
            }
        ], 
        temperature=1,
        max_tokens=1024,
        top_p=1,
        stream=False,
        stop=None,
    )

    print(completion.choices[0].message)

def play_audio(audio_path):
   subprocess.run(['paplay', audio_path])



# init 

picam2 = Picamera2()
picam2.start()
time.sleep(1)
groq_api_key="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"
client = Groq(api_key=groq_api_key)


 