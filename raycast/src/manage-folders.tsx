import {
  List,
  ActionPanel,
  Action,
  Form,
  useNavigation,
  Icon,
  Color,
  showToast,
  Toast,
  confirmAlert,
  Alert,
} from "@raycast/api";
import { useEffect, useState } from "react";
import { homedir } from "os";
import { getFolders, addFolder, removeFolder, startIndex, ensureDaemon, Folder } from "./api";
import { ProgressView } from "./progress-view";

const HOME = homedir();
const tilde = (p: string) => (p.startsWith(HOME) ? "~" + p.slice(HOME.length) : p);

function AddFolderForm({ onDone }: { onDone: () => void }) {
  const { pop } = useNavigation();
  const [error, setError] = useState<string | undefined>();
  return (
    <Form
      navigationTitle="Add Folders to Index"
      actions={
        <ActionPanel>
          <Action.SubmitForm
            title="Add Folders"
            icon={Icon.Plus}
            onSubmit={async (values: { dirs: string[] }) => {
              if (!values.dirs?.length) {
                setError("Pick at least one folder");
                return;
              }
              try {
                for (const d of values.dirs) await addFolder(d);
                await showToast({ style: Toast.Style.Success, title: `Added ${values.dirs.length} folder(s)` });
                onDone();
                pop();
              } catch (e) {
                await showToast({ style: Toast.Style.Failure, title: "Couldn't add folder", message: String(e) });
              }
            }}
          />
        </ActionPanel>
      }
    >
      <Form.Description text="Choose folders to index. Files inside are embedded so you can search them by meaning — not just by filename." />
      <Form.FilePicker
        id="dirs"
        title="Folders"
        allowMultipleSelection
        canChooseDirectories
        canChooseFiles={false}
        error={error}
        onChange={() => setError(undefined)}
      />
    </Form>
  );
}

export default function Command() {
  const [folders, setFolders] = useState<Folder[]>([]);
  const [loading, setLoading] = useState(true);
  const [down, setDown] = useState(false);
  const { push } = useNavigation();

  const refresh = async () => {
    setLoading(true);
    if (!(await ensureDaemon())) {
      setDown(true);
      setLoading(false);
      return;
    }
    setDown(false);
    setFolders(await getFolders());
    setLoading(false);
  };

  useEffect(() => {
    refresh();
  }, []);

  const totalFiles = folders.reduce((n, f) => n + f.count, 0);

  const reindex = async (paths?: string[], label?: string) => {
    try {
      await startIndex(paths);
      push(<ProgressView title={label} onComplete={refresh} />);
    } catch (e) {
      await showToast({ style: Toast.Style.Failure, title: "Couldn't start indexing", message: String(e) });
    }
  };

  const remove = async (f: Folder) => {
    const ok = await confirmAlert({
      title: "Remove folder?",
      message: `${tilde(f.path)} will no longer be indexed. Already-indexed files stay searchable until you re-index.`,
      icon: { source: Icon.Trash, tintColor: Color.Red },
      primaryAction: { title: "Remove", style: Alert.ActionStyle.Destructive },
    });
    if (!ok) return;
    setFolders(await removeFolder(f.path));
    await showToast({ style: Toast.Style.Success, title: "Removed", message: tilde(f.path) });
  };

  const addAction = (
    <Action.Push
      title="Add Folder…"
      icon={Icon.Plus}
      shortcut={{ modifiers: ["cmd"], key: "n" }}
      target={<AddFolderForm onDone={refresh} />}
    />
  );

  if (down) {
    return (
      <List>
        <List.EmptyView
          icon={{ source: Icon.WifiDisabled, tintColor: Color.Red }}
          title="Daemon not running"
          description="Couldn't reach the mac-memory daemon on port 8765."
          actions={
            <ActionPanel>
              <Action title="Retry" icon={Icon.ArrowClockwise} onAction={refresh} />
            </ActionPanel>
          }
        />
      </List>
    );
  }

  if (!loading && folders.length === 0) {
    return (
      <List navigationTitle="Manage Indexed Folders">
        <List.EmptyView
          icon={{ source: Icon.Folder, tintColor: Color.Blue }}
          title="No folders yet"
          description="Add a folder to start indexing your files for semantic search."
          actions={<ActionPanel>{addAction}</ActionPanel>}
        />
      </List>
    );
  }

  return (
    <List isLoading={loading} navigationTitle="Manage Indexed Folders" searchBarPlaceholder="Filter folders…">
      <List.Section
        title="Indexed Folders"
        subtitle={folders.length ? `${folders.length} folders · ${totalFiles} files` : undefined}
      >
        {folders.map((f) => {
          const empty = f.count === 0;
          return (
            <List.Item
              key={f.path}
              icon={{ source: Icon.Folder, tintColor: empty ? Color.SecondaryText : Color.Blue }}
              title={tilde(f.path)}
              accessories={[
                { tag: { value: `${f.count}`, color: empty ? Color.SecondaryText : Color.Green }, icon: Icon.Document },
                ...(empty
                  ? [{ icon: { source: Icon.ExclamationMark, tintColor: Color.Orange }, tooltip: "Registered but not indexed yet — Re-index to populate" }]
                  : []),
              ]}
              actions={
                <ActionPanel>
                  <ActionPanel.Section>
                    <Action
                      title="Re-index This Folder"
                      icon={Icon.ArrowClockwise}
                      onAction={() => reindex([f.path], tilde(f.path))}
                    />
                    <Action
                      title="Re-index All"
                      icon={Icon.Repeat}
                      shortcut={{ modifiers: ["cmd"], key: "r" }}
                      onAction={() => reindex(undefined, "all folders")}
                    />
                    <Action.ShowInFinder path={f.path} />
                  </ActionPanel.Section>
                  <ActionPanel.Section>
                    {addAction}
                    <Action
                      title="Remove Folder"
                      icon={Icon.Trash}
                      style={Action.Style.Destructive}
                      shortcut={{ modifiers: ["ctrl"], key: "x" }}
                      onAction={() => remove(f)}
                    />
                    <Action
                      title="Refresh"
                      icon={Icon.ArrowClockwise}
                      shortcut={{ modifiers: ["cmd"], key: "y" }}
                      onAction={refresh}
                    />
                  </ActionPanel.Section>
                </ActionPanel>
              }
            />
          );
        })}
      </List.Section>

      <List.Section title="Manage">
        <List.Item
          icon={{ source: Icon.Plus, tintColor: Color.Green }}
          title="Add Folder…"
          subtitle="Pick folders to index"
          actions={
            <ActionPanel>
              {addAction}
              <Action title="Re-index All" icon={Icon.Repeat} onAction={() => reindex(undefined, "all folders")} />
              <Action title="Refresh" icon={Icon.ArrowClockwise} onAction={refresh} />
            </ActionPanel>
          }
        />
      </List.Section>
    </List>
  );
}
