# Mac Memory — Phased Build Plan

**Author:** Varun Nihar  
**Date:** 2026-05-19  
**How to use this document:** Work through one phase at a time. Each phase ends with a working checkpoint — a thing you can run and verify before moving to the next. Never skip to a later phase without completing the one before it; each phase's output is the next phase's input.

---

## Phase Overview

| Phase | Name | Time Estimate | Checkpoint |
|-------|------|--------------|------------|
| 0 | Environment Setup | 30–60 min | `python -c "import chromadb; print('ok')"` succeeds |
| 1 | config.py + embedder.py | 2–3 hours | `embed_text("hello")` returns a list of 3072 floats |
| 2 | indexer.py | 2–3 hours | A test file appears in ChromaDB after running indexer |
| 3 | search.py (CLI) | 1–2 hours | `python search.py "test query"` prints ranked results |
| 4 | Raycast Extension | 3–5 hours | Grid appears in Raycast with real search results |
| 5 | Enrichment Layer (v2) | 1–2 days | Images with text are findable by their OCR content |
| 6 | Query Intelligence (v2) | 2–3 days | "photos from last week" respects the time filter |
| 7 | Answer Layer (v3) | 2–3 days | Raycast returns a synthesized answer, not just files |
| 8 | Polish & Ship | 1 day | Live GitHub repo with README + demo GIF |

---

## Phase 0: Environment Setup

**Goal:** Create a working Python environment with all dependencies installed and the Gemini API key configured. You should not write a single line of application code in this phase.

**Time estimate:** 30–60 minutes

---

### Task 0.1 — Create the project directory structure

**Input:** Nothing. You're starting from scratch.

**Expected output:**
```
~/Projects/mac-memory/
├── .env.example
├── .gitignore
├── requirements.txt
└── docs/
    └── BUILD_PHASES.md   ← (this file)
```

**Steps:**
```bash
mkdir -p ~/Projects/mac-memory/docs
cd ~/Projects/mac-memory
```

**Tools:** Terminal (Bash), Finder

---

### Task 0.2 — Create requirements.txt

**Input:** Knowledge of what libraries the project needs.

**Expected output:** A `requirements.txt` file with these exact contents:

```
google-generativeai>=0.8.0
chromadb>=0.5.0
python-dotenv>=1.0.0
Pillow>=10.0.0
PyMuPDF>=1.24.0
```

**Tools:** Any text editor (VS Code, nano, vim)

**Why each package:**
| Package | What it does |
|---------|-------------|
| `google-generativeai` | Gemini API SDK — `genai.embed_content()` |
| `chromadb` | Local vector database — stores and queries embeddings |
| `python-dotenv` | Loads `GEMINI_API_KEY` from `.env` file |
| `Pillow` | Image processing — used by `_embed_image()` |
| `PyMuPDF` | PDF text extraction — `import fitz` |

---

### Task 0.3 — Set up Python virtual environment

**Input:** `requirements.txt` (from Task 0.2)

**Expected output:** A `.venv/` folder in the project root with all packages installed. Running `pip list` inside the venv should show `chromadb`, `google-generativeai`, etc.

**Steps:**
```bash
cd ~/Projects/mac-memory
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Tools:** Python 3.11+ (check with `python3 --version`), pip

**Common issues:**
- `python3: command not found` → install Python from python.org or via `brew install python`
- `pip` errors on PyMuPDF → try `pip install --upgrade pip` first

---

### Task 0.4 — Configure Gemini API key

**Input:** A Google account. Nothing else.

**Expected output:** A `.env` file containing your API key:
```
GEMINI_API_KEY=AIza...your_key_here...
```

**Steps:**
1. Go to [aistudio.google.com](https://aistudio.google.com)
2. Sign in with your Google account
3. Click "Get API key" → Create API key
4. Copy the key
5. In the project: `cp .env.example .env`
6. Open `.env` and paste your key

**Tools:** Web browser, text editor

**Create `.env.example`** (safe to commit — no real key):
```
GEMINI_API_KEY=your_gemini_api_key_here
```

**Create `.gitignore`** (so your real key never gets committed):
```
.env
.venv/
__pycache__/
*.pyc
*.pyo
.DS_Store
raycast/node_modules/
raycast/dist/
```

---

### Task 0.5 — Verify setup

**Input:** Installed `.venv`, configured `.env`

**Expected output:** All three commands below succeed with no errors.

```bash
source .venv/bin/activate
python -c "import chromadb; print('chromadb ok')"
python -c "import google.generativeai; print('gemini ok')"
python -c "import fitz; print('pymupdf ok')"
```

**Phase 0 Checkpoint ✓**

---

## Phase 1: config.py + embedder.py

**Goal:** Write the two foundation files. By the end of this phase you can pass any text string to `embed_text()` and receive a real 3072-dimensional vector from the Gemini API.

**Time estimate:** 2–3 hours

---

### Task 1.1 — Write config.py

**Input:** Your `.env` file with the API key.

**Expected output:** A `config.py` file that:
- Loads `GEMINI_API_KEY` from `.env`
- Raises a clear error if the key is missing
- Exposes `EMBEDDING_MODEL`, `CHROMA_PATH`, `COLLECTION_NAME`
- Defines `SUPPORTED_EXTENSIONS` dict
- Defines `INDEX_PATHS` and `SKIP_DIRS`

**Key code to write:**

```python
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# REQUIRED: fail fast with a helpful message if key is missing
if not GEMINI_API_KEY:
    raise ValueError(
        "GEMINI_API_KEY is not set.\n"
        "1. Go to aistudio.google.com and create an API key\n"
        "2. cp .env.example .env\n"
        "3. Paste your key into .env"
    )

EMBEDDING_MODEL = "gemini-embedding-exp-03-07"
CHROMA_PATH = Path.home() / ".mac-memory" / "chromadb"
COLLECTION_NAME = "mac_files"

SUPPORTED_EXTENSIONS = {
    "image": {".jpg", ".jpeg", ".png", ".gif", ".webp"},
    "pdf":   {".pdf"},
    "text":  {".txt", ".md", ".py", ".js", ".ts", ".json", ".csv", ".html"},
    "audio": set(),   # disabled in v1 — use Whisper in v2
}

INDEX_PATHS = [
    Path.home() / "Desktop",
    Path.home() / "Documents",
    Path.home() / "Downloads",
]

SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".DS_Store",
    "Library", "Applications", "Music", "Movies",
}
```

**Verify it works:**
```bash
python -c "import config; print(config.EMBEDDING_MODEL)"
# Expected: gemini-embedding-exp-03-07
```

**Tools:** Text editor, Python

---

### Task 1.2 — Write embedder.py — text embedding first

**Input:** Working `config.py`

**Expected output:** A function `embed_text(text: str) -> list[float] | None` that calls the Gemini API and returns a list of 3072 floats.

**Core code:**

```python
import google.generativeai as genai
import config

genai.configure(api_key=config.GEMINI_API_KEY)

def embed_text(text: str) -> list[float] | None:
    if not text.strip():
        return None
    try:
        result = genai.embed_content(
            model=config.EMBEDDING_MODEL,
            content=text,
        )
        return result["embedding"]
    except Exception as e:
        print(f"[embedder] text embed error: {e}")
        return None
```

**Verify it works:**
```bash
python -c "
from embedder import embed_text
v = embed_text('a photo of a coffee shop')
print(f'Length: {len(v)}')   # should print: Length: 3072
print(f'First 3: {v[:3]}')   # should print 3 floats
"
```

**Tools:** Text editor, Python, Gemini API (live network call)

**Troubleshooting:**
- `400 error` or `model not found` → verify the model name is exactly `gemini-embedding-exp-03-07`
- `403 error` → your API key is wrong or not set properly
- `429 error` → you've hit the rate limit; wait 60 seconds

---

### Task 1.3 — Add image embedding to embedder.py

**Input:** Working `embed_text()` function

**Expected output:** A function `_embed_image(path)` that reads a JPEG/PNG, base64-encodes it, sends it to the Gemini API as `inline_data`, and returns a 3072-dim vector.

**Core code to add:**

```python
import base64
import mimetypes
from pathlib import Path

MAX_BYTES = 10 * 1024 * 1024   # 10 MB limit (Gemini free tier)

def _embed_image(path: Path) -> list[float] | None:
    if path.stat().st_size > MAX_BYTES:
        print(f"[embedder] skip (too large): {path.name}")
        return None
    try:
        mime, _ = mimetypes.guess_type(str(path))
        mime = mime or "image/jpeg"
        data = base64.standard_b64encode(path.read_bytes()).decode()
        result = genai.embed_content(
            model=config.EMBEDDING_MODEL,
            content={"parts": [{"inline_data": {"mime_type": mime, "data": data}}]},
        )
        return result["embedding"]
    except Exception as e:
        print(f"[embedder] image error {path.name}: {e}")
        return None
```

**Verify:**
```bash
# Use any real .jpg file you have
python -c "
from embedder import _embed_image
from pathlib import Path
v = _embed_image(Path('path/to/any/photo.jpg'))
print(len(v))   # should print 3072
"
```

**Tools:** Text editor, Python, any JPEG file for testing

---

### Task 1.4 — Add PDF embedding to embedder.py

**Input:** Working `embed_text()` and `_embed_image()` functions

**Expected output:** A function `_embed_pdf(path)` that extracts text from the first 10 pages, truncates at 8,000 chars, and calls `embed_text()`.

**Core code:**

```python
def _embed_pdf(path: Path) -> list[float] | None:
    try:
        import fitz   # PyMuPDF
        doc = fitz.open(str(path))
        pages_text = []
        for i, page in enumerate(doc):
            if i >= 10:
                break
            pages_text.append(page.get_text())
        doc.close()
        text = "\n".join(pages_text).strip()
        if not text:
            return None
        return embed_text(text[:8000])
    except Exception as e:
        print(f"[embedder] pdf error {path.name}: {e}")
        return None
```

**Tools:** Text editor, Python, PyMuPDF (`fitz`), a test PDF file

---

### Task 1.5 — Add text file embedding + public dispatch function

**Input:** All the private embed functions written above

**Expected output:** A public `embed_file(path: Path)` function that dispatches to the right private function based on file extension.

```python
def _embed_text_file(path: Path) -> list[float] | None:
    if path.stat().st_size > MAX_BYTES:
        print(f"[embedder] skip (too large): {path.name}")
        return None
    try:
        text = path.read_text(encoding="utf-8", errors="ignore").strip()
        if not text:
            return None
        return embed_text(text[:8000])
    except Exception as e:
        print(f"[embedder] text error {path.name}: {e}")
        return None

def embed_file(path: Path) -> list[float] | None:
    suffix = path.suffix.lower()
    if suffix in config.SUPPORTED_EXTENSIONS["image"]:
        return _embed_image(path)
    elif suffix in config.SUPPORTED_EXTENSIONS["pdf"]:
        return _embed_pdf(path)
    elif suffix in config.SUPPORTED_EXTENSIONS["text"]:
        return _embed_text_file(path)
    return None
```

---

### Phase 1 Checkpoint ✓

Run this verification script:

```bash
python -c "
from embedder import embed_text, embed_file
from pathlib import Path
import numpy as np

# 1. Text embedding returns 3072 floats
v1 = embed_text('a photo of a coffee shop')
assert len(v1) == 3072, f'Expected 3072, got {len(v1)}'
print('✓ embed_text returns 3072 floats')

# 2. Similar texts are close in vector space
v2 = embed_text('a picture from a cafe')
cos = sum(a*b for a,b in zip(v1,v2)) / (sum(a*a for a in v1)**0.5 * sum(b*b for b in v2)**0.5)
assert cos > 0.75, f'Expected > 0.75, got {cos:.3f}'
print(f'✓ Cosine similarity coffee/cafe: {cos:.3f}')

print('Phase 1 complete!')
"
```

---

## Phase 2: indexer.py

**Goal:** Walk the filesystem, call embedder.py on each file, and store the result in ChromaDB. After this phase, you have a real vector database on disk.

**Time estimate:** 2–3 hours

---

### Task 2.1 — Set up ChromaDB collection

**Input:** Working `config.py`

**Expected output:** Code that creates (or opens) a `PersistentClient` at `~/.mac-memory/chromadb/` and a collection named `mac_files` with cosine distance.

```python
import chromadb
import config

config.CHROMA_PATH.mkdir(parents=True, exist_ok=True)
client = chromadb.PersistentClient(path=str(config.CHROMA_PATH))
collection = client.get_or_create_collection(
    name=config.COLLECTION_NAME,
    metadata={"hnsw:space": "cosine"},
)
```

**Why `get_or_create_collection`:** Safe to call on every startup. If the collection already exists, it opens it; if not, it creates it. The `hnsw:space: cosine` MUST be set at creation time.

**Tools:** Text editor, Python, chromadb

---

### Task 2.2 — Write `already_indexed()` function

**Input:** Working ChromaDB collection

**Expected output:** A function that checks if a file is already in the database with the same modification time (mtime). Returns `True` if the file is up-to-date, `False` if it needs re-indexing.

```python
def already_indexed(path: Path, mtime: float) -> bool:
    results = collection.get(ids=[str(path)], include=["metadatas"])
    if not results["ids"]:
        return False
    stored_mtime = results["metadatas"][0].get("mtime", 0)
    return float(stored_mtime) == mtime
```

**Why mtime:** `path.stat().st_mtime` is a float timestamp (seconds since Unix epoch). If the file hasn't been modified, this number doesn't change. Comparing stored vs. current mtime tells you if the file changed since last index — without re-reading the file contents.

**Tools:** Text editor, Python

---

### Task 2.3 — Write `index_file()` function

**Input:** `already_indexed()`, `embedder.embed_file()`

**Expected output:** A function that embeds a single file and stores it in ChromaDB. Returns `True` if the file was indexed, `False` if skipped.

```python
import time

def file_type(path: Path) -> str:
    suffix = path.suffix.lower()
    for ftype, exts in config.SUPPORTED_EXTENSIONS.items():
        if suffix in exts:
            return ftype
    return "unknown"

def index_file(path: Path) -> bool:
    mtime = path.stat().st_mtime

    if already_indexed(path, mtime):
        return False

    vector = embedder.embed_file(path)
    if vector is None:
        return False

    collection.upsert(
        ids=[str(path)],
        embeddings=[vector],
        documents=[path.name],
        metadatas=[{
            "path":  str(path),
            "name":  path.name,
            "type":  file_type(path),
            "mtime": mtime,
            "size":  path.stat().st_size,
        }],
    )
    return True
```

**Why `upsert`:** The file path is the document ID. `upsert` means "insert if new, replace if exists." This makes re-indexing safe — no duplicates accumulate if you run the indexer multiple times.

**Tools:** Text editor, Python

---

### Task 2.4 — Write `walk_and_index()` and `main()`

**Input:** Working `index_file()` function

**Expected output:** A function that walks a directory tree, skips hidden files and non-supported types, calls `index_file()` on each valid file, and prints progress.

```python
ALL_EXTENSIONS = set().union(*config.SUPPORTED_EXTENSIONS.values())

def walk_and_index(root: Path):
    indexed = skipped = errors = 0

    for file_path in root.rglob("*"):
        if not file_path.is_file():
            continue
        # Skip hidden files and blacklisted directories
        if any(part.startswith(".") or part in config.SKIP_DIRS
               for part in file_path.parts):
            continue
        if file_path.suffix.lower() not in ALL_EXTENSIONS:
            continue

        try:
            if index_file(file_path):
                indexed += 1
                print(f"  ✓ {file_path.relative_to(root)}")
                time.sleep(1.5)   # CRITICAL: stay within 60 RPM free tier limit
            else:
                skipped += 1
        except Exception as e:
            errors += 1
            print(f"  ✗ {file_path.name}: {e}")

    return indexed, skipped, errors


def main():
    import sys
    roots = [Path(p).expanduser() for p in sys.argv[1:]] or config.INDEX_PATHS

    for root in roots:
        if not root.exists():
            print(f"[indexer] path not found: {root}")
            continue
        print(f"\n[indexer] scanning {root} ...")
        i, s, e = walk_and_index(root)
        print(f"  → {i} indexed, {s} skipped, {e} errors")

    print(f"\n[indexer] total in DB: {collection.count()}")

if __name__ == "__main__":
    main()
```

**Critical:** `time.sleep(1.5)` is NOT optional. The Gemini free tier allows 60 requests/minute. At `sleep(0.1)` you'd make 600 RPM and get rate-limited within 6 seconds. `1.5s` gives you 40 RPM — safely under the limit.

**Tools:** Text editor, Python

---

### Phase 2 Checkpoint ✓

```bash
# Create a test directory with 2-3 files
mkdir /tmp/mac-memory-test
echo "This is my resume with work experience" > /tmp/mac-memory-test/resume.txt
echo "Invoice for coffee shop meeting" > /tmp/mac-memory-test/invoice.txt

# Run the indexer
python indexer.py /tmp/mac-memory-test

# Expected output:
#   [indexer] scanning /tmp/mac-memory-test ...
#     ✓ resume.txt
#     ✓ invoice.txt
#   → 2 indexed, 0 skipped, 0 errors
#   [indexer] total in DB: 2

# Verify the DB actually has them
python -c "
import chromadb, config
client = chromadb.PersistentClient(path=str(config.CHROMA_PATH))
col = client.get_collection(config.COLLECTION_NAME)
print('Items in DB:', col.count())   # Should print: Items in DB: 2
"
```

---

## Phase 3: search.py (CLI)

**Goal:** Write the search interface. By the end of this phase you can type a natural language query from the terminal and see ranked results. This is the core value proposition working end-to-end.

**Time estimate:** 1–2 hours

---

### Task 3.1 — Write the SearchResult dataclass

**Input:** Nothing new — just defining the data model.

**Expected output:** A dataclass that represents one search result.

```python
from dataclasses import dataclass

@dataclass
class SearchResult:
    path: str
    name: str
    file_type: str
    similarity: float   # 0.0 (unrelated) to 1.0 (identical)
    size: int
```

**Why a dataclass:** Provides `vars(result)` for free JSON serialization, type hints for IDE autocompletion, and clean `result.similarity` access instead of `result["similarity"]`.

**Tools:** Text editor, Python

---

### Task 3.2 — Write `search_files()` function

**Input:** Working ChromaDB collection (from Phase 2), working `embed_text()` (from Phase 1)

**Expected output:** A function that takes a text query and returns a ranked list of `SearchResult` objects.

```python
import chromadb
import config, embedder
import sys

config.CHROMA_PATH.mkdir(parents=True, exist_ok=True)
client = chromadb.PersistentClient(path=str(config.CHROMA_PATH))

try:
    collection = client.get_collection(name=config.COLLECTION_NAME)
except Exception:
    print("[search] no index found — run `python indexer.py` first", file=sys.stderr)
    sys.exit(1)


def search_files(query: str, top_k: int = 8, file_type: str | None = None) -> list[SearchResult]:
    vector = embedder.embed_text(query)
    if vector is None:
        return []

    where = {"type": file_type} if file_type else None

    results = collection.query(
        query_embeddings=[vector],
        n_results=min(top_k, collection.count()),
        where=where,
        include=["metadatas", "distances"],
    )

    output = []
    for meta, distance in zip(results["metadatas"][0], results["distances"][0]):
        similarity = round(1.0 - distance, 4)
        output.append(SearchResult(
            path=meta["path"],
            name=meta["name"],
            file_type=meta["type"],
            similarity=similarity,
            size=meta.get("size", 0),
        ))

    return output
```

**How the math works:** ChromaDB returns `cosine_distance = 1 - cosine_similarity`. So to get similarity back: `similarity = 1.0 - distance`. A score of 1.0 means identical. A score of 0.0 means orthogonal/unrelated. Scores below 0.5 are usually noise.

**Tools:** Text editor, Python, ChromaDB docs

---

### Task 3.3 — Write the CLI interface

**Input:** Working `search_files()` function

**Expected output:** A CLI that supports `--json` flag (for Raycast), `--top N`, `--type`, and `--open` flags.

```python
import argparse, json, subprocess

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
```

**Tools:** Text editor, Python, argparse (stdlib)

---

### Phase 3 Checkpoint ✓

```bash
# Make sure you indexed the test files from Phase 2 first
python search.py "resume experience"
# Expected: resume.txt appears at the top of results

python search.py "coffee invoice" --json
# Expected: valid JSON array with invoice.txt having high similarity

python search.py "resume" --type text
# Expected: only text-type files in results
```

---

## Phase 4: Raycast Extension

**Goal:** Build the TypeScript/React UI that calls `search.py` as a subprocess and shows results in a Raycast Grid. After this phase, you have a complete, usable app.

**Time estimate:** 3–5 hours (depending on TypeScript familiarity)

---

### Task 4.1 — Set up the Raycast extension project

**Input:** Raycast installed on your Mac (raycast.com), Node.js installed.

**Expected output:** A working Raycast extension scaffold in `~/Projects/mac-memory/raycast/` that runs without errors.

```bash
# Prerequisites
brew install node   # if not already installed

# Create the extension scaffold
cd ~/Projects/mac-memory
mkdir raycast && cd raycast
npm init raycast-extension@latest
# Answer the prompts:
#   Template: hello-world
#   Name: mac-memory
```

**Tools:** Homebrew, Node.js, npm, Raycast

---

### Task 4.2 — Create package.json

**Input:** The extension scaffold

**Expected output:** A `package.json` with the correct Raycast metadata and `execa` as a dependency.

```json
{
  "name": "mac-memory",
  "title": "Mac Memory Search",
  "description": "Search your files semantically using Gemini Embedding 2",
  "icon": "icon.png",
  "author": "varunnihar",
  "categories": ["Productivity", "System"],
  "license": "MIT",
  "commands": [
    {
      "name": "search",
      "title": "Search Files",
      "subtitle": "Mac Memory",
      "description": "Search your indexed files with natural language",
      "mode": "view"
    }
  ],
  "dependencies": {
    "@raycast/api": "^1.70.0",
    "execa": "^8.0.1"
  },
  "devDependencies": {
    "@raycast/eslint-config": "^1.0.8",
    "typescript": "^5.4.5"
  },
  "scripts": {
    "build": "ray build -e dist",
    "dev": "ray develop",
    "lint": "ray lint"
  }
}
```

Then:
```bash
npm install
```

**Tools:** Text editor, npm, `@raycast/api`

---

### Task 4.3 — Write search.tsx — the Grid UI

**Input:** Working `search.py --json` from Phase 3

**Expected output:** A TypeScript/React file that:
1. Renders a Raycast `<Grid>` component
2. Debounces user input (600ms)
3. Calls `search.py` as a subprocess via `execa`
4. Parses the JSON output into typed `FileResult` objects
5. Displays results with thumbnails and similarity scores

**Create `src/search.tsx`:**

```typescript
import {
  Action, ActionPanel, Color, Grid,
  Icon, showToast, Toast, open, showInFinder,
} from "@raycast/api";
import { execa } from "execa";
import { useEffect, useState } from "react";

const PYTHON = `${process.env.HOME}/Projects/mac-memory/.venv/bin/python`;
const SEARCH_SCRIPT = `${process.env.HOME}/Projects/mac-memory/search.py`;

interface FileResult {
  path: string;
  name: string;
  file_type: "image" | "pdf" | "text" | "audio";
  similarity: number;
  size: number;
}

const TYPE_ICONS: Record<string, Icon> = {
  image: Icon.Image,
  pdf:   Icon.Document,
  text:  Icon.TextCursor,
  audio: Icon.Music,
};

function similarityLabel(score: number): string {
  if (score > 0.85) return "Excellent";
  if (score > 0.70) return "Good";
  if (score > 0.55) return "Fair";
  return "Weak";
}

async function runSearch(query: string): Promise<FileResult[]> {
  const { stdout } = await execa(PYTHON, [SEARCH_SCRIPT, "--json", "--top", "20", query]);
  return JSON.parse(stdout) as FileResult[];
}

export default function SearchCommand() {
  const [query, setQuery]     = useState("");
  const [results, setResults] = useState<FileResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (!query.trim()) { setResults([]); return; }

    const timer = setTimeout(async () => {
      setIsLoading(true);
      try {
        setResults(await runSearch(query));
      } catch (err) {
        await showToast({ style: Toast.Style.Failure, title: "Search failed", message: String(err) });
        setResults([]);
      } finally {
        setIsLoading(false);
      }
    }, 600);   // 600ms debounce — waits for user to stop typing

    return () => clearTimeout(timer);
  }, [query]);

  return (
    <Grid columns={4} isLoading={isLoading}
          onSearchTextChange={setQuery}
          searchBarPlaceholder="Describe what you're looking for...">

      {results.map((result) => (
        <Grid.Item
          key={result.path}
          content={
            result.file_type === "image"
              ? { fileIcon: result.path }   // actual file thumbnail!
              : TYPE_ICONS[result.file_type] ?? Icon.Document
          }
          title={result.name}
          subtitle={`${(result.similarity * 100).toFixed(0)}% · ${similarityLabel(result.similarity)}`}
          actions={
            <ActionPanel>
              <Action title="Open File" icon={Icon.Eye} onAction={() => open(result.path)} />
              <Action title="Show in Finder" icon={Icon.Finder} onAction={() => showInFinder(result.path)} />
              <Action.CopyToClipboard title="Copy Path" content={result.path}
                shortcut={{ modifiers: ["cmd"], key: "c" }} />
            </ActionPanel>
          }
        />
      ))}

      {!isLoading && query.trim() && results.length === 0 && (
        <Grid.EmptyView icon={Icon.MagnifyingGlass} title="No results"
          description="Try a different description, or run indexer.py first." />
      )}
    </Grid>
  );
}
```

**Tools:** VS Code (TypeScript support), `@raycast/api` types, `execa` docs

---

### Task 4.4 — Run the extension in dev mode

**Input:** Completed `search.tsx`, a running ChromaDB index from Phase 2/3

**Expected output:** Raycast opens with your extension showing a search bar. Typing shows a spinning loader, then results appear.

```bash
cd ~/Projects/mac-memory/raycast
npm run dev
```

Raycast will automatically open and load your extension. Press `Cmd+Space`, search for "Search Files", and test it.

**Common issues:**

| Error | Fix |
|-------|-----|
| "python not found" | The `PYTHON` path in `search.tsx` must point to your `.venv/bin/python` |
| "Module not found" | Run `npm install` in the `raycast/` directory |
| "No results" | Make sure `indexer.py` ran and `~/.mac-memory/chromadb/` exists |
| Grid shows icons but no thumbnails | The `fileIcon` only works for images with valid paths |

**Tools:** Raycast, npm, VS Code

---

### Phase 4 Checkpoint ✓

- Open Raycast → Search Files
- Type: `"resume"` → see your test resume.txt appear
- Type: `"coffee"` → see your test invoice.txt appear
- Click a result → "Show in Finder" opens the file location

**You now have a complete working v1.** Everything after this is the moat.

---

## Phase 5: Enrichment Layer (v2)

**Goal:** Create `enricher.py`. Before sending any file to the Gemini API, extract everything locally knowable: EXIF data from photos, OCR text from images, Whisper transcripts from audio, and PDF metadata. The Gemini vectors become dramatically more discriminative.

**Time estimate:** 1–2 days

---

### Task 5.1 — Install v2 dependencies

**Input:** Working `.venv` from Phase 0

**Expected output:** New packages installed.

```bash
pip install exifread pytesseract openai-whisper
brew install tesseract   # OCR engine (system-level install)
```

Add to `requirements.txt`:
```
exifread>=2.3.2
pytesseract>=0.3.10
openai-whisper>=20231117
```

**Tools:** pip, Homebrew

---

### Task 5.2 — Write `enrich_image()` in enricher.py

**Input:** A `.jpg` or `.png` file path

**Expected output:** A dict with `ocr_text`, `exif_timestamp`, `exif_gps` fields.

```python
# enricher.py
from pathlib import Path
from PIL import Image
import pytesseract
import exifread

def enrich_image(path: Path) -> dict:
    meta = {}

    # OCR: extract any text visible in the image
    try:
        img = Image.open(path)
        ocr_text = pytesseract.image_to_string(img).strip()
        if ocr_text:
            meta["ocr_text"] = ocr_text[:2000]
    except Exception as e:
        print(f"[enricher] OCR failed {path.name}: {e}")

    # EXIF: extract timestamp and GPS
    try:
        with open(path, "rb") as f:
            tags = exifread.process_file(f, stop_tag="GPS GPSLatitude")
        if "EXIF DateTimeOriginal" in tags:
            meta["exif_timestamp"] = str(tags["EXIF DateTimeOriginal"])
        lat = tags.get("GPS GPSLatitude")
        lon = tags.get("GPS GPSLongitude")
        if lat and lon:
            meta["exif_gps"] = f"{lat} {lon}"
    except Exception as e:
        print(f"[enricher] EXIF failed {path.name}: {e}")

    return meta
```

**Verify:**
```bash
python -c "
from enricher import enrich_image
from pathlib import Path
# Use a photo with visible text (receipt, whiteboard, etc.)
result = enrich_image(Path('path/to/receipt.jpg'))
print(result)
# Expected: {'ocr_text': 'Starbucks...', 'exif_timestamp': '2026:05:12 14:23:00'}
"
```

**Tools:** Tesseract (system), pytesseract, Pillow, exifread

---

### Task 5.3 — Write `enrich_audio()` with Whisper

**Input:** An `.mp3` or `.m4a` file path

**Expected output:** A dict with `transcript` and `language` fields.

```python
def enrich_audio(path: Path) -> dict:
    try:
        import whisper
        model = whisper.load_model("tiny")   # 39MB — fast on Apple Silicon
        result = model.transcribe(str(path))
        return {
            "transcript": result["text"].strip()[:8000],
            "language": result.get("language", "en"),
        }
    except Exception as e:
        print(f"[enricher] Whisper failed {path.name}: {e}")
        return {}
```

**Why Whisper instead of Gemini audio API:** The Gemini embedding endpoint's support for audio `inline_data` is undocumented and unreliable. Whisper (`tiny` model, 39MB) runs 100% on-device via Apple Silicon, transcribes in real-time, and gives you searchable text. Your audio becomes findable by what was said — "the meeting where I talked about the startup idea" — which a raw audio embedding can't match reliably.

**Tools:** `openai-whisper`, Apple Silicon (for fast inference), any voice memo/recording

---

### Task 5.4 — Update indexer.py to use enriched metadata

**Input:** Working `enricher.py` functions

**Expected output:** `index_file()` now calls the enricher before embedding. The extra metadata (OCR text, transcript, EXIF) is stored in ChromaDB.

```python
# In indexer.py, update index_file():
import enricher

def index_file(path: Path) -> bool:
    mtime = path.stat().st_mtime
    if already_indexed(path, mtime):
        return False

    vector = embedder.embed_file(path)
    if vector is None:
        return False

    # v2: extract enrichment metadata
    extra_meta = {}
    suffix = path.suffix.lower()
    if suffix in config.SUPPORTED_EXTENSIONS["image"]:
        extra_meta = enricher.enrich_image(path)
    elif suffix in config.SUPPORTED_EXTENSIONS.get("audio", set()):
        extra_meta = enricher.enrich_audio(path)

    base_meta = {
        "path":  str(path),
        "name":  path.name,
        "type":  file_type(path),
        "mtime": mtime,
        "size":  path.stat().st_size,
    }
    collection.upsert(
        ids=[str(path)],
        embeddings=[vector],
        documents=[path.name],
        metadatas=[{**base_meta, **extra_meta}],
    )
    return True
```

**Tools:** Text editor, Python

---

### Phase 5 Checkpoint ✓

```bash
# Index a photo that has visible text (a receipt, whiteboard, sign)
echo "" > /tmp/mac-memory-test/
cp ~/Desktop/any_receipt_photo.jpg /tmp/mac-memory-test/

python indexer.py /tmp/mac-memory-test

# Verify OCR text was stored in ChromaDB
python -c "
import chromadb, config
client = chromadb.PersistentClient(path=str(config.CHROMA_PATH))
col = client.get_collection(config.COLLECTION_NAME)
results = col.get(include=['metadatas'])
for meta in results['metadatas']:
    if meta.get('ocr_text'):
        print('OCR stored:', meta['ocr_text'][:100])
"
```

---

## Phase 6: Query Intelligence Layer (v2)

**Goal:** Write `query_processor.py`. Add temporal parsing (so "last week" becomes a mtime filter), query expansion (so one query becomes three paraphrases), and eventually a hybrid BM25+cosine search with RRF fusion.

**Time estimate:** 2–3 days

---

### Task 6.1 — Write `query_processor.py` — temporal parsing

**Input:** A raw user query string

**Expected output:** A dict with `clean_query` and `where_filter` (for ChromaDB metadata filtering).

```python
# query_processor.py
import re
from datetime import datetime, timedelta

TEMPORAL_PATTERNS = {
    r"last week":  lambda: {"mtime": {"$gte": (datetime.now() - timedelta(days=7)).timestamp()}},
    r"last month": lambda: {"mtime": {"$gte": (datetime.now() - timedelta(days=30)).timestamp()}},
    r"yesterday":  lambda: {"mtime": {"$gte": (datetime.now() - timedelta(days=1)).timestamp()}},
    r"this year":  lambda: {"mtime": {"$gte": datetime(datetime.now().year, 1, 1).timestamp()}},
}

TYPE_HINTS = {
    r"photo|picture|image|screenshot": "image",
    r"document|report|pdf":            "pdf",
    r"note|memo|text":                 "text",
    r"voice|audio|recording":          "audio",
}

def process_query(raw_query: str) -> dict:
    where_filter = {}

    for pattern, filter_fn in TEMPORAL_PATTERNS.items():
        if re.search(pattern, raw_query, re.IGNORECASE):
            where_filter.update(filter_fn())
            break

    for pattern, ftype in TYPE_HINTS.items():
        if re.search(pattern, raw_query, re.IGNORECASE):
            where_filter["type"] = ftype
            break

    return {
        "clean_query": raw_query,
        "where_filter": where_filter if where_filter else None,
    }
```

**Verify:**
```python
from query_processor import process_query

r = process_query("photos from last week")
assert r["where_filter"]["type"] == "image"
assert "mtime" in r["where_filter"]
print("✓ Temporal + type parsing works")
```

**Tools:** Text editor, Python, `re` (stdlib), `datetime` (stdlib)

---

### Task 6.2 — Write `expand_query()` — template-based expansion

**Input:** A query string

**Expected output:** A list of 2–3 paraphrased queries that widen the semantic net.

```python
EXPANSION_RULES = [
    (r"\bmeeting\b",   "meeting conversation discussion"),
    (r"\bphoto\b",     "photo picture image screenshot"),
    (r"\bnotes?\b",    "note memo document"),
    (r"\breceipt\b",   "receipt invoice payment"),
]

def expand_query(query: str) -> list[str]:
    queries = [query]
    for pattern, replacement in EXPANSION_RULES:
        if re.search(pattern, query, re.IGNORECASE):
            expanded = re.sub(pattern, replacement, query, flags=re.IGNORECASE)
            if expanded != query:
                queries.append(expanded)
    return queries[:3]
```

**Why expansion works:** You embed each paraphrase into a separate vector and query ChromaDB with all of them. The union of results is much broader. "Meeting" and "conversation" are close in the vector space, but not identical. Searching both ensures you catch files that use different vocabulary than you used in the query.

**Tools:** Text editor, Python

---

### Task 6.3 — Update search.py to use query processor

**Input:** Working `query_processor.py`

**Expected output:** `search_files()` now processes the query through `process_query()` and `expand_query()` before embedding and searching.

```python
# In search.py, update search_files():
from query_processor import process_query, expand_query

def search_files(query: str, top_k: int = 8, file_type: str | None = None) -> list[SearchResult]:
    parsed = process_query(query)
    queries = expand_query(parsed["clean_query"])
    
    where = parsed["where_filter"]
    if file_type:   # explicit --type flag overrides auto-detected type
        where = {"type": file_type}

    # Multi-vector search: embed each expanded query, merge results
    all_results = {}
    for q in queries:
        vector = embedder.embed_text(q)
        if vector is None:
            continue
        results = collection.query(
            query_embeddings=[vector],
            n_results=min(top_k * 2, collection.count()),
            where=where,
            include=["metadatas", "distances"],
        )
        for meta, dist in zip(results["metadatas"][0], results["distances"][0]):
            path = meta["path"]
            # Keep the best (lowest distance) result per file
            if path not in all_results or dist < all_results[path][1]:
                all_results[path] = (meta, dist)
    
    # Sort by distance (ascending = most similar first)
    sorted_results = sorted(all_results.values(), key=lambda x: x[1])[:top_k]
    
    return [
        SearchResult(
            path=meta["path"],
            name=meta["name"],
            file_type=meta["type"],
            similarity=round(1.0 - dist, 4),
            size=meta.get("size", 0),
        )
        for meta, dist in sorted_results
    ]
```

**Tools:** Text editor, Python

---

### Phase 6 Checkpoint ✓

```bash
# Index some dated files
touch -t 202605010000 /tmp/mac-memory-test/old_file.txt   # May 1
touch /tmp/mac-memory-test/new_file.txt                   # today
python indexer.py /tmp/mac-memory-test

# Test temporal filtering
python search.py "files from last week"
# Expected: new_file.txt appears, old_file.txt does NOT

# Test type filtering
python search.py "photo of the whiteboard"
# Expected: only image-type results
```

---

## Phase 7: Answer Layer (v3)

**Goal:** Add a RAG (Retrieval-Augmented Generation) answer layer. Instead of returning a list of files, synthesize a written answer from the retrieved file contents using a local LLM (Ollama). Everything runs offline — no additional API keys.

**Time estimate:** 2–3 days

---

### Task 7.1 — Install Ollama and pull llama3.2

**Input:** macOS with Apple Silicon (or 8GB+ RAM on Intel)

**Expected output:** Ollama running locally, `llama3.2` model available.

```bash
# Install Ollama
brew install ollama

# Start Ollama service
ollama serve &

# Pull the model (one-time, ~2GB download)
ollama pull llama3.2

# Verify
ollama run llama3.2 "say hello in one word"
# Expected: "Hello" or similar
```

**Tools:** Homebrew, Ollama, internet connection (one-time for model download)

---

### Task 7.2 — Write answer.py

**Input:** Working `search_files()`, working Ollama with llama3.2

**Expected output:** A function `answer_query(query)` that retrieves files, extracts their text content, prompts the LLM, and returns a synthesized answer with source citations.

```python
# answer.py
import ollama
from pathlib import Path
from search import search_files
import enricher, config

def extract_content(path_str: str, file_type: str) -> str:
    path = Path(path_str)
    try:
        if file_type == "text":
            return path.read_text(errors="ignore")[:3000]
        elif file_type == "pdf":
            return enricher.enrich_pdf_text(path)[:3000]
        elif file_type == "audio":
            return enricher.enrich_audio(path).get("transcript", "")[:3000]
        elif file_type == "image":
            return enricher.enrich_image(path).get("ocr_text", "")[:1000]
    except Exception as e:
        return f"[could not read: {e}]"
    return ""


def answer_query(query: str, top_k: int = 5) -> dict:
    results = search_files(query, top_k=top_k)
    if not results:
        return {"answer": "No relevant files found. Try running the indexer first.", "sources": []}

    contexts = []
    for r in results:
        content = extract_content(r.path, r.file_type)
        if content:
            contexts.append(f"[{r.name} — {int(r.similarity*100)}% match]:\n{content}")

    context_block = "\n\n---\n\n".join(contexts)

    prompt = f"""You are a personal assistant with access to the user's files.
Answer the question based ONLY on the file contents below.
If the answer isn't clearly in the files, say "I couldn't find a clear answer in your files."
Always cite which file(s) your answer comes from.

Files:
{context_block}

Question: {query}

Answer:"""

    response = ollama.chat(
        model=config.OLLAMA_MODEL,   # "llama3.2"
        messages=[{"role": "user", "content": prompt}],
    )

    return {
        "answer": response["message"]["content"],
        "sources": [r.path for r in results],
    }


if __name__ == "__main__":
    import sys
    query = " ".join(sys.argv[1:]) or "what files do I have?"
    result = answer_query(query)
    print(f"\nAnswer: {result['answer']}\n")
    print("Sources:")
    for s in result["sources"]:
        print(f"  → {s}")
```

**Tools:** Ollama, `ollama` Python package (`pip install ollama`), Python

---

### Task 7.3 — Add answer mode to Raycast extension

**Input:** Working `answer.py`, working Raycast extension from Phase 4

**Expected output:** A toggle in the Raycast UI between "Search" mode (file grid) and "Ask" mode (text answer with sources).

Add a new command to `package.json`:
```json
{
  "name": "ask",
  "title": "Ask Your Files",
  "subtitle": "Mac Memory",
  "description": "Get a synthesized answer from your indexed files",
  "mode": "view"
}
```

Create `src/ask.tsx` — a `Detail` view that calls `answer.py` and renders the response as markdown.

**Tools:** TypeScript, `@raycast/api` Detail component, `execa`

---

### Phase 7 Checkpoint ✓

```bash
# Make sure some text files are indexed
python answer.py "what is in my resume?"
# Expected: an answer synthesized from resume.txt content

python answer.py "do I have any invoices?"
# Expected: references to invoice.txt with content
```

---

## Phase 8: Polish & Ship

**Goal:** Make the project presentable for GitHub and shareable with others. Create a setup script, write the README, record a demo GIF, and publish.

**Time estimate:** 1 day

---

### Task 8.1 — Write setup.sh

**Input:** All completed Python and TypeScript code

**Expected output:** A single shell script that handles the complete first-time setup.

```bash
#!/bin/bash
# setup.sh — one-command setup for mac-memory

set -e

echo "Setting up mac-memory..."

# Python environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Write Python path for Raycast extension
which python > raycast/.python-path
echo "Python path written: $(cat raycast/.python-path)"

# Raycast extension dependencies
cd raycast && npm install && cd ..

echo ""
echo "Setup complete! Next steps:"
echo "1. cp .env.example .env"
echo "2. Add your GEMINI_API_KEY to .env (get it at aistudio.google.com)"
echo "3. python indexer.py ~/Desktop  # index your first directory"
echo "4. python search.py 'your query'"
echo "5. cd raycast && npm run dev    # launch the Raycast extension"
```

**Tools:** Bash, chmod (`chmod +x setup.sh`)

---

### Task 8.2 — Write README.md

**Input:** All completed code, a recorded demo GIF (Task 8.3)

**Expected output:** A README that: explains what the project does in 2 sentences, shows the demo GIF, lists prerequisites, and gives the 5-step setup.

**README structure:**
```markdown
# Mac Memory

Semantic search for your Mac. Describe what you remember — get the file.
Uses Gemini Embedding 2 + ChromaDB for cross-modal retrieval (text query → image result).

![demo](docs/demo.gif)

## How it works
[1-paragraph explanation of the architecture]

## Prerequisites
- Python 3.11+, Raycast, Gemini API key (free)

## Setup
[5 numbered steps from setup.sh]

## Performance
- Initial index: ~25 min per 1,000 files (free tier rate limit)
- Search: 500ms–1s (Gemini API + local HNSW)

## Architecture
[link to ENGINEERING.md]
```

**Tools:** Text editor, Markdown

---

### Task 8.3 — Record the demo GIF

**Input:** Working Raycast extension, a variety of indexed files (photos, PDFs, notes)

**Expected output:** A 10–15 second GIF showing:
1. Raycast opens → "Search Files"
2. Type a natural language query
3. Results appear with visual thumbnails
4. Click "Show in Finder"

**Steps:**
1. Index 20–30 varied files from your Desktop/Documents
2. Open Kap (free screen recorder) or use QuickTime + ffmpeg
3. Record the Raycast window only (crop to just the extension UI)
4. Export as GIF at 600x400, max 5MB

**Tools:** Kap (brew install --cask kap), or QuickTime + `ffmpeg -i input.mov -vf "fps=10,scale=600:-1" demo.gif`

---

### Task 8.4 — Publish to GitHub

**Input:** Completed project, README, demo GIF

**Expected output:** A public GitHub repository.

```bash
cd ~/Projects/mac-memory
git init
git add .
git commit -m "feat: initial release — semantic file search for macOS"

# On GitHub: create new repo named "mac-memory"
git remote add origin https://github.com/varunnihar/mac-memory.git
git push -u origin main
```

**Double-check `.gitignore` is working:**
```bash
git status
# .env should NOT appear in the list
# .venv/ should NOT appear in the list
```

**Tools:** git, GitHub CLI (`gh`), web browser

---

### Phase 8 Checkpoint ✓

- GitHub repo is public with a README that includes the demo GIF
- `setup.sh` works on a fresh clone (test this!)
- `python search.py "any query"` works end-to-end

---

## Quick Reference: File → Phase Map

| File | Created in Phase | Depends on |
|------|-----------------|-----------|
| `requirements.txt` | Phase 0 | — |
| `.env` / `.env.example` | Phase 0 | — |
| `.gitignore` | Phase 0 | — |
| `config.py` | Phase 1 | `.env` |
| `embedder.py` | Phase 1 | `config.py`, Gemini API |
| `indexer.py` | Phase 2 | `embedder.py`, ChromaDB |
| `search.py` | Phase 3 | `indexer.py` (needs indexed data) |
| `raycast/src/search.tsx` | Phase 4 | `search.py --json` |
| `enricher.py` | Phase 5 | Tesseract, Whisper |
| `query_processor.py` | Phase 6 | — |
| `answer.py` | Phase 7 | Ollama, `search.py` |
| `setup.sh` / `README.md` | Phase 8 | everything |

---

## Time Budget Summary

| Phase | Minimum | Maximum | Can skip? |
|-------|---------|---------|-----------|
| 0 — Setup | 30 min | 1 hour | No — foundation |
| 1 — Embedder | 2 hours | 3 hours | No — core |
| 2 — Indexer | 2 hours | 3 hours | No — core |
| 3 — Search CLI | 1 hour | 2 hours | No — core |
| 4 — Raycast | 3 hours | 5 hours | Yes — CLI still works |
| 5 — Enrichment | 1 day | 2 days | Yes — but this is the moat |
| 6 — Query Intelligence | 2 days | 3 days | Yes — but this is the moat |
| 7 — Answer Layer | 2 days | 3 days | Yes — v3 feature |
| 8 — Ship | 4 hours | 1 day | Yes — but needed for resume |

**Minimum viable demo (Phases 0–4):** 8–14 hours of focused work  
**Full v2 with moat (Phases 0–6):** 3–5 days  
**Complete v3 vision (all phases):** 7–12 days  

---

*This document is your source of truth while building. Each checkpoint is a real, testable state — not a fake milestone. If a checkpoint fails, fix it before moving forward. You're not writing code to completion; you're writing code to checkpoints.*
