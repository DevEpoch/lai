// Local AI Env (lai) - VS Code companion, TypeScript source.
// Build: npm install && npx tsc -p .   (or simply: `lai vscode`)
import * as vscode from "vscode";
import * as fs from "fs";
import * as path from "path";
import * as os from "os";
import { findLaiHome, portFromStateJson } from "./lib";
import { LaiChatProvider } from "./chat";

function laiHome(): string | null {
  return findLaiHome(
    [
      vscode.workspace.getConfiguration("lai").get<string>("home"),
      process.env.LAI_HOME,
      ...(vscode.workspace.workspaceFolders ?? []).map(f => f.uri.fsPath),
      path.join(os.homedir(), "lai"),
      path.join(os.homedir(), "local-ai-env"),
      "D:\\vibe-coding",
    ],
    { exists: p => fs.existsSync(p), read: p => fs.readFileSync(p, "utf-8") },
    (...p) => path.join(...p));
}

function dashboardUrl(): string {
  const home = laiHome();
  let text: string | null = null;
  try {
    text = home
      ? fs.readFileSync(path.join(home, "state", "ports.json"), "utf-8")
      : null;
  } catch { /* defaults */ }
  return `http://127.0.0.1:${portFromStateJson(text, "ui", 8090)}`;
}

function runInTerminal(args: string, cwd?: string): void {
  const home = laiHome();
  if (!home) {
    void vscode.window.showErrorMessage(
      "lai not found - set the 'lai.home' setting to the folder containing lai.py.");
    return;
  }
  const term = vscode.window.createTerminal({ name: "lai", cwd: cwd ?? home });
  term.show();
  const py = process.platform === "win32" ? "python" : "python3";
  term.sendText(`${py} "${path.join(home, "lai.py")}" ${args}`);
}

function projectDir(): string | undefined {
  const ws = vscode.workspace.workspaceFolders;
  return ws && ws.length ? ws[0].uri.fsPath : undefined;
}

interface LaiAction extends vscode.QuickPickItem {
  action: string;
}

const ACTIONS: LaiAction[] = [
  { label: "$(comment-discussion) Chat Sidebar (local AI)", action: "chatview" },
  { label: "$(layout) Dashboard Panel (inside VS Code)", action: "panel" },
  { label: "$(dashboard) Open Dashboard (browser)", action: "dashboard" },
  { label: "$(play) Start Stack", action: "start" },
  { label: "$(debug-stop) Stop Stack", action: "stop" },
  { label: "$(pulse) Status", action: "status" },
  { label: "$(shield) Gate Current Project", action: "gate" },
  { label: "$(git-pull-request) AI Review My Changes", action: "review" },
  { label: "$(terminal) Chat (terminal)", action: "chat" },
  { label: "$(beaker) Validate End-to-End", action: "validate" },
  { label: "$(dashboard) Quality Benchmark", action: "bench" },
  { label: "$(tools) Full Setup", action: "setup" },
];

function openPanel(): void {
  const panel = vscode.window.createWebviewPanel(
    "laiDashboard", "lai dashboard", vscode.ViewColumn.Beside,
    { enableScripts: true, retainContextWhenHidden: true });
  panel.webview.html = `<!DOCTYPE html><html><head><style>
      html,body,iframe{margin:0;padding:0;height:100%;width:100%;border:0}
    </style></head><body>
    <iframe src="${dashboardUrl()}" allow="clipboard-read; clipboard-write"></iframe>
    </body></html>`;
}

function run(action: string): void {
  switch (action) {
    case "chatview":
      void vscode.commands.executeCommand("lai.chatView.focus");
      break;
    case "panel":
      fetch(`${dashboardUrl()}/api/overview`)
        .then(() => openPanel())
        .catch(() => {
          runInTerminal("ui");
          setTimeout(openPanel, 2500);
        });
      break;
    case "dashboard":
      fetch(`${dashboardUrl()}/api/overview`)
        .then(() => vscode.env.openExternal(vscode.Uri.parse(dashboardUrl())))
        .catch(() => {
          runInTerminal("ui");
          setTimeout(() =>
            vscode.env.openExternal(vscode.Uri.parse(dashboardUrl())), 2500);
        });
      break;
    case "start": runInTerminal("start"); break;
    case "stop": runInTerminal("stop"); break;
    case "status": runInTerminal("status"); break;
    case "gate": runInTerminal(`gate "${projectDir() ?? "."}"`); break;
    case "review": runInTerminal("git review", projectDir()); break;
    case "chat": runInTerminal("chat", projectDir()); break;
    case "validate": runInTerminal("validate"); break;
    case "bench": runInTerminal("bench --quality"); break;
    case "setup": runInTerminal("setup"); break;
  }
}

export function activate(context: vscode.ExtensionContext): void {
  const chat = new LaiChatProvider(laiHome);
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider(LaiChatProvider.viewId, chat,
      { webviewOptions: { retainContextWhenHidden: true } }));
  context.subscriptions.push(
    vscode.commands.registerCommand("lai.chatTab", () => chat.openTab()));
  context.subscriptions.push(
    vscode.commands.registerCommand("lai.addSelection",
      () => chat.addSelection()));

  for (const a of ACTIONS) {
    context.subscriptions.push(
      vscode.commands.registerCommand(`lai.${a.action}`, () => run(a.action)));
  }
  context.subscriptions.push(
    vscode.commands.registerCommand("lai.menu", async () => {
      const pick = await vscode.window.showQuickPick(ACTIONS, {
        placeHolder: "Local AI Env",
      });
      if (pick) run(pick.action);
    }));

  const item = vscode.window.createStatusBarItem(
    vscode.StatusBarAlignment.Left, 90);
  item.text = "$(circuit-board) lai";
  item.tooltip = "Local AI Env - click for actions";
  item.command = "lai.menu";
  item.show();
  context.subscriptions.push(item);
}

export function deactivate(): void {
  // nothing to clean up
}
