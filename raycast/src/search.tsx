import { List, ActionPanel, Action, Icon, open } from "@raycast/api";
import { useState, useEffect, useRef } from "react";
import { spawnSync } from "child_process";
import { homedir } from "os";

interface SearchResult {
  path: string;
  name: string;
  file_type: string;
  similarity: number;
  size: number;
}

const UV = "/Users/varunnihar/.local/bin/uv";
const PROJECT_ROOT = `${homedir()}/Projects/mac-memory`;

function runSearch(query: string): SearchResult[] {
  const result = spawnSync(UV, ["run", "src/mac_memory/search.py", "--json", query], {
    cwd: PROJECT_ROOT,
    encoding: "utf-8",
    timeout: 15000,
  });
  if (result.error || result.status !== 0) return [];
  try {
    return JSON.parse(result.stdout);
  } catch {
    return [];
  }
}

const TYPE_ICON: Record<string, Icon> = {
  pdf: Icon.Document,
  image: Icon.Image,
  text: Icon.Text,
  audio: Icon.Music,
};

export default function Command() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => {
    clearTimeout(timer.current);
    if (!query.trim()) {
      setResults([]);
      return;
    }
    setIsLoading(true);
    timer.current = setTimeout(() => {
      setResults(runSearch(query));
      setIsLoading(false);
    }, 400);
    return () => clearTimeout(timer.current);
  }, [query]);

  return (
    <List
      isLoading={isLoading}
      onSearchTextChange={setQuery}
      searchBarPlaceholder="Search your files semantically..."
      throttle
    >
      {results.map((r) => (
        <List.Item
          key={r.path}
          icon={TYPE_ICON[r.file_type] ?? Icon.Document}
          title={r.name}
          subtitle={`${(r.similarity * 100).toFixed(0)}% match`}
          accessories={[{ tag: r.file_type }]}
          actions={
            <ActionPanel>
              <Action title="Open File" onAction={() => open(r.path)} />
              <Action.ShowInFinder path={r.path} />
              <Action.CopyToClipboard title="Copy Path" content={r.path} />
            </ActionPanel>
          }
        />
      ))}
    </List>
  );
}
