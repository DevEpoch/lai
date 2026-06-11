# Local AI Env - VS Code extension

TypeScript companion for [lai](../../README.md). Adds a `lai` status-bar menu and
command-palette actions: **Dashboard Panel** (the full lai dashboard inside a VS Code
tab), browser dashboard, Start/Stop/Status, Gate Current Project, AI Review My
Changes, Chat, Validate, Quality Benchmark, Full Setup.

The agentic heavy lifting stays with **Roo Code** + **Continue** (configured by
`lai ide` / `lai new`); this extension puts lai itself one click away.

## Install (one command)

```text
lai vscode      # builds (npm install + tsc, first time only) and installs
                # into ~/.vscode/extensions - then: Developer: Reload Window
```

## Develop

```bash
cd editors/vscode
npm install
npx tsc -p .          # src/extension.ts -> out/extension.js
```

Source is TypeScript (`src/extension.ts`); the compiled `out/extension.js` is
committed so `lai vscode` works without Node on most machines. Package a shareable
.vsix with `npx @vscode/vsce package --allow-missing-repository`.

If `lai.py` is not auto-detected (workspace folder, `LAI_HOME`, `~/lai`), set the
`lai.home` setting.
