import { useEffect, useState } from "react";
import type { PipelineEvent } from "../types/api";

export function useEvents(onProfileDone: () => void) {
  const [events, setEvents] = useState<PipelineEvent[]>([]);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const source = new EventSource("/events");

    source.onopen = () => setConnected(true);
    source.onerror = () => setConnected(false);
    source.onmessage = (message) => {
      const event = JSON.parse(message.data) as PipelineEvent;
      setEvents((current) => [event, ...current].slice(0, 20));
      if (event.type === "done") {
        onProfileDone();
      }
    };

    return () => {
      source.close();
      setConnected(false);
    };
  }, [onProfileDone]);

  return { events, connected };
}
