export type Profile = {
  id: string;
  name?: string;
  email?: string;
  phone?: string;
  location?: string;
  notes?: string;
  _source?: {
    filename?: string;
    path?: string;
    processed_at?: string;
    line_count?: number;
    size?: number | null;
  };
  _warnings?: string[];
  [key: string]: unknown;
};

export type Status = {
  queue_size: number;
  worker_alive: boolean;
  ollama_reachable: boolean;
  ollama_model: string;
  data_dir: string;
  inbox_dir: string;
  profiles_dir: string;
};

export type PipelineEvent = {
  type: "connected" | "queued" | "started" | "done" | "error";
  id?: string;
  filename?: string;
  path?: string;
  profile_path?: string;
  error?: string;
  warnings?: string[];
  profile?: Profile;
  ts?: string;
};
