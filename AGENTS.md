# AGENTS.md

## Project

lai - the local AI programming environment. A stdlib-only Python package
(`laicore/`, entry `lai.py`) that plans, installs, and runs a fully local AI
coding stack. Read [docs/llm-reference.md](docs/llm-reference.md) first for
the complete command/file/API surface.

## Build / test / run

```bash
python -m compileall -q laicore lai.py        # compile check (the CI gate)
python -c "import json,glob; [json.load(open(f, encoding='utf-8')) for f in glob.glob('config/*.json')]"
python lai.py catalog && python lai.py choices  # smoke
cd ui && npm run build                        # dashboard (Vue 3 + TS -> ui/dist, committed)
cd editors/vscode && npx tsc -p .             # extension (TS -> out/, committed)
```

Agents: run the compile check and the json check before declaring a task done.

## Conventions

- Logic lives in `laicore/` (core kernel <- stack ops <- work/projects <- webui <- cli);
  knowledge lives in `config/catalog.json`. Prefer catalog edits over code.
- Python: stdlib only (sole soft exception: lazy `huggingface_hub`). 79-col
  style, no type annotations in laicore (matches existing code).
- Anything that installs/downloads/overwrites must go through `confirm()`.
- Machine-local files go under `state/` (gitignored) - never `config/`.
- Where there is JavaScript, write TypeScript (ui/, editors/vscode). The one
  exception is documented: config/ui.html legacy fallback.
- Cross-module: modules star-import lower layers; underscore names are NOT
  star-exported - import them explicitly (see webui.py header).

## Architecture map

- `laicore/core.py` - paths/console/http/secrets/ports/hardware/planning/LLM primitives
- `laicore/stack.py` - engines, models, config gen, services, bench/tune, team mode, cloud cmd
- `laicore/work.py` - skills, git AI, chat REPL, docs RAG
- `laicore/projects.py` - lai new + lai gate; `laicore/webui.py` - dashboard API
- Decisions with rationale: `docs/01-architecture.md`, `docs/06-hardware-catalog.md`

## Boundaries for agents

- Never commit anything under `state/`, `models/`, `tools/` (contains secrets/binaries).
- Do not bump model repos in the catalog without `lai catalog --verify` passing.
- Commits: no AI attribution trailers; author is the repo's configured user.
