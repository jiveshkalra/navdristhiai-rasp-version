 
import cv2
import requests
import time 

camera = cv2.VideoCapture(0)

while True:
    current_time = int(time.time())
    if current_time % 5 == 0:
        return_value, image = camera.read()
        cv2.imwrite(f'pics/{current_time}.jpg', image)
        files = {'image': open(f'pics/{current_time}.jpg', 'rb')}
        response = requests.post('https://herring-notable-physically.ngrok-free.app/process_image', files=files)
        print(response.text) 
        time.sleep(1)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    else:
        time.sleep(1)