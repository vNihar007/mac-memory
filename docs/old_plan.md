# Mac Memory — Semantic File Search for macOS

**Author:** Varun Nihar
**Date:** 2026-05-17
**Status:** Draft — awaiting autoplan review

---

## Problem Statement

macOS Finder and Spotlight are keyword-based. They match filenames and indexed text.
They cannot answer questions like "find the screenshot from the coffee meeting last
week" or "show me the voice note where I talked about the business idea." Users with
thousands of files — photos, PDFs, voice memos, docs — have no way to search by
meaning, only by name.

Google's Gemini Embedding 2 (model: `gemini-embedding-exp-03-07`) puts text, images,
audio, and PDF content into the **same vector space**. A text query can retrieve an
image with no labels and no tagging — pure semantic similarity. ChromaDB stores these
vectors locally (SQLite + HNSW graph), so search is instant and private.

This project builds a personal, local semantic memory layer for macOS. The user
describes what they're looking for in plain English. They get a ranked grid of
matching files in Raycast, with similarity scores and instant preview.

---

## Goals

1. Index any supported file on your Mac into a local vector database.
2. Search with plain English — cross-modal (text query → image result, etc.).
3. Zero cloud storage — all embeddings live in `~/.mac-memory/chromadb/`.
4. Fast re-indexing — skip files that haven't changed (mtime-based incremental).
5. Raycast UI — ranked grid of thumbnails, similarity scores, one-click open/reveal.

## Non-Goals (v1)

- No sync across machines.
- No automatic background watching (manual re-run of indexer).
- No fine-tuning or custom models.
- No video embedding (too large for free-tier API, v2 consideration).

---

## Architecture

```
Files on disk (photos, PDFs, voice notes, text)
        │
        ▼
   embedder.py                    ← per-file embedding logic
   ├── _embed_image()             ← reads bytes → base64 → Gemini API
   ├── _embed_pdf()               ← PyMuPDF text extraction → Gemini API
   ├── _embed_text_file()         ← read UTF-8 → Gemini API
   └── _embed_audio()             ← reads bytes → base64 → Gemini API
        │
        ▼ float[3072] vector
        │
   indexer.py                     ← walks INDEX_PATHS, calls embedder, upserts to ChromaDB
   ├── already_indexed(path, mtime)  ← skip unchanged files
   ├── index_file(path)           ← embed + upsert
   └── walk_and_index(root)       ← rglob, skip hidden/SKIP_DIRS
        │
        ▼
   ChromaDB (~/.mac-memory/chromadb/)
   Collection: "mac_files"
   Distance: cosine
   Schema: { id: filepath, embedding: float[3072], metadata: { path, name, type, mtime, size } }
        │
        ▼ (at query time)
        │
   search.py                      ← embed query text → query ChromaDB → return top-K results
   └── search_files(query, top_k, file_type) → list[SearchResult]
        │
        ▼ JSON output (--json flag)
        │
   Raycast Extension (TypeScript/React)
   └── src/search.tsx             ← Grid UI, calls search.py subprocess, shows thumbnails
```

---

## Components

### 1. config.py

Central configuration file. All tuneable settings in one place.

| Setting | Default | Purpose |
|---------|---------|---------|
| `GEMINI_API_KEY` | from `.env` | Gemini API authentication |
| `EMBEDDING_MODEL` | `gemini-embedding-exp-03-07` | Gemini Embedding 2 model ID |
| `CHROMA_PATH` | `~/.mac-memory/chromadb/` | Local vector DB path |
| `COLLECTION_NAME` | `mac_files` | ChromaDB collection name |
| `SUPPORTED_EXTENSIONS` | images, pdf, text, audio | File types to index |
| `INDEX_PATHS` | Desktop, Documents, Downloads | Directories to scan |
| `SKIP_DIRS` | .git, node_modules, Library, etc. | Directories to skip |

### 2. embedder.py

Turns a file into a 3072-dimensional float vector using Gemini Embedding 2.

**Public API:**
- `embed_file(path: Path) -> list[float] | None` — dispatch by extension
- `embed_text(text: str) -> list[float] | None` — for queries and PDF text

**How multimodal embedding works:**
- Text files and PDFs: send UTF-8 string directly to Gemini API
- Images and audio: read raw bytes → base64-encode → send as `inline_data` with MIME type
- All modalities return the same 3072-dim vector in the same geometric space

**Limits:**
- Files over 10 MB are skipped (free-tier API size limit)
- PDFs: only first 10 pages extracted, truncated to 8,000 chars

### 3. indexer.py

Walks the filesystem and builds the ChromaDB index incrementally.

**Key design decision:** Uses `upsert` not `insert`. The file's full path is the
document ID. If you re-index, existing vectors are overwritten, not duplicated.

**Incremental indexing:** Stores `mtime` (last modified timestamp) in ChromaDB
metadata. On re-run, `already_indexed(path, mtime)` queries the DB for the stored
mtime. If it matches, the file is skipped. This makes subsequent runs fast even
for thousands of files.

**Rate limiting:** 100ms sleep between API calls to stay within Gemini free-tier
limits (~60 requests/minute on free tier).

### 4. search.py

Embeds a text query and retrieves the most semantically similar files.

**How similarity works:**
- Query text → Gemini API → 3072-dim vector Q
- ChromaDB HNSW search: find top-K vectors whose cosine distance to Q is smallest
- Cosine distance = 1 - cosine_similarity, so smaller distance = more similar
- Return: similarity score = 1 - distance (0.0 to 1.0)

**Cross-modal:** Q is a text vector. The DB contains image vectors, PDF vectors,
audio vectors. Because all live in the same embedding space, the cosine distance is
meaningful cross-modality — a text query retrieves images of the described subject.

**Filter support:** `--type image|pdf|text|audio` for type-scoped search.

### 5. Raycast Extension

TypeScript/React app that provides the search UI.

- `Grid` component: 4-column grid, each cell = file thumbnail + name + similarity %
- For images: `{ fileIcon: result.path }` shows the actual file as thumbnail
- For other types: shows a type icon (Document, TextCursor, Music)
- Debounced search: waits 600ms after last keystroke before calling `search.py`
- Actions: Open File, Show in Finder, Copy Path

---

## Data Flow (end to end)

### Indexing flow

```
1. User runs: python indexer.py
2. indexer.py reads INDEX_PATHS from config.py
3. For each file:
   a. Check mtime against ChromaDB metadata → skip if unchanged
   b. Call embed_file(path) in embedder.py
   c. embedder.py sends file content to Gemini API
   d. Gemini returns float[3072] vector
   e. indexer.py calls collection.upsert(id=path, embedding=vector, metadata={...})
4. ChromaDB persists to ~/.mac-memory/chromadb/ (SQLite + HNSW index)
```

### Search flow

```
1. User types query in Raycast
2. After 600ms debounce, search.tsx calls: python search.py --json --top 20 "query"
3. search.py calls embed_text("query") → Gemini API → vector Q
4. search.py calls collection.query(query_embeddings=[Q], n_results=20)
5. ChromaDB HNSW traversal: returns top-20 nearest neighbors + distances
6. search.py converts distances to similarity scores, returns JSON
7. search.tsx parses JSON → renders Grid with thumbnails and scores
```

---

## Technology Choices

| Component | Choice | Why |
|-----------|--------|-----|
| Embedding model | Gemini Embedding 2 | Only free multimodal model (same vector space for all types) |
| Vector DB | ChromaDB | Local-first, SQLite-backed, Python library, no server needed |
| Vector index | HNSW (via ChromaDB) | Approximate nearest-neighbor in O(log n), fast at 1K-100K vectors |
| Distance metric | Cosine | Direction matters more than magnitude for semantic similarity |
| PDF extraction | PyMuPDF (fitz) | Fast, handles complex layouts, extracts text and images |
| UI | Raycast extension | Native macOS integration, no Electron, fast to build |
| Language | Python 3.11+ | Best library support for Gemini SDK, ChromaDB, PyMuPDF |

---

## File Structure

```
~/Projects/mac-memory/
├── .env                  ← GEMINI_API_KEY=... (never commit)
├── .env.example          ← template
├── .gitignore            ← .env, .venv/, __pycache__/
├── requirements.txt      ← google-generativeai, chromadb, python-dotenv, Pillow, PyMuPDF
├── config.py             ← all settings
├── embedder.py           ← file → vector
├── indexer.py            ← filesystem walker + incremental index builder
├── search.py             ← query → ranked results (CLI + importable module)
└── raycast/
    ├── package.json
    ├── tsconfig.json
    └── src/
        └── search.tsx    ← Raycast Grid UI
```

---

## Setup Steps (for the builder)

1. Get Gemini API key from `aistudio.google.com`
2. `cd ~/Projects/mac-memory && python -m venv .venv && source .venv/bin/activate`
3. `pip install -r requirements.txt`
4. `cp .env.example .env` → paste API key
5. `python indexer.py ~/Desktop` → index Desktop to test
6. `python search.py "my resume"` → verify results
7. Install Raycast extension: `cd raycast && npm install && npm run dev`

---

## Error Handling Strategy

| Scenario | Handling |
|----------|----------|
| File too large (>10 MB) | Print skip message, continue to next file |
| Gemini API error | Print error message per file, continue (don't crash indexer) |
| PDF with no extractable text | Return None from embed_pdf, file skipped |
| File unreadable (permissions) | Caught by try/except, printed, skipped |
| No index found at search time | Print helpful error: "run indexer first", exit 1 |
| Empty query | embed_text returns None, search returns [] |

---

## Future Work (v2+)

- FSEvents watcher for automatic re-indexing on file change
- HEIC support via `pillow-heif`
- Video: extract keyframes and embed as images
- Similarity threshold filter (e.g., only show results above 60%)
- Multi-machine sync via iCloud/Dropbox for the ChromaDB directory

---

## Open Questions

1. **Model name:** Is `gemini-embedding-exp-03-07` the correct model ID for Gemini Embedding 2? May need to verify against current Google AI Studio docs.
2. **Audio support:** Does the Gemini API actually support audio `inline_data` for embeddings, or is it text-only? Need to verify.
3. **Rate limits:** Free-tier limits may require longer delays between API calls for large initial indexes. 100ms may not be enough.
4. **Raycast `execa` subprocess:** The Raycast extension calls a Python subprocess. On some macOS setups the PATH inside Raycast extensions doesn't include the venv. May need to hardcode the Python binary path.

