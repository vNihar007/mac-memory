<div align="center">

# 🕵️ Mac Memory

### Search your Mac the way you remember it — by meaning, not by filename.

You don't remember that a file was called `IMG_4471.png` or `final_v3_REAL.pdf`.
You remember *"the whiteboard photo from the architecture meeting"* or *"the lease I signed in March."*
Mac Memory lets you search for exactly that.

It reads your files — images, PDFs, notes, Word docs, slide decks — turns their **meaning** into vectors with Google's `gemini-embedding-2` model, and serves instant semantic search straight from a [Raycast](https://raycast.com) command. Everything runs locally on your machine.

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org)
[![FastAPI](https://img.shields.io/badge/API-FastAPI-009688.svg)](https://fastapi.tiangolo.com)
[![ChromaDB](https://img.shields.io/badge/vectors-ChromaDB-ff6b6b.svg)](https://www.trychroma.com)
[![Raycast](https://img.shields.io/badge/UI-Raycast-FF6363.svg)](https://raycast.com)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](#-license)

</div>

---

<!-- ───────────────────────────────────────────────────────────────────── -->
<!-- 📹 DEMO VIDEO — replace this block with your walkthrough.               -->
<!-- On GitHub you can drag-and-drop an .mp4/.mov directly into the README   -->
<!-- editor and it becomes a playable embed. Or link a thumbnail to YouTube: -->
<!--   [![Watch the demo](docs/demo-thumbnail.png)](https://youtu.be/VIDEO_ID) -->
<!-- ───────────────────────────────────────────────────────────────────── -->

> ### 🎬 Demo
>
> **▶ Video walkthrough coming soon — drop your `.mp4` here.**
>
> _(Placeholder: a 60-second clip showing a query like “the chart from the Q3 deck” surfacing the right slide instantly.)_

---

## Why this exists

Spotlight matches **filenames and exact keywords**. It can't find a photo of a sunset unless "sunset" is in the name, and it can't find the PDF where you discussed pricing unless you remember a literal phrase from it.

Mac Memory works differently. It builds a **semantic index** of your files' actual content, so a query and a file match when they *mean* the same thing — even with zero shared words.

Try queries like:

| You type… | It finds… |
|-----------|-----------|
| `the whiteboard photo from standup` | a `.png` screenshot of a whiteboard — no "whiteboard" in the filename |
| `my apartment lease` | the scanned rental contract PDF |
| `that error with the null pointer` | the screenshot of the stack trace |
| `Q3 revenue slides` | the right `.pptx`, matched on its slide text |
| `pasta recipe I saved` | the note, even if it's titled `Untitled 7.md` |
| `passport scan` | the document, matched on its OCR'd text |

---

## ✨ Features

- **Semantic search across file types** — images, PDFs, text/code, Word & PowerPoint, all in one index.
- **Multimodal understanding** — photos are matched on their *visual content*; documents on their *text*; scanned images on their *OCR'd* text.
- **Fully local** — your files never leave your Mac. Only short text/image payloads go to the embedding API; the index lives on disk.
- **Native Raycast UI** — search, pick folders, and watch live indexing progress without touching a terminal.
- **Smart query parsing** — "large screenshots from last week" automatically applies a type, size, and time filter.
- **Incremental & idempotent** — re-indexing only touches files that actually changed (modification-time aware).
- **Background daemon** — a local service keeps the index warm, so searches return with no cold-start.

---

## 🧠 How it works

Mac Memory is three layers: an **embedding pipeline**, a **local daemon**, and a **Raycast front end**.

```
┌─────────────────────────────┐       HTTP (localhost:8765)        ┌──────────────────────────────┐
│   Raycast extension (Node)   │ ───────────────────────────────────▶│   FastAPI daemon (Python)     │
│                              │                                     │                              │
│  • Search Files              │  GET  /search?q=…                   │  search_files()  ───┐        │
│  • Manage Indexed Folders    │  GET/POST/DELETE /folders           │  folder registry    │        │
│  • Live Indexing Progress    │  POST /index                        │  background indexer  │        │
│                              │  GET  /index/stream  (SSE)          │                     ▼        │
└─────────────────────────────┘                                     │   embedder ──▶ ChromaDB      │
                                                                     │   (gemini-embedding-2)       │
                                                                     └──────────────────────────────┘
```

### 1. Embeddings & vector search

Every file is converted into a high-dimensional **embedding** — a vector that captures meaning. Files with similar meaning land close together in vector space. A search query is embedded the same way, and Mac Memory returns the files whose vectors are nearest (by **cosine similarity**), using ChromaDB's HNSW index for fast approximate nearest-neighbor lookup.

- **Images** are embedded *visually* by the multimodal model — a beach photo and the query "ocean at sunset" land near each other with no text in common.
- **PDFs / Word / PowerPoint** are parsed to plain text (PyMuPDF, `python-docx`, `python-pptx`), then embedded as documents.
- **Text & code** files are embedded directly.

### 2. The cross-modal trick (`gemini-embedding-2` task prefixes)

This is the detail that makes search actually good. `gemini-embedding-2` is multimodal, but it does **not** take a `task_type` parameter — instead the retrieval task must be encoded as a **text prefix** on the content:

- **Documents** are embedded as `title: <name> | text: <content>`
- **Queries** are embedded as `task: search result | query: <your query>`

Without these prefixes the model returns generic embeddings, and cross-modal matching collapses — a text query for "dog" scores no higher against a dog photo than against an unrelated PDF. *With* them, the query and the image project into a shared retrieval space and the right result rises to the top. In our benchmark this took a "cat" query from **0.39 → 0.76** cosine similarity against the matching photo, with clean separation from distractors.

### 3. The local daemon (FastAPI)

A small FastAPI service binds to `127.0.0.1:8765` (loopback only — nothing on your network can reach it) and wraps the Python pipeline:

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | liveness check |
| `GET /search?q=&top_k=&type=` | semantic search, optional type filter |
| `GET/POST/DELETE /folders` | the folder registry + per-folder file counts |
| `POST /index` | start a background indexing job |
| `GET /index/stream` | **Server-Sent Events** stream of live progress |
| `GET /index/status` | current job snapshot |

Because the daemon holds the ChromaDB collection open, searches have **no per-query cold start**, and indexing runs in a background thread that streams progress to the UI.

### 4. Query intelligence

Before a query is embedded, a parser extracts structured filters and strips them from the text, so the semantic part stays clean:

- **Temporal** — "last week", "yesterday", "in March", "2025-12-01" → a modification-time range
- **Type** — "photos", "PDFs", "notes" → a type filter
- **Size** — "large files", "under 5mb" → a size filter
- **Negation** — "documents not pdf" → an exclusion
- **Expansion** — "meeting" also searches "conversation / discussion / call", widening recall

### 5. Enrichment

Images get extra context at index time: **OCR** (Tesseract) pulls any text inside the image, and **EXIF** metadata captures timestamps and GPS — so a screenshot full of text is findable by what it *says*, not just how it looks.

---

## 📂 Supported file types

| Category | Extensions | How it's indexed |
|----------|-----------|------------------|
| **Images** | `jpg` `jpeg` `png` `gif` `webp` `heic` `heif` | Visual embedding + OCR text + EXIF |
| **PDF** | `pdf` | Extracted text (first pages) |
| **Text / code** | `txt` `md` `py` `js` `ts` `json` `csv` `html` | Raw text |
| **Office** | `docx` `pptx` | Extracted text |
| **Audio** | `mp3` `wav` `m4a` `ogg` | 🚧 Planned (Whisper transcription) |

---

## 🚀 Getting started

### Prerequisites

- **macOS** (the daemon uses `launchd`; Raycast is Mac-only)
- **Python 3.12+** and **[uv](https://docs.astral.sh/uv/)**
- **[Tesseract](https://github.com/tesseract-ocr/tesseract)** for image OCR — `brew install tesseract`
- A **[Gemini API key](https://aistudio.google.com/apikey)** (free tier works)
- The **[Raycast](https://raycast.com)** app + Node.js (for the extension)

### 1. Clone & install

```bash
git clone https://github.com/vNihar007/mac-memory.git
cd mac-memory
uv sync
brew install tesseract
```

### 2. Add your API key

```bash
echo "GEMINI_API_KEY=your_key_here" > .env
```

### 3. Start the daemon

The one-time installer wires up a `launchd` agent so the daemon starts on login and restarts if it crashes:

```bash
./setup.sh
```

Or, while developing (auto-reloads on code changes):

```bash
cd src && MACMEM_DEV=1 uv run python -m mac_memory.server
```

Verify it's up:

```bash
curl -s localhost:8765/health    # → {"status":"ok"}
```

### 4. Load the Raycast extension

```bash
cd raycast
npm install
ray develop
```

The **Search Files** and **Manage Indexed Folders** commands now appear in Raycast.

---

## 📖 Usage

### Index your folders

1. Open **Manage Indexed Folders** in Raycast.
2. Hit **Add Folder…** and pick any directories (e.g. `~/Documents`, `~/Desktop/screenshots`).
3. Select a folder → **Re-index This Folder**. A live progress view shows the ETA and current file.

> Indexing calls the embedding API once per file with a small rate-limit pause, so the first run of a large folder takes a few minutes. After that, re-indexing only re-processes files that changed.

### Search

Open **Search Files** and type naturally:

- `architecture diagram` → the right image, even if it's named `Screenshot 2025-11-02.png`
- `invoice from the landlord` → the scanned PDF
- `large screenshots from last week` → applies type + size + time filters automatically

Results are grouped by relevance tier (strong / possible / weak), with a similarity meter and a detail panel that previews images and shows metadata. Use the type dropdown to filter to Images, PDFs, Text, or Office files.

---

## 🗂 Project structure

```
mac-memory/
├── src/mac_memory/
│   ├── configure.py        # paths, supported extensions, daemon config
│   ├── embedder.py         # gemini-embedding-2 wrappers (text/image/pdf/office)
│   ├── enricher.py         # OCR + EXIF extraction for images
│   ├── indexer.py          # walk folders, embed, upsert into ChromaDB
│   ├── query_processor.py  # temporal/type/size/negation parsing + expansion
│   ├── search.py           # query → embed → ChromaDB → ranked results
│   ├── registry.py         # persistent folder list (~/.mac-memory/folders.json)
│   ├── jobs.py             # background indexing job + progress state
│   └── server.py           # FastAPI daemon (search / folders / index / SSE)
├── raycast/
│   └── src/
│       ├── api.ts          # typed HTTP client + self-healing daemon check
│       ├── search.tsx      # Search Files command
│       ├── manage-folders.tsx  # folder management UI
│       └── progress-view.tsx   # live indexing progress + ETA
├── setup.sh                # one-time launchd installer
└── pyproject.toml
```

---

## ⚙️ Configuration

Everything lives in `src/mac_memory/configure.py`:

- `SUPPORTED_EXTENSIONS` — which file types get indexed
- `CHROMA_PATH` — where the vector DB is stored
- `HOST` / `PORT` — daemon bind address (default `127.0.0.1:8765`)
- `SKIP_DIRS` — directories to ignore (`.git`, `node_modules`, `__pycache__`)

The folder registry is stored at `~/.mac-memory/folders.json`; daemon logs go to `~/.mac-memory/daemon.log`.

---

## 🛣 Roadmap

- 🎙 **Audio** — transcribe `mp3`/`m4a` with Whisper, then embed the transcript
- 🔁 **Auto-indexing** — file-system watcher so new files index without a manual trigger
- 🧩 **More formats** — `xlsx`, `.pages`, `.key`, plain `.doc`
- 💬 **Answer mode** — synthesize an answer from matched files, not just a file list
- 📦 **One-click install** — package the daemon so no local Python setup is needed

---

## 🧰 Tech stack

| Layer | Tools |
|-------|-------|
| Embeddings | Google `gemini-embedding-2` (multimodal) |
| Vector store | ChromaDB (cosine, HNSW) |
| Extraction | PyMuPDF · `python-docx` · `python-pptx` · Tesseract (OCR) · `exifread` |
| Daemon | FastAPI · Uvicorn · `sse-starlette` |
| Front end | Raycast (`@raycast/api`, React + TypeScript) |
| Tooling | `uv` · `launchd` |

---

## 📄 License

[MIT](LICENSE) © Varun Nihar

<div align="center">
<sub>Built because filenames are a terrible way to remember files.</sub>
</div>
