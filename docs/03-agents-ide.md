# Agents & IDE Setup

Prereq: stack running (`lai start`, `lai docker`), VS Code installed.
(`lai` = `.\lai.ps1` on Windows, `./lai.sh` on Linux.)

## 1. VS Code extensions

Install from the marketplace:

- **Roo Code** (`RooVeterinaryInc.roo-cline`) - main agent
- **Continue** (`Continue.continue`) - tab autocomplete + inline chat
- **Error Lens** - agents read diagnostics; so should you
- Language servers: `rust-analyzer`, `golang.go` (gopls), `clangd`, `dbaeumer.vscode-eslint`

## 2. Roo Code

Settings (gear icon) -> Providers:

| Field | Value |
| --- | --- |
| API Provider | OpenAI Compatible |
| Base URL | `http://localhost:8080/v1` |
| API Key | `local` (any non-empty string) |
| Model | `coder` |
| Context window | 32768 (laptop6) / 65536 (egpu24) |
| Image support | off for `coder` (use `vision` profile below) |

Create additional **configuration profiles** (Roo supports per-mode profiles):

- profile `thinker` -> model `thinker`; assign it to **Architect** mode
- profile `vision` -> model `vision`, image support on; switch to it when pasting screenshots
- **Code / Debug / Orchestrator** modes -> profile with model `coder`

Codebase Indexing (Settings -> Codebase Indexing):

| Field | Value |
| --- | --- |
| Embedder | OpenAI Compatible |
| Base URL | `http://localhost:8082/v1` |
| Model | `embeddings` (dimension 1024) |
| Qdrant URL | `http://localhost:6333` |

Then open your monorepo and let it index (incremental afterwards). Searches appear to the
agent as the `codebase_search` tool.

## 3. Continue

`lai ide` installs [config/continue.config.yaml](../config/continue.config.yaml) to
`~/.continue/config.yaml` (backing up any existing file). It wires:

- chat/edit -> `coder` via :8080
- autocomplete -> :8081 (Qwen2.5-Coder FIM)
- embeddings -> :8082

Disable Continue's chat sidebar if you prefer Roo for chat - keep it for autocomplete.

## 4. Aider (terminal, git-native edits)

Copy [config/aider.conf.yml](../config/aider.conf.yml) to your repo root as
`.aider.conf.yml` (or to your home directory to apply everywhere), then:

```bash
aider src/main.rs           # surgical, token-frugal edits with auto-commits
```

## 5. OpenHands (autonomous tasks)

Started by `lai docker`. Open <http://localhost:3000>, then in Settings -> LLM:

- Custom model: `openai/coder`
- Base URL: `http://host.docker.internal:8080/v1`
- API key: `local`

Use it for **well-specified, test-verifiable** tasks ("add a --version flag and a test;
make tests pass"), not open-ended exploration. It runs in its own sandbox container and
cannot touch files outside the workspace you give it.

## 6. Project memory (AGENTS.md + ADRs)

New projects: `lai new` generates `AGENTS.md`, `.vscode/`, `.lai/project.json`, and
`docs/adr/` for you (see the Projects section of the README). Existing repos: copy
[config/AGENTS.template.md](../config/AGENTS.template.md) to the repo root as
`AGENTS.md` and fill it in, create `docs/adr/`, and optionally add a `.lai/project.json`
(copy one from a scaffolded project) so `lai gate` can verify machines against it.

Roo Code, Continue, Aider, and OpenHands all read `AGENTS.md` automatically. This
versioned, reviewable memory beats any vector-memory system for project knowledge.
Optional later: Mem0 OSS as an MCP server (Qdrant-backed) for cross-project preferences.

## 7. Chat outside the IDE (Open WebUI)

`lai docker` also starts Open WebUI at <http://localhost:3001> - ChatGPT-style chat on
your local models, with document upload/RAG and image input (pick the `vision` model).
It talks to the same llama-swap endpoint, so model switching works from its model picker.
If you enable an API key (`lai apikey`), set it in `config/docker-compose.yml`
(`OPENAI_API_KEY`) and `docker compose -p local-ai up -d` again.

## 8. Cross-project memory (experimental)

Per-project memory is the `AGENTS.md` + ADR files (section 6). For memory that follows
*you* across projects ("prefers thiserror in libraries"), the compose file ships Mem0's
OpenMemory MCP server behind an opt-in profile:

```bash
docker compose -f config/docker-compose.yml -p local-ai --profile memory up -d
```

Then add an MCP server in Roo Code pointing at `http://localhost:8765`. Marked
experimental: verify the image/env names against the current Mem0 docs on first use -
the compose entry has a comment block for exactly this.

## Daily workflow

1. Type -> Continue completes from :8081 (sub-second).
2. Task -> Roo **Code** mode (model `coder`), which greps + `codebase_search`es your repo.
3. Design question -> Roo **Architect** mode (model `thinker`), save decisions to `docs/adr/`.
4. Screenshot/diagram -> switch Roo profile to `vision`.
5. Batchable chore -> OpenHands, review the diff when it is green.
6. Quick surgical edit -> `aider <files>` in the terminal.

On laptop6, expect agent turns to take a minute or two (~10 tok/s); kick off, keep coding.
