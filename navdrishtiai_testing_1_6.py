   
from base64 import b64decode, b64encode
import cv2
import numpy as np
import PIL 
import html
import time  
from PIL import Image
import whisper 
import datetime
from flask import Flask, request, jsonify
import base64
import os
from pyngrok import ngrok, conf
from flask_cors import CORS
from PIL import Image
  

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
port = 5000
CORS(app)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def mode_switch(query_mode,mode):
  print(f'mode ->{mode}')
  print(f'query_mode ->{query_mode}')
  if query_mode == "introduction":
    to_play = '''
    Welcome to NaavDrishti AI . NaavDrishtiAI is a groundbreaking Aritificial Intelligence powered solution designed to empower the visually impaired community and enhance their quality of life.
    Currently It has Three Modes which you can toggle between and each mode has separate functionality
    Firstly is the auto mode , in this the AI automatically takes picture of your surroundings in every 20 seconds and analyses your surroundings for any percieved threats and gives you constant updates on whats happening arround you.
    Secondly is the question mode , this is toggled on by default and in this you can ask the AI model any question while holding the button on the bottom of your screen , and the AI will analyse the image feed from your camera and answer your queries accordingly.
    and Thirdly is the read mode ,in this you can ask the AI to read the text out of a book , newspaper or any other document.

    To switch between different modes, Say Turn On Mode_name  mode , for example : turn on auto mode.
    '''
    return 'question',to_play
  if query_mode == mode:
    to_play= f"{mode} is already turned on.Please say some other mode to switch."
  else:
    to_play= f'Turning on {query_mode} mode.'
    mode = query_mode
  return mode,to_play

@app.route('/audio-processing', methods=['POST'])
def upload_audio():
  app.logger.info("Received audio upload request")
  to_play="Something went wrong ,Please try again."

  audio_blob = request.files['audioBlob']
  image_data = request.form['image']
  mode = request.form['mode']

  with open(f'{UPLOAD_FOLDER}/audio.wav', 'wb') as f:
    f.write(audio_blob.read())
  result = whisper_model.transcribe(f"{UPLOAD_FOLDER}/audio.wav")
  query = result["text"]
  query_cmd = nlp(query.lower().replace('turn','').replace(' on','').replace('.','').replace('mode','').replace('give','').replace('me','').strip())
  question_cmd = nlp('question')
  auto_cmd = nlp('auto')
  read_cmd = nlp('read')
  introduction_cmd = nlp('introduction')
  question_similarity = query_cmd.similarity(question_cmd)
  auto_similarity = query_cmd.similarity(auto_cmd)
  read_similarity = query_cmd.similarity(read_cmd)
  introduction_similarity = query_cmd.similarity(introduction_cmd)
  similarities = {
      "question": question_similarity,
      "auto": auto_similarity,
      "read": read_similarity,
      "introduction": introduction_similarity,
  }
  highest_similarity_variable = max(similarities, key=similarities.get)

  highest_similarity_value = similarities[highest_similarity_variable]
  print(highest_similarity_variable)
  if highest_similarity_value > 0.65:
    query_mode = highest_similarity_variable
    mode,to_play = mode_switch(query_mode,mode)
  else:
    try:
      image_path = download_image(image_data)
    except Exception as e:
      to_play = "Sorry , An error occured, please try again later."
    if mode == 'question':
      try:
        to_play = describe_image(image_path,query)
      except Exception as e:
        to_play = "Sorry , An error occured in running the ai interface, please try again later."
    elif mode == 'read':
      try:
        to_play = run_ocr(image_path)
      except Exception as e:
        to_play = "Sorry , An error occured in running the ai interface, please try again later."
    elif mode == 'auto':
      to_play= f'You are currently in Automatic Summary Mode,If you are trying to ask a question , please say TURN ON QUESTION MODE to toggle question mode and then ask queries'
    else:
      to_play= "Unable to understand the query ,please try again"

  return jsonify({"text":query,"query_cmd":str(query.lower().replace('.','').replace('turn','').replace( ' on','').replace('mode','').strip()),"to_play":to_play,"mode":mode,"highest_similarity_variable":highest_similarity_variable,"highest_similarity_value":highest_similarity_value});

def download_image(image_data):
  image_format = image_data.split(';')[0].split('/')[1]
  decoded_data = base64.b64decode(image_data.split(',')[1])
  time_rn = datetime.datetime.now().strftime("%f")

  filename = f'{time_rn}.{image_format}'
  image_path = os.path.join(UPLOAD_FOLDER, filename)

  with open(image_path, 'wb') as f:
      f.write(decoded_data)
  return image_path

@app.route('/process_image', methods=['POST'])
def process_image_api():
  if request.method == 'POST':
    try:
      if 'image' not in request.form or 'prompt' not in request.form:
        return jsonify({'error': 'Missing image data or prompt in request'}), 400

      image_data = request.form['image']
      prompt = request.form['prompt']
      mode = request.form['mode']
      threat_prompt = 'is there any threat in this image?'
      try:
        image_path = download_image(image_data)
      except Exception as e:
        return jsonify({'to_play': f'Error in downloading the image: {e}'}), 200
      try:
        answers = moondream_model.batch_answer(
            images=[Image.open(image_path), Image.open(image_path)],
            prompts=[prompt,threat_prompt],
            tokenizer=moondream_tokenizer,
        )
        description = answers[0]
        threat_detection = answers[1]
        print(threat_detection)
        if threat_detection.split(',')[0].lower().strip()=='no':
          return jsonify({"to_play":description}),200
        elif threat_detection.split(',')[0].lower().strip()=='yes':
          threat_description ="".join(threat_detection.split(',')[1:])
          to_play = f"ALERT : Threat Detected :{threat_description}"
          return jsonify({"to_play":to_play}),200
        else:
          return jsonify({"to_play":description}),200


      except Exception as e:
        return jsonify({'to_play': f'Error running ai : {e}'}), 200
    except Exception as e:
      print("Error processing image:", e)
      return jsonify({'to_play': 'Error processing image'}), 200

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

 