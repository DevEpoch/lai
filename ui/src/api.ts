// Typed client for the lai localhost API.

export interface RoleEntry {
  model: string;
  mode: string;
  ctx?: number;
}

export interface Choices {
  tier: string;
  tier_label: string;
  engine: string;
  usecase?: string;
  catalog_version: string;
  hardware: {
    platform: string;
    vram_gb: number;
    ram_gb: number;
    gpus: { name: string }[];
  };
  roles: Record<string, RoleEntry | null>;
  targets?: { pp?: number; tg?: number };
}

export interface Overview {
  choices: Choices | null;
  usecases: Record<string, { label: string }>;
  stacks: Record<string, { label: string }>;
  skills: Record<string, string>;
  models_meta: Record<string, { disk_gb: number; why: string }>;
  versions: Record<string, string>;
  running: { download: boolean; bench: boolean };
  last_quality: { model: string; score: number; total: number; when: string } | null;
  logs: string[];
  remote: { host: string; port: number } | null;
  lai_version: string;
}

export interface ServiceStatus { name: string; up: boolean }
export interface DownloadItem { id: string; expected_gb: number; have_gb: number; done: boolean }
export interface PortRow { name: string; default: number; current: number; status: string }
export interface CloudProvider {
  id: string;
  prefix: string;
  has_key: boolean;
  default_model: string;
  params: Record<string, unknown>;
  recommended: { id: string; why: string }[];
}
export interface Project {
  name: string;
  path: string;
  stack: string;
  last_gate: { pass: number; warn: number; fail: number } | null;
}
export interface GateRow { item: string; status: string; detail: string }

export async function get<T>(path: string): Promise<T> {
  const r = await fetch(path);
  if (!r.ok) throw await r.json().catch(() => ({ error: r.statusText }));
  return r.json() as Promise<T>;
}

export async function post<T = { ok: boolean }>(path: string, body: unknown = {}): Promise<T> {
  const r = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw data;
  return data as T;
}
