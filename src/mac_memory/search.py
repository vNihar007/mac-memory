from dataclasses import dataclass 
from mac_memory import query_processor

@dataclass 
class SearchResult: 
    path : str 
    name : str 
    file_type  : str 
    similarity : float 
    size : int 

import chromadb
from mac_memory import embedder
from mac_memory import configure
import sys 

configure.CHROMA_PATH.mkdir(parents = True , exist_ok = True)
client  = chromadb.PersistentClient(path = str (configure.CHROMA_PATH ))        

try:
    collection = client.get_collection(name = configure.COLLECTION_NAME)
except Exception  : 
    print(f"[search] no index found  - run `python indexer.py` first " , file = sys.stderr)
    sys.exit(1)

def search_files(query:str , top_k :int = 8 , file_type:str |None = None ) -> list[SearchResult] :
    
    parsed = query_processor.process_query(query)
    queries = query_processor.expand_query(parsed["clean_query"])
    
    where = parsed["where_filter"]
    if file_type :
        where  = {"type" : file_type}
    
    # Multi-vector search: embed each expanded query, merge results
    all_results = {}
    for q in queries:
        result = embedder.embed_text(q)
        if result is None or not result.embeddings:
            return []
        vector = result.embeddings[0].values
        results = collection.query(
            query_embeddings=[vector],
            n_results=min(top_k * 2, collection.count()),
            where=where,
            include=["metadatas", "distances"],
        )
        for meta, distance in zip(results["metadatas"][0], results["distances"][0]):
            path = meta["path"]
            if path not in all_results or distance < all_results[path][1]:
                all_results[path] = (meta, distance)

    sorted_results = sorted(all_results.values(), key=lambda x: x[1])[:top_k]

    return [
        SearchResult(
            path=meta["path"],
            name=meta["name"],
            file_type=meta["type"],
            similarity=round(1.0 - distance, 4),
            size=meta.get("size", 0),
        )
        for meta, distance in sorted_results
    ]

# CLI INTERFACE 
import argparse 
import json 
import subprocess

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("query", nargs="+")
    parser.add_argument("--top", type=int, default=8)
    parser.add_argument("--type", choices=["image", "pdf", "text", "audio"], dest="file_type")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--open", action="store_true")
    args = parser.parse_args()

    query = " ".join(args.query)
    results = search_files(query, top_k=args.top, file_type=args.file_type)

    if args.json:
        print(json.dumps([vars(r) for r in results], indent=2))
        return

    if not results:
        print("No results found.")
        return

    print(f'\nResults for "{query}":\n')
    for i, r in enumerate(results, 1):
        bar = "█" * int(r.similarity * 20)
        print(f"  {i}. [{r.file_type:5}] {r.name}")
        print(f"     {bar} {r.similarity:.1%}")
        print(f"     {r.path}\n")

    if args.open and results:
        subprocess.run(["open", "-R", results[0].path])

if __name__ == "__main__":
    main()