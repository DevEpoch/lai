# Troubleshooting

`lai` works from any terminal once installed (`lai path` adds it). Logs live in `logs/`.

## `lai` is not recognized in the terminal

The installer adds lai to your user PATH, but only NEW terminal windows
see it. Open a fresh terminal first. If it still fails (e.g. you cloned
manually), run `python lai.py path` once from the lai folder - it adds
the folder to PATH on Windows and creates `~/.local/bin/lai` on
Linux/macOS. In cmd.exe specifically, `lai` runs through `lai.cmd`;
never invoke `lai.ps1` from cmd (cmd cannot execute PowerShell scripts
and will open the file in an editor instead).

## Where is the dashboard?

`http://localhost:8090` (or your remapped `ui` port - `lai ports` shows
it). Three equivalent ways in: the **Local AI Env** Desktop/app-menu
shortcut, `lai ui`, or the URL in a browser. `lai start` also starts it.

## GPU out of memory (model fails to load or crashes mid-generation)

Edit the role's entry in `state/choices.json` (ctx / kv / ngl fields) and re-run
`lai config`, or hand-edit `state/llama-swap.generated.yaml` directly:

1. Reduce context: `"ctx": 32768` -> `16384`.
2. Quantize KV harder: `"kv": "q8_0"` -> `"q4_0"`.
3. Reduce GPU layers for a too-big model: add `"ngl": 10` (the rest goes to CPU).
4. Pick a smaller model for the role: `lai choices` shows fitting alternatives,
   `lai set <role> <model>` switches.
5. Make sure autocomplete/embeddings are not on the same GPU as the big model
   (with two NVIDIA GPUs they are pinned apart; check `state/active.json`).

After edits: `lai restart`.

## Generation much slower than the targets

- laptop6 below ~6 tok/s on `coder`: your RAM is the bottleneck. This machine has mixed
  sticks (3200 + 2400) running at 2400. A matched 2x32 GB DDR4-3200 SO-DIMM kit (~$130)
  is worth ~25%. Also close RAM-hungry apps - if the OS pages the expert tensors out,
  speed collapses.
- egpu24 below ~60 tok/s: confirm the model actually loaded on the 3090
  (`nvidia-smi` while generating; look at memory-used per GPU), and that the eGPU is on
  the Thunderbolt port, not a plain USB-C data port.
- Prompt processing slow on laptop6 is expected (~100-150 tok/s): 6 CPU cores. Keep agent
  system prompts lean; Roo's default is fine.

## llama-swap returns 502 / "model failed to start"

- Check `logs/llama-swap.log`, then run the failing `cmd:` line from the YAML by hand in
  a terminal - the real error (OOM, bad path, missing DLL/.so) prints there.
- First load of an 18 GB model from NVMe takes 15-30 s; `healthCheckTimeout: 600` covers
  it, but a cold antivirus scan can exceed it once. Retry.
- Linux: if `llama-server` reports no CUDA devices, you likely have the CPU-only release
  build - `lai engines` warns about this; build from source with `-DGGML_CUDA=ON`.

## Tool calls come back as plain text instead of `tool_calls`

- Ensure the model entry has `--jinja` (uses the GGUF's chat template with tool support).
- Qwen3-Coder is tool-call trained; if a swapped-in model is not, agents degrade -
  prefer "agentic" coder models.

## Continue autocomplete does nothing

- `curl http://localhost:8081/health` must return ok - if not: `lai status` and check
  `logs/autocomplete.log`.
- Continue config must be at `~/.continue/config.yaml` (re-run `lai ide`).
- VS Code: "Continue: Enable Tab Autocomplete" must be on.

## Roo Code indexing fails

- Qdrant up? `curl http://localhost:6333/collections` (or `lai status`).
- Embedder URL must be `http://localhost:8082/v1`, model name `embeddings`.
- The embeddings server requires `--pooling last` for Qwen3-Embedding (the generator
  sets it).

## Docker / OpenHands

- Windows: Docker Desktop must be running with the WSL2 backend.
  Linux: the docker daemon must be up and your user in the `docker` group.
- OpenHands needs `/var/run/docker.sock` mounted (the compose file does this) to spawn
  its runtime sandbox. If the runtime image pull fails, check the image tags in
  `config/docker-compose.yml` against the current OpenHands docs and update.
- From inside containers the host endpoint is `http://host.docker.internal:8080/v1`
  (the compose file maps this on Linux via `host-gateway`). llama-swap listens on all
  interfaces for this reason - firewall the port if the machine is on an untrusted LAN.

## Hugging Face downloads

- Interrupted? Re-run `lai models` - downloads resume.
- 404 on a repo: the model was superseded; see docs/02-models.md "Swapping in a
  successor".
- Slow: `pip install hf_transfer` - lai enables it automatically when present.

## Stale PID file ("pids.json exists" on start)

If the machine rebooted or processes died, `run/pids.json` can be left behind:
run `lai stop` (safe - it ignores already-dead PIDs), then `lai start`.

## Everything is weird after a driver / OS update

```text
lai stop
lai check
lai config
lai start
lai validate
```
