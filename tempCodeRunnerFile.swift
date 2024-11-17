import requests

url = "https://text-to-speech-ai-tts-api.p.rapidapi.com/"

querystring = {"text":"Salom Dunyo!","language":"uz-UZ","voice":"uz-UZ-MadinaNeural"}

headers = {
	"x-rapidapi-key": "f00308b42cmsh53ef42b40385409p19097ejsn06a3a5fdd395",
	"x-rapidapi-host": "text-to-speech-ai-tts-api.p.rapidapi.com"
}

response = requests.get(url, headers=headers, params=querystring)

print(response.json())

