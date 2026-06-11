# Hardware Catalog - research notes

The machine-readable table is [config/catalog.json](../config/catalog.json) - that file is
the single source of truth (`lai plan` re-reads it every run; edit it freely and this doc
when recommendations change). This document records *why* the table says what it says,
per platform, with sources (researched June 2026).

## How the planner uses the table

1. `lai plan` detects: OS, GPU vendor (NVIDIA via nvidia-smi / AMD via CIM-sysfs-rocm-smi /
   Apple Silicon / none), VRAM, RAM. AMD VRAM is often unreadable on Windows - the planner
   asks, or take `--vram-gb N`.
2. First tier in the table whose conditions match wins (ordered most- to least-capable).
3. Each role (coder / thinker / vision / autocomplete / embeddings) gets the tier default;
   if a default doesn't fit (or its repo is marked `verify`), the best fitting alternative
   is substituted automatically and flagged.
4. The user reviews the proposal (interactive accept/edit), and can change any choice
   later: `lai set <role> <model>` or edit `state/choices.json`.

## NVIDIA (Windows / Linux) - engine: llama.cpp CUDA

| VRAM | Recommended coder | Why |
| --- | --- | --- |
| 40+ GB | Qwen3-Coder-30B-A3B at 128K ctx (or Qwen3-Coder-Next resident) | everything fits; consider vLLM for parallel agents |
| 20-40 GB | Qwen3-Coder-30B-A3B fully resident, 64K ctx + 128K longctx profile | ~100-130 tok/s; the sweet spot |
| 14-20 GB | Devstral Small 24B (dense, agent-tuned) | MoE-30B doesn't fit VRAM; Devstral is the best dense agent model at 16 GB |
| 10-14 GB | Qwen2.5-Coder-14B Q4 (~9-10 GB) | 12 GB is the floor for 14B-class coders; ~14-18 tok/s on a 3060/3080Ti |
| 6-10 GB **+ 28+ GB RAM** | Qwen3-Coder-30B-A3B *hybrid* (experts in RAM) | 30B-class intelligence at ~8-13 tok/s beats a fast 7B for agent work |
| 6-10 GB | Qwen2.5-Coder-7B | 8 GB caps at 7B-8B dense; a RAM upgrade unlocks the hybrid tier |
| 3-6 GB | Qwen3-4B | utility-grade |

## AMD Radeon (Windows / Linux) - engine: llama.cpp Vulkan (Linux: ROCm optional)

Same VRAM ladder as NVIDIA (the tiers accept both vendors). Engine differences:

- **Windows**: Vulkan build - the practical choice, broadest compatibility.
- **Linux**: Vulkan works out of the box; a ROCm/HIP source build is ~10-20% faster on
  supported Radeons (RX 7000/9000, MI). llama.cpp on ROCm runs ~70-80% of CUDA speed.
- Notable cards: RX 7900 XTX 24 GB lands in the gpu-24gb tier; RX 9070 XT 16 GB in
  gpu-16gb; Strix Halo APUs behave more like Apple-style unified memory.

## Apple Silicon (macOS) - engine: llama.cpp Metal

Unified memory = VRAM. Rule from every 2026 source: **buy/use memory first** - memory
decides what runs at all; GPU cores only decide speed. Metal can address ~75% of RAM.

| Unified memory | Recommended coder | Notes |
| --- | --- | --- |
| 48+ GB | Qwen3-Coder-30B-A3B, 64K ctx | ~50+ tok/s on M3/M4 Pro/Max class; 96/128 GB can try Qwen3-Coder-Next |
| 28-48 GB | Qwen3-Coder-30B-A3B, 32K ctx | 32 GB is the entry point for the 30B-MoE class (~40+ tok/s, little headroom) |
| 14-28 GB | Qwen2.5-Coder-7B (24 GB: try 14B) | 16 GB Macs swap under 14B+ models |
| < 14 GB | Qwen3-4B | demo grade |

Why llama.cpp and not MLX: MLX is ~10-25% faster (more on M5), but llama.cpp keeps the
exact same server, API, model files, and llama-swap router across all three OSes. If you
want the extra speed on a Mac-only setup, LM Studio (MLX backend) can replace the engine -
everything downstream (Roo, Continue, Qdrant) only sees an OpenAI endpoint.

## CPU-only (any OS)

- 28+ GB RAM: Qwen3-Coder-30B-A3B on CPU - MoE means only ~3B active params per token,
  so ~5-8 tok/s on a modern 8-core. Chat-usable, too slow for agents. Autocomplete is
  disabled (latency would be worse than typing).
- 12-28 GB: Qwen3-4B. Below 12 GB: 1.5B, demo grade.

## Updating this table

1. Edit `config/catalog.json` (add models, retune tiers, bump `catalog_version`).
2. `lai plan` -> review -> accept.
3. `lai models && lai config && lai restart`.
4. `lai bench` to confirm the tier targets still hold; adjust `targets` if hardware/
   engine improved.

New model checklist: GGUF repo exists on HF; tool-calling trained (for coder role);
fill `disk_gb`, `fits_vram_gb`, `hybrid_ram_gb` (MoE only), `cpu_ok`, `roles`, `why`.
Set `"verify": true` until you have confirmed the repo name - the planner will then
never auto-pick it, only offer it.

## Sources

- [Apple Silicon local LLM guide 2026 (SitePoint)](https://www.sitepoint.com/local-llms-apple-silicon-mac-2026/)
- [Best Mac for local AI 2026, 8-128 GB tested (Local AI Master)](https://localaimaster.com/blog/apple-silicon-ai-buying-guide)
- [MLX vs llama.cpp on Apple Silicon (Groundy)](https://groundy.com/articles/mlx-vs-llamacpp-on-apple-silicon-which-runtime-to-use-for-local-llm-inference/)
- [llama.cpp on Apple M-series performance (GitHub discussion)](https://github.com/ggml-org/llama.cpp/discussions/4167)
- [AMD ROCm 7.1 vs Vulkan for llama.cpp (Phoronix)](https://www.phoronix.com/review/rocm-71-llama-cpp-vulkan)
- [AMD Radeon for local LLMs in 2026 (RunLocalModel)](https://runlocalmodel.com/amd-radeon-rocm-local-llm-2026.html)
- [Vulkan vs ROCm benchmarks on RDNA4 (digtvbg)](https://digtvbg.com/blog/llama-server-vulkan-rdna4-vllm-rocm-benchmark/)
- [llama.cpp CUDA/ROCm/Vulkan scoreboard (knightli)](https://knightli.com/en/2026/04/23/llama-cpp-gpu-benchmark-cuda-rocm-vulkan-scoreboard/)
- [Best coding LLM per 12 GB VRAM tier (PromptQuorum)](https://www.promptquorum.com/prompt-bites/best-local-llm-coding-12gb-vram)
- [Best local coding models by VRAM tier 2026 (InsiderLLM)](https://insiderllm.com/guides/best-local-coding-models-2026/)
- [Best local LLMs for 8/16/32 GB memory (Micro Center)](https://www.microcenter.com/site/mc-news/article/best-local-llms-8gb-16gb-32gb-memory-guide.aspx)
- [Best local coding LLMs 2026: Qwen vs DeepSeek vs Llama (PromptQuorum)](https://www.promptquorum.com/local-llms/best-local-llms-for-coding)
- [Open-weight coding models 2026 (Kilo)](https://kilo.ai/open-source-models)
