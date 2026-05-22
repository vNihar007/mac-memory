import json
from pathlib import Path
from mac_memory import configure

def load() -> list[str]:
    if configure.FOLDERS_FILE.exists():
        return json.loads(configure.FOLDERS_FILE.read_text())
    return []

def save(folders: list[str]) -> None:
    configure.FOLDERS_FILE.write_text(json.dumps(sorted(set(folders)), indent=2))

def list_folders() -> list[str]:
    return load()

def add_folder(path: str) -> list[str]:
    p = str(Path(path).expanduser())
    if not Path(p).is_dir():
        raise ValueError(f"not a directory : {p}")
    folders = load(); folders.append(p); save(folders)
    return load()

def remove_folder(path: str) -> list[str]:
    p = str(Path(path).expanduser())
    save([f for f in load() if f != p])
    return load()
