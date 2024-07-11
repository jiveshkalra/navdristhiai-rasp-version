# Writting the code to call the upload route via requests in python
import json
from picamera2 import Picamera2
picam2 = Picamera2()
picam2.start()
picam2.capture_file("test2.jpg")

import requests
url = 'https://herring-notable-physically.ngrok-free.app/process_image'
files = {'image': open('test2.jpg', 'rb')}
response = requests.post(url, files=files)
print(response.text)
 