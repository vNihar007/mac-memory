from fastapi import FastAPI 
from fastapi import HTTPException
from mac_memory import configure

from dataclasses import asdict
from typing import Optional
from mac_memory import search

from pydantic import BaseModel
from mac_memory import registry
from mac_memory.indexer import collection


import asyncio , json 
from pathlib import Path 
from typing import Optional
from sse_starlette.sse import EventSourceResponse
from mac_memory import jobs, registry

app = FastAPI(title="mac-memory daemon")

class FolderBody(BaseModel):
    path:str

class IndexBody(BaseModel):
    folders :Optional[list[str]] = None 

def count(folder:str) -> int :
    got = collection.get(where ={"root":folder},include = [])
    return len(got["ids"])



@app.post("/index")
def start_index(body:IndexBody):
    paths = body.folders or registry.list_folders()
    roots = [Path(p).expanduser() for p in paths if Path(p).expanduser().is_dir()]
    if not roots :
        raise HTTPException(status_code=400 , detail = "no valid folders")
    if not jobs.start(roots):
        raise HTTPException(status_code=409 , detail  = "index alaredy running")
    return {"started" :True , "folders" : [str(r) for r in roots ]}


@app.get("/index/status")
def index_status():
    return jobs.current_job.snapshot()

@app.get("/index/stream")
async def index_stream():
    async def gen():
        last = -1 
        while True : 
            job = jobs.current_job
            if job.done != last or job.status != "running" :
                last = job.done
                yield {"event":"progress" , "data" : json.dumps(job.snapshot())}
            if job.status in {"done","error"}:
                break
            await asyncio.sleep(0.3)
    return EventSourceResponse(gen())


@app.get("/folders")
def get_folders():
    return [{"path":f , "count":count(f)} for f in registry.list_folders()]

@app.post("/folders")
def post_folder(body:FolderBody):
    try : 
        registry.add_folder(body.path)
    except ValueError as e :
        raise HTTPException(status_code=400 , detail = str(e))
    return get_folders()

@app.delete("/folders")
def delete_folder(body:FolderBody):
    p = str(Path(body.path).expanduser())
    collection.delete(where={"root": p})
    registry.remove_folder(p)
    return get_folders()


@app.get('/health')
def health():
    return{"status":"ok"}

@app.get("/search")
def search_endpoint(q:str , top_k: int=8 , type:Optional[str]=None ):
    results  = search.search_files(q,top_k= top_k,file_type=type)
    return [asdict(r) for r in results]

def run():
    import os
    import uvicorn
    # MACMEM_DEV=1 enables auto-reload on .py changes (dev); launchd runs without it.
    dev = os.getenv("MACMEM_DEV") == "1"
    uvicorn.run(
        "mac_memory.server:app",
        host=configure.HOST,
        port=configure.PORT,
        reload=dev,
        reload_dirs=[str(Path(__file__).parent)] if dev else None,
    )

if __name__ == "__main__" :
    run()
