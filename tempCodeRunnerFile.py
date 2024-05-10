import base64 

 
 

def save_base64_image(base64_string, save_path): 
    with open(save_path, "wb") as file:
        file.write(base64.b64decode(base64_string))

 

