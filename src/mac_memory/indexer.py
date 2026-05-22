import sys 
import time 
import chromadb
from pathlib import Path
from mac_memory import configure
from mac_memory import embedder
from mac_memory import enricher


configure.CHROMA_PATH.mkdir(parents=True, exist_ok=True)
chroma_client = chromadb.PersistentClient(path=str(configure.CHROMA_PATH))
# command to run the chromadb Explorer --> to view the files being indexed -->  `uv run chroma run --path chroma-db --port 8000`

# collection 
collection  = chroma_client.get_or_create_collection(
    name = configure.COLLECTION_NAME ,
    metadata ={"hnsw:space":"cosine"}
)

# checking for the file is indexed or not based on the mtime(modified time)

def already_indexed(path:Path, mtime: float) -> bool:
    results = collection.get(ids=[str(path)], include=["metadatas"])
    if not results["ids"]:
        return False
    stored_mtime = results["metadatas"][0].get("mtime", 0)
    # re-index when the file has been modified since it was stored
    return float(stored_mtime) == mtime

# to check for an alredy indexded file first we need to index an file..


def file_type(path:Path) -> str: 
    suffix = path.suffix.lower()
    for ftype ,exts in configure.SUPPORTED_EXTENSIONS.items():
        if suffix in exts:  
            return ftype 
    return "Unknown file type"

def index_file(path:Path,root:Path) -> bool : 
    mtime = path.stat().st_mtime
    
    if already_indexed(path,mtime):
        return False
    
    result = embedder.embed_file(path)
    if result is None or not result.embeddings:
        return False

    vector = result.embeddings[0].values  # unwrap EmbedContentResponse → list[float]

    # to add extra context to the embedding 
    extra_meta = {}
    suffix = path.suffix.lower()
    if suffix in configure.SUPPORTED_EXTENSIONS["image"]:
        extra_meta = enricher.enrich_image(path)
    # for the nxt version
    # elif suffix in configure.SUPPORTED_EXTENSIONS["audio",set()]:
    #     extra_meta = enricher.enrich_audio(path)

    base_metadatas = {
            "path" : str(path),
            "name" : path.name ,
            "type" : file_type(path),
            "mtime": mtime , 
            "size" : path.stat().st_size ,
            "root" : str(root),
    }
    collection.upsert(
        ids = [str(path)],
        embeddings = [vector],
        documents  = [path.name],
        metadatas = [{**base_metadatas , **extra_meta}],
    )
    return True

# go over the files and index an append them into the vector space 

ALL_EXTENSIONS = set().union(*configure.SUPPORTED_EXTENSIONS.values())

def walk_and_index(root:Path):
    indexed  = skipped = errors  = 0

    # accept either a single file or a directory to walk
    candidates = [root] if root.is_file() else root.rglob("*")
    for file_path in candidates:
        if not file_path.is_file():
            continue
        # skip hidden files 
        if any(part.startswith(".") or part in configure.SKIP_DIRS for part in file_path.parts):
            continue 
        if file_path.suffix.lower() not in ALL_EXTENSIONS : 
            continue
        try :
            if index_file(file_path, root) :
                indexed  += 1
                rel = file_path.name if root.is_file() else file_path.relative_to(root)
                print(f" ✅ {rel}")
                time.sleep(1.5)
            else : 
                skipped += 1 
        except Exception as e : 
            errors += 1 
            print(f" ❌ {file_path.name} with error {e}")  
    return indexed, skipped, errors

# count_indexable([Path("~/Downloads").expanduser()]) returns an int.

def  is_indexable(fp:Path) ->bool :
    if not fp.is_file():
        return False
    if any(part.startswith(".") or part in configure.SKIP_DIRS for part in fp.parts):
        return False
    return fp.suffix.lower() in ALL_EXTENSIONS

def count_indexable(roots: list[Path]) -> int :
    return sum(1 for root in roots  for fp in root.rglob("*") if is_indexable(fp))

def main(): 
    roots  = [Path(p).expanduser() for p in sys.argv[1:]]or configure.INDEX_PATHS
    for root in roots :  
        if not root.exists():
            print(f"[indexer] path not found : {root}")
            continue
        print(f"\n[indexer] scanning {root} ..")
        i,s,e = walk_and_index(root)
        print(f" ->  {i} : indexed , {s} :skipped , {e} :errors")
    print(f"\n[indexer] total in DB : {collection.count()}")

if __name__  == "__main__":
    main()


