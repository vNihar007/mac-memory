import os 
from pathlib import Path 
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError(
        "google-embeddings-api-key is not set"
    )
# this provides the multi-modal embedding capabilities for the gemini api
EMBEDDING_MODEL = "gemini-embedding-2" 

# chroma db paths 
CHROMA_PATH  = Path.home() / "Projects" / "mac-memory" / "chroma-db" 
# collection name : like the schema_name / table name
COLLECTION_NAME  = "mac-memory_indexed_files_table"
# supported extensions : image, pdf, text, office, audio
SUPPORTED_EXTENSIONS = {
    "image": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".heif"},
    "pdf": {".pdf"},
    "text": {".txt", ".md", ".py", ".js", ".ts", ".json", ".csv", ".html"},
    "office": {".docx", ".pptx"},
    "audio": {".mp3", ".wav", ".m4a", ".ogg"},
}

# files to be indexed 
INDEX_PATHS = [
    Path.home() / "Downloads",
    Path.home() / "Documents",
    Path.home() / "Desktop",
]

# skip dirs : .git, node_modules, __pycache__, ... 
SKIP_DIRS = {".git", "node_modules", "__pycache__"}

# daemon config 

HOST  = '127.0.0.1'
PORT = 8765
CONFIG_DIR = Path.home() / ".mac-memory"
FOLDERS_FILE = CONFIG_DIR / 'folders.json'
CONFIG_DIR.mkdir(parents = True , exist_ok = True)



