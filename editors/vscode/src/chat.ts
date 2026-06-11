// lai Chat - a Claude-Code-style sidebar: streaming chat on YOUR local
// models, with editor context and insert-into-editor.
import * as vscode from "vscode";
import * as fs from "fs";
import * as path from "path";
import { apiKeyFromSecrets, lastCodeBlock, pickRole, portFromStateJson,
  sseToken } from "./lib";

interface Msg { role: "system" | "user" | "assistant"; content: string }
interface CtxBlock { label: string; text: string }

const SKIP_DIRS = new Set([".git", "node_modules", "dist", "out", "build",
  ".venv", "__pycache__", ".idea", ".vscode", "target", "bin", "obj"]);
const BINARY_EXT = new Set([".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf",
  ".zip", ".gz", ".exe", ".dll", ".so", ".dylib", ".gguf", ".woff2",
  ".lock", ".bin"]);
const MAX_FILE_BYTES = 24_000;   // per file
const MAX_TOTAL_BYTES = 64_000;  // per attach action
const MAX_FILES = 40;

export class LaiChatProvider implements vscode.WebviewViewProvider {
  public static readonly viewId = "lai.chatView";
  private view?: vscode.WebviewView;
  private msgs: Msg[] = [];
  private ctx: CtxBlock[] = [];

  constructor(private laiHome: () => string | null) {}

  private postCtx(): void {
    this.view?.webview.postMessage({
      type: "context", label: this.ctx.map(c => c.label).join(", "),
    });
  }

  addSelection(): void {
    const ed = vscode.window.activeTextEditor;
    if (!ed) return;
    const sel = ed.selection.isEmpty
      ? ed.document.getText()
      : ed.document.getText(ed.selection);
    const rel = vscode.workspace.asRelativePath(ed.document.uri);
    const fence = "```";
    this.ctx.push({ label: `${rel} (${sel.split("\n").length} lines)`,
      text: `--- ${rel} ---\n${fence}\n${sel}\n${fence}` });
    this.postCtx();
    this.view?.show?.(true);
  }

  private readFileBlock(file: string, rel: string,
                        budget: { left: number }): string | null {
    if (BINARY_EXT.has(path.extname(file).toLowerCase())) return null;
    let stat: fs.Stats;
    try { stat = fs.statSync(file); } catch { return null; }
    if (stat.size > MAX_FILE_BYTES || stat.size > budget.left) {
      return `--- ${rel} (${stat.size} bytes, too big - skipped) ---`;
    }
    try {
      const body = fs.readFileSync(file, "utf-8");
      if (body.includes("\u0000")) return null; // binary masquerading
      budget.left -= stat.size;
      const fence = "```";
      return `--- ${rel} ---\n${fence}\n${body}\n${fence}`;
    } catch { return null; }
  }

  async addPath(kind: "file" | "folder"): Promise<void> {
    const picked = await vscode.window.showOpenDialog({
      canSelectFiles: kind === "file", canSelectFolders: kind === "folder",
      canSelectMany: kind === "file",
      openLabel: `Add ${kind} to chat`,
    });
    if (!picked?.length) return;
    const budget = { left: MAX_TOTAL_BYTES };
    for (const uri of picked) {
      const p = uri.fsPath;
      const rel = vscode.workspace.asRelativePath(uri);
      if (kind === "file") {
        const block = this.readFileBlock(p, rel, budget);
        if (block) this.ctx.push({ label: rel, text: block });
        continue;
      }
      const blocks: string[] = [];
      let count = 0;
      const walk = (dir: string, relDir: string): void => {
        if (count >= MAX_FILES || budget.left <= 0) return;
        let names: string[] = [];
        try { names = fs.readdirSync(dir); } catch { return; }
        for (const n of names.sort()) {
          if (count >= MAX_FILES || budget.left <= 0) return;
          const full = path.join(dir, n);
          const relPath = relDir ? `${relDir}/${n}` : n;
          let st: fs.Stats;
          try { st = fs.statSync(full); } catch { continue; }
          if (st.isDirectory()) {
            if (!SKIP_DIRS.has(n) && !n.startsWith(".")) walk(full, relPath);
          } else {
            const block = this.readFileBlock(full, `${rel}/${relPath}`,
                                             budget);
            if (block) { blocks.push(block); count++; }
          }
        }
      };
      walk(p, "");
      this.ctx.push({ label: `${rel}/ (${count} files)`,
        text: blocks.join("\n\n") });
    }
    this.postCtx();
    this.view?.show?.(true);
  }

  resolveWebviewView(view: vscode.WebviewView): void {
    this.view = view;
    view.webview.options = { enableScripts: true };
    view.webview.html = HTML;
    view.webview.onDidReceiveMessage(async (m: { type: string;
        text?: string; model?: string; code?: string }) => {
      if (m.type === "send" && m.text) await this.send(m.text, m.model);
      if (m.type === "insert" && m.code !== undefined) this.insert(m.code);
      if (m.type === "clear") { this.msgs = []; this.ctx = []; }
      if (m.type === "addfile") await this.addPath("file");
      if (m.type === "addfolder") await this.addPath("folder");
      if (m.type === "clearctx") { this.ctx = []; this.postCtx(); }
    });
  }

  private insert(code: string): void {
    const ed = vscode.window.activeTextEditor;
    if (!ed) {
      void vscode.window.showWarningMessage("No active editor to insert into.");
      return;
    }
    void ed.edit(b => b.insert(ed.selection.active, code));
  }

  private endpoint(): { url: string; agent: string; key: string | null } {
    const home = this.laiHome();
    const readState = (f: string): string | null => {
      try {
        return home ? fs.readFileSync(
          path.join(home, "state", f), "utf-8") : null;
      } catch { return null; }
    };
    const port = portFromStateJson(readState("ports.json"), "swap", 8080);
    const uiPort = portFromStateJson(readState("ports.json"), "ui", 8090);
    return { url: `http://127.0.0.1:${port}/v1/chat/completions`,
             agent: `http://127.0.0.1:${uiPort}/api/agent`,
             key: apiKeyFromSecrets(readState("secrets.json")) };
  }

  /** Claude-Code-style path: the lai agent loop (skills auto-matched,
   *  tools used when the model needs them) against the open workspace. */
  private async sendAgent(ws: string, text: string, model: string,
                          post: (m: unknown) => void): Promise<void> {
    const { agent, key } = this.endpoint();
    let reply = "";
    try {
      const res = await fetch(agent, {
        method: "POST",
        headers: { "Content-Type": "application/json",
          ...(key ? { Authorization: `Bearer ${key}` } : {}) },
        body: JSON.stringify({ text, path: ws, model,
          history: this.msgs.slice(0, -1) }),
      });
      if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let buf = "";
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const lines = buf.split("\n");
        buf = lines.pop() ?? "";
        for (const line of lines) {
          if (!line.startsWith("data:")) continue;
          let ev: { type: string; name?: string; text?: string;
                    args?: unknown };
          try { ev = JSON.parse(line.slice(5)); } catch { continue; }
          if (ev.type === "skill") post({ type: "note",
            text: `* skill: ${ev.name}` });
          if (ev.type === "tool") post({ type: "note",
            text: `> ${ev.name} ${JSON.stringify(ev.args ?? {})
              .slice(0, 100)}` });
          if (ev.type === "text" && ev.text) {
            reply += ev.text + "\n";
            post({ type: "delta", text: ev.text + "\n" });
          }
          if (ev.type === "error") throw new Error(ev.text);
        }
      }
      this.msgs.push({ role: "assistant", content: reply });
      post({ type: "end", code: lastCodeBlock(reply) });
    } catch {
      post({ type: "error", text:
        "lai agent not reachable - run `lai ui` + `lai start` first." });
    }
  }

  private async send(text: string, model = "auto"): Promise<void> {
    const role = (!model || model === "auto") ? pickRole(text) : model;
    const ctxText = this.ctx.map(c => c.text).join("\n\n");
    const ctxLabels = this.ctx.map(c => c.label).join(", ");
    this.ctx = [];
    const content = ctxText ? `${ctxText}\n\n${text}` : text;
    this.msgs.push({ role: "user", content });
    if (this.msgs.length > 24) this.msgs = this.msgs.slice(-20);
    const post = (m: unknown) => this.view?.webview.postMessage(m);
    post({ type: "user",
           text: ctxLabels ? `[+] ${ctxLabels}\n${text}` : text });
    post({ type: "begin", model: role });
    const ws = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
    if (ws) { await this.sendAgent(ws, content, role, post); return; }
    const { url, key } = this.endpoint();
    let reply = "";
    try {
      const res = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(key ? { Authorization: `Bearer ${key}` } : {}),
        },
        body: JSON.stringify({
          model: role, stream: true, max_tokens: 4096, temperature: 0.3,
          messages: [{
            role: "system",
            content: "You are a concise expert pair-programmer inside " +
              "VS Code. Prefer code blocks. State assumptions explicitly.",
          }, ...this.msgs],
        }),
      });
      if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let buf = "";
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const lines = buf.split("\n");
        buf = lines.pop() ?? "";
        for (const line of lines) {
          const tok = sseToken(line);
          if (tok) { reply += tok; post({ type: "delta", text: tok }); }
        }
      }
      this.msgs.push({ role: "assistant", content: reply });
      post({ type: "end", code: lastCodeBlock(reply) });
    } catch {
      post({ type: "error", text:
        "Your local AI is not reachable - run `lai start` " +
        "(or wait for the model download to finish)." });
    }
  }
}

const HTML = /* html */ `<!DOCTYPE html><html><head><style>
  body { font: 13px var(--vscode-font-family); color: var(--vscode-foreground);
    margin: 0; padding: 8px; display: flex; flex-direction: column;
    height: 100vh; box-sizing: border-box; }
  #log { flex: 1; overflow-y: auto; display: flex; flex-direction: column;
    gap: 6px; padding-bottom: 8px; }
  .m { border-radius: 8px; padding: 6px 10px; white-space: pre-wrap;
    word-break: break-word; max-width: 95%; }
  .u { align-self: flex-end; background: var(--vscode-button-background);
    color: var(--vscode-button-foreground); }
  .a { align-self: flex-start; background: var(--vscode-editorWidget-background);
    border: 1px solid var(--vscode-widget-border, transparent); }
  .err { color: var(--vscode-errorForeground); }
  .t { opacity: .65; font-size: 11px; padding: 2px 10px; }
  #ctx { font-size: 11px; opacity: .7; min-height: 14px; }
  #bar { display: flex; gap: 6px; }
  textarea { flex: 1; resize: none; height: 52px;
    background: var(--vscode-input-background);
    color: var(--vscode-input-foreground);
    border: 1px solid var(--vscode-input-border, transparent);
    border-radius: 6px; padding: 6px; font: inherit; }
  button, select { background: var(--vscode-button-secondaryBackground);
    color: var(--vscode-button-secondaryForeground); border: 0;
    border-radius: 6px; padding: 4px 10px; cursor: pointer; font: inherit; }
  #send { background: var(--vscode-button-background);
    color: var(--vscode-button-foreground); }
  #tools { display: flex; gap: 6px; margin-top: 6px; align-items: center; }
</style></head><body>
  <div id="log"><div class="m a">Hi! I'm your local AI. Ask me anything about
your code - use the "lai: Add Selection to Chat" command to give me context.
Nothing leaves this machine.</div></div>
  <div id="ctx"></div>
  <div id="bar"><textarea id="in" placeholder="Ask your local AI…"></textarea>
    <button id="send">▶</button></div>
  <div id="tools">
    <select id="model" title="auto: lai picks the right model for each task">
      <option value="auto" selected>auto</option>
      <option value="coder">coder</option>
      <option value="thinker">thinker</option>
      <option value="or:">or: (cloud default)</option></select>
    <button id="addf" title="Attach a file">+ file</button>
    <button id="addd" title="Attach a folder">+ folder</button>
    <button id="ins" disabled>Insert last code</button>
    <button id="clr">Clear</button>
  </div>
<script>
  const vs = acquireVsCodeApi();
  const log = document.getElementById("log");
  const input = document.getElementById("in");
  const ins = document.getElementById("ins");
  let cur = null, lastCode = null;
  function add(cls, text) {
    const d = document.createElement("div");
    d.className = "m " + cls; d.textContent = text;
    log.appendChild(d); log.scrollTop = log.scrollHeight; return d;
  }
  function send() {
    const t = input.value.trim(); if (!t) return;
    input.value = "";
    vs.postMessage({ type: "send", text: t,
      model: document.getElementById("model").value });
  }
  document.getElementById("send").onclick = send;
  input.addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
  });
  ins.onclick = () => lastCode && vs.postMessage({ type: "insert", code: lastCode });
  document.getElementById("addf").onclick = () => vs.postMessage({ type: "addfile" });
  document.getElementById("addd").onclick = () => vs.postMessage({ type: "addfolder" });
  document.getElementById("clr").onclick = () => {
    vs.postMessage({ type: "clear" }); log.innerHTML = ""; };
  window.addEventListener("message", e => {
    const m = e.data;
    if (m.type === "user") add("u", m.text);
    if (m.type === "context")
      document.getElementById("ctx").textContent =
        m.label ? "context: " + m.label : "";
    if (m.type === "begin") {
      cur = add("a", "");
      document.getElementById("ctx").textContent = "model: " + m.model;
    }
    if (m.type === "delta" && cur) {
      cur.textContent += m.text; log.scrollTop = log.scrollHeight; }
    if (m.type === "end") {
      document.getElementById("ctx").textContent = "";
      lastCode = m.code; ins.disabled = !m.code; cur = null; }
    if (m.type === "note") add("a t", m.text);
    if (m.type === "error") { add("a err", m.text); cur = null; }
  });
</script></body></html>`;
