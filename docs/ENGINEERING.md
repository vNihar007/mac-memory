# Mac Memory — Complete Engineering Reference

**Author:** Varun Nihar  
**Date:** 2026-05-19  
**Version:** 2.0 — Enriched Architecture (v1 built, v2/v3 designed)

---

## Table of Contents

1. [Project Summary](#1-project-summary)
2. [Honest Moat Analysis](#2-honest-moat-analysis)
3. [Full System Architecture (Target)](#3-full-system-architecture-target)
4. [What Is Built vs. Planned](#4-what-is-built-vs-planned)
5. [Component Deep Dives](#5-component-deep-dives)
   - [Enrichment Layer (v2)](#51-enrichment-layer-v2---the-real-moat)
   - [config.py (v1)](#52-configpy)
   - [embedder.py (v1)](#53-embedderpy)
   - [indexer.py (v1)](#54-indexerpy)
   - [search.py + Query Intelligence (v2)](#55-searchpy--query-intelligence-layer-v2)
   - [Answer Layer (v3)](#56-answer-layer-v3---rag-on-top-of-retrieval)
   - [Raycast Extension (v1)](#57-raycast-extension)
6. [Data Schemas](#6-data-schemas)
7. [API Contracts](#7-api-contracts)
8. [Performance Model](#8-performance-model)
9. [Known Bugs & Required Fixes (v1)](#9-known-bugs--required-fixes-v1)
10. [Test Strategy](#10-test-strategy)
11. [Deployment & Distribution Guide](#11-deployment--distribution-guide)
12. [Resume Worthiness Assessment](#12-resume-worthiness-assessment)

---

## 1. Project Summary

Mac Memory is a personal semantic memory engine that runs entirely on your Mac. It replaces keyword-based Spotlight with meaning-based retrieval — but the real goal is to go further than search: to answer questions about your own files the way a human assistant with perfect memory would.

**Core premise:** Google's Gemini Embedding 2 maps text, images, PDFs, and audio into the same 3072-dimensional vector space. A text query "receipt from the coffee shop" lands geometrically close to the JPEG of that receipt — even with no text labels on the image. But raw vector similarity is just the engine. The car around it is:

1. **Enrichment before embedding** — extract EXIF, OCR text, Whisper transcriptions, and calendar context before sending to Gemini, so the vectors encode richer meaning
2. **Query intelligence after retrieval** — parse temporal hints, expand queries, run hybrid BM25+cosine search, re-rank with a cross-encoder
3. **An answer layer** — pass retrieved files through a local LLM (Ollama) to return synthesized answers, not just a file list

**Why the distinction matters:** The embedding API is a commodity — Google, OpenAI, Cohere, and Voyage all have one. Gemini Embedding 2 is differentiated today because it's the only free multimodal one. In 12 months there will be three more. The enrichment, query intelligence, and answer layers are what you own. The API cannot give them to you.

---

## 2. Honest Moat Analysis

```
WHAT V1 GIVES YOU (no real moat):

  File ──► [Gemini API does everything] ──► Vector ──► ChromaDB ──► Top-K files
            ↑                                                         ↑
       Google's moat                                          table stakes

WHAT BUILDS A MOAT (v2/v3 target):

  File + context
    ├── EXIF (GPS, timestamp, camera)          ← YOU own this
    ├── OCR (Tesseract, on-device)             ← YOU own this
    ├── Whisper transcript (on-device)         ← YOU own this
    ├── Calendar/messages context              ← YOU own this
    └── Screen context (app, URL at capture)  ← YOU own this
          │
          ▼
    Gemini Embed (the engine, not the moat)
          │
          ▼
      ChromaDB
          │
    Query layer                                ← YOU own this
    ├── Temporal parse ("last week" → mtime filter)
    ├── Type inference ("photo of" → image filter)
    ├── Query expansion (3 paraphrases → merge)
    ├── Hybrid BM25 + cosine re-ranking
    └── Cross-encoder re-ranker (local model)
          │
    Answer layer                               ← YOU own this
    └── Ollama + llama3.2 (local, offline)
        → synthesized answer + source files
```

**The ownership map:**

| Layer | Owner | Moat strength |
|-------|-------|--------------|
| Embedding model | Google | None — commodity API |
| Vector storage (ChromaDB) | ChromaDB | None — pip install |
| Raycast UI shell | Thin wrapper | Weak |
| File enrichment (EXIF/OCR/Whisper) | **You** | Strong |
| Query intelligence (temporal/expand/re-rank) | **You** | Strong |
| Context graph (calendar + files + messages) | **You** | Very strong |
| Answer layer (local RAG via Ollama) | **You** | Very strong |

The API is the engine. You're building the navigation system, the driver assistance, and the memory of everywhere you've ever been.

---

## 3. Full System Architecture (Target)

### 3.1 Enriched Indexing Pipeline

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    ENRICHED INDEXING PIPELINE (v2 target)                │
│                                                                          │
│  Files on disk                                                           │
│  ┌──────────┐                                                           │
│  │ photo.jpg│──┐                                                        │
│  │ doc.pdf  │  │   enricher.py (v2)          embedder.py               │
│  │ note.txt │  │   ┌───────────────────┐     ┌──────────────────┐      │
│  │ memo.m4a │  └──▶│ EXIF extractor    │     │                  │      │
│  └──────────┘      │ OCR (Tesseract)   ├────▶│  Gemini Embed    │──┐   │
│                    │ Whisper (audio)   │     │  API (cloud)     │  │   │
│  Context sources   │ PDF text (fitz)   │     │                  │  │   │
│  ┌──────────┐      │ Screen meta       │     │  float[3072]     │  │   │
│  │ Calendar │──┐   └───────────────────┘     └──────────────────┘  │   │
│  │ Messages │  │                                                    │   │
│  │ Browser  │──┴──▶ enriched_metadata{}                            │   │
│  └──────────┘             │                                        │   │
│                           │                                        │   │
│                           ▼                                        ▼   │
│                    ┌────────────────────────────────────────────────┐  │
│                    │              ChromaDB                          │  │
│                    │  ┌──────────────┐    ┌──────────────────────┐ │  │
│                    │  │  HNSW graph  │    │  SQLite              │ │  │
│                    │  │  float[3072] │    │  enriched metadata   │ │  │
│                    │  │  (ANN index) │    │  + BM25 FTS index    │ │  │
│                    │  └──────────────┘    └──────────────────────┘ │  │
│                    └────────────────────────────────────────────────┘  │
│                                    ~/.mac-memory/                       │
└──────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Enriched Search + Answer Pipeline

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    ENRICHED SEARCH PIPELINE (v2/v3 target)               │
│                                                                          │
│  User: "coffee meeting last week"                                        │
│          │                                                               │
│          ▼                                                               │
│   query_processor.py (v2)                                               │
│   ┌────────────────────────────────────────────────────────┐            │
│   │  1. Temporal parse:  "last week" → mtime > May 12      │            │
│   │  2. Type inference:  "meeting" → boost pdf/text/audio  │            │
│   │  3. Query expansion: generate 3 paraphrases            │            │
│   │     • "coffee meeting last week"                       │            │
│   │     • "cafe business discussion recently"              │            │
│   │     • "espresso work conversation this month"          │            │
│   └─────────────────┬──────────────────────────────────────┘            │
│                     │ 3 expanded queries + metadata filters              │
│                     ▼                                                    │
│   ┌────────────────────────────────────────────────────────┐            │
│   │  Gemini Embed API  →  3 × float[3072] query vectors    │            │
│   └─────────────────┬──────────────────────────────────────┘            │
│                     │                                                    │
│          ┌──────────┴──────────┐                                        │
│          ▼                     ▼                                        │
│   ChromaDB HNSW ANN     SQLite FTS5 BM25                               │
│   (semantic search)     (keyword search)                                │
│          │                     │                                        │
│          └──────────┬──────────┘                                        │
│                     ▼                                                    │
│   RRF Fusion (Reciprocal Rank Fusion — merge ranked lists)              │
│                     │                                                    │
│                     ▼ top-50 candidates                                 │
│   ┌────────────────────────────────────────────────────────┐            │
│   │  Cross-encoder re-ranker (local, tiny model)           │            │
│   │  Input: (query, file_context) pairs                    │            │
│   │  Output: relevance scores → re-ranked top-20           │            │
│   └─────────────────┬──────────────────────────────────────┘            │
│                     │                                                    │
│          ┌──────────┴──────────────────────────────────────┐            │
│          │ SEARCH mode              │ ANSWER mode (v3)      │           │
│          ▼                          ▼                       │           │
│   Raycast Grid              Ollama + llama3.2 (local)       │           │
│   ranked file thumbnails    reads top-5 file contents       │           │
│   + similarity scores       generates synthesized answer    │           │
│                             + cites source files            │           │
└──────────────────────────────────────────────────────────────────────────┘
```

### 3.3 Context Graph (v3)

```
Each file is a node. Edges are temporal and contextual proximity.

  photo.jpg (taken 2:23 PM, May 12)
       │
       ├─[calendar]──▶ "Coffee with Rahul" event (2:00 PM, May 12)
       │                    │
       │                    ├─[attendees]──▶ "Rahul" person node
       │                    └─[location]───▶ "Third Wave Coffee, Indiranagar"
       │
       ├─[messages]──▶ Rahul texted "blue building near Indiranagar" (1:45 PM)
       │
       └─[browser]───▶ Searched "Third Wave Coffee menu" (1:50 PM)

ChromaDB metadata for photo.jpg:
{
  "path": "/Users/varun/Desktop/photo.jpg",
  "type": "image",
  "mtime": 1747052580.0,
  "ocr_text": "Menu: Cappuccino ₹180",
  "exif_gps": "12.9716° N, 77.5946° E",
  "exif_timestamp": "2026-05-12T14:23:00",
  "people": ["Rahul"],
  "calendar_event": "Coffee with Rahul",
  "location": "Third Wave Coffee, Indiranagar"
}

Query: "coffee with Rahul" now finds:
  → photo.jpg (image, cosine match)
  → The calendar event reference (metadata match)
  → Any messages mentioning Rahul around that time
```

---

## 4. What Is Built vs. Planned

| Component | Status | Notes |
|-----------|--------|-------|
| `config.py` — settings | ✅ Built (v1) | Missing API key validation |
| `embedder.py` — raw file → vector | ✅ Built (v1) | Audio unverified; no enrichment |
| `indexer.py` — filesystem walker | ✅ Built (v1) | Rate limit bug; N DB reads |
| `search.py` — cosine top-K | ✅ Built (v1) | No temporal parse, no expansion |
| `raycast/search.tsx` — Grid UI | ✅ Built (v1) | Hardcoded Python path |
| `enricher.py` — EXIF/OCR/Whisper | 🔲 Planned (v2) | Core moat layer |
| `query_processor.py` — temporal + expand | 🔲 Planned (v2) | Core moat layer |
| Hybrid BM25 + cosine search | 🔲 Planned (v2) | Needs SQLite FTS5 index |
| Cross-encoder re-ranker | 🔲 Planned (v2) | Local model, on-device |
| Context graph (calendar/messages) | 🔲 Planned (v3) | Biggest long-term moat |
| Answer layer (Ollama RAG) | 🔲 Planned (v3) | Requires Ollama installed |

---

## 5. Component Deep Dives

### 5.1 Enrichment Layer (v2) — The Real Moat

**File:** `enricher.py` (to be built)

**Role:** Before calling the Gemini API, extract everything knowable about a file from local tools. The richer the input, the richer the vector.

**Why this matters:** Gemini Embedding 2 only sees what you give it. A raw JPEG gives it pixels. An enriched JPEG gives it pixels + location + time + people + any text in the image. The resulting vectors are dramatically more discriminative.

#### 5.1.1 Image Enrichment

```python
import exifread
import pytesseract
from PIL import Image

def enrich_image(path: Path) -> dict:
    meta = {}

    # EXIF: GPS, timestamp, camera model
    with open(path, "rb") as f:
        tags = exifread.process_file(f, stop_tag="GPS GPSLatitude")
    meta["exif_timestamp"] = str(tags.get("EXIF DateTimeOriginal", ""))
    meta["exif_gps"] = _parse_gps(tags)   # → "12.97°N, 77.59°E"

    # OCR: any text visible in the image (receipts, whiteboards, signs)
    img = Image.open(path)
    ocr_text = pytesseract.image_to_string(img).strip()
    if ocr_text:
        meta["ocr_text"] = ocr_text[:2000]   # cap at 2000 chars

    return meta
```

**What this unlocks:**
- A receipt photo with "Starbucks ₹340" in OCR text becomes findable by "coffee receipt" AND "Starbucks" AND "₹340"
- A whiteboard photo becomes findable by any equation or text written on it
- A photo taken at a specific GPS coordinate becomes findable by location name (after reverse geocoding)

#### 5.1.2 Audio Enrichment via Whisper

```python
# Instead of _embed_audio() with unverified API support:
import whisper   # openai-whisper, runs on-device via whisper.cpp

def enrich_audio(path: Path) -> dict:
    model = whisper.load_model("tiny")   # 39MB, runs in real-time on Apple Silicon
    result = model.transcribe(str(path))
    transcript = result["text"].strip()
    return {
        "transcript": transcript[:8000],
        "language": result.get("language", "en"),
    }

# Then embed the transcript as text — no Gemini audio API needed
# embed_text(transcript) → valid 3072-dim vector
```

**Why this beats `_embed_audio`:** The Gemini embedding API's audio support via `inline_data` is undocumented and unverified. Whisper is battle-tested, runs on-device, produces a searchable text transcript, and gives you the actual words — so "what did I say about the startup idea" now returns voice memos where that phrase appears.

#### 5.1.3 PDF Enrichment

```python
def enrich_pdf(path: Path) -> dict:
    import fitz
    doc = fitz.open(str(path))
    
    pages_text = []
    for i, page in enumerate(doc):
        if i >= 10: break
        text = page.get_text()
        if not text.strip():
            # Scanned page — run OCR on the rendered image
            pix = page.get_pixmap()
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            text = pytesseract.image_to_string(img)
        pages_text.append(text)
    
    return {
        "pdf_text": "\n".join(pages_text)[:8000],
        "page_count": len(doc),
        "title": doc.metadata.get("title", ""),
        "author": doc.metadata.get("author", ""),
    }
```

**What this unlocks:** Scanned PDFs (insurance docs, signed contracts, bank statements) that previously returned `None` now get OCR'd and become searchable.

#### 5.1.4 The Enriched Embedding Call

```python
def embed_file_enriched(path: Path) -> tuple[list[float] | None, dict]:
    """
    Returns (embedding_vector, enriched_metadata).
    The vector is built from enriched content; metadata is stored in ChromaDB.
    """
    suffix = path.suffix.lower()
    content_for_embedding = ""
    extra_meta = {}

    if suffix in config.SUPPORTED_EXTENSIONS["image"]:
        extra_meta = enrich_image(path)
        ocr = extra_meta.get("ocr_text", "")
        # Build a rich text description for embedding
        content_for_embedding = f"Image file: {path.name}. {ocr}"
        if extra_meta.get("exif_timestamp"):
            content_for_embedding += f" Taken at: {extra_meta['exif_timestamp']}."
        # Also pass the raw image to Gemini for visual understanding
        visual_vector = _embed_image_raw(path)
        text_vector = embed_text(content_for_embedding)
        # Average the two vectors — captures both visual and textual meaning
        vector = _average_vectors([visual_vector, text_vector])

    elif suffix in config.SUPPORTED_EXTENSIONS["audio"]:
        extra_meta = enrich_audio(path)
        transcript = extra_meta.get("transcript", "")
        vector = embed_text(transcript) if transcript else None

    # ... etc for pdf, text

    return vector, extra_meta
```

**The averaging trick:** For images with OCR text, averaging the visual embedding (Gemini image → vector) with the text embedding (OCR text → vector) produces a vector that responds to both visual queries ("whiteboard diagram") and text queries ("the equation on the whiteboard"). This is not documented anywhere — it's a technique you derived from understanding the math.

---

### 5.2 config.py

**Role:** Single source of truth for all settings. No hardcoded values anywhere else.

**Current state (v1):**
```python
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
EMBEDDING_MODEL = "gemini-embedding-exp-03-07"
CHROMA_PATH = Path.home() / ".mac-memory" / "chromadb"
COLLECTION_NAME = "mac_files"
SUPPORTED_EXTENSIONS = {
    "image": {".jpg", ".jpeg", ".png", ".gif", ".webp"},
    "pdf":   {".pdf"},
    "text":  {".txt", ".md", ".py", ".js", ".ts", ".json", ".csv", ".html"},
    "audio": {".mp3", ".wav", ".m4a", ".ogg"},
}
INDEX_PATHS = [Desktop, Documents, Downloads]
SKIP_DIRS = {".git", "node_modules", "__pycache__", ...}
```

**Required fix — API key validation:**
```python
if not GEMINI_API_KEY:
    raise ValueError(
        "GEMINI_API_KEY is not set.\n"
        "1. Go to aistudio.google.com → Get API key\n"
        "2. cp .env.example .env\n"
        "3. Paste your key into .env"
    )
```

Without this, `embedder.py` receives `None`, makes authenticated requests with `None`, and produces cryptic `401` errors instead of a clear setup instruction.

**v2 additions to config.py:**
```python
# Enrichment settings
WHISPER_MODEL = "tiny"          # tiny=39MB, base=74MB, small=244MB
OCR_ENABLED = True              # requires: pip install pytesseract
EXIF_ENABLED = True             # requires: pip install exifread
MAX_OCR_CHARS = 2000
MAX_TRANSCRIPT_CHARS = 8000

# Query intelligence settings
QUERY_EXPANSION_COUNT = 3       # how many paraphrases to generate
TEMPORAL_LOOKBACK_DAYS = 7      # default window for "recently"
HYBRID_ALPHA = 0.7              # weight: 0.7 semantic + 0.3 BM25

# Answer layer
OLLAMA_MODEL = "llama3.2"       # must be pulled: ollama pull llama3.2
OLLAMA_ENABLED = False          # off by default — requires Ollama installed
```

---

### 5.3 embedder.py

**Role:** Takes a `Path`, returns a `list[float]` (3072 dimensions) or `None`.

**How multimodal embedding works — the key insight:**

The Gemini Embedding 2 API returns a `float[3072]` for every modality. This is not a coincidence — the model was trained with a contrastive objective: images of coffee shops and text descriptions of coffee shops were pulled close together in the latent space. The geometric result: `cosine_similarity(text_vector("coffee shop"), image_vector(coffee_shop_jpeg)) > 0.7`.

```
Text input path:
  "my resume" ──► genai.embed_content(model, content=str) ──► float[3072]

Image input path:
  photo.jpg ──► base64 encode ──► genai.embed_content(model, content={"parts": [{"inline_data": {...}}]}) ──► float[3072]

Same vector space — cosine distance between them is semantically meaningful.
```

**Size limit:** `MAX_BYTES = 10 MB`. Files over this limit are skipped. This is a Gemini free-tier API constraint.

**PDF extraction:**
```
PDF → fitz.open() → text per page → first 10 pages → truncate at 8,000 chars → embed_text()
```
PDFs are embedded as text. Scanned PDFs (no text layer) return `None` in v1, get OCR'd in v2.

**Audio (v1 status):** `_embed_audio` is implemented but audio `inline_data` support is unverified in the Gemini embedding endpoint. In v2, audio is handled via Whisper transcription → text embedding — no Gemini audio API needed.

---

### 5.4 indexer.py

**Role:** Filesystem walker that builds the ChromaDB index incrementally.

**ChromaDB initialization:**
```python
client = chromadb.PersistentClient(path=str(config.CHROMA_PATH))
collection = client.get_or_create_collection(
    name=config.COLLECTION_NAME,
    metadata={"hnsw:space": "cosine"},
)
```

`hnsw:space: cosine` must be set at collection creation time — it cannot be changed without rebuilding the entire index. Cosine distance is: `distance = 1 - cosine_similarity`, so smaller distance = more similar.

**Incremental indexing:**
```
For each file:
  1. mtime = path.stat().st_mtime      (float: Unix timestamp)
  2. already_indexed(path, mtime)
       → collection.get(ids=[str(path)], include=["metadatas"])
       → if stored mtime == current mtime: skip
  3. embed_file(path) → vector
  4. collection.upsert(id=str(path), embedding=vector, metadata={...})
```

**Why upsert, not insert:** The file's full absolute path is the document ID. `upsert` overwrites if the ID exists. Re-indexing is idempotent — no duplicate vectors, no stale entries.

**Performance bug — N sequential DB reads:**
```python
# Current: 1 collection.get() call per file = N disk reads
def already_indexed(path, mtime):
    results = collection.get(ids=[str(path)], include=["metadatas"])
    ...

# Fix: pre-fetch all stored mtimes in ONE call at walk start
def build_indexed_map() -> dict[str, float]:
    results = collection.get(include=["metadatas"])
    return {
        results["ids"][i]: results["metadatas"][i].get("mtime", 0.0)
        for i in range(len(results["ids"]))
    }
# Then: already_indexed_map = build_indexed_map()
# Check: already_indexed_map.get(str(path), 0.0) == mtime
```

At 10,000 files, this is a 10,000x reduction in DB calls. ChromaDB calls are synchronous SQLite reads — this matters.

**Rate limit (critical bug):**
```python
time.sleep(0.1)   # BUG: 600 RPM — 10x the free tier limit of 60 RPM
time.sleep(1.5)   # FIX:  40 RPM — safely under 60 RPM
```

---

### 5.5 search.py + Query Intelligence Layer (v2)

**Current (v1) — thin cosine search:**
```python
def search_files(query, top_k=8, file_type=None):
    vector = embedder.embed_text(query)     # one embedding
    results = collection.query(
        query_embeddings=[vector],
        n_results=top_k,
        where={"type": file_type} if file_type else None,
        include=["metadatas", "distances"],
    )
    similarity = 1.0 - distance
    return results
```

**v2 — enriched query pipeline:**

```python
# query_processor.py (v2)

import re
from datetime import datetime, timedelta

TEMPORAL_PATTERNS = {
    r"last week":       lambda: ("mtime", "$gte", (datetime.now() - timedelta(days=7)).timestamp()),
    r"last month":      lambda: ("mtime", "$gte", (datetime.now() - timedelta(days=30)).timestamp()),
    r"yesterday":       lambda: ("mtime", "$gte", (datetime.now() - timedelta(days=1)).timestamp()),
    r"this year":       lambda: ("mtime", "$gte", datetime(datetime.now().year, 1, 1).timestamp()),
}

TYPE_HINTS = {
    r"photo|picture|image|screenshot": "image",
    r"document|report|pdf|file":       "pdf",
    r"note|memo|text|message":         "text",
    r"voice|audio|recording|call":     "audio",
}

def process_query(raw_query: str) -> dict:
    where_filter = {}
    
    # Extract temporal constraints
    for pattern, filter_fn in TEMPORAL_PATTERNS.items():
        if re.search(pattern, raw_query, re.IGNORECASE):
            field, op, val = filter_fn()
            where_filter[field] = {op: val}
            break
    
    # Infer file type hint
    inferred_type = None
    for pattern, ftype in TYPE_HINTS.items():
        if re.search(pattern, raw_query, re.IGNORECASE):
            inferred_type = ftype
            break
    if inferred_type:
        where_filter["type"] = inferred_type
    
    return {
        "clean_query": raw_query,
        "where_filter": where_filter if where_filter else None,
    }


def expand_query(query: str) -> list[str]:
    """
    Generate paraphrases for multi-vector search.
    In v2 this calls a local LLM (Ollama) or uses a fixed template.
    In v2.1 this calls Gemini's generative API (not embedding) for expansion.
    """
    # Template-based (no API call, instant):
    expansions = [query]
    if "meeting" in query.lower():
        expansions.append(query.replace("meeting", "conversation discussion"))
    if "photo" in query.lower() or "picture" in query.lower():
        expansions.append(query.replace("photo", "image screenshot").replace("picture", "image"))
    return expansions[:3]


def search_files_v2(query: str, top_k: int = 20) -> list[SearchResult]:
    # Step 1: Parse query
    parsed = process_query(query)
    queries = expand_query(parsed["clean_query"])
    
    # Step 2: Embed all expanded queries
    vectors = [embedder.embed_text(q) for q in queries]
    vectors = [v for v in vectors if v is not None]
    
    # Step 3: Multi-vector semantic search (union of results)
    all_semantic = {}
    for vector in vectors:
        results = collection.query(
            query_embeddings=[vector],
            n_results=50,                          # fetch more for re-ranking
            where=parsed["where_filter"],
            include=["metadatas", "distances"],
        )
        for meta, dist in zip(results["metadatas"][0], results["distances"][0]):
            path = meta["path"]
            current_best = all_semantic.get(path, (meta, 2.0))
            if dist < current_best[1]:             # keep closest match
                all_semantic[path] = (meta, dist)
    
    # Step 4: RRF fusion with BM25 (if BM25 index exists)
    fused = _rrf_fusion(
        semantic_results=list(all_semantic.items()),
        bm25_results=_bm25_search(query, top_n=50),
        alpha=config.HYBRID_ALPHA,                 # 0.7 semantic, 0.3 BM25
    )
    
    # Step 5: Re-rank with cross-encoder (top-50 candidates → top-20 final)
    reranked = _cross_encoder_rerank(query, fused[:50])
    
    return [
        SearchResult(
            path=meta["path"],
            name=meta["name"],
            file_type=meta["type"],
            similarity=round(1.0 - dist, 4),
            size=meta.get("size", 0),
        )
        for meta, dist in reranked[:top_k]
    ]
```

**How the cross-encoder re-ranker works:**
```
Bi-encoder (what Gemini does):   query → vector, file → vector → cosine score
  Fast: O(1) per comparison, vectors precomputed
  Limitation: query and file encoded independently, no interaction

Cross-encoder (re-ranker):       (query, file_context) → single relevance score
  Slow: O(N) encoder calls at query time
  Strength: joint encoding captures interaction between query and content
  Used only on top-50 candidates to keep latency manageable
```

In practice: use `cross-encoder/ms-marco-TinyBERT-L-2-v2` via `sentence-transformers`. It's 67MB, runs in ~50ms for 50 candidates on Apple Silicon.

---

### 5.6 Answer Layer (v3) — RAG on Top of Retrieval

**Role:** Instead of returning a file list, return a synthesized answer with citations.

```python
# answer.py (v3)

import ollama   # pip install ollama (requires Ollama installed locally)

def answer_query(query: str, top_k: int = 5) -> dict:
    # Step 1: Retrieve top files (same as search_files_v2)
    results = search_files_v2(query, top_k=top_k)
    
    # Step 2: Extract text content from each result
    contexts = []
    for result in results:
        path = Path(result.path)
        if result.file_type == "text":
            text = path.read_text(errors="ignore")[:3000]
        elif result.file_type == "pdf":
            text = enricher.enrich_pdf(path)["pdf_text"][:3000]
        elif result.file_type == "audio":
            text = enricher.enrich_audio(path).get("transcript", "")[:3000]
        elif result.file_type == "image":
            text = enricher.enrich_image(path).get("ocr_text", "")[:1000]
        contexts.append(f"[{result.name}]:\n{text}")
    
    # Step 3: Pass to local LLM (Ollama — runs 100% offline)
    context_block = "\n\n---\n\n".join(contexts)
    prompt = f"""You are a personal assistant with access to the user's files.
Answer the question based ONLY on the provided file contents.
If the answer isn't in the files, say so.

Files:
{context_block}

Question: {query}

Answer (cite which file(s) your answer comes from):"""

    response = ollama.chat(
        model=config.OLLAMA_MODEL,   # "llama3.2" — 2GB, runs on Apple Silicon
        messages=[{"role": "user", "content": prompt}],
    )
    
    return {
        "answer": response["message"]["content"],
        "sources": [r.path for r in results],
    }
```

**What this looks like in Raycast:**
```
Query: "what did I decide about the startup idea?"

Answer: Based on your voice note from May 10 (startup_brainstorm.m4a) and
the whiteboard photo from May 12, you decided to focus on B2B customers first.
You also noted that the embedding approach was "technically validated" and
wrote "need to find 3 design partners by June."

Sources:
  → startup_brainstorm.m4a (87% match)
  → whiteboard_may12.jpg (79% match)
  → meeting_notes_rahul.pdf (71% match)
```

**Why Ollama specifically:** Runs 100% offline. No API key for the answer layer. No data leaves your machine. `llama3.2` (3B params) fits in 2GB RAM and runs fast on Apple Silicon via Metal.

---

### 5.7 Raycast Extension

**File:** `raycast/src/search.tsx`

**Architecture:**
```
User types → 600ms debounce → execa(python, search.py --json) → JSON → Grid
```

**Grid rendering:**
```tsx
content={
  result.file_type === "image"
    ? { fileIcon: result.path }    // actual macOS thumbnail — real preview
    : TYPE_ICONS[result.file_type] // Document / TextCursor / Music icon
}
```

`{ fileIcon: result.path }` is a Raycast API feature that renders the file's native macOS Quick Look thumbnail. A JPEG shows its preview. A PDF shows its first page. This is zero-effort visual search.

**Known issue — hardcoded Python path:**
```typescript
// BREAKS for pyenv, conda, homebrew, or non-standard project location
const PYTHON = `${process.env.HOME}/Projects/mac-memory/.venv/bin/python`;

// FIX: write path during setup, read it dynamically
// setup.sh writes: echo $(which python) > ~/Projects/mac-memory/raycast/.python-path
import { readFileSync } from "fs";
const PYTHON = readFileSync(`${process.env.HOME}/Projects/mac-memory/raycast/.python-path`, "utf8").trim();
```

---

## 6. Data Schemas

### 6.1 ChromaDB Collection Schema

**Collection:** `mac_files` | **Distance:** Cosine | **Dimensions:** 3072

| Field | Type | Notes |
|-------|------|-------|
| `id` | `string` | Absolute file path — document ID, deduplication key |
| `embedding` | `float[3072]` | Semantic vector from Gemini Embedding 2 |
| `documents` | `string` | Filename (for ChromaDB internal FTS, mostly unused in v1) |
| `metadata.path` | `string` | Absolute path (redundant with ID, easier to retrieve) |
| `metadata.name` | `string` | Filename for display |
| `metadata.type` | `string` | `image` \| `pdf` \| `text` \| `audio` |
| `metadata.mtime` | `float` | Unix timestamp of last modification |
| `metadata.size` | `int` | File size in bytes |
| `metadata.ocr_text` | `string` | (v2) OCR-extracted text from images |
| `metadata.transcript` | `string` | (v2) Whisper transcript from audio |
| `metadata.exif_timestamp` | `string` | (v2) Photo capture time from EXIF |
| `metadata.exif_gps` | `string` | (v2) GPS coordinates from EXIF |
| `metadata.calendar_event` | `string` | (v3) Calendar event near file creation time |
| `metadata.people` | `string` | (v3) People detected/mentioned in context |

### 6.2 SearchResult Dataclass

```python
@dataclass
class SearchResult:
    path: str         # absolute file path
    name: str         # filename
    file_type: str    # "image" | "pdf" | "text" | "audio"
    similarity: float # 0.0 (unrelated) to 1.0 (identical)
    size: int         # file size in bytes
```

### 6.3 JSON Wire Format (search.py → Raycast)

```json
[
  {
    "path": "/Users/varun/Documents/receipt.pdf",
    "name": "receipt.pdf",
    "file_type": "pdf",
    "similarity": 0.8742,
    "size": 156032
  }
]
```

### 6.4 Answer Response Schema (v3)

```json
{
  "answer": "Based on your voice note from May 10...",
  "sources": [
    "/Users/varun/voice_note_may10.m4a",
    "/Users/varun/whiteboard_may12.jpg"
  ]
}
```

---

## 7. API Contracts

### 7.1 Gemini Embedding API

```python
# Text
result = genai.embed_content(model="gemini-embedding-exp-03-07", content="text")
# result["embedding"] → list[float], len=3072

# Image / Audio (multimodal)
result = genai.embed_content(
    model="gemini-embedding-exp-03-07",
    content={"parts": [{"inline_data": {"mime_type": "image/jpeg", "data": base64_str}}]},
)
```

**Free-tier limits:** 60 RPM, ~1,500 RPD (verify at aistudio.google.com)  
**Required sleep between calls:** `time.sleep(1.5)` = 40 RPM  

### 7.2 ChromaDB API

```python
# Write (idempotent)
collection.upsert(ids, embeddings, documents, metadatas)

# Read by ID
collection.get(ids=["path"], include=["metadatas"])

# Semantic search
collection.query(query_embeddings=[vector], n_results=20, where={"type": "image"}, include=["metadatas", "distances"])
# Returns: {"ids": [[...]], "metadatas": [[...]], "distances": [[...]]}
```

### 7.3 Raycast ↔ search.py

**Call:** `python search.py --json --top 20 "query"`  
**Success:** JSON array to stdout, exit 0  
**Error:** Human-readable to stderr, exit 1  

---

## 8. Performance Model

### 8.1 Initial Indexing Time

| Files | Time (correct: 1.5s sleep) | Time (buggy: 0.1s sleep) |
|-------|---------------------------|--------------------------|
| 100 | ~2.5 min | Hits rate limit in ~10s |
| 1,000 | ~25 min | Rate limited, fails |
| 10,000 | ~4 hours | Rate limited, fails |

Re-runs (only modified files): 50 changes in 1,000 files = ~1.5 min.

### 8.2 Search Latency Breakdown

| Step | Latency | Owner |
|------|---------|-------|
| Query embedding (Gemini API) | 300–800ms | Google |
| Query expansion × 3 | +600–1500ms | Google (or free with templates) |
| ChromaDB HNSW (10K vectors) | ~5ms | Local |
| ChromaDB HNSW (100K vectors) | ~20ms | Local |
| Cross-encoder re-rank (50 candidates) | ~50ms | Local |
| Ollama answer generation (v3) | 2–8s | Local |

**Practical total (v2 search):** 1–3s. Acceptable for a desktop search tool.

### 8.3 Storage at Scale

Per file: 3072 floats × 4 bytes = ~12 KB embedding + ~500 bytes metadata ≈ 12.5 KB

| Files | Index size |
|-------|-----------|
| 1,000 | ~12 MB |
| 10,000 | ~125 MB |
| 100,000 | ~1.25 GB |

At 100,000 files: HNSW graph still fits in RAM on a 16GB MacBook Pro.

---

## 9. Known Bugs & Required Fixes (v1)

Fix all four before running indexing on a real dataset.

### Bug 1 — Rate limit 10x too fast (CRITICAL)
**File:** `indexer.py:99` | **Fix:** `time.sleep(0.1)` → `time.sleep(1.5)`

### Bug 2 — No API key validation (HIGH)
**File:** `config.py:7` | **Fix:** Add `if not GEMINI_API_KEY: raise ValueError("...")`

### Bug 3 — Hardcoded Python path in Raycast (HIGH)
**File:** `raycast/src/search.tsx:16` | **Fix:** Write path during `setup.sh`, read dynamically

### Bug 4 — Audio support unverified (MEDIUM)
**File:** `config.py` | **Fix:** `"audio": set()` until Whisper replacement is built

### Bug 5 — N sequential DB reads (LOW — performance)
**File:** `indexer.py:already_indexed()` | **Fix:** Pre-fetch all mtimes in one batch call

---

## 10. Test Strategy

### 10.1 Embedder Sanity Check

```python
# python test_embedder.py
import numpy as np
from embedder import embed_text

v1 = embed_text("a photo of a coffee shop")
v2 = embed_text("a picture from a cafe")
assert len(v1) == 3072

cos = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
assert cos > 0.8, f"Expected similar, got {cos:.3f}"
print(f"coffee/cafe cosine similarity: {cos:.3f} ✓")
```

### 10.2 Cross-Modal Retrieval Test

```bash
mkdir /tmp/mm-test
cp ~/Desktop/any_photo.jpg /tmp/mm-test/
python indexer.py /tmp/mm-test
python search.py "photo" --json | python -c "import json,sys; d=json.load(sys.stdin); print(d[0]['name'])"
# Expected: any_photo.jpg
```

### 10.3 Temporal Filter Test (v2)

```python
results = search_files_v2("photos from last week")
from datetime import datetime, timedelta
cutoff = datetime.now() - timedelta(days=7)
for r in results:
    assert r.mtime > cutoff.timestamp(), f"{r.name} is older than 7 days"
```

---

## 11. Deployment & Distribution Guide

### 11.1 Personal Setup

```bash
cd ~/Projects/mac-memory
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # paste GEMINI_API_KEY
python indexer.py ~/Desktop   # test with a small directory first
python search.py "test" --json
cd raycast && npm install && npm run dev
```

### 11.2 GitHub Release Checklist

**Include:**
```
mac-memory/
├── .env.example
├── .gitignore          # .env, .venv/, __pycache__/, *.pyc, raycast/node_modules/
├── README.md           # with animated demo GIF
├── requirements.txt
├── setup.sh            # one-command setup
├── config.py / embedder.py / indexer.py / search.py
└── raycast/
```

**Never commit:** `.env`, `.venv/`, `~/.mac-memory/` (personal embeddings)

### 11.3 Demo Strategy

**10-second GIF script:**
1. Open Raycast
2. Type: "invoice from the dentist" — PDF result appears
3. Clear, type: "whiteboard photo from last month" — JPEG thumbnail appears
4. Click: "Show in Finder" — Finder reveals the file

**Recording tools:** Kap (free), Gifox, or QuickTime + ffmpeg → GIF

**Post caption:**
> Built semantic search for my Mac using Gemini Embedding 2 + ChromaDB.  
> Text query → image result. No tagging. No keywords. Pure meaning.  
> All embeddings stored locally — nothing leaves your machine.  
> Open source. [link]

---

## 12. Resume Worthiness Assessment

### 12.1 Verdict: Strong for AI/ML Infrastructure Roles

This project demonstrates ML system design literacy that is genuinely hard to fake. Done right, it generates 3–5 substantive interview questions and signals you understand the full stack from model choice through retrieval to UX.

### 12.2 What to Say on Your Resume

```
Mac Memory — Semantic File Search for macOS (github.com/varunnihar/mac-memory)
• Designed an enriched multimodal retrieval pipeline: EXIF/OCR/Whisper enrichment
  before embedding, multi-vector query expansion, hybrid BM25+cosine search with
  RRF fusion, and cross-encoder re-ranking — achieving precision a raw cosine search
  cannot match
• Built incremental indexing with mtime-based skip logic and ChromaDB's HNSW ANN;
  search latency <50ms local after single Gemini API call for query embedding
• Delivered results through a Raycast extension (TypeScript/React) with debounced
  search, native macOS file thumbnails, and one-click Finder reveal
• Architected a local RAG answer layer (Ollama + llama3.2) that synthesizes answers
  from retrieved files — 100% offline, no API keys for inference
```

### 12.3 Interview Questions You'll Get — With Answers

**"Why cosine distance instead of L2?"**  
Embeddings vary in magnitude (a longer document has a larger magnitude vector). Cosine normalizes magnitude and measures only directional similarity. L2 would penalize long documents vs. short ones for the same semantic content. Cosine is the right choice when the direction encodes meaning, not the magnitude.

**"How does a text query retrieve an image?"**  
Gemini Embedding 2 is trained with a contrastive objective that pulls semantically related inputs from different modalities close together in the same latent space. The concept "coffee shop" exists as a geometric direction in that space whether the input is the text "coffee shop" or a JPEG of one. The model learned the correspondence from massive multimodal training data.

**"What's the tradeoff between HNSW and exact search?"**  
HNSW is approximate — it can miss the true nearest neighbor. The tradeoff: O(log n) vs. O(n). At 10,000 vectors, HNSW returns results in 5ms; linear scan takes ~500ms. The recall tradeoff is tunable via `ef_construction` and `M` parameters. For a personal file search tool where approximate is fine, HNSW is clearly correct.

**"What would break at 1 million files?"**  
Three things: (1) HNSW graph at 1M × 3072 × 4 bytes ≈ 12GB exceeds laptop RAM — need to shard or move to a remote vector store; (2) Initial indexing at 1.5s/file = 17 days on free tier — need batch embedding API or a paid tier; (3) The mtime pre-fetch optimization is critical at this scale — N individual SQLite reads at 1M files would take minutes before you even start embedding.

**"What does the re-ranker add over cosine alone?"**  
The bi-encoder (cosine) encodes query and document independently, so there's no interaction between them. The cross-encoder encodes (query, document) jointly — it can see which specific words in the document match which parts of the query. This captures relevance signals the bi-encoder misses. The cost is one forward pass per candidate pair at query time, so you run it only on the top-50, not the full index.

### 12.4 Who This Impresses

**Strong signal for:** ML infrastructure, AI product engineering, full-stack at AI-first companies (Anthropic, Google DeepMind, Cohere, Together.ai), backend roles where AI integration is expected.

**Weaker signal for:** Pure frontend (UI is a thin Raycast wrapper), pure data science (no model training), backend at non-AI companies.

### 12.5 What to Know and Acknowledge

- Audio support is unverified in the embedding API — Whisper is the real solution
- No automated test suite — prototype-quality code, not production-hardened
- File content leaves the machine during indexing (to Gemini API) — not 100% private
- v1 moat is thin — the enrichment and query intelligence layers are what make it defensible

---

*This document reflects the full intended architecture. V1 (built) is the foundation; v2 (enrichment + query intelligence) is the moat; v3 (context graph + answer layer) is the vision.*  
*Last updated: 2026-05-19*
