# Changelog

All notable changes to lai. Format: [Keep a Changelog](https://keepachangelog.com).
Rule: every `VERSION` bump in `laicore/core.py` adds an entry here - `lai update`
shows users exactly these entries when offering an update.

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
