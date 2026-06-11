# Changelog

All notable changes to lai. Format: [Keep a Changelog](https://keepachangelog.com).
Rule: every `VERSION` bump in `laicore/core.py` adds an entry here - `lai update`
shows users exactly these entries when offering an update.

## [0.13.0] - 2026-06-11

### Changed
- `lai go` no longer downloads models automatically. It sets up the
  engine, wiring, and dashboard, then hands the model choice to YOU:
  review/change the picks in the dashboard (or `lai set`) and start the
  download yourself. Nothing heavy lands on disk without your say-so.

### Added
- Hugging Face token ask before downloads: `lai models` (terminal) and
  the dashboard's Download button both offer to save a free HF token
  when none is set - with a skip option. Tokens go to gitignored
  `state/secrets.json` with owner-only permissions, never the repo.
- `POST /api/hftoken` dashboard endpoint; `/api/downloads` now reports
  `has_hftoken` so the UI knows whether to ask.

## [0.12.0] - 2026-06-11

### Added
- `lai path`: puts `lai` on your PATH so it runs from any folder in any
  terminal (Windows user PATH + change broadcast; `~/.local/bin/lai`
  launcher and `.bashrc`/`.zshrc` on Linux/macOS). Installers run it
  automatically.
- `lai.cmd`: `lai` now works in plain cmd.exe too (cmd cannot execute
  `.ps1` files - it was opening them in an editor).
- Installers install missing prerequisites instead of just warning:
  Python/Git via winget on Windows, apt/dnf/pacman/zypper/brew on
  Linux/macOS; both end with a clear "open a new terminal, type
  `lai go`, dashboard at `http://localhost:8090`" message.
- `assets/icon.ico` + Desktop/Start-Menu shortcuts now carry the lai
  icon; `lai vscode` derives its install folder from package.json.

### Security
- Dashboard API hardening: cross-origin POST guard (localhost-CSRF),
  request paths confined to home/workspace/registered projects
  (`workspace_roots` in `state/settings.json` extends the allowlist),
  `secrets.json` written owner-only (0600), least-privilege CI workflow
  permissions, strict skill-name validation. Documented in
  docs/01-architecture.md "Security model".

## [0.11.0] - 2026-06-11

### Added
- Bulletproof downloads for slow/unstable networks: native ranged-HTTP
  downloader (byte-true resume across stalls, kills, reboots) as the
  primary path, stall watchdog, single-download mutex, stale-lock
  cleanup, `lai mirror` speed-tests and mirror rotation between retries.
- `lai doctor`: full diagnosis + support zip (logs + state, no secrets).
- Testing across the project: 36 Python tests (planning kernel, parsers,
  catalog integrity, dashboard API integration, repo hygiene), 9 Vitest
  dashboard tests (i18n parity/RTL, api client), 9 extension tests;
  `lai selftest`; CI runs all suites on three OSes.
- VS Code extension 0.3.0: Claude-Code-style "Local AI Chat" sidebar
  (streaming, add-selection context, insert code into editor) +
  Marketplace publish pipeline (publish.ps1, release-vscode workflow).
- Skills 9 -> 14: performance, a11y, refactor, browser (Playwright MCP),
  security-scan (Semgrep MCP); `lai skill new` creates custom skills
  (hand-written or model-drafted), globally or inside a project.
- Models 13 -> 17: Gemma 4 (26B-A4B, 12B), Kimi-Linear-48B-A3B
  (long-context champion), LFM2.5-1.2B (new cpu-min default),
  DeepSeek V4-Flash (watch). Stacks 15 -> 21: vue-app, static-site,
  python-game, godot-game, astro-site, expo-app (+ game use case).
- Dashboard: Home chat streams token-by-token; honest download progress
  (dead chunks excluded); truthful Start/Download buttons (409 on no-op).
- `lai docs add` uses docling when installed (layout/tables, docx/pptx).

### Fixed
- Stale pids no longer dead-end `lai start`; concurrent downloads
  impossible; per-session .incomplete restarts eliminated; changelog
  version comparison is numeric.

## [0.10.0] - 2026-06-09

### Added
- `lai update`: differential self-update over git (fetch/pull moves only
  changed files - no separate update server). Shows the changelog delta
  before applying; `--policy ask|auto|never` controls behavior
  (auto also applies during scheduled `lai refresh` runs); `--list` shows
  versions, `--to <version>` switches to any tagged release and back.
- `lai refresh`: scheduled discovery of new models + catalog updates with
  native OS notifications (Windows toast / notify-send / osascript).
- `lai skill new <name> [--ai "description"] [--project <path>]`: create
  your own skills - hand-written or drafted by your local model; project
  skills live in `.lai/skills/` and travel with the repo.
- Skills: debug (scientific debugging), security (review checklist),
  docs (docs-first answers) - 9 built-in skills total.
- Dashboard in three languages: English, Persian, Arabic - full RTL
  support; code, ports, and model ids stay LTR.
- Stacks: vue-app, static-site, python-game, godot-game (+ `game` use case).
- Catalog: Gemma 4 (26B-A4B, 12B), DeepSeek V4-Flash (verify), corrected
  Qwen3-Coder-Next repo (public), refreshed cloud offers.

## [0.9.3] - 2026-06-01

### Added
- Vue 3 + TypeScript dashboard (served compiled; legacy fallback kept).
- Configurable ports with conflict auto-fix (`lai ports check --fix`).
- Cloud per-model control: live model lists with prices, per-provider
  default model + params, token-lean defaults.
- Terminal progress bars for all downloads; smallest-models-first order.
- `lai go` beginner mode + dashboard Home screen with built-in chat.
- `lai hftoken`; HF token-aware downloads.

## [0.9.2] - 2026-05-18

### Changed
- lai.py split into the `laicore/` package (core/stack/work/projects/
  webui/cli) via AST-verbatim refactor.

### Added
- TypeScript VS Code extension + `lai vscode` installer; dashboard panel
  inside VS Code; OS shortcuts; project icon and banner.

## [0.9.1] - 2026-05-11

### Added
- Project rename to lai. Cloud fallbacks (OpenRouter/OpenAI/Anthropic),
  project memory (.lai/memory.md), 15 project stacks, swap-aware defaults.

## [0.9.0] - 2026-05-10

### Added
- Initial public layout: hardware catalog + planner, llama.cpp/llama-swap
  runtime, projects + gate, skills, git AI, docs RAG, team server mode,
  benchmarks and auto-tuning, installers, CI.
