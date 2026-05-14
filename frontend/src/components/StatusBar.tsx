import { Activity, Brain, Database, Radio } from "lucide-react";
import type { Status } from "../types/api";

type Props = {
  status: Status | null;
  eventsConnected: boolean;
};

export function StatusBar({ status, eventsConnected }: Props) {
  return (
    <section className="status-bar" aria-label="System status">
      <div className="status-item">
        <Activity size={18} />
        <span>Queue</span>
        <strong>{status?.queue_size ?? "..."}</strong>
      </div>
      <div className="status-item">
        <Brain size={18} />
        <span>Ollama</span>
        <strong className={status?.ollama_reachable ? "good" : "bad"}>
          {status?.ollama_reachable ? status.ollama_model : "offline"}
        </strong>
      </div>
      <div className="status-item">
        <Radio size={18} />
        <span>Events</span>
        <strong className={eventsConnected ? "good" : "bad"}>{eventsConnected ? "live" : "waiting"}</strong>
      </div>
      <div className="status-item wide">
        <Database size={18} />
        <span>Data</span>
        <strong>{status?.data_dir ?? "./data"}</strong>
      </div>
    </section>
  );
}
