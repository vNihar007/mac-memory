import { List, ActionPanel, Action, Icon, Color } from "@raycast/api";
import { useState, useEffect, useRef } from "react";
import { homedir, tmpdir } from "os";
import { spawn } from "child_process";
import { statSync, mkdirSync, existsSync, readFileSync } from "fs";
import { search as apiSearch, ensureDaemon, SearchResult } from "./api";

const HOME = homedir();
const THUMB_DIR = `${tmpdir()}/mac-memory-thumbs`;

// ── file type helpers ─────────────────────────────────────────────────────────

const TYPE_COLOR: Record<string, Color> = {
  image: Color.Purple,
  pdf: Color.Red,
  text: Color.Blue,
  office: Color.Magenta,
  audio: Color.Orange,
};

function typeColor(t: string): Color {
  return TYPE_COLOR[t] ?? Color.SecondaryText;
}

function fileTypeDesc(path: string, fileType: string): string {
  const ext = path.split(".").pop()?.toLowerCase() ?? "";
  const map: Record<string, string> = {
    docx: "Word Document", doc: "Word Document",
    xlsx: "Excel Spreadsheet", xls: "Excel Spreadsheet",
    pptx: "PowerPoint Presentation", ppt: "PowerPoint Presentation",
    pdf: "PDF Document",
    png: "PNG Image", jpg: "JPEG Image", jpeg: "JPEG Image",
    gif: "GIF Image", heic: "HEIC Image", webp: "WebP Image", svg: "SVG Image",
    txt: "Text File", md: "Markdown Document", csv: "CSV Spreadsheet",
    mp3: "MP3 Audio", mp4: "MP4 Video", wav: "WAV Audio", m4a: "M4A Audio",
    js: "JavaScript", ts: "TypeScript", py: "Python Script",
    json: "JSON", yaml: "YAML", toml: "TOML", sh: "Shell Script",
  };
  return map[ext] ?? fileType;
}

function tierColor(s: number): Color {
  if (s >= 0.65) return Color.Green;
  if (s >= 0.5) return Color.Yellow;
  return Color.SecondaryText;
}

function meter(s: number, width = 10): string {
  const filled = Math.max(0, Math.min(width, Math.round(s * width)));
  return "█".repeat(filled) + "░".repeat(width - filled);
}

function humanSize(bytes: number): string {
  if (!bytes) return "—";
  const units = ["B", "KB", "MB", "GB"];
  let n = bytes, i = 0;
  while (n >= 1024 && i < units.length - 1) { n /= 1024; i++; }
  return `${n.toFixed(n < 10 && i > 0 ? 1 : 0)} ${units[i]}`;
}

function prettyDir(path: string): string {
  const dir = path.slice(0, path.lastIndexOf("/")) || "/";
  return dir.startsWith(HOME) ? "~" + dir.slice(HOME.length) : dir;
}

function parentFolder(path: string): string {
  return path.split("/").slice(-2, -1)[0] ?? "—";
}

function fileDate(path: string): string {
  try {
    return statSync(path).mtime.toLocaleDateString("en-AU", {
      day: "2-digit", month: "2-digit", year: "2-digit",
    });
  } catch {
    return "—";
  }
}

// ── preview helpers ───────────────────────────────────────────────────────────

async function generateThumbnail(filePath: string): Promise<string | null> {
  return new Promise((resolve) => {
    try { mkdirSync(THUMB_DIR, { recursive: true }); } catch { resolve(null); return; }
    const proc = spawn("qlmanage", ["-t", "-s", "600", "-o", THUMB_DIR, filePath]);
    const timeout = setTimeout(() => { proc.kill(); resolve(null); }, 5000);
    proc.on("close", () => {
      clearTimeout(timeout);
      const thumbPath = `${THUMB_DIR}/${filePath.split("/").pop()}.png`;
      resolve(existsSync(thumbPath) ? thumbPath : null);
    });
    proc.on("error", () => { clearTimeout(timeout); resolve(null); });
  });
}

function textPreview(path: string): string {
  try {
    const content = readFileSync(path, "utf-8");
    const lines = content.split("\n").slice(0, 60).join("\n");
    const ext = path.split(".").pop()?.toLowerCase() ?? "";
    const lang = ext === "md" ? "" : ext;
    return `\`\`\`${lang}\n${lines}\n\`\`\``;
  } catch {
    return "_Could not read file._";
  }
}

function detailMarkdown(r: SearchResult, thumbnail?: string): string {
  if (r.file_type === "image") {
    return `![${r.name}](${encodeURI("file://" + r.path)})`;
  }
  if (thumbnail) {
    return `![preview](${encodeURI("file://" + thumbnail)})`;
  }
  if (r.file_type === "text") {
    return textPreview(r.path);
  }
  const pct = Math.round(r.similarity * 100);
  return `# ${r.name}\n\n\`${meter(r.similarity, 20)}\`  **${pct}% match**\n\n\`${prettyDir(r.path)}\`\n\n_Generating preview…_`;
}

// ── tiers ─────────────────────────────────────────────────────────────────────

const TIERS: { key: string; title: string; min: number }[] = [
  { key: "strong", title: "Strong matches", min: 0.65 },
  { key: "likely", title: "Possible matches", min: 0.5 },
  { key: "weak", title: "Weak matches", min: -1 },
];

// ── command ───────────────────────────────────────────────────────────────────

export default function Command() {
  const [query, setQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState<string>("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [showDetail, setShowDetail] = useState(true);
  const [daemonDown, setDaemonDown] = useState(false);
  const [thumbnails, setThumbnails] = useState<Map<string, string>>(new Map());
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const queuedThumbs = useRef<Set<string>>(new Set());

  useEffect(() => {
    clearTimeout(timer.current);
    if (!query.trim()) { setResults([]); setIsLoading(false); return; }
    setIsLoading(true);
    timer.current = setTimeout(async () => {
      if (!(await ensureDaemon())) {
        setDaemonDown(true); setResults([]); setIsLoading(false); return;
      }
      setDaemonDown(false);
      setResults(await apiSearch(query, 12, typeFilter || undefined));
      setIsLoading(false);
    }, 400);
    return () => clearTimeout(timer.current);
  }, [query, typeFilter]);

  // generate Quick Look thumbnails for non-image files in the background
  useEffect(() => {
    for (const r of results) {
      if (r.file_type === "image" || queuedThumbs.current.has(r.path)) continue;
      queuedThumbs.current.add(r.path);
      generateThumbnail(r.path).then((thumb) => {
        if (thumb) setThumbnails((prev) => new Map(prev).set(r.path, thumb));
      });
    }
  }, [results]);

  function renderItem(r: SearchResult) {
    const pct = Math.round(r.similarity * 100);
    const thumb = thumbnails.get(r.path);

    return (
      <List.Item
        key={r.path}
        icon={{ fileIcon: r.path }}
        title={r.name}
        subtitle={showDetail ? undefined : `${fileTypeDesc(r.path, r.file_type)} · ${humanSize(r.size)}`}
        accessories={[
          { tag: { value: `${pct}%`, color: tierColor(r.similarity) } },
          ...(showDetail ? [] : [
            { text: { value: fileDate(r.path), color: Color.SecondaryText } },
            { text: { value: parentFolder(r.path), color: Color.SecondaryText } },
          ]),
        ]}
        detail={
          <List.Item.Detail
            markdown={detailMarkdown(r, thumb)}
            metadata={
              <List.Item.Detail.Metadata>
                <List.Item.Detail.Metadata.Label
                  title="Name"
                  text={r.name}
                  icon={{ fileIcon: r.path }}
                />
                <List.Item.Detail.Metadata.TagList title="Type">
                  <List.Item.Detail.Metadata.TagList.Item
                    text={fileTypeDesc(r.path, r.file_type)}
                    color={typeColor(r.file_type)}
                  />
                </List.Item.Detail.Metadata.TagList>
                <List.Item.Detail.Metadata.Label title="Match" text={`${meter(r.similarity)}  ${pct}%`} />
                <List.Item.Detail.Metadata.Label title="Size" text={humanSize(r.size)} />
                <List.Item.Detail.Metadata.Label title="Modified" text={fileDate(r.path)} />
                <List.Item.Detail.Metadata.Separator />
                <List.Item.Detail.Metadata.Label title="Folder" text={parentFolder(r.path)} />
                <List.Item.Detail.Metadata.Label title="Path" text={prettyDir(r.path)} />
              </List.Item.Detail.Metadata>
            }
          />
        }
        actions={
          <ActionPanel>
            <ActionPanel.Section>
              <Action title="Open File" icon={Icon.ArrowNe} onAction={() => spawn("open", [r.path], { detached: true })} />
              <Action.ShowInFinder path={r.path} />
            </ActionPanel.Section>
            <ActionPanel.Section>
              <Action
                title={showDetail ? "Hide Preview" : "Show Preview"}
                icon={Icon.Sidebar}
                shortcut={{ modifiers: ["cmd"], key: "d" }}
                onAction={() => setShowDetail((v) => !v)}
              />
              <Action.CopyToClipboard title="Copy Path" content={r.path} shortcut={{ modifiers: ["cmd"], key: "." }} />
              <Action.CopyToClipboard title="Copy Name" content={r.name} shortcut={{ modifiers: ["cmd", "shift"], key: "." }} />
            </ActionPanel.Section>
          </ActionPanel>
        }
      />
    );
  }

  return (
    <List
      isLoading={isLoading}
      onSearchTextChange={setQuery}
      searchBarPlaceholder='Search your files by meaning — "a photo of a cat", "my resume"…'
      isShowingDetail={showDetail && results.length > 0}
      throttle
      searchBarAccessory={
        <List.Dropdown tooltip="Filter by type" value={typeFilter} onChange={setTypeFilter}>
          <List.Dropdown.Item title="All types" value="" icon={Icon.Layers} />
          <List.Dropdown.Item title="Images" value="image" icon={{ source: Icon.Image, tintColor: Color.Purple }} />
          <List.Dropdown.Item title="PDFs" value="pdf" icon={{ source: Icon.Document, tintColor: Color.Red }} />
          <List.Dropdown.Item title="Text" value="text" icon={{ source: Icon.Text, tintColor: Color.Blue }} />
          <List.Dropdown.Item title="Office" value="office" icon={{ source: Icon.Document, tintColor: Color.Magenta }} />
          <List.Dropdown.Item title="Audio" value="audio" icon={{ source: Icon.Music, tintColor: Color.Orange }} />
        </List.Dropdown>
      }
    >
      {daemonDown ? (
        <List.EmptyView
          icon={{ source: Icon.WifiDisabled, tintColor: Color.Red }}
          title="Daemon not running"
          description="Couldn't reach the mac-memory daemon on port 8765. Make sure it's loaded via launchctl."
          actions={
            <ActionPanel>
              <Action title="Retry" icon={Icon.ArrowClockwise} onAction={() => setQuery((q) => q + " ")} />
            </ActionPanel>
          }
        />
      ) : !query.trim() ? (
        <List.EmptyView
          icon={{ source: Icon.MagnifyingGlass, tintColor: Color.Blue }}
          title="Search your Mac by meaning"
          description="Type a description — the index understands concepts, not just filenames."
        />
      ) : results.length === 0 && !isLoading ? (
        <List.EmptyView
          icon={{ source: Icon.Tray, tintColor: Color.SecondaryText }}
          title="No matches"
          description={`Nothing indexed matches "${query}"${typeFilter ? ` in ${typeFilter}` : ""}.`}
        />
      ) : (
        TIERS.map((tier, i) => {
          const max = i === 0 ? Infinity : TIERS[i - 1].min;
          const items = results.filter((r) => r.similarity >= tier.min && r.similarity < max);
          return items.length === 0 ? null : (
            <List.Section key={tier.key} title={tier.title} subtitle={`${items.length}`}>
              {items.map(renderItem)}
            </List.Section>
          );
        })
      )}
    </List>
  );
}
