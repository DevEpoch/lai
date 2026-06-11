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

/** Route a chat request to the best local role - the user asks, lai picks
 *  the model. Heuristic, offline, instant. Order matters: explicit coding
 *  verbs win, then reasoning/translation verbs, then code-looking input. */
export function pickRole(text: string): "coder" | "thinker" {
  const t = text.toLowerCase();
  const code = /\b(write|fix|refactor|implement|debug|bug|error|exception|test|function|class|method|regex|sql|api|compile|build|rename|optimi[sz]e code|stack ?trace)\b/;
  const think = /\b(why|explain|plan|design|architecture|compare|choose|review|trade-?offs?|translate|summari[sz]e|document|describe|brainstorm|idea|teach|learn)\b/;
  const thinkFaAr = /ترجمه|توضیح|چرا|خلاصه|طراحی|مقایسه|اشرح|لماذا|ترجم|لخص|قارن/;
  if (code.test(t) || /```/.test(text)) return "coder";
  if (think.test(t) || thinkFaAr.test(text)) return "thinker";
  return "coder";
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
