import { AlertTriangle, CheckCircle2, CircleDot, FileClock, Play } from "lucide-react";
import type { PipelineEvent } from "../types/api";

type Props = {
  events: PipelineEvent[];
};

const iconFor = {
  connected: CircleDot,
  queued: FileClock,
  started: Play,
  done: CheckCircle2,
  error: AlertTriangle
};

export function LiveFeed({ events }: Props) {
  return (
    <section className="panel live-feed">
      <div className="panel-heading">
        <h2>Live feed</h2>
        <span>{events.length} recent</span>
      </div>
      <div className="event-list">
        {events.length === 0 ? <p className="empty">Waiting for pipeline events.</p> : null}
        {events.map((event, index) => {
          const Icon = iconFor[event.type] ?? CircleDot;
          return (
            <article className={`event event-${event.type}`} key={`${event.ts}-${event.type}-${index}`}>
              <Icon size={18} />
              <div>
                <strong>{event.type}</strong>
                <span>{event.error || event.filename || event.id || event.path || "connected"}</span>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
