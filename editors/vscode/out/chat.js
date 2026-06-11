"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.LaiChatProvider = void 0;
// lai Chat - a Claude-Code-style sidebar: streaming chat on YOUR local
// models, with editor context and insert-into-editor.
const vscode = __importStar(require("vscode"));
const fs = __importStar(require("fs"));
const path = __importStar(require("path"));
const lib_1 = require("./lib");
const SKIP_DIRS = new Set([".git", "node_modules", "dist", "out", "build",
    ".venv", "__pycache__", ".idea", ".vscode", "target", "bin", "obj"]);
const BINARY_EXT = new Set([".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf",
    ".zip", ".gz", ".exe", ".dll", ".so", ".dylib", ".gguf", ".woff2",
    ".lock", ".bin"]);
const MAX_FILE_BYTES = 24_000; // per file
const MAX_TOTAL_BYTES = 64_000; // per attach action
const MAX_FILES = 40;
class LaiChatProvider {
    laiHome;
    static viewId = "lai.chatView";
    view;
    msgs = [];
    ctx = [];
    constructor(laiHome) {
        this.laiHome = laiHome;
    }
    postCtx() {
        this.view?.webview.postMessage({
            type: "context", label: this.ctx.map(c => c.label).join(", "),
        });
    }
    addSelection() {
        const ed = vscode.window.activeTextEditor;
        if (!ed)
            return;
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
    readFileBlock(file, rel, budget) {
        if (BINARY_EXT.has(path.extname(file).toLowerCase()))
            return null;
        let stat;
        try {
            stat = fs.statSync(file);
        }
        catch {
            return null;
        }
        if (stat.size > MAX_FILE_BYTES || stat.size > budget.left) {
            return `--- ${rel} (${stat.size} bytes, too big - skipped) ---`;
        }
        try {
            const body = fs.readFileSync(file, "utf-8");
            if (body.includes("\u0000"))
                return null; // binary masquerading
            budget.left -= stat.size;
            const fence = "```";
            return `--- ${rel} ---\n${fence}\n${body}\n${fence}`;
        }
        catch {
            return null;
        }
    }
    async addPath(kind) {
        const picked = await vscode.window.showOpenDialog({
            canSelectFiles: kind === "file", canSelectFolders: kind === "folder",
            canSelectMany: kind === "file",
            openLabel: `Add ${kind} to chat`,
        });
        if (!picked?.length)
            return;
        const budget = { left: MAX_TOTAL_BYTES };
        for (const uri of picked) {
            const p = uri.fsPath;
            const rel = vscode.workspace.asRelativePath(uri);
            if (kind === "file") {
                const block = this.readFileBlock(p, rel, budget);
                if (block)
                    this.ctx.push({ label: rel, text: block });
                continue;
            }
            const blocks = [];
            let count = 0;
            const walk = (dir, relDir) => {
                if (count >= MAX_FILES || budget.left <= 0)
                    return;
                let names = [];
                try {
                    names = fs.readdirSync(dir);
                }
                catch {
                    return;
                }
                for (const n of names.sort()) {
                    if (count >= MAX_FILES || budget.left <= 0)
                        return;
                    const full = path.join(dir, n);
                    const relPath = relDir ? `${relDir}/${n}` : n;
                    let st;
                    try {
                        st = fs.statSync(full);
                    }
                    catch {
                        continue;
                    }
                    if (st.isDirectory()) {
                        if (!SKIP_DIRS.has(n) && !n.startsWith("."))
                            walk(full, relPath);
                    }
                    else {
                        const block = this.readFileBlock(full, `${rel}/${relPath}`, budget);
                        if (block) {
                            blocks.push(block);
                            count++;
                        }
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
    resolveWebviewView(view) {
        this.view = view;
        view.webview.options = { enableScripts: true };
        view.webview.html = HTML;
        view.webview.onDidReceiveMessage(async (m) => {
            if (m.type === "send" && m.text)
                await this.send(m.text, m.model);
            if (m.type === "insert" && m.code !== undefined)
                this.insert(m.code);
            if (m.type === "clear") {
                this.msgs = [];
                this.ctx = [];
            }
            if (m.type === "addfile")
                await this.addPath("file");
            if (m.type === "addfolder")
                await this.addPath("folder");
            if (m.type === "clearctx") {
                this.ctx = [];
                this.postCtx();
            }
        });
    }
    insert(code) {
        const ed = vscode.window.activeTextEditor;
        if (!ed) {
            void vscode.window.showWarningMessage("No active editor to insert into.");
            return;
        }
        void ed.edit(b => b.insert(ed.selection.active, code));
    }
    endpoint() {
        const home = this.laiHome();
        const readState = (f) => {
            try {
                return home ? fs.readFileSync(path.join(home, "state", f), "utf-8") : null;
            }
            catch {
                return null;
            }
        };
        const port = (0, lib_1.portFromStateJson)(readState("ports.json"), "swap", 8080);
        return { url: `http://127.0.0.1:${port}/v1/chat/completions`,
            key: (0, lib_1.apiKeyFromSecrets)(readState("secrets.json")) };
    }
    async send(text, model = "auto") {
        const role = (!model || model === "auto") ? (0, lib_1.pickRole)(text) : model;
        const ctxText = this.ctx.map(c => c.text).join("\n\n");
        const ctxLabels = this.ctx.map(c => c.label).join(", ");
        this.ctx = [];
        const content = ctxText ? `${ctxText}\n\n${text}` : text;
        this.msgs.push({ role: "user", content });
        if (this.msgs.length > 24)
            this.msgs = this.msgs.slice(-20);
        const post = (m) => this.view?.webview.postMessage(m);
        post({ type: "user",
            text: ctxLabels ? `[+] ${ctxLabels}\n${text}` : text });
        post({ type: "begin", model: role });
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
            if (!res.ok || !res.body)
                throw new Error(`HTTP ${res.status}`);
            const reader = res.body.getReader();
            const dec = new TextDecoder();
            let buf = "";
            for (;;) {
                const { done, value } = await reader.read();
                if (done)
                    break;
                buf += dec.decode(value, { stream: true });
                const lines = buf.split("\n");
                buf = lines.pop() ?? "";
                for (const line of lines) {
                    const tok = (0, lib_1.sseToken)(line);
                    if (tok) {
                        reply += tok;
                        post({ type: "delta", text: tok });
                    }
                }
            }
            this.msgs.push({ role: "assistant", content: reply });
            post({ type: "end", code: (0, lib_1.lastCodeBlock)(reply) });
        }
        catch {
            post({ type: "error", text: "Your local AI is not reachable - run `lai start` " +
                    "(or wait for the model download to finish)." });
        }
    }
}
exports.LaiChatProvider = LaiChatProvider;
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
    if (m.type === "error") { add("a err", m.text); cur = null; }
  });
</script></body></html>`;
