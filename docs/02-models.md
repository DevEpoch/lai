# Model Stack

All models are GGUF, served by llama.cpp. **The authoritative model registry now lives in
[config/catalog.json](../config/catalog.json)** (view with `lai catalog`); which ones are
active on this machine is decided by `lai plan` and stored in `state/choices.json`.
`lai models` downloads the chosen ones into `models/<id>/`.

The tables below document the original stack for *this* machine (6 GB laptop -> 24 GB
eGPU) and remain accurate for those two tiers.

## Manifest (snapshot - see `lai catalog` for the live list)

| id | Repo (Hugging Face) | Quant | Disk | Role |
| --- | --- | --- | --- | --- |
| coder | `unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF` | Q4_K_M | ~18.6 GB | primary coding + agents, 256K native ctx |
| thinker | `unsloth/Qwen3-30B-A3B-Thinking-2507-GGUF` | Q4_K_M | ~18.6 GB | planning, architecture, hard debugging |
| autocomplete-3b | `Qwen/Qwen2.5-Coder-3B-Instruct-GGUF` | q4_k_m | ~2.0 GB | tab-completion (egpu24 profile) |
| autocomplete-1.5b | `Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF` | q4_k_m | ~1.1 GB | tab-completion (laptop6 profile) |
| embeddings | `Qwen/Qwen3-Embedding-0.6B-GGUF` | Q8_0 | ~0.7 GB | repo RAG vectors (needs `--pooling last`) |
| vision | `unsloth/Qwen3-VL-8B-Instruct-GGUF` | Q4_K_M + mmproj F16 | ~6 GB | screenshots, diagrams, PDFs |

`core` set = coder + autocomplete + embeddings (~22 GB). `all` adds thinker + vision (~47 GB).

## VRAM / RAM budgets

### laptop6 (Quadro RTX 3000, 6 GB + 32 GB RAM)

| Process | GPU | RAM | Notes |
| --- | --- | --- | --- |
| coder (hybrid) | ~4.0 GB (attention + KV q8, 32K ctx) | ~19 GB (experts) | `--n-cpu-moe 99`, ~8-13 tok/s gen |
| autocomplete-1.5b | ~1.3 GB | - | always on |
| embeddings | 0 (CPU, `-ngl 0`) | ~0.8 GB | always on |
| **Headroom** | ~0.5 GB | ~10 GB for OS + IDE | tight but workable |

The thinker swaps in *instead of* the coder (same budget). Vision on 6 GB is tight; if it
OOMs, lower `-ngl` for the vision entry (see troubleshooting).

### egpu24 (+ RTX 3090 24 GB)

| Process | GPU | Notes |
| --- | --- | --- |
| coder | ~18.6 GB weights + KV on 3090 | `-c 65536` with q8 KV; ~100-130 tok/s |
| coder-longctx | same weights, `-c 131072`, q4_0 KV | for whole-subsystem reviews |
| thinker / vision | swap onto 3090 | |
| autocomplete-3b + embeddings | laptop GPU (~3 GB) | never touch the 3090 |

## Realistic context guidance

- Daily agent work: 32-64K context is the sweet spot. Let Qdrant RAG carry monorepo scale.
- `coder-longctx` (egpu24) reaches ~128K via q4_0 KV cache - use for big design reviews,
  expect quality to be best in the first ~64K.

## Swapping in a successor model

The local-model field moves monthly. To adopt a newer model (e.g. a Qwen3-Coder-Next GGUF
or Devstral successor):

1. Add an entry for it under `models` in `config/catalog.json` (repo, include patterns,
   disk_gb, fits_vram_gb / hybrid_ram_gb, roles - see the checklist in
   [06-hardware-catalog.md](06-hardware-catalog.md)).
2. `lai set coder <new-id>` - it offers to download and reconfigure for you.
3. `lai restart`, then `lai bench` to compare against the old choice.

Rule of thumb for this hardware: prefer MoE models with <= 4B active parameters
(they survive CPU offload) and check the GGUF fits: weights + ~2-4 GB KV must fit in
24 GB (egpu24) or weights must fit in ~26 GB RAM (laptop6 hybrid).

> Qwen3-Coder-Next (80B-A3B class) is worth trying on egpu24: Q4 weights split across
> 24 GB VRAM + system RAM via `--n-cpu-moe`, ~15-25 tok/s, near-frontier quality.
> Add it as a fourth llama-swap entry rather than replacing `coder`.

## The cost of swapping models (how many models is too many?)

llama-swap serves ONE big model at a time; requesting another unloads and
reloads (~10-30 s from NVMe on 24 GB GPUs). The real trap is hybrid tiers:
two 18.6 GB MoE models swapped through 32 GB RAM evict each other's pages,
so coder<->thinker ping-pong costs 30-60 s per turn. Hence the policy:

- autocomplete + embeddings are tiny and always-on - they never swap.
- coder handles ~95% of traffic and should stay resident.
- thinker is DISABLED by default on hybrid tiers (use the coder with
  Architect-mode prompts); enable it only for long uninterrupted planning
  sessions. On 20 GB+ VRAM or 48 GB+ Macs the swap is cheap - keep it.
- vision swaps in on demand; on 24 GB+ the 4B vision model can co-reside
  with the coder (llama-swap groups) - see the tier notes.
- Better than more local models: `lai tune` (make the one model faster),
  `coder-longctx` (same weights, different config), or an explicit cloud
  fallback for the rare task above local quality (`lai cloud`).
