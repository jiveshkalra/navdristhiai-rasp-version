import subprocess
from flask import Flask, request, jsonify
import os  
from PIL import Image
  

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app = Flask(__name__)
port = 5000 
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

port = 5000


@app.route('/',methods=["GET"])
def index():
  return "Hello World"


@app.route('/process_image', methods=['POST'])
def process_image_api():
  if request.method == 'POST':
    return jsonify({"to_play","Recieved data"}),200;


@app.route('/audio-processing', methods=['POST'])
def upload_audio():    
    return jsonify({"to_play","Recieved data"}),200; 
   
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

# def start_ngrok():
#     subprocess.Popen(['ngrok', 'http', f'--domain=herring-notable-physically.ngrok-free.app' ,str(port)])


if __name__ == '__main__':
    # start_ngrok()
    app.run(host='127.0.0.1', port=port, use_reloader=False, debug=True)