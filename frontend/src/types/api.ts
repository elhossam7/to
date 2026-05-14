export type Profile = {
  id: string;
  personal?: {
    first_name?: string | null;
    last_name?: string | null;
    full_name?: string | null;
    date_of_birth?: string | null;
    age?: number | null;
    place_of_birth?: string | null;
    nationality?: string | null;
    national_id?: string | null;
  };
  address?: {
    street?: string | null;
    city?: string | null;
    region?: string | null;
    postal_code?: string | null;
    country?: string | null;
    country_code?: string | null;
  };
  contact?: {
    phones?: Array<{ number?: string | null; type?: string | null; primary?: boolean | null }>;
    emails?: Array<{ address?: string | null; primary?: boolean | null }>;
  };
  name?: string;
  email?: string;
  phone?: string;
  location?: string;
  notes?: string;
  _source?: {
    filename?: string;
    filenames?: string[];
    files?: Array<{ filename?: string; path?: string; size?: number | null }>;
    path?: string;
    batch_id?: string;
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
  filenames?: string[];
  batch_id?: string;
  path?: string;
  profile_path?: string;
  error?: string;
  warnings?: string[];
  profile?: Profile;
  ts?: string;
};
