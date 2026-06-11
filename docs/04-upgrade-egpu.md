# eGPU Upgrade Path (< $1,000)

The single highest-leverage upgrade for this laptop: a Thunderbolt 3 eGPU with a used
RTX 3090 (24 GB). Thunderbolt bandwidth is irrelevant for LLM inference - weights live on
the GPU, only tokens cross the cable - so you lose ~0% generation speed vs a desktop slot.

## Shopping list (June 2026 prices)

| Item | Est. cost | Notes |
| --- | --- | --- |
| ADT-Link TH3P4G3 TB3 eGPU dock (or Razer Core X used) | ~$130 | dock needs an external ATX PSU |
| 750 W ATX PSU (any reputable brand) | ~$70 | 3090 peaks ~350 W |
| Used RTX 3090 24 GB | ~$800-850 | market average is ~$1,000-1,070; the low end takes 2-4 weeks of patient eBay/local sniping. Under $600 = probably mining-damaged; walk away |
| **Total** | **~$1,000** | |

**Plan B** (warranty, lower risk, lower ceiling): new RTX 5060 Ti 16 GB (~$450) + dock +
64 GB matched DDR4-3200 SO-DIMM kit (~$130) = ~$780. 16 GB runs the coder at smaller
context; 24 GB is the cliff that lets 30B-class models sit fully resident. Prefer the 3090.

### Used 3090 checklist

- Ask for a `nvidia-smi` screenshot from the seller's machine (shows it alive + driver).
- On arrival: run `nvidia-smi -q -d TEMPERATURE,POWER` under load; memory-junction temps
  >100 C under sustained load mean repaste/repad needed (~$20 DIY).
- Stress test: `.\lai.ps1 bench` twice back-to-back; throughput should not degrade.

## Install steps

1. Assemble: dock -> PSU -> 3090 -> Thunderbolt port (use the TB3 port, not plain USB-C).
2. Windows: latest NVIDIA driver (your current 573.91 already supports it; newer is fine).
3. Verify both GPUs:

   ```bash
   nvidia-smi --query-gpu=index,name,memory.total --format=csv
   ```

4. Regenerate config and restart - this is the whole software migration:

   ```text
   lai config      # auto-detects >= 20 GB GPU -> egpu24 profile
   lai restart
   lai bench       # expect generation >= 90 tok/s on `coder`
   ```

5. In Roo Code / Continue, raise the context window setting to 65536.

## What changes on egpu24

- `coder` / `thinker` / `vision` run fully on the 3090 (~100-130 tok/s for the coder).
- A new `coder-longctx` model id appears (131072 ctx, q4_0 KV) for huge reviews.
- Autocomplete upgrades from 1.5B to 3B and stays on the laptop GPU with embeddings,
  so the 3090 is never interrupted.
- OpenHands becomes genuinely pleasant (agent iterations in seconds, not minutes).

## Beyond $1,000 (later)

- ~$3,500: dedicated Linux box, 2x used 3090, 128 GB DDR5, vLLM/TabbyAPI -> parallel
  agents, 100B-class MoEs, 128K+ real context. Laptop becomes a thin client (Tailscale).
- ~$9,000+: RTX PRO 6000 Blackwell 96 GB -> frontier-class open models fully resident.
- The software stack in this repo is unchanged in all cases - only endpoints move.
