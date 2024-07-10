import firebase_admin 
from picamera import PiCamera

cred = firebase_admin.credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred, {'storageBucket': 'navdrishtiai.appspot.com'})

camera = PiCamera()
camera.capture("image.jpg")
fileName = "image.jpg"
bucket = firebase_admin.storage.bucket()
blob = bucket.blob(fileName)
blob.upload_from_filename(fileName)
blob.make_public()
print("your file url", blob.public_url)