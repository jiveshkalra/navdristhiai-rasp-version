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


@app.route('/audio-processing', methods=['POST'])
def upload_audio():
  app.logger.info("Received audio upload request")
  to_play="Something went wrong ,Please try again."

  audio_blob = request.files['audioBlob']
  image_data = request.form['image']
  mode = request.form['mode']
 
  with open(f'{UPLOAD_FOLDER}/audio.wav', 'wb') as f:
    f.write(audio_blob.read())
  return jsonify({ "to_play":to_play,"mode":mode })
 

def download_image(image_data): 
    time_rn = datetime.datetime.now().strftime("%f")

    filename = f'{time_rn}.png'
    image_path = os.path.join(UPLOAD_FOLDER, filename)

    with open(image_path, "wb") as file:
        file.write(base64.b64decode(image_data))
    return image_path 

@app.route('/process_image', methods=['POST']) 
def process_image_api():
  if request.method == 'POST':
      image_data = request.form['image'] 
      image_path = download_image(image_data)
      return jsonify({"to_play":"description"}),200
 
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
