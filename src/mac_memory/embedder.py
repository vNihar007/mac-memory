from google import genai
from google.genai import types
from mac_memory import configure

# client = genai.Client(api_key=configure.GEMINI_API_KEY)
client = genai.Client(api_key=configure.GEMINI_API_KEY)

# gemini-embedding-2 has no task_type param; the retrieval task is given as a
# content prefix instead. Query and document sides must use the matching format.
def _doc_prefix(title: str, content: str) -> str:
    if title is None : 
        title = "None"
    return f"title: {title} | text: {content}"

def _query_prefix(query: str) -> str:
    return f"task: search result | query: {query}"

def embed_text(text:str) -> list[float] | None :
    if not text.strip():
        return None
    try:
        result = client.models.embed_content(
            # api_key = configure.GEMINI_API_KEY,
            model = configure.EMBEDDING_MODEL,
            contents = text
        )
        return result
    except Exception as e:
        print(f"text embedder error : {e}")
        return None

def embed_query(query: str) -> list[float] | None:
    """Embed a search query with the retrieval-query prefix (search side)."""
    return embed_text(_query_prefix(query))

# for testing 
# text  = "whats is todays date "
# res = embed_text(text)
# if res and res.embeddings : 
#     embeddings_value = res.embeddings[0].values
#     print(f"len of the embeddign : {len(embeddings_value)}")
#     print(f"first 3 embedding values :{embeddings_value[:3]}")


## TO EMBED IMAGES

from PIL import Image
import pillow_heif
pillow_heif.register_heif_opener()
import io
import base64
import mimetypes
from pathlib import Path

MAX_BYTES  = 10 * 1024 * 1024  # 10 MB limit (Gemini free tier)

def embed_image(path:Path) -> list[float] | None : 
    path = Path(path)
    if path.stat().st_size > MAX_BYTES :
        print(f"skip too large: {path.name}")
        return None
    try:
        with Image.open(path) as img:
            img_data = io.BytesIO()
            img.save(img_data, format=img.format)
            mime = f'image/{img.format.lower()}'
            part = types.Part(
                inline_data=types.Blob(data=img_data.getvalue(), mime_type=mime)
            )
            result = client.models.embed_content(
                model=configure.EMBEDDING_MODEL,
                contents=[_doc_prefix("photo", ""), part],
            )
            return result
    except Exception as e : 
        print(f"error while embedding image {path.name} wihh error : {e}")
        return None




# testing the embeddigns
# path = "/Users/varunnihar/Downloads/break_down_soham_parekh_email.jpeg"
# res = embed_image(path)
# if res and res.embeddings : 
#     embeddings_value = res.embeddings[0].values
#     print(f"len of the embeddign : {len(embeddings_value)}")
#     print(f"first 3 embedding values :{embeddings_value[:3]}")

# FOR PDF EMBEDDINGS
import pymupdf as fitz
def embed_pdf(path:Path) ->list[float] |None : 
    try : 
        doc = fitz.open(str(path))
        pages_text  = []
        for i , page in enumerate(doc):
            if i >= 10: 
                break
            pages_text.append(page.get_text())
        doc.close()
        text  = '\n'.join(pages_text).strip()
        if not text:
            return None
        return embed_text(_doc_prefix(path.name, text[:8000]))
    except Exception as e :
        print(f"error while embedding pdf {path} with error {e}")
        return None
    

# test for embedding pdf
# path = '/Users/varunnihar/Downloads/vaurnnihar_4068.pdf'
# res = embed_pdf(path)
# if res and res.embeddings :
#     embeddings_value = res.embeddings[0].values
#     print(f"len of the embeddign : {len(embeddings_value)}")
#     print(f"first 3 embedding values :{embeddings_value[:3]}")


# for embedding a text file
# here we are usign the embed_text --> text
# converting to embed_text_file --> that takes path
def embed_text_file(path:Path) -> list[float] | None :
    if path.stat().st_size >  MAX_BYTES : 
        print(f"skip files too large {path.name}")
        return None 
    try : 
        text  = path.read_text(encoding='utf-8', errors='ignore').strip()
        if not text :
            return None
        return embed_text(_doc_prefix(path.name, text[:8000]))
    except Exception as e :
        print(f"falied to embed file {path.name} as error {e}")
        return None

# final funtion for public display

def embed_file(path:Path) ->list[float] |  None : 
    suffix = path.suffix.lower()
    if suffix in configure.SUPPORTED_EXTENSIONS["image"]:
        return embed_image(path)
    elif suffix in configure.SUPPORTED_EXTENSIONS["pdf"]:
        return embed_pdf(path)
    elif suffix in configure.SUPPORTED_EXTENSIONS["text"]:
        return embed_text_file(path)
    return None

        

