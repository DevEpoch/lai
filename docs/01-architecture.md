# Architecture

Three design rules govern everything:

1. **Logic in a small stdlib-only package** ([laicore/](../laicore/): core, stack, work, projects, webui, cli; entry [lai.py](../lai.py)) - runs unmodified on
   Windows/Linux/macOS, no build step, readable and patchable in place.
2. **Knowledge in data** ([config/catalog.json](../config/catalog.json)) - models,
   hardware tiers, use cases, and project stacks are an editable table, re-evaluated
   by `lai plan`. Updating recommendations never means changing code.
3. **Machine-local state stays in `state/`** (gitignored: choices, secrets, generated
   configs) - `config/` is purely versioned knowledge and templates.

The web dashboard (`lai ui`) and the CLI are the same commands: every UI button maps
1:1 onto a `lai` subcommand via a localhost JSON API.

## Data flow

```text
                                  YOU (VS Code)
                                       |
        +---------------+--------------+----------------+
        |               |                               |
   Continue (tab)   Roo Code (chat/agent modes)    Aider (terminal)
        |               |                               |
        |               +---------------+---------------+
        v                               v
 llama-server :8081              llama-swap :8080  <---------- OpenHands (Docker :3000)
 Qwen2.5-Coder 1.5B/3B                  |                       autonomous tasks,
 (always on, laptop GPU)                | spawns/swaps          sandboxed runtime
                                        v
                          llama-server (one at a time)
                    coder | thinker | vision | coder-longctx
                 laptop6: hybrid CPU+GPU   egpu24: RTX 3090 24GB

 Roo Code codebase indexing
        |
        v
 llama-server :8082 (Qwen3-Embedding, always on)  --->  Qdrant :6333 (Docker)
        chunks via tree-sitter                            vector store
```

## Why each winner won

- **llama.cpp over Ollama/vLLM/SGLang/TabbyAPI/TensorRT-LLM**: it is the only engine that
  offloads MoE *expert* tensors to system RAM while keeping attention on the GPU
  (`--n-cpu-moe` / `-ot`), which is what makes a 30B-class coder usable on a 6 GB laptop.
  It runs natively on Windows with CUDA, supports GGUF + KV-cache quantization, and
  `llama-server` exposes an OpenAI-compatible API with tool calling (`--jinja`).
  - Ollama wraps llama.cpp with less control and lagging features.
  - vLLM/SGLang want VRAM headroom and Linux; they become the right answer at 48 GB+ for
    parallel agents (Power build).
  - TabbyAPI/ExLlamaV2 is the fastest single-GPU option *after* the 24 GB upgrade but has
    no CPU offload, so it cannot serve the $0 build. Optional later.
- **llama-swap**: agents speak to one endpoint; the proxy starts/stops the right
  `llama-server` per request model name. This is how 5 models share one GPU.
- **Qwen3-Coder-30B-A3B**: the only model class that is simultaneously strong at agentic
  tool-calling, 256K context, runnable in 32 GB RAM today (3B active params -> only ~2 GB
  of weights read per token), and very fast once fully VRAM-resident.
- **Roo Code over Cline/Goose/Open Interpreter/editor forks**: any OpenAI endpoint, modes
  (Architect/Code/Debug/Orchestrator) that map cleanly onto our thinker/coder split, and
  built-in codebase indexing that targets Qdrant + a local embeddings endpoint natively.
- **Continue**: the only first-class *local tab-autocomplete* layer; runs alongside Roo.
- **OpenHands**: best autonomous loop (edit/compile/test in a sandbox container); point it
  at llama-swap and give it well-specified, test-verifiable tasks.
- **Qdrant over Chroma/LanceDB/FAISS/Weaviate**: single container, fast filtered search,
  and zero glue code because Roo Code speaks to it directly.
- **Memory = versioned markdown first**: `AGENTS.md` + `docs/adr/*.md` in each repo carries
  80% of the value deterministically; add Mem0 OSS (MCP) later if you want cross-project
  preference memory.

## Concurrency model

One big GPU model runs at a time (llama-swap swaps on demand, ~10-30 s load from NVMe).
Autocomplete and embeddings are separate always-on processes so tab-completion and repo
indexing never evict the main model. True parallel multi-agent serving arrives with the
Power build (2x GPU + vLLM), not before.

## Requests cheat-sheet

All chat traffic is standard OpenAI Chat Completions:

```text
POST http://localhost:8080/v1/chat/completions   { "model": "coder" | "thinker" | "vision" | "coder-longctx", ... }
POST http://localhost:8081/v1/completions        autocomplete (FIM)
POST http://localhost:8082/v1/embeddings         embeddings
```

## Security model

Everything binds to `127.0.0.1` (LAN exposure only via explicit `lai share`,
which also turns on the `lai apikey` bearer token). On top of that:

- **Cross-origin guard.** The dashboard API rejects POSTs whose `Origin`/`Host`
  is not localhost. Without this, any website open in your browser could fire
  state-changing requests at local daemons (classic localhost CSRF).
- **Workspace confinement.** Paths arriving over the dashboard HTTP API
  (`/api/new`, `/api/gate`, `/api/skill`) must resolve under your home folder,
  a registered project's parent, or an entry in `workspace_roots` in
  `state/settings.json`. The CLI is intentionally unconfined - a path typed in
  your own terminal is your own decision, like `git clone <dir>`.
- **Secrets.** `state/secrets.json` (API keys, HF token) is gitignored, never
  shipped in `lai doctor` zips, and written with owner-only permissions (0600
  on POSIX; the user-profile ACL covers it on Windows).
