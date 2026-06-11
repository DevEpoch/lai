# lai - LLM Reference

Machine-oriented reference for AI assistants writing tutorials, integrations,
or automation around lai. Everything here is factual surface area; for design
rationale see docs/01 and docs/06.

## What lai is (one paragraph)

lai turns any developer machine into a fully local AI programming environment.
It detects hardware (GPU vendor, VRAM, RAM, OS), matches it against an
editable catalog of tiers, downloads the right open models (GGUF), runs them
behind one OpenAI-compatible endpoint (llama.cpp + llama-swap), configures IDE
agents and repo RAG, scaffolds projects whose AI config travels in git, and
verifies any machine against a project's requirements ("gate"). Cloud APIs are
optional, explicit-use-only fallbacks. Python 3.9+ stdlib only; approval is
asked before any install/download (`--yes` auto-approves).

## Invocation

```text
Windows:  .\lai.ps1 <command>     Linux/mac: ./lai.sh <command>
anywhere: python lai.py <command> [--yes]
```

## Command reference

| Command | Purpose |
| --- | --- |
| `go` | EASIEST PATH: one friendly approval, then everything (beginners) |
| `check` | hardware + dependency report with per-OS install hints |
| `refresh [--quiet] [--schedule daily\|weekly\|off]` | discover new HF models + catalog/self updates; OS notifications |
| `update [--check] [--policy ask\|auto\|never] [--list] [--to <ver>]` | git-based differential self-update with CHANGELOG delta |
| `selftest` | offline test suite (36 unittest cases incl. live API integration) |
| `doctor` | full diagnosis + support zip (logs + state, never secrets) |
| `mirror [--set URL]` | speed-test HF mirrors (catalog hf_mirrors); retries rotate mirrors |
| `storage [path] [--no-move]` | show/relocate the models directory; moves models, repoints downloads + config |
| `setup` | guided install: ports check -> plan -> engines -> models -> config -> IDE -> docker -> start |
| `plan [--use-case X] [--vram-gb N]` | detect hardware, match tier, apply use-case overlay, review/edit, save to state/choices.json |
| `choices` | show current per-role model selections + fitting alternatives |
| `set <role> <model\|none>` | change one role (roles: coder, thinker, vision, autocomplete, embeddings) |
| `catalog [--verify] [--update [--url U]]` | show the table; verify repos on HF; pull published catalog with diff+backup |
| `engines` | download llama.cpp + llama-swap release binaries for this OS/GPU |
| `models [--all]` | download chosen GGUFs (resumable, smallest first, HF token aware) |
| `config` | regenerate runtime configs from choices (state/llama-swap.generated.yaml etc.) |
| `start / stop / restart / status` | run the stack: side servers + llama-swap + the dashboard |
| `ui [--port N] [--no-browser]` | serve the Vue dashboard (auto-started by `start`) |
| `validate` | end-to-end smoke tests: chat, tool calls, FIM, embeddings, RAG services |
| `bench [--quality] [--model M]` | tokens/sec vs tier targets; or 12-task solving suite |
| `tune` | timed llama-server trials (offload depth / KV / threads), apply fastest |
| `new [--stack S --path P]` | scaffold a project (ecosystem generator + AI layer) |
| `gate [path] [--fix]` | verify/fix this machine against a project's .lai/project.json |
| `skill list / add / new <name> [--ai "desc"] [--project P]` | 14 built-in skill packs (incl. Playwright-MCP browser + Semgrep scan); custom ones model-draftable; project-local in .lai/skills/ |
| `git review\|commit\|resolve\|explain [--model M]` | AI git helper on the local endpoint |
| `chat [--model M] [--polish]` | streaming terminal REPL; @file attach; /model /polish /clear |
| `docs add <url\|file\|pdf> / search "q" / list` | per-project documentation RAG (Qdrant) |
| `ports [show\|set <name> <port>\|check --fix]` | configurable service ports + conflict auto-fix |
| `cloud add\|remove\|list\|models\|use <provider>` | optional cloud fallbacks (openrouter/openai/anthropic) |
| `hftoken [--key K] [--off]` | Hugging Face token for fast downloads |
| `connect <host> [--key K] / connect --off` | use a team server's models instead of local |
| `share on\|off` | serve this machine's models to the LAN |
| `apikey [--off]` | bearer token required on all model endpoints |
| `docker` | start Qdrant, OpenHands, Open WebUI, SearXNG (per-service, port-env aware) |
| `autostart [--remove] / watchdog` | login service + auto-restart monitor |
| `upgrade` | llama.cpp / llama-swap release check |
| `vscode` | build (TypeScript) + install the VS Code companion extension |
| `shortcut [--remove]` | Desktop / app-menu launcher (with icon) |
| `path` | add `lai` to PATH (Windows user PATH; `~/.local/bin/lai` on Unix) |
| `info` | one-screen summary of the whole environment |

## File & directory contract

```text
lai.py            entry point        laicore/         implementation package
config/catalog.json   THE TABLE: models, tiers, usecases, stacks, cloud offers (versioned, editable)
config/*.yml|yaml|md  templates: docker-compose, Continue config, AGENTS template, enhance-prompt
skills/<name>/        agent skill packs (rules + optional Roo mode)
ui/                   Vue 3 + TS dashboard source; ui/dist is served
editors/vscode/       TypeScript VS Code extension
state/                MACHINE-LOCAL (gitignored): choices.json, ports.json, cloud.json,
                      secrets.json (api keys + hf token), llama-swap.generated.yaml,
                      sideservers.generated.json, active.json, projects.json, remote.json
models/ tools/ logs/  GGUFs, engine binaries, service logs (gitignored)
```

Per-project files created by `lai new` (committed with the project):

```text
AGENTS.md            agent conventions + build/test commands (read by Roo/Cline/Aider/OpenHands)
.lai/project.json    team contract: stack, required AI roles, min_ctx, toolchains
.lai/local.json      personal overrides (gitignored), e.g. {"preferred": {"coder": "x"}}
.lai/memory.md       durable project facts; agents read at task start, append dated bullets
.roo/                rules + modes installed by skills; .roomodes; optional mcp.json
.vscode/             recommended extensions + settings    docs/adr/  decision records
```

## HTTP surfaces (default ports; all remappable via `lai ports`)

| Port | Service | Notes |
| --- | --- | --- |
| 8080 | llama-swap | OpenAI-compatible: `/v1/chat/completions`, `/v1/models`; model ids = role names `coder`, `thinker`, `vision` (+`coder-longctx`); streaming + tools (`--jinja`) supported |
| 8081 / 8082 | autocomplete / embeddings | always-on llama-servers; `/v1/completions` (FIM), `/v1/embeddings` |
| 8090 | dashboard + JSON API | GET/POST under `/api/`: overview, status, candidates, downloads, projects, ports, cloudcfg, logs; POST plan, set, config, start/stop/restart, download, bench, gate, new, skill, verify, ports, cloudcfg, easy, chat, chat-stream (SSE) |
| 6333 | Qdrant | repo RAG + `lai docs` collections (`lai-docs-<project>`) |
| 3000 / 3001 / 8888 | OpenHands / Open WebUI / SearXNG | docker services |

If `state/secrets.json` has `api_key`, model endpoints require
`Authorization: Bearer <key>`.

## Concepts an explainer must get right

1. **Catalog-driven**: recommendations are data (config/catalog.json), not
   code. Tiers match top-down on platform/vendor/VRAM/RAM; use cases overlay
   role enable/disable; `lai plan` re-evaluates after any edit.
2. **Roles, not models**: agents talk to stable names (`coder`, `thinker`,
   `vision`); which GGUF serves a role differs per machine. llama-swap loads
   ONE big model at a time (autocomplete/embeddings are separate, always on).
3. **Hybrid MoE offload**: on small GPUs (e.g. 6 GB + 32 GB RAM) the 30B-A3B
   coder runs with experts in system RAM (`--n-cpu-moe`) at ~8-13 tok/s -
   that is the headline trick versus generic launchers.
4. **Identity vs capability**: project requirements travel in the repo
   (.lai/project.json + AGENTS.md); machine capability is local; `lai gate
   --fix` reconciles them on any machine - including against a team server
   when `lai connect` is active.
5. **Cloud is explicit**: only model ids prefixed `or:` / `oa:` / `an:` reach
   a cloud provider; bare prefix uses the saved per-provider default with
   token-lean params (max_tokens 1024). Local is always the implicit default.
6. **Approval gates**: every install/download/overwrite prompts; `--yes`
   approves; non-interactive runs without `--yes` skip and say why.

## Canonical workflows (tutorial seeds)

```text
# zero to working stack
irm https://raw.githubusercontent.com/DevEpoch/lai/main/install.ps1 | iex
cd ~/lai ; .\lai.ps1 setup ; .\lai.ps1 validate

# new Rust project with a working AI loop
lai new --stack rust-cli --path ~/mytool
code ~/mytool      # Roo Code: Interview mode -> spec -> Code mode implements

# teammate onboarding (any OS)
git clone <project> && cd <project> && lai gate --fix

# daily git loop
lai git review --base origin/main ; git add -A ; lai git commit --apply

# model experiment, evidence-based
lai cloud models openrouter --key qwen ; lai bench --quality --model or:qwen/qwen3-coder:free
lai set coder <new-local-model> ; lai bench --quality

# port conflict with another app
lai ports check --fix ; lai restart ; lai docker ; lai ide
```

## Things tutorials get wrong (pre-corrections)

- `lai start` already starts the dashboard; `lai ui` is only needed alone.
- Models download resumably and smallest-first; interruption is safe.
- Roo Code base URL must use the CURRENT swap port (`lai ports`), api key
  any non-empty string unless `lai apikey` is set.
- The thinker role is intentionally disabled on hybrid tiers (model-swap
  eviction cost) - not a bug; `lai set thinker ...` re-enables.
- `.lai/memory.md` and `AGENTS.md` are committed; `state/` and
  `.lai/local.json` never are.
