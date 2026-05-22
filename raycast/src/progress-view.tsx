import { Detail, ActionPanel, Action, Icon, Color, useNavigation } from "@raycast/api";
import { useEffect, useState } from "react";
import { streamProgress, Progress } from "./api";

function bar(frac: number, width = 24): string {
  const filled = Math.max(0, Math.min(width, Math.round(frac * width)));
  return "█".repeat(filled) + "░".repeat(width - filled);
}

function fmtEta(s: number | null): string {
  if (s == null) return "—";
  const m = Math.floor(s / 60);
  const sec = Math.round(s % 60);
  return `${m}:${sec.toString().padStart(2, "0")}`;
}

const STATUS: Record<Progress["status"], { text: string; color: Color }> = {
  idle: { text: "Idle", color: Color.SecondaryText },
  running: { text: "Indexing", color: Color.Blue },
  done: { text: "Complete", color: Color.Green },
  error: { text: "Failed", color: Color.Red },
};

export function ProgressView({ title, onComplete }: { title?: string; onComplete?: () => void }) {
  const [p, setP] = useState<Progress | null>(null);
  const { pop } = useNavigation();

  useEffect(() => {
    let alive = true;
    let notified = false;
    streamProgress((next) => {
      if (!alive) return;
      setP(next);
      if (!notified && (next.status === "done" || next.status === "error")) {
        notified = true;
        onComplete?.();
      }
    }).catch(() => {
      /* stream closed */
    });
    return () => {
      alive = false;
    };
  }, []);

  const frac = p && p.total ? p.done / p.total : 0;
  const pct = Math.round(frac * 100);
  const running = !p || p.status === "running";
  const st = STATUS[p?.status ?? "idle"];

  let markdown: string;
  if (!p) {
    markdown = `# Starting…\n\nConnecting to the indexer…`;
  } else if (p.status === "error") {
    markdown = `# ⚠︎ Indexing failed\n\n\`\`\`\n${p.message || "unknown error"}\n\`\`\``;
  } else {
    const head = p.status === "done" ? "✓ Indexing complete" : "Indexing…";
    markdown = [
      `# ${head}`,
      ``,
      `\`${bar(frac)}\`  **${pct}%**`,
      ``,
      `**${p.done} / ${p.total}** files${running ? ` · ETA ${fmtEta(p.eta_seconds)}` : ""}`,
      ``,
      running && p.current ? `Indexing  \`${p.current}\`` : "",
    ].join("\n");
  }

  return (
    <Detail
      isLoading={running}
      navigationTitle={title ? `Indexing ${title}` : "Indexing"}
      markdown={markdown}
      metadata={
        <Detail.Metadata>
          <Detail.Metadata.TagList title="Status">
            <Detail.Metadata.TagList.Item text={st.text} color={st.color} />
          </Detail.Metadata.TagList>
          <Detail.Metadata.Label title="Progress" text={p ? `${p.done} / ${p.total}` : "—"} icon={Icon.BarChart} />
          <Detail.Metadata.Label title="ETA" text={running ? fmtEta(p?.eta_seconds ?? null) : "—"} icon={Icon.Clock} />
          <Detail.Metadata.Separator />
          <Detail.Metadata.TagList title="Results">
            <Detail.Metadata.TagList.Item text={`${p?.indexed ?? 0} indexed`} color={Color.Green} />
            <Detail.Metadata.TagList.Item text={`${p?.skipped ?? 0} skipped`} color={Color.SecondaryText} />
            <Detail.Metadata.TagList.Item
              text={`${p?.errors ?? 0} errors`}
              color={(p?.errors ?? 0) > 0 ? Color.Red : Color.SecondaryText}
            />
          </Detail.Metadata.TagList>
        </Detail.Metadata>
      }
      actions={
        <ActionPanel>
          {!running && <Action title="Done" icon={Icon.Check} onAction={pop} />}
        </ActionPanel>
      }
    />
  );
}

export default ProgressView;
