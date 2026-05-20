import sys 
import time 
import chromadb
from pathlib import Path
from mac_memory import configure
from mac_memory import embedder


configure.CHROMA_PATH.mkdir(parents=True, exist_ok=True)
chroma_client = chromadb.PersistentClient(path=str(configure.CHROMA_PATH))

# collection 
collection  = chroma_client.get_or_create_collection(
    name = configure.COLLECTION_NAME ,
    metadata ={"hnsw:space":"cosine"}
)

# checking for the file is indexed or not based on the mtime(modified time)

def already_indexed(path:Path,mtime : float ) -> bool |None :
    results  = collection.get(ids = [str(path)], include  = ["metadatas"])
    if not results["ids"] :
        return False 
    return results
    # stored_mtime = results['metadatas'][0].get("mtime",0)
    # return float(stored_mtime) == mtime  # returns an bool 

# to check for an alredy indexded file first we need to index an file..


def file_type(path:Path) -> str: 
    suffix = path.suffix.lower()
    for ftype ,exts in configure.SUPPORTED_EXTENSIONS.items():
        if suffix in exts:  
            return ftype 
    return "Unknown file type"

def index_file(path:Path) -> bool : 
    mtime = path.stat().st_mtime
    
    if already_indexed(path,mtime):
        return False
    
    result = embedder.embed_file(path)
    if result is None or not result.embeddings:
        return False

    vector = result.embeddings[0].values  # unwrap EmbedContentResponse → list[float]

    collection.upsert(
        ids = [str(path)],
        embeddings = [vector],
        documents  = [path.name],
        metadatas = [{
            "path" : str(path),
            "name" : path.name ,
            "type" : file_type(path),
            "mtime": mtime , 
            "size" : path.stat().st_size ,
        }],
    )
    return True

# go over the files and index an append them into the vector space 

ALL_EXTENSIONS = set().union(*configure.SUPPORTED_EXTENSIONS.values())

def walk_and_index(root:Path):
    indexed  = skipped = errors  = 0 

    for file_path in root.rglob("*"):
        if not file_path.is_file():
            continue
        # skip hidden files 
        if any(part.startswith(".") or part in configure.SKIP_DIRS for part in file_path.parts):
            continue 
        if file_path.suffix.lower() not in ALL_EXTENSIONS : 
            continue
        try : 
            if index_file(file_path) :
                indexed  += 1 
                print(f" ✅{file_path.relative_to(root)}")
                time.sleep(1.5) 
            else : 
                skipped += 1 
        except Exception as e : 
            errors += 1 
            print(f" ❌ {file_path.name} with error {e}")  
    return indexed, skipped, errors

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


