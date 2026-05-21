
from mac_memory import configure
from pathlib import Path

from google import genai
from google.genai import types 

MAX_BYTES  = 10 * 1024 * 1024  # 10 MB limit (Gemini free tier)

client = genai.Client()

def google_embed_image(path:Path)->list[float] |None : 
    path = Path(path)
    if path.stat().st_size  > MAX_BYTES :
        print(f"skip file too large {path.name}")
        return None
    try:
        with open( path ,"rb") as f : 
            image_bytes  = f.read()
        result = client.models.embed_content(
            model = configure.EMBEDDING_MODEL,
            contents = [
                types.Part.from_bytes(
                    data = image_bytes ,
                    mime_type = 'image/png' )
            ]
        )
        return result
    except Exception as e :
        print(f"error while embedding image {path.name} with error {e} ")

path  = "/Users/varunnihar/Downloads/break_down_soham_parekh_email.jpeg"
res = google_embed_image(path)
if res and res.embeddings : 
    embeddings_value  = res.embeddings[0].values
    print(f"len of the embeddign : {len(embeddings_value)}")
    print(f"first 3 embedding values :{embeddings_value[:3]}")




