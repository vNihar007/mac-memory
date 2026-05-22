import sys
import threading , time
from dataclasses import dataclass , field, asdict
from pathlib import Path
from mac_memory import indexer


@dataclass 
class Job: 
    status : str = "idle"   # idle | running | done | error
    total : int = 0
    done : int = 0
    indexed : int = 0
    skipped : int =0 
    errors :int = 0
    current :str  = ""
    started_at :float = 0.0
    message :str = ""

    def snapshot(self) -> dict:
        d = asdict(self)
        elapsed = time.time() - self.started_at if self.started_at else 0 
        rate = self.done / elapsed if elapsed > 0 and self.done else 0 
        d["eta_seconds"] = round((self.total - self.done) / rate , 1) if rate else None
        return d 

current_job = Job()
lock = threading.Lock()


def run(folders:list[Path]) :
    job  = current_job
    try : 
        job.total = indexer.count_indexable(folders)
        job.started_at = time.time()
        for root in folders :
            for fp in root.rglob("*"):
                if not indexer.is_indexable(fp):
                    continue
                job.current = fp.name
                try :
                    if indexer.index_file(fp,root):
                        job.indexed += 1 
                        time.sleep(1.5) # api rate limit 
                    else:
                        job.skipped +=1 
                except Exception as e :
                    job.errors += 1
                    job.message = f"{fp.name}: {e}"
                    print(f"[index] error {fp.name}: {e}", file=sys.stderr)
                job.done +=1
        job.status  = "done"    
    except Exception as e :
        job.status = "error" ; job.message = str(e)

def start(folders:list[Path]) -> bool  :
    with lock :
        if current_job.status == "running":
            return False 
        globals()["current_job"] = Job(status="running")
        threading.Thread(target=run , args= (folders,),daemon= True).start()
        return True



