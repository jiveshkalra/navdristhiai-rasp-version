# Upload image code ->

        # cv2.imwrite(f'pics/{current_time}.jpg', image)
        # files = {'image': open(f'pics/{current_time}.jpg', 'rb')}
        # response = requests.post('https://herring-notable-physically.ngrok-free.app/upload_image', files=files)
        # print(response.text) 
        # time.sleep(1)

# task -> create the server that will accept the image and save it to the server 
 
from flask import request, jsonify,Flask
import os ,subprocess

app = Flask(__name__)

@app.route('/upload_image', methods=['POST'])
def upload_image():
    image = request.files['image']
    os.makedirs('uploads', exist_ok=True)
    image.save(f'uploads/{image.filename}')
    return jsonify({'message': 'Image uploaded successfully'})

@app.route('/upload_audio', methods=['POST'])
def upload_audio():
    audio = request.files['audio']
    os.makedirs('uploads', exist_ok=True)
    audio.save(f'uploads/{audio.filename}')
    return jsonify({'message': 'Audio uploaded successfully'})

def start_ngrok(port):
    subprocess.Popen(['ngrok', 'http', f'--domain=herring-notable-physically.ngrok-free.app', str(port)])


if __name__ == '__main__':
    port = 5003
    start_ngrok(5003)
    app.run(debug=True, port=port)

