import { spawn } from "child_process";

const BASE = "http://127.0.0.1:8765";

export interface SearchResult {
  path: string;
  name: string;
  file_type: string;
  similarity: number;
  size: number;
}

export interface Folder {
  path: string;
  count: number;
}

export interface Progress {
  status: "idle" | "running" | "done" | "error";
  total: number;
  done: number;
  indexed: number;
  skipped: number;
  errors: number;
  current: string;
  eta_seconds: number | null;
  message: string;
}

// FastAPI returns either {detail: "msg"} or {detail: [{msg, ...}]} (validation).
async function errorDetail(r: Response, fallback: string): Promise<string> {
  try {
    const j = (await r.json()) as { detail?: unknown };
    if (typeof j.detail === "string") return j.detail;
    if (Array.isArray(j.detail)) return j.detail.map((d: { msg?: string }) => d.msg ?? "").join("; ");
  } catch {
    /* body not JSON */
  }
  return fallback;
}

export async function health(): Promise<boolean> {
  try {
    const r = await fetch(`${BASE}/health`);
    return r.ok;
  } catch {
    return false;
  }
}

export async function search(q: string, topK = 8, type?: string): Promise<SearchResult[]> {
  const params = new URLSearchParams({ q, top_k: String(topK) });
  if (type) params.set("type", type);
  const r = await fetch(`${BASE}/search?${params.toString()}`);
  return r.ok ? (r.json() as Promise<SearchResult[]>) : [];
}

export async function getFolders(): Promise<Folder[]> {
  const r = await fetch(`${BASE}/folders`);
  return r.ok ? (r.json() as Promise<Folder[]>) : [];
}

export async function addFolder(path: string): Promise<Folder[]> {
  const r = await fetch(`${BASE}/folders`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ path }),
  });
  if (!r.ok) throw new Error(await errorDetail(r, "add failed"));
  return r.json() as Promise<Folder[]>;
}

export async function removeFolder(path: string): Promise<Folder[]> {
  const r = await fetch(`${BASE}/folders`, {
    method: "DELETE",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ path }),
  });
  if (!r.ok) throw new Error(await errorDetail(r, "remove failed"));
  return r.json() as Promise<Folder[]>;
}

export async function startIndex(folders?: string[]): Promise<void> {
  const r = await fetch(`${BASE}/index`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ folders }),
  });
  if (!r.ok) throw new Error(await errorDetail(r, "index failed"));
}

// Reads the daemon's SSE progress stream, invoking onUpdate per event.
export async function streamProgress(onUpdate: (p: Progress) => void): Promise<void> {
  const res = await fetch(`${BASE}/index/stream`);
  if (!res.body) return;
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    const lines = buf.split("\n");
    buf = lines.pop() ?? "";
    for (const line of lines) {
      if (line.startsWith("data:")) {
        try {
          onUpdate(JSON.parse(line.slice(5).trim()));
        } catch {
          /* partial line */
        }
      }
    }
  }
}

// If the daemon is down, try to revive it via launchd, then poll /health.
export async function ensureDaemon(): Promise<boolean> {
  if (await health()) return true;
  try {
    spawn("launchctl", ["start", "com.macmemory.daemon"], { detached: true });
  } catch {
    /* launchctl unavailable */
  }
  for (let i = 0; i < 10; i++) {
    await new Promise((r) => setTimeout(r, 500));
    if (await health()) return true;
  }
  return false;
}
