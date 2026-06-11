# Contributing

The design rule of this project: **logic in a small stdlib-only Python package (laicore/; entry lai.py), i.e.
([lai.py](lai.py)), knowledge in editable data ([config/catalog.json](config/catalog.json))**.
Most contributions should touch the catalog, not the code.

## Adding a model

1. Add an entry under `models` in `config/catalog.json` - repo, `include` patterns,
   `disk_gb`, `fits_vram_gb`, `hybrid_ram_gb` (MoE only), `cpu_ok`, `roles`, `why`.
   Set `"verify": true` until you have confirmed the Hugging Face repo name.
2. Run `python lai.py catalog --verify` (checks every repo against the HF API).
3. Reference it from a tier/use case if it should ever be a default.
4. Run `python lai.py bench --quality` before and after switching to it, and put the
   numbers in your PR.

## Adding a tier, use case, or project stack

All three are data: `tiers`, `usecases`, `stacks` in the catalog. Tiers match top-down
(first hit wins) - place new ones accordingly. Stacks must use the ecosystem's own
generator (`cargo init`, `npm create ...`) wherever one exists; seed files are only for
ecosystems without a generator.

## Code changes

- Python 3.9+ compatible, standard library only - no dependencies will be accepted
  (the only soft exception: `huggingface_hub`, imported lazily for downloads).
- Must work on Windows, Linux, and macOS - guard anything platform-specific.
- Anything that installs, downloads, or overwrites must go through `confirm()`.
- Machine-local files belong under `state/` (gitignored), never `config/`.

## Checks before a PR

```bash
python -m compileall -q laicore lai.py
python -m unittest discover -s tests
python -c "import json,glob; [json.load(open(f)) for f in glob.glob('config/*.json')]"
python lai.py plan --yes --use-case scripts && python lai.py choices
bash -n lai.sh   # linux/mac
```

CI runs the same on all three OSes.
