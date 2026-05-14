import { useCallback, useEffect, useMemo, useState } from "react";
import { RefreshCw } from "lucide-react";
import { LiveFeed } from "./components/LiveFeed";
import { ProfileDetail } from "./components/ProfileDetail";
import { ProfileList } from "./components/ProfileList";
import { StatusBar } from "./components/StatusBar";
import { UploadDropzone } from "./components/UploadDropzone";
import { fetchProfiles, fetchStatus } from "./lib/api";
import { useEvents } from "./hooks/useEvents";
import type { Profile, Status } from "./types/api";

export function App() {
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [status, setStatus] = useState<Status | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refreshProfiles = useCallback(async () => {
    try {
      const rows = await fetchProfiles();
      setProfiles(rows);
      setSelectedId((current) => current ?? rows[0]?.id ?? null);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load profiles");
    }
  }, []);

  const refreshStatus = useCallback(async () => {
    try {
      setStatus(await fetchStatus());
    } catch {
      setStatus(null);
    }
  }, []);

  const { events, connected } = useEvents(refreshProfiles);

  useEffect(() => {
    void refreshProfiles();
    void refreshStatus();
    const interval = window.setInterval(refreshStatus, 10000);
    return () => window.clearInterval(interval);
  }, [refreshProfiles, refreshStatus]);

  const selectedProfile = useMemo(
    () => profiles.find((profile) => profile.id === selectedId) ?? null,
    [profiles, selectedId]
  );

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <p>Local Ollama pipeline</p>
          <h1>Profile Extraction Console</h1>
        </div>
        <button className="icon-button" onClick={() => void refreshProfiles()} title="Refresh profiles">
          <RefreshCw size={20} />
        </button>
      </header>

      <StatusBar status={status} eventsConnected={connected} />

      {error ? <div className="banner">{error}</div> : null}

      <section className="workbench">
        <aside className="left-rail">
          <UploadDropzone
            onUploaded={() => {
              void refreshStatus();
              void refreshProfiles();
            }}
          />
          <LiveFeed events={events} />
        </aside>
        <ProfileList profiles={profiles} selectedId={selectedId} onSelect={(profile) => setSelectedId(profile.id)} />
        <ProfileDetail profile={selectedProfile} />
      </section>
    </main>
  );
}
