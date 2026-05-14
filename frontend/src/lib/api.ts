import type { Profile, Status } from "../types/api";

export async function fetchProfiles(): Promise<Profile[]> {
  const response = await fetch("/profiles?limit=100");
  if (!response.ok) {
    throw new Error(`Profile fetch failed: ${response.status}`);
  }
  return response.json();
}

export async function fetchStatus(): Promise<Status> {
  const response = await fetch("/status");
  if (!response.ok) {
    throw new Error(`Status fetch failed: ${response.status}`);
  }
  return response.json();
}

export async function uploadFile(file: File): Promise<void> {
  const form = new FormData();
  form.append("file", file);
  const response = await fetch("/ingest", { method: "POST", body: form });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Upload failed: ${response.status}`);
  }
}
