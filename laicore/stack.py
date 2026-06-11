"""Environment operations: plan/choices, engines, models, config, services,
benchmarks, tuning, team mode, keys."""

from .core import *  # noqa: F401,F403

def pick_usecase(cat, args):
    ucs = cat.get("usecases", {})
    ids = [k for k in ucs if not k.startswith("_")]
    asked = getattr(args, "use_case", None)
    if asked:
        if asked not in ids:
            die(f"unknown use case '{asked}' - one of: {', '.join(ids)}")
        return asked
    if not sys.stdin.isatty() or assume_yes():
        return "general"
    print()
    info("what do you mainly build? (tunes which roles are enabled)")
    for i, k in enumerate(ids, 1):
        print(f"      {i}) {k:<10} {ucs[k].get('label', '')}")
    try:
        raw = input(c("35", "  ?   choice # (blank = general): ")).strip()
        if raw and 1 <= int(raw) <= len(ids):
            return ids[int(raw) - 1]
    except (EOFError, ValueError):
        pass
    return "general"

def cmd_plan(args):
    ensure_dirs()
    cat = load_catalog()
    hw = detect_hw(getattr(args, "vram_gb", None))
    tier = match_tier(cat, hw)
    if not tier:
        die("no catalog tier matches this hardware - "
            f"edit the tiers in {CATALOG_PATH}")
    choices = build_choices(cat, tier, hw)
    uc = pick_usecase(cat, args)
    apply_usecase(cat, choices, uc)
    print_choices(cat, choices)
    if sys.stdin.isatty() and not assume_yes():
        if not edit_choices_interactive(cat, choices):
            die("aborted - nothing saved")
    choices["saved"] = datetime.now().isoformat(timespec="seconds")
    save_text(CHOICES_PATH, json.dumps(choices, indent=2))
    ok(f"choices saved - change anytime with `lai set <role> <model>` "
       f"or by editing {CHOICES_PATH.name}")

def cmd_choices(args):
    cat = load_catalog()
    choices = load_choices()
    print_choices(cat, choices)

def cmd_set(args):
    cat = load_catalog()
    choices = load_choices()
    role, mid = args.role, args.model
    try:
        warnings = set_choice(cat, choices, role, mid)
    except ValueError as e:
        if "does NOT fit" in str(e):
            if not confirm(f"{e}. Set anyway?"):
                die("aborted")
            warnings = set_choice(cat, choices, role, mid, force=True)
        else:
            die(str(e))
    for w in warnings:
        warn(w)
    e = choices["roles"][role]
    info(f"{role} disabled" if e is None else
         f"{role} -> {mid} ({MODE_LABEL.get(e['mode'], e['mode'])})")
    choices["saved"] = datetime.now().isoformat(timespec="seconds")
    save_text(CHOICES_PATH, json.dumps(choices, indent=2))
    if confirm("apply now (download model if missing + regenerate config)?"):
        cmd_models(args)
        cmd_config(args)
        info("restart the stack to pick it up: lai restart")
    else:
        info("apply later with: lai models && lai config && lai restart")

CATALOG_UPDATE_URL = ("https://raw.githubusercontent.com/"
                      "DevEpoch/lai/main/config/catalog.json")

def cmd_vscode(args):
    src = ROOT / "editors" / "vscode"
    out_js = src / "out" / "extension.js"
    if not out_js.exists():
        npx = shutil.which("npx")
        if npx and confirm("compile the TypeScript extension now "
                           "(npx typescript, one-time)?"):
            subprocess.run([shutil.which("npm"), "install",
                            "--no-audit", "--no-fund"], cwd=str(src))
            r = subprocess.run([npx, "tsc", "-p", "."], cwd=str(src))
            if r.returncode != 0 or not out_js.exists():
                die("tsc failed - see output above")
        else:
            die("extension is not compiled (editors/vscode/out missing) - "
                "install Node.js and re-run, or use a packaged release")
    dest = Path.home() / ".vscode" / "extensions" / \
        "local-ai-env.local-ai-env-0.1.0"
    if not confirm(f"install the VS Code extension to {dest}?"):
        return
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for item in ("package.json", "README.md"):
        if (src / item).exists():
            shutil.copy2(src / item, dest / item)
    shutil.copytree(src / "out", dest / "out")
    ok(f"installed to {dest}")
    info("reload VS Code (Developer: Reload Window) - look for the "
         "$(circuit-board) lai button in the status bar")

def cmd_hftoken(args):
    sec = load_json(SECRETS_PATH) or {}
    if getattr(args, "off", False):
        sec.pop("hf_token", None)
        if sec:
            save_text(SECRETS_PATH, json.dumps(sec, indent=2))
        else:
            SECRETS_PATH.unlink(missing_ok=True)
        ok("Hugging Face token removed")
        return
    key = getattr(args, "key", None)
    if not key:
        info("get a FREE token: huggingface.co/settings/tokens -> "
             "'Create new token' -> type: Read")
        if not sys.stdin.isatty():
            die("pass it with: lai hftoken --key hf_...")
        try:
            key = input(c("35", "  ?   HF token (hf_...): ")).strip()
        except EOFError:
            key = ""
    if not key:
        die("no token given")
    if not key.startswith("hf_"):
        warn("tokens normally start with 'hf_' - storing anyway")
    sec["hf_token"] = key
    save_text(SECRETS_PATH, json.dumps(sec, indent=2))
    ok("HF token stored in state/secrets.json (gitignored, keep private)")
    info("model downloads now use it: higher rate limits + access to "
         "gated repos you have accepted")

def cmd_cloud(args):
    sec = load_json(SECRETS_PATH) or {}
    cloud = sec.setdefault("cloud", {})
    if args.action == "list":
        prefs = cloud_prefs()
        recs = (load_json(CATALOG_PATH) or {}).get("cloud", {})
        for prov, spec in CLOUD.items():
            mark = "key configured" if cloud.get(prov) else "no key"
            pp = prefs.get(prov) or {}
            dft = pp.get("model", "-")
            print(c("1", f"\n  {prov}  (prefix '{spec['prefix']}:')  "
                         f"[{mark}]"))
            print(f"    default model: {dft}"
                  + (f"  params: {pp.get('params')}" if pp.get("params")
                     else ""))
            for r in (recs.get(prov) or {}).get("recommended", []):
                print(c("90", f"    offer: {r['id']:<34} {r['why']}"))
        print()
        info("policy: local models are ALWAYS the default; cloud runs only "
             "on explicit prefixed ids (or:/oa:/an:) - bare prefix 'or:' "
             "uses your saved default")
        info("set a default + per-model settings:  lai cloud use openrouter "
             "<model> --max-tokens 1024 --temperature 0.2")
        info("browse what a service offers:        lai cloud models "
             "openrouter")
        return
    if args.action == "models":
        prov = args.provider or die("usage: lai cloud models <provider>")
        key = cloud.get(prov)
        try:
            if prov == "openrouter":
                data = http_json("https://openrouter.ai/api/v1/models",
                                 timeout=30)
                rows = [(m["id"],
                         f"in ${float(m['pricing']['prompt']) * 1e6:.2f}/M "
                         f"out ${float(m['pricing']['completion']) * 1e6:.2f}/M"
                         if m.get("pricing") else "")
                        for m in data.get("data", [])]
            elif prov == "openai":
                if not key:
                    die("add a key first: lai cloud add openai")
                data = http_json(f"{CLOUD['openai']['base']}/models",
                                 timeout=30,
                                 headers={"Authorization": f"Bearer {key}"})
                rows = [(m["id"], "") for m in data.get("data", [])]
            else:
                if not key:
                    die("add a key first: lai cloud add anthropic")
                data = http_json("https://api.anthropic.com/v1/models",
                                 timeout=30,
                                 headers={"x-api-key": key,
                                          "anthropic-version": "2023-06-01"})
                rows = [(m["id"], m.get("display_name", ""))
                        for m in data.get("data", [])]
        except SystemExit:
            raise
        except Exception as e:
            die(f"could not list {prov} models: {e}")
        flt = (getattr(args, "key", None) or "").lower()
        shown = 0
        for mid_, note in rows:
            if flt and flt not in mid_.lower():
                continue
            print(f"  {mid_:<48} {note}")
            shown += 1
            if shown >= 40:
                info(f"... {len(rows) - shown} more (filter: lai cloud "
                     f"models {prov} --key <substring>)")
                break
        info(f"pick one: lai cloud use {prov} <model-id>")
        return
    if args.action == "use":
        prov = args.provider or die("usage: lai cloud use <provider> "
                                    "<model> [--max-tokens N] "
                                    "[--temperature T] [--param k=v]")
        if prov not in CLOUD:
            die(f"unknown provider - one of: {', '.join(CLOUD)}")
        if not args.model_id:
            die("give a model id (see: lai cloud models " + prov + ")")
        prefs = cloud_prefs()
        params = {"max_tokens": int(getattr(args, "max_tokens", None)
                                    or 1024)}
        if getattr(args, "temperature", None) is not None:
            params["temperature"] = float(args.temperature)
        for kv in getattr(args, "param", None) or []:
            if "=" in kv:
                k, v = kv.split("=", 1)
                try:
                    params[k] = json.loads(v)
                except ValueError:
                    params[k] = v
        prefs[prov] = {"model": args.model_id, "params": params}
        save_cloud_prefs(prefs)
        ok(f"{prov} default -> {args.model_id}  params: {params}")
        info(f"use it with the bare prefix: --model "
             f"{CLOUD[prov]['prefix']}:   (token-lean by design: "
             "max_tokens defaults to 1024 - raise per call if needed)")
        return
    prov = args.provider
    if prov not in CLOUD:
        die(f"unknown provider - one of: {', '.join(CLOUD)}")
    if args.action == "remove":
        cloud.pop(prov, None)
        save_text(SECRETS_PATH, json.dumps(sec, indent=2))
        ok(f"{prov} key removed")
        return
    key = args.key
    if not key:
        if not sys.stdin.isatty():
            die("pass the key with --key in non-interactive sessions")
        try:
            key = input(c("35", f"  ?   {prov} API key: ")).strip()
        except EOFError:
            key = ""
    if not key:
        die("no key given")
    cloud[prov] = key
    save_text(SECRETS_PATH, json.dumps(sec, indent=2))
    ok(f"{prov} key stored in state/secrets.json (gitignored, keep private)")
    info("use it explicitly via prefixed model ids - it is never the default")

def _catalog_update(args):
    url = getattr(args, "url", None) or CATALOG_UPDATE_URL
    info(f"fetching {url}")
    try:
        status, raw = http_get(url, timeout=30)
        new = json.loads(raw.decode("utf-8-sig"))  # tolerate Windows BOM
    except Exception as e:
        die(f"could not fetch/parse remote catalog: {e}")
    cur = load_catalog()
    if not new.get("models") or not new.get("tiers"):
        die("remote catalog is missing models/tiers - refusing")
    info(f"installed: {cur.get('catalog_version')}  ->  "
         f"remote: {new.get('catalog_version')}")
    cm, nm = set(cur.get("models", {})), set(new.get("models", {}))
    if nm - cm:
        info("new models: " + ", ".join(sorted(nm - cm)))
    if cm - nm:
        warn("removed models: " + ", ".join(sorted(cm - nm)))
    def n_stacks(c):
        return len([k for k in c.get("stacks", {}) if not k.startswith("_")])
    info(f"tiers: {len(cur.get('tiers', []))} -> {len(new.get('tiers', []))}"
         f" | stacks: {n_stacks(cur)} -> {n_stacks(new)}")
    if new.get("catalog_version") == cur.get("catalog_version") \
            and nm == cm:
        ok("catalog is up to date")
        return
    if not confirm("apply the remote catalog? (current one is backed up)"):
        return
    backup = STATE / f"catalog-backup-{datetime.now():%Y%m%d-%H%M%S}.json"
    shutil.copy2(CATALOG_PATH, backup)
    save_text(CATALOG_PATH, json.dumps(new, indent=2))
    ok(f"catalog updated (backup: {backup.name}) - re-evaluate: lai plan")

def cmd_catalog(args):
    if getattr(args, "update", False):
        return _catalog_update(args)
    cat = load_catalog()
    print()
    info(f"catalog {cat.get('catalog_version', '?')} at {CATALOG_PATH}")
    info("edit the file directly (then: lai plan), or pull the latest "
         "published table: lai catalog --update")
    print(c("1", f"\n  {'TIER':<18}{'HARDWARE':<46}TARGET t/s (pp/tg)"))
    for t in cat["tiers"]:
        tg = t.get("targets", {})
        print(f"  {t['id']:<18}{t.get('label', ''):<46}"
              f"{tg.get('pp', '?')}/{tg.get('tg', '?')}")
    print(c("1", f"\n  {'MODEL':<26}{'DISK':<9}{'ROLES':<26}NEEDS"))
    for mid, m in cat["models"].items():
        needs = []
        if "fits_vram_gb" in m:
            needs.append(f"{m['fits_vram_gb']}GB VRAM")
        if m.get("hybrid_ram_gb"):
            needs.append(f"or {m['hybrid_ram_gb']}GB RAM (hybrid)")
        if m.get("cpu_ok"):
            needs.append("cpu-ok")
        flag = " [verify]" if m.get("verify") else ""
        print(f"  {mid:<26}{str(m['disk_gb']) + ' GB':<9}"
              f"{','.join(m['roles']):<26}{' '.join(needs)}{flag}")
    print()
    if getattr(args, "verify", False):
        info("verifying every catalog repo against the Hugging Face API...")
        bad = 0
        for mid, m in cat["models"].items():
            try:
                http_get(f"https://huggingface.co/api/models/{m['repo']}",
                         timeout=15)
                ok(f"{mid}: {m['repo']}")
            except Exception as e:
                code = getattr(e, "code", None)
                if code in (401, 403):
                    warn(f"{mid}: {m['repo']} is gated or not public yet - "
                         "check the name / accept its license on huggingface.co")
                else:
                    fail(f"{mid}: {m['repo']} NOT FOUND - update this entry "
                         f"in {CATALOG_PATH.name}")
                    bad += 1
        if bad:
            die(f"{bad} repo(s) missing")
        ok("all repos resolve")

def cmd_check(args):
    ensure_dirs()
    print()
    info(f"lai {VERSION} | platform: {SYSTEM} {platform.release()} "
         f"({platform.machine()}), python {platform.python_version()}")
    hw = detect_hw(getattr(args, "vram_gb", None))
    info(f"cpu: {hw['cores']} logical cores | ram: {hw['ram_gb']} GB")
    free_gb = shutil.disk_usage(ROOT).free / 2 ** 30
    info(f"disk free at {ROOT}: {free_gb:.0f} GB")
    for g in hw["gpus"]:
        ok(f"gpu {g['index']}: {g['name']} ({g['mem_mib']} MiB)")
    if not hw["gpus"]:
        warn("no GPU detected - CPU-only tiers will be used")

    cat = load_json(CATALOG_PATH)
    if cat:
        tier = match_tier(cat, hw)
        ok(f"catalog {cat.get('catalog_version')} | matching tier: "
           f"{tier['id'] if tier else 'NONE'}")
    else:
        warn(f"catalog missing: {CATALOG_PATH}")

    deps = [("git", "winget install Git.Git", "sudo apt install -y git",
             "xcode-select --install"),
            ("docker", "winget install Docker.DockerDesktop",
             "curl -fsSL https://get.docker.com | sh",
             "brew install --cask docker")]
    for name, win_hint, lin_hint, mac_hint in deps:
        if shutil.which(name):
            ok(f"{name} found")
        else:
            hint = win_hint if IS_WIN else (mac_hint if IS_MAC else lin_hint)
            warn(f"{name} missing -> {hint}")

    try:
        import huggingface_hub  # noqa: F401
        ok("huggingface_hub installed")
    except ImportError:
        warn(f"huggingface_hub missing -> "
             f"{sys.executable} -m pip install -U huggingface_hub")

    for tool in ("llama-server", "llama-bench", "llama-swap"):
        path = find_tool(tool, required=False)
        if path:
            ok(f"{tool}: {path}")
        else:
            warn(f"{tool} not installed -> lai engines")

    choices = load_json(CHOICES_PATH)
    if choices:
        ok(f"choices saved (tier {choices['tier']}, "
           f"saved {choices.get('saved', '?')}) - view: lai choices")
        for role, e in choices["roles"].items():
            if e and not model_file(e["model"]):
                warn(f"chosen model for {role} not downloaded -> lai models")
    else:
        warn("no choices saved yet -> lai plan")
    print()

def cmd_engines(args):
    ensure_dirs()
    cat = load_catalog()
    choices = load_choices(required=False)
    key = choices["engine"] if choices else engine_key(detect_hw())
    spec = cat["engines"].get(key)
    if not spec:
        die(f"no engine spec for '{key}' in the catalog")
    info(f"engine flavor: {key} - {spec.get('note', '')}")
    if not confirm("download llama.cpp + llama-swap release binaries "
                   "(~0.5-1 GB)?"):
        return
    TMP.mkdir(exist_ok=True)

    rel = gh_latest_release("ggml-org/llama.cpp")
    info(f"llama.cpp release: {rel.get('tag_name')}")
    asset = gh_pick_asset(rel, spec["patterns"], exclude=spec.get("exclude"))
    if not asset:
        die("no suitable llama.cpp binary asset found - build from source:\n"
            "  git clone https://github.com/ggml-org/llama.cpp\n"
            "  cmake -B build <backend flags> && cmake --build build -j\n"
            f"  then copy build/bin/* into {TOOLS / 'llama.cpp'}")
    arc = TMP / asset["name"]
    download(asset["browser_download_url"], arc)
    extract(arc, TOOLS / "llama.cpp")
    if spec.get("cudart"):
        cudart = gh_pick_asset(rel, [spec["cudart"]])
        if cudart:
            arc2 = TMP / cudart["name"]
            download(cudart["browser_download_url"], arc2)
            extract(arc2, TOOLS / "llama.cpp")

    rel2 = gh_latest_release("mostlygeek/llama-swap")
    info(f"llama-swap release: {rel2.get('tag_name')}")
    asset2 = gh_pick_asset(rel2, cat["engines"]["llama_swap"][PLAT])
    if not asset2:
        die("no llama-swap binary for this OS found in latest release")
    arc3 = TMP / asset2["name"]
    download(asset2["browser_download_url"], arc3)
    extract(arc3, TOOLS / "llama-swap")

    shutil.rmtree(TMP, ignore_errors=True)
    save_text(VERSIONS_PATH, json.dumps(
        {"llama.cpp": rel.get("tag_name"),
         "llama-swap": rel2.get("tag_name")}, indent=2))
    for tool in ("llama-server", "llama-bench", "llama-swap"):
        ok(f"{tool}: {find_tool(tool)}")

def cmd_models(args):
    ensure_dirs()
    cat = load_catalog()
    choices = load_choices()
    wanted = wanted_models(cat, choices)
    if getattr(args, "all", False):
        for mid, m in cat["models"].items():
            if not m.get("verify") and not model_file(mid) \
                    and mid not in [w[0] for w in wanted]:
                wanted.append((mid, m))
    if not wanted:
        ok("all chosen models already downloaded")
        return
    marker = RUN / "download.pid"
    if marker.exists():
        try:
            other = int(marker.read_text().strip())
        except ValueError:
            other = None
        if other and other != os.getpid() and pid_alive(other):
            die(f"a download is already running (pid {other}) - one at a "
                "time keeps Hugging Face file locks happy; watch progress "
                "in the dashboard")
    marker.write_text(str(os.getpid()), encoding="utf-8")
    for lk in MODELS.rglob("*.lock"):  # stale locks from killed downloaders
        lk.unlink(missing_ok=True)     # block hf_hub forever; we hold the
    # cross-process mutex, so clearing them is safe here
    total = sum(m["disk_gb"] for _, m in wanted)
    info("to download: " + ", ".join(f"{mid} ({m['disk_gb']} GB)"
                                     for mid, m in wanted))
    if not confirm(f"download {len(wanted)} model(s), ~{total:.0f} GB total, "
                   "from Hugging Face?"):
        return
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        if not confirm("huggingface_hub (Python package) is required - "
                       "pip install it now?"):
            die("cannot download models without huggingface_hub")
        subprocess.run([sys.executable, "-m", "pip", "install", "-U",
                        "huggingface_hub"], check=True)
        from huggingface_hub import snapshot_download
    try:
        import hf_transfer  # noqa: F401
    except ImportError:
        if confirm("install 'hf_transfer' (pip) for 3-10x faster, "
                   "multi-connection downloads?"):
            subprocess.run([sys.executable, "-m", "pip", "install",
                            "hf_transfer"], check=False)
    try:
        import hf_transfer  # noqa: F401,F811
        os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "1")
        info("hf_transfer enabled (multi-connection downloads)")
    except ImportError:
        pass
    hf_tok = (load_json(SECRETS_PATH) or {}).get("hf_token")
    if hf_tok:
        os.environ.setdefault("HF_TOKEN", hf_tok)
        info("HF token applied (higher rate limits)")
    else:
        info("tip: `lai hftoken` adds a free Hugging Face token -> faster, "
             "rate-limit-free downloads (huggingface.co/settings/tokens)")
    def _dir_gb(p):
        return sum(f.stat().st_size for f in Path(p).rglob("*")
                   if f.is_file()) / 2 ** 30 if Path(p).exists() else 0.0

    def _attempt(m, dest, use_ht, endpoint):
        """One download attempt in a subprocess, killed if bytes stop
        moving for 3 minutes (hf_transfer can hang silently on flaky
        networks - a stall watchdog is the only reliable cure)."""
        code = ("import sys, json\n"
                "from huggingface_hub import snapshot_download\n"
                "snapshot_download(repo_id=sys.argv[1], "
                "allow_patterns=json.loads(sys.argv[2]), "
                "local_dir=sys.argv[3])\n")
        env = os.environ.copy()
        env["HF_HUB_ENABLE_HF_TRANSFER"] = "1" if use_ht else "0"
        env.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "30")
        env["HF_HUB_DISABLE_XET"] = "1"  # classic backend resumes after
        # kills; xet restarts from zero - fatal on slow/flaky links
        env["HF_ENDPOINT"] = endpoint
        proc = subprocess.Popen(
            [sys.executable, "-c", code, m["repo"],
             json.dumps(m["include"]), str(dest)], env=env)
        last, still = -1.0, 0
        while proc.poll() is None:
            time.sleep(20)
            have = _dir_gb(dest)
            pct = min(100, int(have / max(m["disk_gb"], 0.01) * 100))
            if not sys.stdout.isatty():
                print(f"       {dest.name}: {render_bar(pct, 20)} {pct}% "
                      f"({have:.1f}/{m['disk_gb']} GB)", flush=True)
            still = still + 1 if have <= last + 0.001 else 0
            last = max(last, have)
            if still >= 9:  # ~3 min without a single new megabyte
                warn(f"{dest.name}: transfer stalled - restarting it "
                     "(resume loses nothing)")
                proc.kill()
                proc.wait()
                return False
        return proc.returncode == 0

    try:
        import hf_transfer  # noqa: F401,F811
        ht_available = True
    except ImportError:
        ht_available = False

    wanted.sort(key=lambda x: x[1]["disk_gb"])  # small models first:
    # side servers + vision come online while the big coder downloads
    failed = []
    for i, (mid, m) in enumerate(wanted, 1):
        info(f"[{i}/{len(wanted)}] {mid}  ({m['repo']}, ~{m['disk_gb']} GB)")
        eps = [hf_endpoint()] + [e for e in hf_mirrors()
                                 if e != hf_endpoint()]
        done = False
        for attempt in range(1, 6):
            use_ht = ht_available and attempt == 1
            ep = eps[((attempt - 1) // 2) % len(eps)]  # rotate mirrors
            if attempt > 1:
                info(f"       attempt {attempt}/5 via {ep} "
                     f"({'accelerated' if use_ht else 'steady mode'}) ...")
                time.sleep(10)
            won = (_native_fetch(m, MODELS / mid, ep) if attempt <= 3
                   else _attempt(m, MODELS / mid, use_ht, ep))
            if won:
                done = True
                break
        if done:
            ok(f"{mid} complete")
        else:
            fail(f"{mid}: gave up after 5 attempts - re-run `lai models` "
                 "later, it resumes")
            failed.append(mid)
    if failed:
        warn(f"failed: {', '.join(failed)} - repo may have moved; update its "
             f"entry in {CATALOG_PATH.name} and re-run (downloads resume)")
    else:
        ok("all chosen models present")

def cmd_config(args):
    ensure_dirs()
    cat = load_catalog()
    choices = load_choices()
    hw = choices["hardware"]
    server = find_tool("llama-server")

    # GPU pinning only matters with >1 NVIDIA GPU (big model vs side servers)
    multi_gpu = hw["vendor"] == "nvidia" and len(hw["gpus"]) > 1
    main_gpu = side_gpu = None
    if multi_gpu:
        main_gpu = max(hw["gpus"], key=lambda g: g["mem_mib"])["index"]
        side_gpu = min(hw["gpus"], key=lambda g: g["mem_mib"])["index"]

    def yaml_block(mid, cmd, cuda):
        lines = [f'  "{mid}":', f"    cmd: '{cmd} --port ${{PORT}}'"]
        if cuda is not None:
            lines += ["    env:", f'      - "CUDA_VISIBLE_DEVICES={cuda}"']
        lines.append("    ttl: 0")
        return lines

    key = api_key()
    if key:
        info("API key found in secrets.json - it will be required on all "
             "model endpoints")
    yaml = ["# AUTO-GENERATED from choices.json - regenerate with: lai config",
            f"# tier: {choices['tier']} | engine: {choices['engine']} | "
            f"generated: {datetime.now().isoformat(timespec='seconds')}",
            "healthCheckTimeout: 600", "logLevel: info", "", "models:"]
    missing = []
    for role in BIG_ROLES:
        e = choices["roles"].get(role)
        if not e:
            continue
        m = cat["models"][e["model"]]
        f = model_file(e["model"])
        mm = model_file(e["model"], mmproj=True) if m.get("mmproj") else None
        if not f or (m.get("mmproj") and not mm):
            missing.append(f"{role} ({e['model']})")
            continue
        cmd = f"{server} {role_flags(e, m, f, mm)}"
        if e["mode"] == "gpu" and m.get("draft"):
            df = model_file(m["draft"])
            if df:  # speculative decoding: small same-family draft model
                cmd += f" -md {df} -ngld 99 --draft-max 16 --draft-min 1"
            else:
                warn(f"{role}: draft model '{m['draft']}' not downloaded - "
                     "speculative decoding skipped (lai models fetches it)")
        if key:
            cmd += f" --api-key {key}"
        yaml += yaml_block(role, cmd, main_gpu if multi_gpu else None)
        if role == "coder" and e.get("longctx"):
            e2 = dict(e, ctx=e["longctx"], kv="q4_0")
            cmd2 = f"{server} {role_flags(e2, m, f, mm)}"
            if key:
                cmd2 += f" --api-key {key}"
            yaml += yaml_block("coder-longctx", cmd2,
                               main_gpu if multi_gpu else None)
    if missing:
        warn("not downloaded, omitted from config: " + ", ".join(missing) +
             " -> lai models")
    save_text(GEN_YAML, "\n".join(yaml) + "\n")

    side = []
    for role, port in (("autocomplete", P('autocomplete')), ("embeddings", P('embeddings'))):
        e = choices["roles"].get(role)
        if not e:
            continue
        f = model_file(e["model"])
        if not f:
            warn(f"{role} model not downloaded - side server disabled")
            continue
        m = cat["models"][e["model"]]
        ngl = "0" if e["mode"] == "cpu" else "99"
        cmd = ["-m", str(f), "-ngl", ngl, "-c", str(e.get("ctx", 8192)),
               "--port", str(port)]
        if role == "embeddings":
            cmd += ["--embedding"]
            if m.get("pooling"):
                cmd += ["--pooling", m["pooling"]]
        if key:
            cmd += ["--api-key", key]
        if (load_json(STATE / "share.json") or {}).get("enabled"):
            cmd += ["--host", "0.0.0.0"]  # team-server mode (lai share on)
        side.append({"name": role, "args": cmd,
                     "cuda": side_gpu if multi_gpu else None, "port": port})
    save_text(GEN_SIDE, json.dumps(side, indent=2))

    save_text(ACTIVE_PATH, json.dumps({
        "tier": choices["tier"], "engine": choices["engine"],
        "main_gpu": main_gpu, "side_gpu": side_gpu,
        "targets": choices.get("targets", {}),
        "coder_file": str(model_file((choices["roles"].get("coder") or
                                      {}).get("model", "")) or ""),
        "coder_mode": (choices["roles"].get("coder") or {}).get("mode", ""),
        "generated": datetime.now().isoformat(timespec="seconds")}, indent=2))
    ok("runtime config generated")

def cmd_ide(args):
    src = CONFIG / "continue.config.yaml"
    dest = Path.home() / ".continue" / "config.yaml"
    if dest.exists():
        if not confirm(f"overwrite existing {dest} (a backup is kept)?"):
            return
        backup = dest.with_suffix(f".yaml.bak-{datetime.now():%Y%m%d-%H%M%S}")
        shutil.copy2(dest, backup)
        info(f"backed up existing Continue config to {backup}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    text = src.read_text(encoding="utf-8")
    for nm, dflt in (("swap", 8080), ("autocomplete", 8081),
                     ("embeddings", 8082)):
        if P(nm) != dflt:
            text = text.replace(f":{dflt}", f":{P(nm)}")
    host = endpoint_host()
    if host != "localhost":
        text = text.replace("http://localhost:", f"http://{host}:")
        info(f"Continue endpoints rewired to team server {host}")
    dest.write_text(text, encoding="utf-8", newline="\n")
    ok(f"Continue config installed at {dest}")
    info("Roo Code is configured in its GUI - see docs/03-agents-ide.md")

def _docker_daemon_up():
    return subprocess.run(["docker", "info"], capture_output=True,
                          timeout=30).returncode == 0

def cmd_docker(args):
    compose_file = CONFIG / "docker-compose.yml"
    if not shutil.which("docker"):
        if IS_WIN and confirm("Docker not found - install Docker Desktop "
                              "via winget now (~1.5 GB, needs a logout "
                              "afterwards)?"):
            subprocess.run(["winget", "install", "-e", "--id",
                            "Docker.DockerDesktop",
                            "--accept-package-agreements",
                            "--accept-source-agreements"])
            info("installed - start Docker Desktop once, then re-run: "
                 "lai docker")
            return
        die("docker missing -> " + (
            "winget install Docker.DockerDesktop" if IS_WIN else
            "brew install --cask docker" if IS_MAC else
            "curl -fsSL https://get.docker.com | sh"))
    if not _docker_daemon_up():
        dd = Path(r"C:\Program Files\Docker\Docker\Docker Desktop.exe")
        if IS_WIN and dd.exists() and \
                confirm("Docker daemon is not running - launch Docker "
                        "Desktop and wait for it?"):
            subprocess.Popen([str(dd)])
            info("waiting for the Docker daemon (up to 120 s)...")
            deadline = time.time() + 120
            while time.time() < deadline:
                if _docker_daemon_up():
                    break
                time.sleep(5)
        if not _docker_daemon_up():
            die("the Docker daemon is not running - start Docker "
                "Desktop / `sudo systemctl start docker` and retry")
    base = ["docker", "compose"]
    if subprocess.run(base + ["version"], capture_output=True).returncode != 0:
        if shutil.which("docker-compose"):
            base = ["docker-compose"]
        else:
            die("docker compose not available")
    if not confirm("pull and start Qdrant + OpenHands + Open WebUI + "
                   "SearXNG containers (several GB on first run)?"):
        return
    # one service at a time: a single unreachable registry must not
    # cancel the pulls of the others
    failed = []
    for svc in ("qdrant", "searxng", "open-webui", "openhands"):
        info(f"bringing up {svc} ...")
        denv = os.environ.copy()
        denv.update({"LAI_QDRANT_PORT": str(P("qdrant")),
                     "LAI_OPENHANDS_PORT": str(P("openhands")),
                     "LAI_WEBUI_PORT": str(P("webui")),
                     "LAI_SEARXNG_PORT": str(P("searxng")),
                     "LAI_OPENMEMORY_PORT": str(P("openmemory")),
                     "LAI_SWAP_PORT": str(P("swap"))})
        r = subprocess.run(base + ["-f", str(compose_file), "-p",
                                   "local-ai", "up", "-d", "--no-deps", svc],
                           env=denv)
        (ok if r.returncode == 0 else fail)(svc)
        if r.returncode != 0:
            failed.append(svc)
    if failed:
        warn(f"failed: {', '.join(failed)} - registry unreachable? "
             "re-run `lai docker` later; the rest are up")
    else:
        ok("Qdrant :6333 | OpenHands :3000 | Open WebUI :3001 | "
           "SearXNG :8888")

def _spawn(name, cmd, cuda=None):
    env = os.environ.copy()
    if cuda is not None:
        env["CUDA_VISIBLE_DEVICES"] = str(cuda)
    log = open(LOGS / f"{name}.log", "ab")
    kwargs = {"stdout": log, "stderr": subprocess.STDOUT,
              "cwd": str(ROOT), "env": env}
    if IS_WIN:
        # CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
        kwargs["creationflags"] = 0x08000000 | 0x00000200
    else:
        kwargs["start_new_session"] = True
    proc = subprocess.Popen([str(x) for x in cmd], **kwargs)
    info(f"started {name} (pid {proc.pid})")
    return proc.pid

def cmd_start(args):
    ensure_dirs()
    old = load_json(RUN / "pids.json")
    if old:
        try:
            http_get(f"http://localhost:{P('swap')}/v1/models", timeout=2)
            info("stack already running - use `lai restart` to bounce it")
            return
        except Exception:
            info("previous run is stale/partially dead - cleaning up first")
            for name, pid in old.items():
                if pid_alive(pid):
                    _kill(pid)
            (RUN / "pids.json").unlink(missing_ok=True)
    server = find_tool("llama-server")
    swap = find_tool("llama-swap")
    yaml_path = GEN_YAML
    side = load_json(GEN_SIDE)
    if not yaml_path.exists() or side is None:
        die("config missing - run: lai config")
    # self-heal: models that finished downloading after the last `lai config`
    ch = load_json(CHOICES_PATH) or {"roles": {}}
    configured = {s_["name"] for s_ in side}
    arrived = [r for r in ("autocomplete", "embeddings")
               if r not in configured and (ch["roles"].get(r) or {})
               and model_file((ch["roles"].get(r) or {}).get("model"))]
    if arrived:
        info(f"models arrived since last config ({', '.join(arrived)}) - "
             "regenerating")
        cmd_config(args)
        side = load_json(GEN_SIDE)

    pids = {}
    for s in side:
        pids[s["name"]] = _spawn(s["name"], [server] + s["args"], s.get("cuda"))
    pids["llama-swap"] = _spawn(
        "llama-swap", [swap, "--config", yaml_path, "--listen", f":{P('swap')}"])
    try:  # the dashboard is part of the stack - a real program has its UI up
        http_get(f"http://127.0.0.1:{P('ui')}/api/overview", timeout=1.5)
        info(f"dashboard already running: http://127.0.0.1:{P('ui')}")
    except Exception:
        pids["ui"] = _spawn("ui", [sys.executable, str(ROOT / "lai.py"),
                                   "ui", "--no-browser"])
        info(f"dashboard: http://127.0.0.1:{P('ui')}")
    save_text(RUN / "pids.json", json.dumps(pids, indent=2))
    time.sleep(3)
    cmd_status(args)
    info("note: the first request to `coder` loads the model from disk "
         "(15-30 s for large models)")

def _kill(pid):
    try:
        if IS_WIN:
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                           capture_output=True)
        else:
            os.killpg(pid, signal.SIGTERM)
    except (OSError, ProcessLookupError):
        pass

def cmd_stop(args):
    pids = load_json(RUN / "pids.json", {})
    if not pids:
        info("nothing recorded in run/pids.json")
    for name, pid in pids.items():
        info(f"stopping {name} (pid {pid})")
        _kill(pid)
    if not IS_WIN:
        time.sleep(2)
        for pid in pids.values():  # escalate stragglers
            try:
                os.killpg(pid, signal.SIGKILL)
            except (OSError, ProcessLookupError):
                pass
    (RUN / "pids.json").unlink(missing_ok=True)
    ok("stopped (llama-swap child servers terminate with their parent)")

def cmd_restart(args):
    cmd_stop(args)
    time.sleep(2)
    cmd_start(args)

def cmd_status(args):
    for name, url in probes():
        try:
            status, _ = http_get(url, timeout=3)
            ok(f"{name} (HTTP {status})")
        except Exception:
            fail(f"{name} - not responding")

_QT_READ = {"type": "function", "function": {
    "name": "read_file", "description": "Read a file from disk",
    "parameters": {"type": "object",
                   "properties": {"path": {"type": "string"}},
                   "required": ["path"]}}}

_QT_GREP = {"type": "function", "function": {
    "name": "grep_search",
    "description": "Search all files in the repository for a regex pattern",
    "parameters": {"type": "object",
                   "properties": {"pattern": {"type": "string"}},
                   "required": ["pattern"]}}}

QUALITY_TASKS = [
    {"id": "py-reverse", "type": "python",
     "prompt": "Write a Python function `reverse_words(s)` that reverses the "
               "order of words in a string, with single spaces between them. "
               "Reply with a single python code block only.",
     "test": "assert reverse_words('hello world foo')=='foo world hello'\n"
             "assert reverse_words('a')=='a'"},
    {"id": "py-fizzbuzz", "type": "python",
     "prompt": "Write a Python function `fizzbuzz(n)` returning a list for "
               "1..n where multiples of 3 are 'Fizz', of 5 are 'Buzz', of "
               "both 'FizzBuzz', else the number itself. Single python code "
               "block only.",
     "test": "assert fizzbuzz(5)==[1,2,'Fizz',4,'Buzz']\n"
             "assert fizzbuzz(15)[14]=='FizzBuzz'"},
    {"id": "py-semver", "type": "python",
     "prompt": "Write a Python function `cmp_semver(a,b)` comparing version "
               "strings like '1.2.10' vs '1.3'. Return -1, 0 or 1; missing "
               "parts count as 0. Single python code block only.",
     "test": "assert cmp_semver('1.2.10','1.3')==-1\n"
             "assert cmp_semver('2.0','2.0.0')==0\n"
             "assert cmp_semver('1.10.0','1.9.9')==1"},
    {"id": "py-bugfix", "type": "python",
     "prompt": "This Kadane implementation is buggy because the loop "
               "re-processes a[0]:\n\ndef max_sub(a):\n    best=cur=a[0]\n"
               "    for x in a:\n        cur=max(x,cur+x)\n"
               "        best=max(best,cur)\n    return best\n\n"
               "Provide the fixed `max_sub`. Single python code block only.",
     "test": "assert max_sub([2,-1,2,3])==6\nassert max_sub([-2,-1])==-1\n"
             "assert max_sub([5])==5"},
    {"id": "py-deepmerge", "type": "python",
     "prompt": "Write `merge_dicts(a,b)` deep-merging nested dicts (b wins "
               "on conflicts, nested dicts merge recursively, inputs not "
               "mutated). Single python code block only.",
     "test": "a={'x':{'y':1,'z':2}}\n"
             "assert merge_dicts(a,{'x':{'y':9},'w':3})=="
             "{'x':{'y':9,'z':2},'w':3}\nassert a=={'x':{'y':1,'z':2}}"},
    {"id": "py-fib", "type": "python",
     "prompt": "Write `fib(n)` returning the n-th Fibonacci number "
               "(fib(0)=0, fib(1)=1), efficient up to n=500. Single python "
               "code block only.",
     "test": "assert fib(10)==55\nassert len(str(fib(500)))==105"},
    {"id": "py-ips", "type": "python",
     "prompt": "Write a Python function `find_ips(text)` returning all valid "
               "IPv4 addresses (each octet 0-255, no leading partial "
               "matches) found in text, in order. Single python code block "
               "only.",
     "test": "assert find_ips('a 10.0.0.1 b 999.1.1.1 c 192.168.1.255')=="
             "['10.0.0.1','192.168.1.255']"},
    {"id": "tool-read", "type": "tool", "tools": [_QT_READ],
     "expect_tool": "read_file",
     "prompt": "Read the file src/main.rs using the tool."},
    {"id": "tool-pick", "type": "tool", "tools": [_QT_READ, _QT_GREP],
     "expect_tool": "grep_search",
     "prompt": "Find every TODO comment in the repository."},
    {"id": "fact-float", "type": "regex",
     "pattern": r"0\.30000000000000004",
     "prompt": "In Python, what exactly does print(0.1+0.2) output? Reply "
               "with just the printed value."},
    {"id": "fact-amend", "type": "regex",
     "pattern": r"git\s+commit\s+--amend",
     "prompt": "What single git command edits the message of the most "
               "recent (unpushed) commit? Reply with just the command."},
    {"id": "sql-agg", "type": "regex",
     "pattern": r"(?is)join.+group\s+by.+order\s+by",
     "prompt": "Write a single SQL query: total order amount per customer "
               "name, from tables customers(id,name) and "
               "orders(id,customer_id,amount), highest total first."},
]

def _extract_code(text):
    m = re.search(r"```(?:python)?\s*\n(.*?)```", text, re.S)
    return m.group(1) if m else text

def _chat(model, prompt, tools=None):
    payload = {"model": model, "max_tokens": 1024, "temperature": 0,
               "messages": [{"role": "user", "content": prompt}]}
    if tools:
        payload["tools"] = tools
    prov, name = parse_model(model)
    if prov == "anthropic":  # bench via anthropic: text-only tasks
        return {"content": cloud_chat(prov, name, payload["messages"])}
    if prov:
        key = cloud_keys().get(prov)
        if not key:
            die(f"no {prov} key -> lai cloud add {prov}")
        payload["model"] = name
        r = http_json(f"{CLOUD[prov]['base']}/chat/completions", payload,
                      timeout=300,
                      headers={"Authorization": f"Bearer {key}"})
        return r["choices"][0]["message"]
    r = http_json(f"{endpoint_base()}/v1/chat/completions",
                  payload, timeout=900, headers=auth_headers())
    return r["choices"][0]["message"]

def quality_bench(args):
    model = getattr(args, "model", None) or "coder"
    try:
        http_get(f"{endpoint_base()}/v1/models", timeout=3)
    except Exception:
        die(f"endpoint {endpoint_base()} not reachable -> lai start")
    info(f"quality benchmark: {len(QUALITY_TASKS)} tasks against "
         f"'{model}' (several minutes on slow tiers)...")
    results = []
    for t in QUALITY_TASKS:
        try:
            msg = _chat(model, t["prompt"], t.get("tools"))
            if t["type"] == "python":
                code = _extract_code(msg.get("content") or "")
                r = subprocess.run([sys.executable, "-c",
                                    code + "\n" + t["test"]],
                                   capture_output=True, timeout=30)
                passed = r.returncode == 0
            elif t["type"] == "tool":
                calls = msg.get("tool_calls") or []
                passed = bool(calls) and \
                    calls[0]["function"]["name"] == t["expect_tool"]
            else:
                passed = bool(re.search(t["pattern"],
                                        msg.get("content") or ""))
        except Exception:
            passed = False
        (ok if passed else fail)(t["id"])
        results.append({"id": t["id"], "passed": passed})
    score = sum(r["passed"] for r in results)
    print()
    info(f"score: {score}/{len(results)}")
    prev_score = None
    for f in sorted(BENCH_DIR.glob("quality-*.json"), reverse=True):
        prev = load_json(f)
        if prev and prev.get("model") == model:
            prev_score = prev.get("score")
            break
    if prev_score is not None:
        delta = score - prev_score
        info(f"previous run for '{model}': {prev_score} "
             f"({'+' if delta >= 0 else ''}{delta})")
    out = BENCH_DIR / f"quality-{datetime.now():%Y%m%d-%H%M%S}.json"
    save_text(out, json.dumps({"model": model, "score": score,
                               "total": len(results), "results": results,
                               "when": datetime.now().isoformat(
                                   timespec="seconds")}, indent=2))

def cmd_bench(args):
    if getattr(args, "quality", False):
        return quality_bench(args)
    bench = find_tool("llama-bench")
    active = load_json(ACTIVE_PATH)
    if not active:
        die("run `lai config` first")
    coder = active.get("coder_file")
    mode = active.get("coder_mode")
    targets = active.get("targets", {})
    if not coder:
        die("no coder model configured/downloaded")
    cmd = [bench, "-m", coder, "-p", "512", "-n", "128"]
    if mode == "cpu":
        cmd += ["-ngl", "0"]
    elif mode == "hybrid":
        cmd += ["-ngl", "99", "-ot", r".ffn_.*_exps.=CPU"]
    else:
        cmd += ["-ngl", "99"]
    env = os.environ.copy()
    if active.get("main_gpu") is not None:
        env["CUDA_VISIBLE_DEVICES"] = str(active["main_gpu"])
    info("benchmarking the coder model (a few minutes)...")
    r = subprocess.run([str(x) for x in cmd], capture_output=True, text=True,
                       env=env, timeout=3600)
    print(r.stdout)
    print(r.stderr)
    out_path = BENCH_DIR / f"bench-{datetime.now():%Y%m%d-%H%M%S}.txt"
    save_text(out_path, r.stdout + "\n" + r.stderr +
              f"\ntargets: pp >= {targets.get('pp', '?')} t/s, "
              f"tg >= {targets.get('tg', '?')} t/s\n")
    info(f"targets for this tier: pp >= {targets.get('pp', '?')} t/s, "
         f"tg >= {targets.get('tg', '?')} t/s (see docs/05 if below)")

def cmd_validate(args):
    results = []

    def record(name, status, detail=""):
        results.append((name, status))
        {"PASS": ok, "WARN": warn, "FAIL": fail}[status](f"{name} {detail}")

    base = f"{endpoint_base()}/v1"
    try:
        data = http_json(f"{base}/models", timeout=5)
        names = [m.get("id") for m in data.get("data", [])]
        record("llama-swap model list", "PASS", f"-> {names}")
    except Exception as e:
        record("llama-swap model list", "FAIL", str(e))
        die(f"endpoint {endpoint_base()} not reachable -> lai start "
            "(or lai connect <server>)")

    info("chat test (first call loads the model from disk - be patient)...")
    try:
        r = http_json(f"{base}/chat/completions", {
            "model": "coder", "max_tokens": 32,
            "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
        }, timeout=900, headers=auth_headers())
        text = r["choices"][0]["message"].get("content", "")
        record("chat completion (coder)", "PASS" if text.strip() else "FAIL",
               repr(text.strip()[:40]))
    except Exception as e:
        record("chat completion (coder)", "FAIL", str(e))

    try:
        r = http_json(f"{base}/chat/completions", {
            "model": "coder", "max_tokens": 256,
            "messages": [{"role": "user",
                          "content": "Read the file src/main.rs using the tool."}],
            "tools": [{"type": "function", "function": {
                "name": "read_file", "description": "Read a file from disk",
                "parameters": {"type": "object",
                               "properties": {"path": {"type": "string"}},
                               "required": ["path"]}}}],
        }, timeout=300, headers=auth_headers())
        calls = r["choices"][0]["message"].get("tool_calls")
        if calls:
            record("tool calling (agent readiness)", "PASS",
                   f"-> {calls[0]['function']['name']}")
        else:
            record("tool calling (agent readiness)", "WARN",
                   "answered in text; check --jinja in config")
    except Exception as e:
        record("tool calling (agent readiness)", "FAIL", str(e))

    try:
        r = http_json(f"{endpoint_base(P('autocomplete'))}/v1/completions", {
            "model": "autocomplete", "prompt": "def add(a, b):\n    return",
            "max_tokens": 8,
        }, timeout=120, headers=auth_headers())
        record("FIM autocomplete", "PASS",
               repr(r["choices"][0].get("text", "")[:30]))
    except Exception as e:
        record("FIM autocomplete", "WARN" if not load_json(CHOICES_PATH, {})
               .get("roles", {}).get("autocomplete") else "FAIL", str(e))

    try:
        r = http_json(f"{endpoint_base(P('embeddings'))}/v1/embeddings", {
            "model": "embeddings", "input": "func main() {}",
        }, timeout=120, headers=auth_headers())
        dim = len(r["data"][0]["embedding"])
        record("embeddings", "PASS", f"dim={dim}")
    except Exception as e:
        record("embeddings", "FAIL", str(e))

    try:
        http_get("http://localhost:6333/collections", timeout=5)
        record("qdrant", "PASS")
    except Exception:
        record("qdrant", "WARN", "not running -> lai docker")

    try:
        http_get("http://localhost:3000/", timeout=5)
        record("openhands", "PASS")
    except Exception:
        record("openhands", "WARN", "not running -> lai docker")

    print()
    failed = [n for n, s in results if s == "FAIL"]
    if failed:
        die(f"{len(failed)} test(s) failed: {', '.join(failed)}")
    ok(f"all critical tests passed ({len(results)} checks)")

def cmd_apikey(args):
    sec = load_json(SECRETS_PATH) or {}
    if getattr(args, "off", False):
        sec.pop("api_key", None)  # keep cloud keys intact
        if sec:
            save_text(SECRETS_PATH, json.dumps(sec, indent=2))
        else:
            SECRETS_PATH.unlink(missing_ok=True)
        info("API key removed - endpoints are open again (localhost trust)")
    else:
        key = token_secrets.token_hex(24)
        sec["api_key"] = key
        save_text(SECRETS_PATH, json.dumps(sec, indent=2))
        ok("API key generated (stored in state/secrets.json - keep private)")
        print(f"\n      {key}\n")
        info("set this key in: Continue (~/.continue/config.yaml -> apiKey),")
        info("Roo Code provider settings, OpenHands LLM settings, and the")
        info("OPENAI_API_KEY / LLM_API_KEY values in config/docker-compose.yml")
    if confirm("regenerate runtime config now?"):
        cmd_config(args)
        info("restart to apply: lai restart")

def cmd_autostart(args):
    lai = ROOT / "lai.py"
    if IS_WIN:
        startup = Path(os.environ["APPDATA"]) / \
            "Microsoft/Windows/Start Menu/Programs/Startup"
        target = startup / "lai-stack.cmd"
        if getattr(args, "remove", False):
            target.unlink(missing_ok=True)
            ok(f"removed {target}")
            return
        if not confirm(f"create login startup entry at {target}?"):
            return
        pyw = Path(sys.executable).with_name("pythonw.exe")
        py = pyw if pyw.exists() else Path(sys.executable)
        save_text(target, f'@start "" "{py}" "{lai}" watchdog\n')
    elif IS_MAC:
        plist = Path.home() / "Library/LaunchAgents/com.local-ai.lai.plist"
        if getattr(args, "remove", False):
            subprocess.run(["launchctl", "unload", str(plist)],
                           capture_output=True)
            plist.unlink(missing_ok=True)
            ok(f"removed {plist}")
            return
        if not confirm(f"create launchd agent at {plist}?"):
            return
        save_text(plist, f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.local-ai.lai</string>
  <key>ProgramArguments</key>
  <array><string>{sys.executable}</string><string>{lai}</string>
  <string>watchdog</string></array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
</dict></plist>
""")
        subprocess.run(["launchctl", "load", "-w", str(plist)])
    else:
        unit = Path.home() / ".config/systemd/user/lai-stack.service"
        if getattr(args, "remove", False):
            subprocess.run(["systemctl", "--user", "disable", "--now",
                            "lai-stack"], capture_output=True)
            unit.unlink(missing_ok=True)
            ok(f"removed {unit}")
            return
        if not confirm(f"create systemd user unit at {unit}?"):
            return
        unit.parent.mkdir(parents=True, exist_ok=True)
        save_text(unit, f"""[Unit]
Description=lai local AI stack (watchdog)

[Service]
ExecStart={sys.executable} {lai} watchdog
Restart=on-failure
RestartSec=10

[Install]
WantedBy=default.target
""")
        subprocess.run(["systemctl", "--user", "daemon-reload"])
        subprocess.run(["systemctl", "--user", "enable", "--now",
                        "lai-stack"])
    ok("autostart installed - the watchdog starts and monitors the stack "
       "at login (remove with: lai autostart --remove)")

def _wd_log(msg):
    line = f"{datetime.now().isoformat(timespec='seconds')} {msg}"
    print(line, flush=True)
    try:
        with open(LOGS / "watchdog.log", "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass

def cmd_watchdog(args):
    ensure_dirs()
    _wd_log("watchdog started (checks llama-swap every 60 s, Ctrl+C to stop)")
    while True:
        healthy = True
        try:
            http_get(f"http://localhost:{P('swap')}/v1/models", timeout=5)
        except Exception:
            healthy = False
        if not healthy:
            _wd_log("llama-swap not responding - (re)starting the stack")
            try:
                cmd_stop(args)
            except SystemExit:
                pass
            time.sleep(2)
            try:
                cmd_start(args)
                _wd_log("stack started")
            except SystemExit:
                _wd_log("start failed - will retry in 60 s "
                        "(see logs/ for the reason)")
        time.sleep(60)

def cmd_upgrade(args):
    vers = load_json(VERSIONS_PATH, {})
    newer = False
    for repo, key in (("ggml-org/llama.cpp", "llama.cpp"),
                      ("mostlygeek/llama-swap", "llama-swap")):
        latest = gh_latest_release(repo).get("tag_name")
        cur = vers.get(key)
        if cur == latest:
            ok(f"{key}: {cur} (up to date)")
        else:
            warn(f"{key}: installed {cur or 'unknown'} -> latest {latest}")
            newer = True
    info(f"the model catalog is local data ({CATALOG_PATH.name}) - update it "
         "by editing the file; verify repos with: lai catalog --verify")
    if newer:
        cmd_engines(args)  # asks its own approval before downloading
        info("restart to run on the new binaries: lai restart")
    else:
        ok("engines are current")

def cmd_setup(args):
    ensure_dirs()
    bad = [n for n in DEFAULT_PORTS
           if not port_free(P(n)) and "CONFLICT" in _port_status(n, P(n))]
    if bad:
        warn(f"port conflicts with other apps: {', '.join(bad)}")
        try:
            cmd_ports(argparse.Namespace(action="check", fix=True,
                                         name=None, value=None,
                                         yes=assume_yes()))
        except SystemExit:
            pass
    cmd_plan(args)
    cmd_engines(args)
    cmd_models(args)
    cmd_config(args)
    if confirm("install the Continue IDE config to ~/.continue/?"):
        cmd_ide(args)
    try:
        cmd_docker(args)  # asks its own approval; skippable
    except SystemExit:
        warn("docker services skipped - run `lai docker` later")
    if confirm("start the inference stack now?"):
        try:
            cmd_start(args)
        except SystemExit:
            warn("start failed - check `lai check` and `lai start`")
    print()
    ok("setup complete. next:")
    wrapper = ".\\lai.ps1" if IS_WIN else "./lai.sh"
    for step in ("validate", "bench", "ui"):
        print(f"        {wrapper} {step}")

def cmd_connect(args):
    if getattr(args, "off", False):
        (STATE / "remote.json").unlink(missing_ok=True)
        ok("disconnected - back to the local stack")
        info("re-run `lai ide` to point Continue back at localhost")
        return
    if not args.host:
        die("usage: lai connect <host[:port]> [--key K]  |  lai connect --off")
    host, _, port = args.host.partition(":")
    port = int(port or P('swap'))
    url = f"http://{host}:{port}/v1/models"
    try:
        data = http_json(url, timeout=5, headers=(
            {"Authorization": f"Bearer {args.key}"} if args.key else {}))
        served = [m.get("id") for m in data.get("data", [])]
    except Exception as e:
        die(f"cannot reach {url}: {e}\n"
            "       on the server: lai share on && lai restart "
            "(and open the firewall for 8080-8082)")
    save_text(STATE / "remote.json", json.dumps(
        {"host": host, "port": port,
         **({"api_key": args.key} if args.key else {})}, indent=2))
    ok(f"connected to {host}:{port} - serving: {served}")
    info("this machine now needs NO local models or GPU")
    if confirm("rewire the Continue IDE config to the server now?"):
        cmd_ide(args)

def cmd_share(args):
    if args.state == "on":
        save_text(STATE / "share.json", json.dumps({"enabled": True}))
        if not api_key():
            warn("no API key set - anyone on the network can use this "
                 "server. Strongly consider: lai apikey")
        cmd_config(args)
        ok("sharing enabled - side servers now bind 0.0.0.0; "
           "restart to apply: lai restart")
        info("teammates connect with: lai connect <this-machine-ip>"
             + (" --key <key>" if api_key() else ""))
        info("open inbound ports 8080-8082 in the firewall for the LAN")
    else:
        (STATE / "share.json").unlink(missing_ok=True)
        cmd_config(args)
        ok("sharing disabled - restart to apply: lai restart")

def _tune_trial(label, entry, m, model_file_path, mm, env):
    server = find_tool("llama-server")
    cmd = f"{server} {role_flags(entry, m, model_file_path, mm)} --port 8199"
    log = open(LOGS / "tune.log", "ab")
    log.write(f"\n=== {label}: {cmd}\n".encode())
    kwargs = {"stdout": log, "stderr": subprocess.STDOUT, "env": env}
    if IS_WIN:
        kwargs["creationflags"] = 0x08000000
    proc = subprocess.Popen(cmd.split(), **kwargs)
    try:
        deadline = time.time() + 240
        while time.time() < deadline:
            if proc.poll() is not None:
                return None  # crashed (likely OOM) - variant infeasible
            try:
                http_get("http://localhost:8199/health", timeout=2)
                break
            except Exception:
                time.sleep(2)
        else:
            return None
        r = http_json("http://localhost:8199/completion",
                      {"prompt": "Explain this code:\n" + ("x = x + 1\n" * 180),
                       "n_predict": 64, "temperature": 0},
                      timeout=600)
        t = r.get("timings", {})
        return {"pp": round(t.get("prompt_per_second", 0), 1),
                "tg": round(t.get("predicted_per_second", 0), 1)}
    except Exception:
        return None
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
        time.sleep(1)

def cmd_tune(args):
    cat = load_catalog()
    choices = load_choices()
    entry = choices["roles"].get("coder")
    if not entry:
        die("no coder configured")
    m = cat["models"][entry["model"]]
    f = model_file(entry["model"])
    if not f:
        die("coder model not downloaded -> lai models")
    mm = model_file(entry["model"], mmproj=True) if m.get("mmproj") else None
    env = os.environ.copy()
    active = load_json(ACTIVE_PATH, {})
    if active.get("main_gpu") is not None:
        env["CUDA_VISIBLE_DEVICES"] = str(active["main_gpu"])

    mode = entry["mode"]
    variants = [("current configuration", {})]
    if mode == "hybrid":
        for n in (40, 32, 24):
            variants.append((f"experts of first {n} layers on CPU "
                             f"(rest on GPU)", {"n_cpu_moe": n}))
    elif mode == "gpu":
        variants.append(("KV cache f16 (less quantization overhead)",
                         {"kv": "f16"}))
    else:
        cores = os.cpu_count() or 4
        variants.append((f"threads={cores // 2} (physical cores)",
                         {"threads": cores // 2}))

    if not confirm(f"run {len(variants)} timed trials of the coder model "
                   "(~2-5 min each, GPU/CPU will be busy)?"):
        return
    results = []
    for label, override in variants:
        info(f"trial: {label} ...")
        res = _tune_trial(label, dict(entry, **override), m, f, mm, env)
        if res:
            ok(f"  pp {res['pp']} t/s | tg {res['tg']} t/s")
            results.append((label, override, res))
        else:
            warn("  infeasible on this hardware (crashed or timed out) - "
                 "skipped")
    if not results:
        die("no variant completed - see logs/tune.log")
    best = max(results, key=lambda x: (x[2]["tg"], x[2]["pp"]))
    print()
    for label, _, res in results:
        marker = " <- best" if label == best[0] else ""
        info(f"{res['tg']:>7} tg | {res['pp']:>7} pp | {label}{marker}")
    save_text(BENCH_DIR / f"tune-{datetime.now():%Y%m%d-%H%M%S}.json",
              json.dumps([{"label": x[0], **x[2]} for x in results],
                         indent=2))
    if best[1] and confirm(f"apply '{best[0]}' to the coder config?"):
        entry.update(best[1])
        save_text(CHOICES_PATH, json.dumps(choices, indent=2))
        cmd_config(args)
        info("restart to run tuned: lai restart")
    elif not best[1]:
        ok("current configuration is already the fastest")

def cmd_shortcut(args):
    lai = ROOT / "lai.py"
    icon = ROOT / "assets" / "icon.svg"
    remove = getattr(args, "remove", False)
    if IS_WIN:
        pyw = Path(sys.executable).with_name("pythonw.exe")
        py = pyw if pyw.exists() else Path(sys.executable)
        ps = (
            "$sh = New-Object -ComObject WScript.Shell; "
            "$desk = [Environment]::GetFolderPath('Desktop'); "
            "$menu = Join-Path ([Environment]::GetFolderPath('Programs')) ''; "
            "foreach ($dir in @($desk, $menu)) { "
            "  $p = Join-Path $dir 'Local AI Env.lnk'; "
            + ("Remove-Item -ErrorAction SilentlyContinue $p; " if remove else
               f"  $s = $sh.CreateShortcut($p); "
               f"  $s.TargetPath = '{py}'; "
               f"  $s.Arguments = '\"\"{lai}\"\" ui'; "
               f"  $s.WorkingDirectory = '{ROOT}'; "
               f"  $s.Description = 'Local AI programming environment'; "
               f"  $s.Save(); ")
            + "} ")
        if remove or confirm("create 'Local AI Env' shortcuts on the "
                             "Desktop and Start Menu (opens the dashboard)?"):
            r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                               capture_output=True, text=True)
            if r.returncode != 0:
                die(f"shortcut creation failed: {r.stderr.strip()}")
            ok("shortcuts removed" if remove else
               "shortcuts created (Desktop + Start Menu)")
    elif IS_MAC:
        app = Path.home() / "Applications" / "Local AI Env.command"
        if remove:
            app.unlink(missing_ok=True)
            ok(f"removed {app}")
            return
        if confirm(f"create launcher at {app}?"):
            app.parent.mkdir(parents=True, exist_ok=True)
            save_text(app, f"#!/bin/bash\ncd '{ROOT}'\n"
                           f"'{sys.executable}' '{lai}' ui\n")
            app.chmod(0o755)
            ok(f"created {app} (double-click opens the dashboard)")
    else:
        desktop_file = Path.home() / ".local/share/applications" / \
            "local-ai-env.desktop"
        if remove:
            desktop_file.unlink(missing_ok=True)
            ok(f"removed {desktop_file}")
            return
        if confirm(f"create launcher at {desktop_file}?"):
            desktop_file.parent.mkdir(parents=True, exist_ok=True)
            save_text(desktop_file, f"""[Desktop Entry]
Type=Application
Name=Local AI Env
Comment=Local AI programming environment
Exec={sys.executable} {lai} ui
Icon={icon}
Terminal=false
Categories=Development;
""")
            ok(f"created {desktop_file} (appears in the app menu)")


def _port_status(name, port):
    # our own probe first: docker port-forwarding on Windows does not
    # always block a localhost bind, so a bind test alone lies
    for label, url in probes():
        if f":{port}" in url.split("/", 3)[2]:
            try:
                http_get(url, timeout=1.5)
                return "in use by lai (ok)"
            except Exception:
                continue
    if port_free(port):
        return "free"
    return "CONFLICT (another app)"


def cmd_ports(args):
    action = getattr(args, "action", None) or "show"
    if action == "set":
        if not args.name or not args.value:
            die("usage: lai ports set <name> <port>")
        if args.name not in DEFAULT_PORTS:
            die(f"unknown port name - one of: {', '.join(DEFAULT_PORTS)}")
        set_port(args.name, args.value)
        ok(f"{args.name} -> {args.value}")
        info("apply: lai config && lai restart | docker services: "
             "lai docker | IDE: lai ide")
        return
    rows = [(n, DEFAULT_PORTS[n], P(n), _port_status(n, P(n)))
            for n in DEFAULT_PORTS]
    print()
    print(c("1", f"  {'PORT NAME':<14}{'DEFAULT':<10}{'CURRENT':<10}STATUS"))
    for n, d, cur, st in rows:
        line = f"  {n:<14}{d:<10}{cur:<10}{st}"
        (fail if "CONFLICT" in st else info)(line) if "CONFLICT" in st \
            else print(line)
    conflicts = [(n, cur) for n, d, cur, st in rows if "CONFLICT" in st]
    if not conflicts:
        ok("no port conflicts")
        return
    if action == "check" and not getattr(args, "fix", False):
        warn(f"{len(conflicts)} conflict(s) - resolve with: lai ports check "
             "--fix  (or: lai ports set <name> <port>)")
        sys.exit(1)
    if action == "check":
        for n, cur in conflicts:
            new = next_free_port(cur)
            if confirm(f"move '{n}' from busy port {cur} to free port "
                       f"{new}?"):
                set_port(n, new)
                ok(f"{n} -> {new}")
        info("re-applying configuration...")
        try:
            cmd_config(args)
        except SystemExit:
            pass
        info("then: lai restart | lai docker | lai ide (to rewire Continue)")


def cmd_go(args):
    """The one-word beginner path: set everything up with one question."""
    print()
    print(c("1", "  Hi! I'm lai. I'll set up your very own AI helper - it"))
    print(c("1", "  lives on THIS computer, it's free, and nothing you type"))
    print(c("1", "  ever leaves your machine."))
    print()
    cat = load_catalog()
    choices = load_json(CHOICES_PATH)
    if not choices:
        hw = detect_hw(interactive=False)
        tier = match_tier(cat, hw)
        if not tier:
            die("this computer is below the minimum (see docs/06)")
        choices = build_choices(cat, tier, hw)
        apply_usecase(cat, choices, "general")
        save_text(CHOICES_PATH, json.dumps(choices, indent=2))
    need_models = wanted_models(cat, choices)
    gb = sum(m["disk_gb"] for _, m in need_models)
    need_engine = not find_tool("llama-server", required=False)
    todo = []
    if need_engine:
        todo.append("the AI engine (about 1 GB)")
    if need_models:
        todo.append(f"the AI brains (about {gb:.0f} GB - this is the "
                    "slow part, you can keep using the computer)")
    if todo:
        if not confirm("I need to download " + " and ".join(todo) +
                       ". Everything is free. Start?"):
            info("okay - run `lai go` whenever you're ready")
            return
    was = assume_yes()
    set_assume_yes(True)  # the user just gave the one approval that matters
    try:
        try:
            cmd_ports(argparse.Namespace(action="check", fix=True, name=None,
                                         value=None, yes=True))
        except SystemExit:
            pass
        if need_engine:
            info("step 1: getting the AI engine...")
            cmd_engines(args)
        if need_models:
            info("step 2: downloading the AI brains (smallest first)...")
            cmd_models(args)
        info("step 3: wiring everything together...")
        cmd_config(args)
        try:
            cmd_ide(args)
        except SystemExit:
            pass
        try:
            cmd_docker(args)
        except SystemExit:
            warn("extra tools skipped (Docker not ready) - everything "
                 "important still works")
        info("step 4: starting your AI...")
        try:
            cmd_stop(args)
        except SystemExit:
            pass
        cmd_start(args)
    finally:
        set_assume_yes(was)
    print()
    ok("ALL DONE! Your AI helper is running.")
    print(f"""
  Try these:
    1. Open  http://127.0.0.1:{P('ui')}  - your control room
       (or double-click the 'Local AI Env' icon)
    2. Type in the chat box: "write a snake game in Python"
    3. In a terminal:  lai chat
""")


def notify_os(title, msg):
    """Best-effort native OS notification (toast / notify-send / osascript)."""
    title = re.sub(r"[\"`$']", "", title)[:60]
    msg = re.sub(r"[\"`$']", "", msg)[:200]
    try:
        if IS_WIN:
            ps = (
                "[Windows.UI.Notifications.ToastNotificationManager, "
                "Windows.UI.Notifications, ContentType=WindowsRuntime] "
                "| Out-Null; "
                "$t = [Windows.UI.Notifications.ToastNotificationManager]::"
                "GetTemplateContent([Windows.UI.Notifications."
                "ToastTemplateType]::ToastText02); "
                "$x = $t.GetElementsByTagName('text'); "
                f"$x.Item(0).AppendChild($t.CreateTextNode('{title}')) "
                "| Out-Null; "
                f"$x.Item(1).AppendChild($t.CreateTextNode('{msg}')) "
                "| Out-Null; "
                "[Windows.UI.Notifications.ToastNotificationManager]::"
                "CreateToastNotifier('lai').Show("
                "[Windows.UI.Notifications.ToastNotification]::new($t))")
            subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                           capture_output=True, timeout=20)
        elif IS_MAC:
            subprocess.run(["osascript", "-e",
                            f'display notification "{msg}" '
                            f'with title "{title}"'],
                           capture_output=True, timeout=10)
        elif shutil.which("notify-send"):
            subprocess.run(["notify-send", title, msg],
                           capture_output=True, timeout=10)
    except Exception:
        pass


def cmd_refresh(args):
    """Look for newly released models + catalog updates; notify on findings."""
    sched = getattr(args, "schedule", None)
    if sched:
        return _refresh_schedule(sched)
    cat = load_catalog()
    quiet = getattr(args, "quiet", False)
    state = load_json(STATE / "updates.json") or {}
    seen = set(state.get("seen", []))
    findings = []

    # 1. is a newer published catalog available?
    catalog_newer = False
    try:
        status, raw = http_get(CATALOG_UPDATE_URL, timeout=30)
        remote_ver = json.loads(raw.decode("utf-8-sig")).get(
            "catalog_version", "")
        catalog_newer = remote_ver > cat.get("catalog_version", "")
        if catalog_newer:
            findings.append(f"published catalog {remote_ver} is newer - "
                            "apply with: lai catalog --update")
    except Exception:
        pass

    # 1b. is lai itself behind? (policy auto -> apply right here)
    if (ROOT / ".git").exists() and shutil.which("git"):
        subprocess.run(["git", "-C", str(ROOT), "fetch", "--quiet"],
                       capture_output=True)
        behind = subprocess.run(
            ["git", "-C", str(ROOT), "rev-list", "--count",
             "HEAD..@{upstream}"], capture_output=True,
            text=True).stdout.strip()
        if behind.isdigit() and int(behind) > 0:
            if update_policy() == "auto":
                r = subprocess.run(["git", "-C", str(ROOT), "pull",
                                    "--ff-only"], capture_output=True,
                                   text=True)
                findings.append(
                    f"lai auto-updated ({behind} commit(s)) - see CHANGELOG"
                    if r.returncode == 0 else
                    "lai update available but auto-pull failed - run "
                    "`lai update`")
            else:
                findings.append(f"lai update available ({behind} "
                                "commit(s)) - run `lai update`")

    # 2. do all current repos still resolve?
    broken = []
    for mid, m in cat["models"].items():
        try:
            http_get(f"https://huggingface.co/api/models/{m['repo']}",
                     timeout=15)
        except Exception as e:
            if getattr(e, "code", None) not in (401, 403):  # gated is fine
                broken.append(mid)
    if broken:
        findings.append("repos no longer resolve: " + ", ".join(broken) +
                        f" - update entries in {CATALOG_PATH.name}")

    # 3. discover fresh GGUF releases on Hugging Face
    disc = cat.get("discovery", {})
    known = {m["repo"].lower() for m in cat["models"].values()}
    fresh = {}
    cutoff = time.time() - disc.get("max_age_days", 90) * 86400
    for author in disc.get("authors", []):
        for q in disc.get("queries", []):
            try:
                rows = http_json(
                    "https://huggingface.co/api/models"
                    f"?author={author}&search={q}&sort=createdAt"
                    "&direction=-1&limit=10&filter=gguf", timeout=30)
            except Exception:
                continue
            for r in rows:
                rid = r.get("id", "")
                dl = r.get("downloads", 0)
                created = r.get("createdAt", "")
                if rid.lower() in known or rid in seen:
                    continue
                if dl < disc.get("min_downloads", 2000):
                    continue
                try:
                    ts = datetime.fromisoformat(
                        created.replace("Z", "+00:00")).timestamp()
                    if ts < cutoff:
                        continue
                except (ValueError, AttributeError):
                    continue
                fresh[rid] = dl
    new_models = sorted(fresh.items(), key=lambda x: -x[1])[:10]
    if new_models:
        findings.append(f"{len(new_models)} new GGUF model(s) since this "
                        "catalog - review below, add the good ones to "
                        "catalog.json, then: lai plan")

    save_text(STATE / "updates.json", json.dumps({
        "when": datetime.now().isoformat(timespec="seconds"),
        "catalog_newer": catalog_newer,
        "broken": broken,
        "new_models": [{"id": i, "downloads": d} for i, d in new_models],
        "seen": sorted(seen | {i for i, _ in new_models})[-200:],
    }, indent=2))

    if not quiet:
        print()
        if findings:
            for f_ in findings:
                warn(f_)
            for rid, dl in new_models:
                print(f"    new: {rid:<52} {dl:>8,} downloads")
            info("nothing changes without you: review, edit the catalog, "
                 "re-plan, bench - approval stays yours")
        else:
            ok("everything is current: catalog, repos, and no notable new "
               "models for your hardware")
    if findings:
        notify_os("lai: model updates found",
                  findings[0] + (" (+more)" if len(findings) > 1 else ""))


def _refresh_schedule(mode):
    lai = ROOT / "lai.py"
    if IS_WIN:
        if mode == "off":
            subprocess.run(["schtasks", "/Delete", "/F", "/TN",
                            "lai-refresh"], capture_output=True)
            ok("scheduled refresh removed")
            return
        pyw = Path(sys.executable).with_name("pythonw.exe")
        py = pyw if pyw.exists() else Path(sys.executable)
        freq = {"daily": ["/SC", "DAILY"],
                "weekly": ["/SC", "WEEKLY", "/D", "SUN"]}[mode]
        r = subprocess.run(
            ["schtasks", "/Create", "/F", "/TN", "lai-refresh",
             "/TR", f'"{py}" "{lai}" refresh --quiet --yes'] + freq,
            capture_output=True, text=True)
        if r.returncode != 0:
            die(f"schtasks failed: {r.stderr.strip()}")
    elif IS_MAC:
        plist = Path.home() / "Library/LaunchAgents/com.local-ai.refresh.plist"
        if mode == "off":
            subprocess.run(["launchctl", "unload", str(plist)],
                           capture_output=True)
            plist.unlink(missing_ok=True)
            ok("scheduled refresh removed")
            return
        day = "<key>Weekday</key><integer>0</integer>" \
            if mode == "weekly" else ""
        save_text(plist, f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.local-ai.refresh</string>
  <key>ProgramArguments</key>
  <array><string>{sys.executable}</string><string>{lai}</string>
  <string>refresh</string><string>--quiet</string><string>--yes</string></array>
  <key>StartCalendarInterval</key>
  <dict>{day}<key>Hour</key><integer>12</integer></dict>
</dict></plist>
""")
        subprocess.run(["launchctl", "load", "-w", str(plist)])
    else:
        marker = "# lai-refresh"
        cur = subprocess.run(["crontab", "-l"], capture_output=True,
                             text=True).stdout
        lines = [ln for ln in cur.splitlines() if marker not in ln]
        if mode != "off":
            spec = "0 12 * * 0" if mode == "weekly" else "0 12 * * *"
            lines.append(f"{spec} {sys.executable} {lai} refresh --quiet "
                         f"--yes {marker}")
        p = subprocess.run(["crontab", "-"], input="\n".join(lines) + "\n",
                           capture_output=True, text=True)
        if p.returncode != 0:
            die("crontab failed - is cron installed?")
        if mode == "off":
            ok("scheduled refresh removed")
            return
    ok(f"refresh scheduled ({mode}) - you will get an OS notification "
       "whenever new models or catalog updates appear")


def update_policy():
    return (load_json(STATE / "settings.json") or {}).get("update_policy",
                                                          "ask")


def ver_key(v):
    """Numeric version ordering: 0.10.0 > 0.9.3 (string compare lies)."""
    return [int(x) for x in re.findall(r"\d+", v)[:4]] or [0]


def _changelog_delta(since_version):
    """Entries from CHANGELOG.md newer than the given version."""
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8",
                                             errors="replace") \
        if (ROOT / "CHANGELOG.md").exists() else ""
    out, take = [], False
    for line in text.splitlines():
        m = re.match(r"## \[([0-9][\w.\-]*)\]", line)
        if m:
            take = ver_key(m.group(1)) > ver_key(since_version)
        if take:
            out.append(line)
    return "\n".join(out).strip()


def cmd_update(args):
    """Self-update via git: only changed files move - no update server."""
    if getattr(args, "policy", None):
        s = load_json(STATE / "settings.json") or {}
        s["update_policy"] = args.policy
        save_text(STATE / "settings.json", json.dumps(s, indent=2))
        ok(f"update policy: {args.policy} "
           "(auto = applied silently, also by scheduled refresh; "
           "ask = confirm first; never = manual `lai update` only)")
        return
    if not (ROOT / ".git").exists() or not shutil.which("git"):
        die("this install is not a git clone - update by re-running the "
            "installer (it preserves your state/ and models/)")
    subprocess.run(["git", "-C", str(ROOT), "fetch", "--tags", "--quiet"],
                   capture_output=True)
    if getattr(args, "list_versions", False):
        tags = subprocess.run(["git", "-C", str(ROOT), "tag", "--sort",
                               "-creatordate"], capture_output=True,
                              text=True).stdout.split()
        cur = subprocess.run(["git", "-C", str(ROOT), "describe", "--tags",
                              "--always"], capture_output=True,
                             text=True).stdout.strip()
        info(f"current: {cur} (lai {VERSION})")
        for t in tags[:15] or ["(no tags published yet)"]:
            print(f"  {t}")
        info("switch: lai update --to <tag>   |   back to newest: "
             "lai update --to main")
        return
    if getattr(args, "to", None):
        dirty = subprocess.run(["git", "-C", str(ROOT), "status",
                                "--porcelain"], capture_output=True,
                               text=True).stdout.strip()
        if dirty:
            die("local changes present - commit or stash them before "
                "switching versions")
        target = args.to
        r = subprocess.run(["git", "-C", str(ROOT), "checkout", target],
                           capture_output=True, text=True)
        if r.returncode != 0:
            die(f"cannot switch to '{target}': {r.stderr.strip()}")
        if target in ("main", "master"):
            subprocess.run(["git", "-C", str(ROOT), "pull", "--ff-only"],
                           capture_output=True)
        ok(f"now on {target} - restart the stack: lai restart")
        return

    behind = subprocess.run(
        ["git", "-C", str(ROOT), "rev-list", "--count",
         "HEAD..@{upstream}"], capture_output=True, text=True).stdout.strip()
    if not behind.isdigit() or int(behind) == 0:
        ok(f"lai {VERSION} is up to date")
        return
    files = subprocess.run(
        ["git", "-C", str(ROOT), "diff", "--name-only",
         "HEAD..@{upstream}"], capture_output=True, text=True
    ).stdout.split()
    sections = {}
    for f in files:
        sections.setdefault(f.split("/")[0], 0)
        sections[f.split("/")[0]] += 1
    info(f"update available: {behind} commit(s), {len(files)} file(s) - "
         + ", ".join(f"{k} ({v})" for k, v in sorted(sections.items())))
    delta = _changelog_delta(VERSION)
    if delta:
        print(c("90", "\n" + delta + "\n"))
    if getattr(args, "check", False):
        info("apply with: lai update")
        return
    pol = update_policy()
    if pol == "never":
        info("update policy is 'never' - apply manually with "
             "`lai update --policy ask` first, or review the diff yourself")
        return
    if pol == "ask" and not confirm("apply this update now? (only the "
                                    "changed files move; your state/, "
                                    "models/, and projects are untouched)"):
        return
    r = subprocess.run(["git", "-C", str(ROOT), "pull", "--ff-only"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        die(f"pull failed: {r.stderr.strip()}")
    ok("updated - changed sections only")
    if any(f.startswith("laicore") or f == "lai.py" for f in files):
        info("code changed: lai restart")
    if any(f.startswith("ui/") for f in files):
        info("dashboard changed: it reloads on next open")
    if any(f.startswith("config/catalog") for f in files):
        info("catalog changed: lai plan to re-evaluate")
    notify_os("lai updated", f"{behind} change(s) applied - see CHANGELOG")


def cmd_selftest(args):
    info("running the offline test suite (tests/)...")
    r = subprocess.run([sys.executable, "-m", "unittest", "discover",
                        "-s", str(ROOT / "tests")], cwd=str(ROOT))
    if r.returncode != 0:
        die("selftest FAILED")
    ok("all tests passed")


def cmd_mirror(args):
    """Pick the fastest Hugging Face mirror for model downloads."""
    if getattr(args, "set_url", None):
        s = load_json(STATE / "settings.json") or {}
        s["hf_endpoint"] = args.set_url.rstrip("/")
        save_text(STATE / "settings.json", json.dumps(s, indent=2))
        ok(f"downloads will use {args.set_url}")
        return
    info("measuring real download speed from each mirror (~2 MB each)...")
    results = []
    for ep in hf_mirrors():
        speed = mirror_speed(ep)
        mark = " (current)" if ep == hf_endpoint() else ""
        (ok if speed > 0 else fail)(f"{ep:<28} {speed:6.2f} MB/s{mark}")
        results.append((speed, ep))
    results.sort(reverse=True)
    best_speed, best = results[0]
    if best_speed <= 0:
        die("no mirror is reachable - check your connection")
    if best == hf_endpoint():
        ok(f"already using the fastest mirror: {best}")
        return
    if confirm(f"switch downloads to {best} ({best_speed} MB/s)?"):
        s = load_json(STATE / "settings.json") or {}
        s["hf_endpoint"] = best
        save_text(STATE / "settings.json", json.dumps(s, indent=2))
        ok(f"downloads now use {best} - restart any running download "
           "to apply")


def _native_fetch(m, dest, endpoint):
    """Last-resort downloader: plain ranged HTTP, our own resume loop.
    Survives the network conditions that wedge the hf client stack."""
    tok = (load_json(SECRETS_PATH) or {}).get("hf_token")
    auth = {"Authorization": f"Bearer {tok}"} if tok else {}
    try:
        tree = http_json(f"{endpoint}/api/models/{m['repo']}/tree/main",
                         timeout=30, headers=auth)
    except Exception:
        return False
    files = []
    for f in tree:
        if f.get("type") != "file":
            continue
        if any(fnmatch.fnmatch(Path(f["path"]).name.lower(), p.lower())
               for p in m["include"]):
            size = f.get("size") or (f.get("lfs") or {}).get("size") or 0
            files.append((f["path"], size))
    if not files:
        return False
    for name, size in files:
        out = dest / name
        if out.exists() and (not size or out.stat().st_size == size):
            continue
        part = Path(str(out) + ".part")
        out.parent.mkdir(parents=True, exist_ok=True)
        url = f"{endpoint}/{m['repo']}/resolve/main/{name}"
        pos = part.stat().st_size if part.exists() else 0
        info(f"       native fetch: {Path(name).name} "
             f"({size / 2**30:.2f} GB, resuming at {pos / 2**20:.0f} MB)")
        idle = 0
        with open(part, "ab") as fh:
            while pos < size:
                req = urllib.request.Request(url, headers={
                    "User-Agent": "lai", "Range": f"bytes={pos}-", **auth})
                before = pos
                try:
                    with urllib.request.urlopen(req, timeout=30) as r:
                        while True:
                            chunk = r.read(262144)
                            if not chunk:
                                break
                            fh.write(chunk)
                            pos += len(chunk)
                            if pos // (200 * 2**20) != \
                                    (pos - len(chunk)) // (200 * 2**20):
                                pct = pos * 100 // max(size, 1)
                                print(f"       {Path(name).name}: "
                                      f"{render_bar(pct, 20)} {pct}% "
                                      f"({pos / 2**30:.2f}/"
                                      f"{size / 2**30:.2f} GB)", flush=True)
                except Exception:
                    pass  # drop -> reconnect with a fresh Range below
                idle = idle + 1 if pos == before else 0
                if idle >= 40:  # ~20 min of pure failure: let the
                    return False  # ladder rotate to another mirror
                if pos == before:
                    time.sleep(min(30, 3 * idle))
        if size and part.stat().st_size != size:
            return False
        part.replace(out)
        ok(f"       {Path(name).name} complete")
    return True
