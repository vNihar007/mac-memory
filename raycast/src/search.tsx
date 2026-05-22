import { List, ActionPanel, Action, Icon, Color, open } from "@raycast/api";
import { useState, useEffect, useRef } from "react";
import { homedir } from "os";
import { search as apiSearch, ensureDaemon, SearchResult } from "./api";

const HOME = homedir();

// ── presentation helpers ─────────────────────────────────────────────────────

const TYPE_STYLE: Record<string, { icon: Icon; color: Color }> = {
  image: { icon: Icon.Image, color: Color.Purple },
  pdf: { icon: Icon.Document, color: Color.Red },
  text: { icon: Icon.Text, color: Color.Blue },
  office: { icon: Icon.Document, color: Color.Magenta },
  audio: { icon: Icon.Music, color: Color.Orange },
};

function typeStyle(t: string) {
  return TYPE_STYLE[t] ?? { icon: Icon.Dot, color: Color.SecondaryText };
}

// relevance tiers tuned to gemini-embedding-2 retrieval scores
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
  let n = bytes;
  let i = 0;
  while (n >= 1024 && i < units.length - 1) {
    n /= 1024;
    i++;
  }
  return `${n.toFixed(n < 10 && i > 0 ? 1 : 0)} ${units[i]}`;
}

function prettyDir(path: string): string {
  const dir = path.slice(0, path.lastIndexOf("/")) || "/";
  return dir.startsWith(HOME) ? "~" + dir.slice(HOME.length) : dir;
}

function detailMarkdown(r: SearchResult): string {
  if (r.file_type === "image") {
    return `![${r.name}](${encodeURI("file://" + r.path)})`;
  }
  const pct = Math.round(r.similarity * 100);
  return `# ${r.name}\n\n\`${meter(r.similarity, 20)}\`  **${pct}% match**\n\n\`${prettyDir(r.path)}\``;
}

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
  const [showDetail, setShowDetail] = useState(false);
  const [daemonDown, setDaemonDown] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  useEffect(() => {
    clearTimeout(timer.current);
    if (!query.trim()) {
      setResults([]);
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    timer.current = setTimeout(async () => {
      if (!(await ensureDaemon())) {
        setDaemonDown(true);
        setResults([]);
        setIsLoading(false);
        return;
      }
      setDaemonDown(false);
      setResults(await apiSearch(query, 12, typeFilter || undefined));
      setIsLoading(false);
    }, 400);
    return () => clearTimeout(timer.current);
  }, [query, typeFilter]);

  function renderItem(r: SearchResult) {
    const style = typeStyle(r.file_type);
    const pct = Math.round(r.similarity * 100);
    return (
      <List.Item
        key={r.path}
        icon={{ source: style.icon, tintColor: style.color }}
        title={r.name}
        subtitle={showDetail ? undefined : prettyDir(r.path)}
        accessories={[
          { tag: { value: `${pct}%`, color: tierColor(r.similarity) } },
          ...(showDetail ? [] : [{ text: r.file_type }]),
        ]}
        detail={
          <List.Item.Detail
            markdown={detailMarkdown(r)}
            metadata={
              <List.Item.Detail.Metadata>
                <List.Item.Detail.Metadata.Label title="Name" text={r.name} icon={{ source: style.icon, tintColor: style.color }} />
                <List.Item.Detail.Metadata.TagList title="Type">
                  <List.Item.Detail.Metadata.TagList.Item text={r.file_type} color={style.color} />
                </List.Item.Detail.Metadata.TagList>
                <List.Item.Detail.Metadata.Label title="Match" text={`${meter(r.similarity)}  ${pct}%`} />
                <List.Item.Detail.Metadata.Label title="Size" text={humanSize(r.size)} />
                <List.Item.Detail.Metadata.Separator />
                <List.Item.Detail.Metadata.Label title="Folder" text={prettyDir(r.path)} />
                <List.Item.Detail.Metadata.Label title="Path" text={r.path} />
              </List.Item.Detail.Metadata>
            }
          />
        }
        actions={
          <ActionPanel>
            <ActionPanel.Section>
              <Action title="Open File" icon={Icon.ArrowNe} onAction={() => open(r.path)} />
              <Action.ShowInFinder path={r.path} />
            </ActionPanel.Section>
            <ActionPanel.Section>
              <Action
                title={showDetail ? "Hide Details" : "Show Details"}
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
      searchBarPlaceholder="Search your files by meaning — “a photo of a cat”, “my resume”…"
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
          description="Couldn’t reach the mac-memory daemon on port 8765. Make sure it’s loaded via launchctl."
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
          description={`Nothing indexed matches “${query}”${typeFilter ? ` in ${typeFilter}` : ""}.`}
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
