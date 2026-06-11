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
exports.activate = activate;
exports.deactivate = deactivate;
// Local AI Env (lai) - VS Code companion, TypeScript source.
// Build: npm install && npx tsc -p .   (or simply: `lai vscode`)
const vscode = __importStar(require("vscode"));
const fs = __importStar(require("fs"));
const path = __importStar(require("path"));
const os = __importStar(require("os"));
function dashboardUrl() {
    // respect a relocated UI port (lai ports set ui <n>)
    const home = laiHome();
    if (home) {
        try {
            const p = JSON.parse(fs.readFileSync(path.join(home, "state", "ports.json"), "utf-8"));
            if (p.ui)
                return `http://127.0.0.1:${p.ui}`;
        }
        catch { /* defaults below */ }
    }
    return "http://127.0.0.1:8090";
}
function laiHome() {
    const candidates = [
        vscode.workspace.getConfiguration("lai").get("home"),
        process.env.LAI_HOME,
        ...(vscode.workspace.workspaceFolders ?? []).map(f => f.uri.fsPath),
        path.join(os.homedir(), "lai"),
        path.join(os.homedir(), "local-ai-env"),
        "D:\\vibe-coding",
    ];
    for (const c of candidates) {
        if (c && fs.existsSync(path.join(c, "lai.py")))
            return c;
    }
    return null;
}
function runInTerminal(args, cwd) {
    const home = laiHome();
    if (!home) {
        void vscode.window.showErrorMessage("local-ai-env not found - set the 'lai.home' setting to the folder containing lai.py.");
        return;
    }
    const term = vscode.window.createTerminal({ name: "lai", cwd: cwd ?? home });
    term.show();
    const py = process.platform === "win32" ? "python" : "python3";
    term.sendText(`${py} "${path.join(home, "lai.py")}" ${args}`);
}
function projectDir() {
    const ws = vscode.workspace.workspaceFolders;
    return ws && ws.length ? ws[0].uri.fsPath : undefined;
}
const ACTIONS = [
    { label: "$(layout) Dashboard Panel (inside VS Code)", action: "panel" },
    { label: "$(dashboard) Open Dashboard (browser)", action: "dashboard" },
    { label: "$(play) Start Stack", action: "start" },
    { label: "$(debug-stop) Stop Stack", action: "stop" },
    { label: "$(pulse) Status", action: "status" },
    { label: "$(shield) Gate Current Project", action: "gate" },
    { label: "$(git-pull-request) AI Review My Changes", action: "review" },
    { label: "$(comment-discussion) Chat", action: "chat" },
    { label: "$(beaker) Validate End-to-End", action: "validate" },
    { label: "$(dashboard) Quality Benchmark", action: "bench" },
    { label: "$(tools) Full Setup", action: "setup" },
];
function openPanel() {
    const panel = vscode.window.createWebviewPanel("laiDashboard", "lai dashboard", vscode.ViewColumn.Beside, { enableScripts: true, retainContextWhenHidden: true });
    panel.webview.html = `<!DOCTYPE html><html><head><style>
      html,body,iframe{margin:0;padding:0;height:100%;width:100%;border:0}
    </style></head><body>
    <iframe src="${dashboardUrl()}" allow="clipboard-read; clipboard-write"></iframe>
    </body></html>`;
}
function run(action) {
    switch (action) {
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
                setTimeout(() => vscode.env.openExternal(vscode.Uri.parse(dashboardUrl())), 2500);
            });
            break;
        case "start":
            runInTerminal("start");
            break;
        case "stop":
            runInTerminal("stop");
            break;
        case "status":
            runInTerminal("status");
            break;
        case "gate":
            runInTerminal(`gate "${projectDir() ?? "."}"`);
            break;
        case "review":
            runInTerminal("git review", projectDir());
            break;
        case "chat":
            runInTerminal("chat", projectDir());
            break;
        case "validate":
            runInTerminal("validate");
            break;
        case "bench":
            runInTerminal("bench --quality");
            break;
        case "setup":
            runInTerminal("setup");
            break;
    }
}
function activate(context) {
    for (const a of ACTIONS) {
        context.subscriptions.push(vscode.commands.registerCommand(`lai.${a.action}`, () => run(a.action)));
    }
    context.subscriptions.push(vscode.commands.registerCommand("lai.menu", async () => {
        const pick = await vscode.window.showQuickPick(ACTIONS, {
            placeHolder: "Local AI Env",
        });
        if (pick)
            run(pick.action);
    }));
    const item = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 90);
    item.text = "$(circuit-board) lai";
    item.tooltip = "Local AI Env - click for actions";
    item.command = "lai.menu";
    item.show();
    context.subscriptions.push(item);
}
function deactivate() {
    // nothing to clean up
}
