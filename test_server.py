# Example server for the pi to hit
# Things to have in server :
# 1. POST Req to recieve the 30 sec Audio and picture(in blob)  
from flask import Flask, request, jsonify 
import os
# from pyngrok import ngrok, conf
from flask_cors import CORS
import subprocess 
from PIL import Image 
import base64
import datetime

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
port = 5000
CORS(app)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
 
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB limit

@app.route('/process_image', methods=['POST'])
def process_image_api():
    if 'image' not in request.files:
        return jsonify({"error": "No image file provided"}), 400

    image_file = request.files['image']

    if image_file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if image_file and image_file.read(1) == b'':  # Check if the file is empty
        return jsonify({"error": "The file is empty"}), 400
    image_file.seek(0)  # Reset file pointer after reading

    filename = datetime.datetime.now().strftime("%Y%m%d%H%M%S%f") + '.png'
    image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    image_file.save(image_path)

    # Process the image as needed
    return jsonify({"image_path": image_path}), 200

@app.route('/',methods=["GET"])
def index():
  return "Hello World"

def start_ngrok():
    subprocess.Popen(['ngrok', 'http', f'--domain=herring-notable-physically.ngrok-free.app' ,str(port)])

    # public_url = ngrok.connect(port).public_url
    # print(f" * ngrok tunnel {public_url} -> http://127.0.0.1:{port}")


if __name__ == '__main__':
    start_ngrok()
    app.run(host='127.0.0.1', port=port, use_reloader=False, debug=True)
