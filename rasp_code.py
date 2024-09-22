import json
from picamera2 import Picamera2
import requests
import time 

picam2 = Picamera2()
picam2.start()
time.sleep(1)
while True:
    try:
        timestamp = int(time.time())
        picam2.capture_file(f'pics/{str(timestamp)}.jpg')
        url = 'https://herring-notable-physically.ngrok-free.app/upload_image'
        files = {'image': open(f'pics/{str(timestamp)}.jpg', 'rb')}
        response = requests.post(url, files=files)
        print(response.text)
        time.sleep(1)
    except Exception as e:
        print(f"Error: {e}")
        time.sleep(1)
        