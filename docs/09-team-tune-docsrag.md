# Team Server, Auto-Tuning, Docs RAG, Updates

## Install & stay current

One-line install:

```text
Windows:    irm https://raw.githubusercontent.com/DevEpoch/lai/main/install.ps1 | iex
Linux/mac:  curl -fsSL https://raw.githubusercontent.com/DevEpoch/lai/main/install.sh | bash
```

The recommendation table is living data - pull the latest published catalog any time:

```text
lai catalog --update            # shows version + model diff, asks, backs up, applies
lai catalog --update --url ...  # from your own fork/mirror
lai upgrade                     # engine binaries (llama.cpp ships speedups monthly)
```

## Team server mode

One strong machine serves models to the whole team; laptops need no GPU, no
downloads, no local stack.

**On the server** (the box with the GPU):

```text
lai apikey            # strongly recommended before sharing
lai share on          # side servers bind 0.0.0.0 (llama-swap already does)
lai restart
# open inbound TCP 8080-8082 on the LAN firewall
```

**On each client:**

```text
lai connect 192.168.1.50 --key <key>    # verifies the server, saves state/remote.json
lai ide                                  # rewires Continue to the server
lai gate --fix                           # project gates now check the SERVER's models
lai connect --off                        # back to local serving any time
```

While connected: `lai validate`, `lai git ...`, `lai bench --quality`, and
`lai docs` all target the server automatically. Roo Code/OpenHands: set their
base URL to `http://<server>:8080/v1` once. Qdrant for shared docs RAG is also
expected on the server host.

Honest limits: llama-swap serves one big model at a time, swapping per request
model - fine for a small team with mixed usage; heavy parallel agent fleets want
the multi-GPU + vLLM build (see docs/04). Traffic is plain HTTP on your LAN -
use the API key, and for remote work put it behind Tailscale/WireGuard.

## `lai tune` - automatic per-machine calibration

Generic launchers ship one-size-fits-all configs; the same model can run 2-3x
faster with machine-specific flags. `lai tune` measures instead of guessing:

1. Builds variants for your coder's mode:
   - **hybrid** (MoE offload): how many layers' experts stay on CPU
     (`--n-cpu-moe` 99 vs 40/32/24 - more on GPU = faster, until VRAM runs out)
   - **gpu**: KV cache quantized vs f16
   - **cpu**: thread count vs physical cores
2. Starts a real `llama-server` per variant on a test port, runs a timed
   completion, reads the server's own `timings` (pp/tg tokens-per-second).
   Variants that OOM simply fail health and drop out - no guessing about VRAM.
3. Shows the table, and with your approval locks the winner into
   `state/choices.json` (config regenerates; `lai restart` applies).

Re-run after hardware, driver, or model changes. Results land in `benchmarks/`.

## `lai docs` - project documentation RAG

Index the docs your project depends on (framework guides, internal wikis, API
references) so agents can query them locally:

```text
lai docs add https://docs.example.com/guide      # url (html -> text)
lai docs add ./design/architecture.pdf           # pdf (needs: pip install pypdf)
lai docs add ./README-vendor.md                  # local file
lai docs search "how do I configure retries"     # top-5 chunks with sources
lai docs list
```

Chunks are embedded by your local embeddings server and stored in Qdrant in a
**per-project collection** (named after the `--project` directory, default:
current). Agents use it through their command tool - add one line to the
project's `AGENTS.md`:

```text
- Library/framework questions: run `lai docs search "<question>"` before guessing.
```

Everything stays local: fetching the page is the only network access; embedding
and storage never leave your machines.
