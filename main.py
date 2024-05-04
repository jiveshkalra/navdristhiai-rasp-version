import requests
import base64 

serverURL = "https://herring-notable-physically.ngrok-free.app/"
mode = "question"
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

