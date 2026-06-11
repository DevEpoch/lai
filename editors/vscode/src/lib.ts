// Pure helpers - unit-tested without the vscode module.
export interface FsLike {
  exists(p: string): boolean;
  read(p: string): string;
}

export function findLaiHome(candidates: (string | undefined)[],
                            fs: FsLike, join: (...p: string[]) => string,
                            ): string | null {
  for (const c of candidates) {
    if (c && fs.exists(join(c, "lai.py"))) return c;
  }
  return null;
}

export function portFromStateJson(text: string | null, name: string,
                                  fallback: number): number {
  if (!text) return fallback;
  try {
    const data = JSON.parse(text) as Record<string, unknown>;
    const v = data[name];
    return typeof v === "number" && v > 0 && v < 65536 ? v : fallback;
  } catch {
    return fallback;
  }
}

export function apiKeyFromSecrets(text: string | null): string | null {
  if (!text) return null;
  try {
    const data = JSON.parse(text) as { api_key?: string };
    return data.api_key ?? null;
  } catch {
    return null;
  }
}

/** Extract the last fenced code block from a chat reply. */
export function lastCodeBlock(markdown: string): string | null {
  const matches = [...markdown.matchAll(/```[^\n]*\n([\s\S]*?)```/g)];
  return matches.length ? matches[matches.length - 1][1] : null;
}

/** Parse one SSE line from an OpenAI-compatible stream into a token. */
export function sseToken(line: string): string | null {
  const t = line.trim();
  if (!t.startsWith("data:")) return null;
  const data = t.slice(5).trim();
  if (data === "[DONE]") return null;
  try {
    const j = JSON.parse(data) as
      { choices?: { delta?: { content?: string } }[] };
    return j.choices?.[0]?.delta?.content ?? null;
  } catch {
    return null;
  }
}
