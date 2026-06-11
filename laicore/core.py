"""lai kernel: paths, console, http, secrets, hardware detection, planning,
model-fit logic, and LLM primitives. No internal imports - everything else
imports this."""

import argparse
import ctypes
import fnmatch
import json
import os
import platform
import re
import secrets as token_secrets
import shutil
import signal
import subprocess
import sys
import tarfile
import time
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path

VERSION = "0.9.0"

SYSTEM = platform.system()

IS_WIN = SYSTEM == "Windows"

IS_MAC = SYSTEM == "Darwin"

PLAT = {"Windows": "windows", "Darwin": "mac"}.get(SYSTEM, "linux")

EXE = ".exe" if IS_WIN else ""

ROOT = Path(__file__).resolve().parent.parent

TOOLS = ROOT / "tools"

MODELS = ROOT / "models"

CONFIG = ROOT / "config"

LOGS = ROOT / "logs"

RUN = ROOT / "run"

BENCH_DIR = ROOT / "benchmarks"

TMP = ROOT / "tmp"

STATE = ROOT / "state"  # machine-local, never committed (see .gitignore)

CATALOG_PATH = CONFIG / "catalog.json"

CHOICES_PATH = STATE / "choices.json"

SECRETS_PATH = STATE / "secrets.json"

PROJECTS_PATH = STATE / "projects.json"

GEN_YAML = STATE / "llama-swap.generated.yaml"

GEN_SIDE = STATE / "sideservers.generated.json"

ACTIVE_PATH = STATE / "active.json"

VERSIONS_PATH = TOOLS / "versions.json"

_LEGACY_STATE = ("choices.json", "secrets.json", "active.json",
                 "projects.json", "llama-swap.generated.yaml",
                 "sideservers.generated.json")

DEFAULT_PORTS = {"swap": 8080, "autocomplete": 8081, "embeddings": 8082,
                 "ui": 8090, "qdrant": 6333, "openhands": 3000,
                 "webui": 3001, "searxng": 8888, "openmemory": 8765}
PORTS_PATH = STATE / "ports.json"
_PORTS_CACHE = None


def ports():
    global _PORTS_CACHE
    if _PORTS_CACHE is None:
        _PORTS_CACHE = {**DEFAULT_PORTS, **(load_json(PORTS_PATH) or {})}
    return _PORTS_CACHE


def P(name):
    return ports()[name]


def set_port(name, value):
    global _PORTS_CACHE
    cur = load_json(PORTS_PATH) or {}
    cur[name] = int(value)
    save_text(PORTS_PATH, json.dumps(cur, indent=2))
    _PORTS_CACHE = None


def port_free(port):
    """True if nothing answers on the port (connect test - reliable even
    for docker-forwarded and 0.0.0.0 listeners, unlike a bind test)."""
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.8)
    try:
        return s.connect_ex(("127.0.0.1", int(port))) != 0
    finally:
        s.close()


def next_free_port(start):
    p = int(start) + 1
    taken = set(ports().values())
    while p < 65000 and (not port_free(p) or p in taken):
        p += 1
    return p

ROLES = ["coder", "thinker", "vision", "autocomplete", "embeddings"]

BIG_ROLES = ["coder", "thinker", "vision"]  # served via llama-swap, one at a time

ASSUME_YES = False

def set_assume_yes(value):
    global ASSUME_YES
    ASSUME_YES = bool(value)

def assume_yes():
    return ASSUME_YES

if IS_WIN:
    os.system("")  # enable ANSI escape processing in legacy consoles

def c(code, text):
    return f"\033[{code}m{text}\033[0m" if sys.stdout.isatty() else text

def info(msg):
    print(c("36", "[lai] ") + msg)

def ok(msg):
    print(c("32", "  OK  ") + msg)

def warn(msg):
    print(c("33", " WARN ") + msg)

def fail(msg):
    print(c("31", " FAIL ") + msg)

def die(msg):
    fail(msg)
    sys.exit(1)

def confirm(question):
    """Approval gate for anything that installs/downloads/overwrites."""
    if ASSUME_YES:
        info(f"{question} -> auto-approved (--yes)")
        return True
    if not sys.stdin.isatty():
        warn(f"skipped (needs approval, non-interactive session): {question}")
        warn("re-run with --yes to approve automatically")
        return False
    try:
        ans = input(c("35", f"  ?   {question} [y/N] ")).strip().lower()
    except EOFError:
        return False
    return ans in ("y", "yes")

def ensure_dirs():
    for d in (TOOLS, MODELS, CONFIG, LOGS, RUN, BENCH_DIR, STATE):
        d.mkdir(parents=True, exist_ok=True)
    for name in _LEGACY_STATE:  # one-time migration from the old layout
        old, new = CONFIG / name, STATE / name
        if old.exists() and not new.exists():
            old.rename(new)
            info(f"migrated {name} from config/ to state/")

def http_json(url, payload=None, timeout=10, headers=None, method=None):
    hdrs = {"User-Agent": "lai-setup", "Content-Type": "application/json"}
    hdrs.update(headers or {})
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())

def http_get(url, timeout=5):
    req = urllib.request.Request(url, headers={"User-Agent": "lai"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read()

def render_bar(pct, width=26):
    full, empty = ("#", "-")
    try:
        "?".encode(sys.stdout.encoding or "utf-8")
        full, empty = "?", "?"
    except (UnicodeEncodeError, LookupError):
        pass
    n = max(0, min(width, int(width * pct / 100)))
    return full * n + empty * (width - n)


def download(url, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    info(f"downloading {url}")
    state = {"last": -10, "t0": time.time()}

    def hook(blocks, bsize, total):
        if total <= 0:
            return
        done = min(blocks * bsize, total)
        pct = done * 100 // total
        if sys.stdout.isatty():
            speed = done / max(time.time() - state["t0"], 0.1) / 2 ** 20
            print(f"\r  {render_bar(pct)} {pct:3d}%  "
                  f"{done / 2**20:7.1f}/{total / 2**20:.1f} MB  "
                  f"{speed:5.1f} MB/s  {dest.name[:30]}",
                  end="", flush=True)
        elif pct >= state["last"] + 10:  # logs/CI: one line per 10%
            state["last"] = pct
            print(f"       {dest.name}: {pct}%", flush=True)

    urllib.request.urlretrieve(url, dest, reporthook=hook)
    if sys.stdout.isatty():
        print()

def extract(archive, dest):
    dest.mkdir(parents=True, exist_ok=True)
    name = archive.name.lower()
    if name.endswith(".zip"):
        with zipfile.ZipFile(archive) as z:
            z.extractall(dest)
    elif name.endswith((".tar.gz", ".tgz", ".tar")):
        with tarfile.open(archive) as t:
            t.extractall(dest)
    else:
        die(f"unknown archive format: {archive}")
    if not IS_WIN:  # restore execute bits lost by zip extraction
        for f in dest.rglob("*"):
            if f.is_file():
                f.chmod(0o755)

def gh_latest_release(repo):
    return http_json(f"https://api.github.com/repos/{repo}/releases/latest",
                     timeout=30)

def gh_pick_asset(release, patterns, exclude=None):
    for pat in patterns:
        for asset in release.get("assets", []):
            if exclude and re.search(exclude, asset["name"], re.I):
                continue
            if re.search(pat, asset["name"], re.I):
                return asset
    return None

def find_tool(name, required=True):
    hits = sorted(TOOLS.rglob(name + EXE))
    if hits:
        return hits[0]
    on_path = shutil.which(name)
    if on_path:
        return Path(on_path)
    if required:
        die(f"'{name}' not found under {TOOLS} or on PATH - run: lai engines")
    return None

def load_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default

def save_text(path, text):
    Path(path).write_text(text, encoding="utf-8", newline="\n")
    info(f"wrote {path}")

CLOUD = {  # optional cloud fallbacks - local is ALWAYS the default
    "openrouter": {"base": "https://openrouter.ai/api/v1", "prefix": "or"},
    "openai": {"base": "https://api.openai.com/v1", "prefix": "oa"},
    "anthropic": {"base": "https://api.anthropic.com", "prefix": "an"},
}

def api_key():
    return (load_json(SECRETS_PATH) or {}).get("api_key")

def cloud_keys():
    return (load_json(SECRETS_PATH) or {}).get("cloud", {})

def cloud_prefs():
    return load_json(STATE / "cloud.json") or {}


def save_cloud_prefs(prefs):
    save_text(STATE / "cloud.json", json.dumps(prefs, indent=2))


def parse_model(mid):
    """'or:qwen/x' -> ('openrouter','qwen/x'). Bare 'or:' uses the saved
    default model for that provider. Plain ids stay local."""
    for prov, spec in CLOUD.items():
        if mid and (mid == spec["prefix"] or
                    mid.startswith(spec["prefix"] + ":")):
            name = mid.split(":", 1)[1] if ":" in mid else ""
            if not name:
                name = (cloud_prefs().get(prov) or {}).get("model", "")
                if not name:
                    die(f"no default model saved for {prov} - set one: "
                        f"lai cloud use {prov} <model>  (see: lai cloud "
                        f"models {prov})")
            return prov, name
    return None, mid

def cloud_chat(prov, model, msgs, max_tokens=2048, temperature=0.2):
    key = cloud_keys().get(prov)
    if not key:
        die(f"no {prov} key configured -> lai cloud add {prov}")
    saved = (cloud_prefs().get(prov) or {}).get("params", {})
    # token-lean by default: saved per-model settings win over call defaults
    max_tokens = int(saved.get("max_tokens", max_tokens))
    temperature = float(saved.get("temperature", temperature))
    extra = {k: v for k, v in saved.items()
             if k not in ("max_tokens", "temperature")}
    if prov == "anthropic":
        system = "\n".join(m["content"] for m in msgs
                           if m["role"] == "system") or None
        conv = [m for m in msgs if m["role"] != "system"]
        payload = {"model": model, "max_tokens": max_tokens,
                   "messages": conv, "temperature": temperature}
        for k in ("top_p", "top_k"):  # anthropic accepts these passthroughs
            if k in extra:
                payload[k] = extra[k]
        if system:
            payload["system"] = system
        r = http_json("https://api.anthropic.com/v1/messages", payload,
                      timeout=300,
                      headers={"x-api-key": key,
                               "anthropic-version": "2023-06-01"})
        return "".join(b.get("text", "") for b in r.get("content", []))
    payload = {"model": model, "messages": msgs,
               "max_tokens": max_tokens, "temperature": temperature}
    payload.update(extra)  # provider-specific knobs pass through untouched
    hdrs = {"Authorization": f"Bearer {key}"}
    if prov == "openrouter":  # service-specific niceties
        hdrs.update({"HTTP-Referer": "https://github.com/DevEpoch/lai",
                     "X-Title": "lai"})
    r = http_json(f"{CLOUD[prov]['base']}/chat/completions", payload,
                  timeout=300, headers=hdrs)
    return r["choices"][0]["message"].get("content") or ""

def remote_cfg():
    """Team-server connection (lai connect), or None for local serving."""
    return load_json(STATE / "remote.json")

def endpoint_host():
    r = remote_cfg()
    return r["host"] if r else "localhost"

def endpoint_base(port=P('swap')):
    return f"http://{endpoint_host()}:{port}"

def auth_headers():
    r = remote_cfg()
    k = (r or {}).get("api_key") or api_key()
    return {"Authorization": f"Bearer {k}"} if k else {}

def load_catalog():
    cat = load_json(CATALOG_PATH)
    if not cat:
        die(f"catalog missing or invalid JSON: {CATALOG_PATH}")
    return cat

def load_choices(required=True):
    ch = load_json(CHOICES_PATH)
    if not ch and required:
        die("no saved choices - run: lai plan")
    return ch

def nvidia_gpus():
    smi = shutil.which("nvidia-smi")
    if not smi:
        return []
    try:
        out = subprocess.run(
            [smi, "--query-gpu=index,name,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=20, check=True).stdout
    except Exception:
        return []
    gpus = []
    for line in out.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 3:
            gpus.append({"index": int(parts[0]), "name": parts[1],
                         "mem_mib": int(float(parts[2]))})
    return gpus

def detect_amd():
    """Best-effort AMD GPU detection. Returns (name, vram_gb_or_None)."""
    if IS_WIN:
        try:
            out = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "(Get-CimInstance Win32_VideoController).Name"],
                capture_output=True, text=True, timeout=30).stdout
            for line in out.splitlines():
                if re.search(r"radeon|amd", line, re.I):
                    return line.strip(), None  # Windows misreports VRAM >4GB
        except Exception:
            pass
        return None, None
    # Linux: rocm-smi if present, else sysfs vendor ids (0x1002 = AMD)
    if shutil.which("rocm-smi"):
        try:
            out = subprocess.run(["rocm-smi", "--showmeminfo", "vram"],
                                 capture_output=True, text=True,
                                 timeout=20).stdout
            m = re.search(r"Total.*?(\d{6,})", out)
            vram = round(int(m.group(1)) / 2 ** 30, 1) if m else None
            return "AMD GPU (rocm-smi)", vram
        except Exception:
            pass
    try:
        for card in Path("/sys/class/drm").glob("card[0-9]"):
            vendor = (card / "device/vendor").read_text().strip()
            if vendor == "0x1002":
                return "AMD GPU (sysfs)", None
    except OSError:
        pass
    return None, None

def total_ram_gb():
    if IS_WIN:
        class MemStat(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong),
                        ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        stat = MemStat()
        stat.dwLength = ctypes.sizeof(stat)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
        return stat.ullTotalPhys / 2 ** 30
    if IS_MAC:
        try:
            out = subprocess.run(["sysctl", "-n", "hw.memsize"],
                                 capture_output=True, text=True,
                                 timeout=10).stdout
            return int(out.strip()) / 2 ** 30
        except Exception:
            return 0.0
    with open("/proc/meminfo") as f:
        for line in f:
            if line.startswith("MemTotal:"):
                return int(line.split()[1]) / 2 ** 20
    return 0.0

def detect_hw(vram_override=None, interactive=True):
    ram = total_ram_gb()
    gpus = nvidia_gpus()
    if IS_MAC:
        name = f"Apple Silicon ({platform.machine()})" \
            if platform.machine() == "arm64" else "Apple (Intel)"
        hw = {"platform": "mac", "vendor": "apple", "vram_gb": round(ram, 1),
              "gpus": [{"index": 0, "name": name,
                        "mem_mib": int(ram * 1024)}]}
    elif gpus:
        hw = {"platform": PLAT, "vendor": "nvidia",
              "vram_gb": round(max(g["mem_mib"] for g in gpus) / 1024, 1),
              "gpus": gpus}
    else:
        amd_name, amd_vram = detect_amd()
        if amd_name:
            if vram_override is None and amd_vram is None:
                warn(f"AMD GPU detected ({amd_name}) but VRAM size is unknown "
                     "on this OS")
                if interactive and sys.stdin.isatty() and not ASSUME_YES:
                    try:
                        raw = input("  ?   enter its VRAM in GB "
                                    "(blank = assume 8): ").strip()
                        amd_vram = float(raw) if raw else 8.0
                    except (EOFError, ValueError):
                        amd_vram = 8.0
                else:
                    amd_vram = 8.0
                    warn("assuming 8 GB - override with: lai plan --vram-gb N")
            hw = {"platform": PLAT, "vendor": "amd",
                  "vram_gb": amd_vram or 8.0,
                  "gpus": [{"index": 0, "name": amd_name,
                            "mem_mib": int((amd_vram or 8.0) * 1024)}]}
        else:
            hw = {"platform": PLAT, "vendor": "none", "vram_gb": 0, "gpus": []}
    if vram_override is not None:
        hw["vram_gb"] = vram_override
    hw["ram_gb"] = round(ram, 1)
    hw["cores"] = os.cpu_count()
    return hw

def engine_key(hw):
    if hw["platform"] == "mac":
        return "mac-metal"
    suffix = {"nvidia": "cuda", "amd": "vulkan", "none": "cpu"}[hw["vendor"]]
    return f"{hw['platform']}-{suffix}"

def fit_mode(cat, mid, hw):
    """How can model `mid` run on this hardware? 'gpu'|'hybrid'|'cpu'|None."""
    m = cat["models"].get(mid)
    if not m:
        return None
    vram = hw["vram_gb"] or 0
    if hw["vendor"] == "apple":
        # unified memory: model + ~2 GB ctx must fit in ~75% of RAM (Metal cap)
        return "gpu" if m["disk_gb"] + 2 <= hw["ram_gb"] * 0.75 else None
    if hw["vendor"] in ("nvidia", "amd"):
        if vram >= m.get("fits_vram_gb", 1e9):
            return "gpu"
        if m.get("moe") and hw["ram_gb"] >= m.get("hybrid_ram_gb", 1e9) \
                and vram >= 3:
            return "hybrid"
        if m.get("cpu_ok") and hw["ram_gb"] >= m["disk_gb"] + 4:
            return "cpu"
        return None
    if m.get("cpu_ok") and hw["ram_gb"] >= m["disk_gb"] + 4:
        return "cpu"
    return None

def candidates(cat, role, hw):
    out = []
    for mid, m in cat["models"].items():
        if role in m.get("roles", []) and fit_mode(cat, mid, hw):
            out.append(mid)
    return sorted(out, key=lambda i: -cat["models"][i]["disk_gb"])

def match_tier(cat, hw):
    for t in cat["tiers"]:
        if hw["platform"] not in t.get("platform", [hw["platform"]]):
            continue
        if hw["vendor"] not in t.get("vendor", [hw["vendor"]]):
            continue
        if (hw["vram_gb"] or 0) < t.get("min_vram_gb", 0):
            continue
        if hw["ram_gb"] < t.get("min_ram_gb", 0):
            continue
        return t
    return None

def build_choices(cat, tier, hw):
    roles = {}
    for role in ROLES:
        raw = tier.get("defaults", {}).get(role)
        d = dict(raw or {})
        mid = d.pop("model", "__unset__")
        if raw is not None and mid is None:
            roles[role] = None  # tier explicitly disables this role
            continue
        if mid == "__unset__":
            mid = None
        entry = None
        if mid and not cat["models"].get(mid, {}).get("verify"):
            mode = fit_mode(cat, mid, hw)
            if mode:
                entry = {"model": mid,
                         "mode": mode if mode != "gpu" else d.get("mode", mode)}
                for k in ("ctx", "kv", "ngl", "longctx"):
                    if k in d:
                        entry[k] = d[k]
        if entry is None:  # default missing/unfit -> best fitting alternative
            for alt in candidates(cat, role, hw):
                if cat["models"][alt].get("verify"):
                    continue
                entry = {"model": alt, "mode": fit_mode(cat, alt, hw),
                         "ctx": d.get("ctx", 8192)}
                if mid:
                    warn(f"{role}: default '{mid}' does not fit - "
                         f"falling back to '{alt}'")
                break
        roles[role] = entry
    return {"catalog_version": cat.get("catalog_version", "?"),
            "tier": tier["id"], "tier_label": tier.get("label", tier["id"]),
            "engine": engine_key(hw), "hardware": hw, "roles": roles,
            "targets": tier.get("targets", {}),
            "saved": datetime.now().isoformat(timespec="seconds")}

def apply_usecase(cat, choices, uc_id):
    """Overlay a use-case profile (catalog `usecases`) onto the choices."""
    uc = cat.get("usecases", {}).get(uc_id)
    if uc is None:
        warn(f"unknown use case '{uc_id}' - keeping tier defaults")
        return choices
    hw = choices["hardware"]
    for role, ov in uc.get("overlay", {}).items():
        if role not in ROLES:
            continue
        entry = choices["roles"].get(role)
        if ov.get("enabled") is False:
            choices["roles"][role] = None
            continue
        if ov.get("enabled") is True and entry is None:
            for alt in candidates(cat, role, hw):
                if not cat["models"][alt].get("verify"):
                    entry = {"model": alt, "mode": fit_mode(cat, alt, hw),
                             "ctx": ov.get("ctx", 8192)}
                    choices["roles"][role] = entry
                    break
        if entry and ov.get("ctx"):
            # big roles: only lower ctx (raising can OOM - that is the
            # tier's call). Tiny side models may raise freely.
            if role in ("autocomplete", "embeddings") \
                    or ov["ctx"] <= entry.get("ctx", 8192):
                entry["ctx"] = ov["ctx"]
    choices["usecase"] = uc_id
    return choices

def set_choice(cat, choices, role, mid, force=False):
    """Core of `lai set` - returns a list of warnings; raises ValueError."""
    if role not in ROLES:
        raise ValueError(f"unknown role '{role}' - one of: {', '.join(ROLES)}")
    warnings = []
    if mid in ("none", "off", "disable"):
        choices["roles"][role] = None
        return warnings
    m = cat["models"].get(mid)
    if not m:
        raise ValueError(f"'{mid}' is not in the catalog - see `lai catalog`")
    if role not in m.get("roles", []):
        warnings.append(f"'{mid}' is not tagged for role '{role}' "
                        "in the catalog")
    mode = fit_mode(cat, mid, choices["hardware"])
    if not mode:
        if not force:
            raise ValueError(
                f"'{mid}' likely does NOT fit this hardware (needs "
                f"{m.get('fits_vram_gb', '?')} GB VRAM or "
                f"{m.get('hybrid_ram_gb', '?')} GB RAM)")
        warnings.append(f"forced '{mid}' despite a likely hardware misfit")
        mode = "gpu"
    if m.get("verify"):
        warnings.append(f"'{mid}' is marked verify=true - confirm the repo "
                        f"'{m['repo']}' on Hugging Face")
    old = choices["roles"].get(role) or {}
    choices["roles"][role] = {"model": mid, "mode": mode,
                              "ctx": old.get("ctx", 16384),
                              **({"kv": old["kv"]} if "kv" in old else {})}
    return warnings

def wanted_models(cat, choices, include_downloaded=False):
    """Chosen models (plus speculative-decoding drafts) as (id, meta)."""
    wanted = []

    def want(mid):
        if mid and mid in cat["models"] \
                and mid not in [w[0] for w in wanted] \
                and (include_downloaded or not model_file(mid)):
            wanted.append((mid, cat["models"][mid]))

    for e in choices["roles"].values():
        if e:
            want(e["model"])
            want(cat["models"].get(e["model"], {}).get("draft"))
    return wanted

MODE_LABEL = {"gpu": "fully on GPU", "hybrid": "hybrid CPU+GPU (MoE offload)",
              "cpu": "CPU only"}

def print_choices(cat, choices, show_alternatives=True):
    hw = choices["hardware"]
    gpu_txt = ", ".join(g["name"] for g in hw["gpus"]) or "none"
    print()
    info(f"hardware: {hw['platform']} | gpu: {gpu_txt} "
         f"({hw['vram_gb']} GB) | ram: {hw['ram_gb']} GB")
    info(f"tier: {choices['tier']} - {choices['tier_label']} | "
         f"engine: {choices['engine']} | catalog {choices['catalog_version']}")
    uc = choices.get("usecase")
    if uc:
        ucd = cat.get("usecases", {}).get(uc, {})
        info(f"use case: {uc} - {ucd.get('label', '')}")
        for ext in ucd.get("extensions", []):
            print(c("90", f"        recommended extension: {ext}"))
    print()
    head = f"  {'ROLE':<13}{'MODEL':<26}{'RUNS AS':<30}{'CTX':<8}DISK"
    print(c("1", head))
    for role in ROLES:
        e = choices["roles"].get(role)
        if not e:
            print(f"  {role:<13}"
                  f"{c('90', '(disabled - hardware or use case)')}")
            continue
        m = cat["models"][e["model"]]
        ctx = str(e.get("ctx", "-"))
        print(f"  {role:<13}{e['model']:<26}"
              f"{MODE_LABEL.get(e['mode'], e['mode']):<30}{ctx:<8}"
              f"{m['disk_gb']} GB")
        print(f"  {'':<13}{c('90', m.get('why', ''))}")
    t = choices.get("targets", {})
    if t:
        print(f"\n  expected (healthy install): prompt >= {t.get('pp', '?')} "
              f"t/s, generation >= {t.get('tg', '?')} t/s")
    tier = next((x for x in cat["tiers"] if x["id"] == choices["tier"]), {})
    for note in tier.get("notes", []):
        print(f"  note: {note}")
    if show_alternatives:
        print()
        for role in ROLES:
            current = (choices["roles"].get(role) or {}).get("model")
            alts = [x for x in candidates(cat, role, hw) if x != current]
            if alts:
                print(c("90", f"  {role} alternatives: {', '.join(alts)}  "
                              f"(switch: lai set {role} <model>)"))
        ck = [p for p in cloud_keys() if cloud_keys().get(p)]
        if ck:
            print(c("90", f"  cloud fallback configured ({', '.join(ck)}): "
                          "for the hardest tasks use prefixed ids, e.g. "
                          "`/model or:...` in chat or `lai git review "
                          "--model an:claude-sonnet-4-6` - local stays the "
                          "default"))
    print()

def edit_choices_interactive(cat, choices):
    hw = choices["hardware"]
    while True:
        try:
            ans = input(c("35", "  ?   accept these choices? "
                                "[Y]es / [e]dit a role / [q]uit: ")
                        ).strip().lower()
        except EOFError:
            return True
        if ans in ("", "y", "yes"):
            return True
        if ans in ("q", "quit"):
            return False
        if ans not in ("e", "edit"):
            continue
        role = input(f"      role to change ({'/'.join(ROLES)}): ").strip()
        if role not in ROLES:
            warn("unknown role")
            continue
        opts = candidates(cat, role, hw)
        print("      0) none (disable this role)")
        for i, mid in enumerate(opts, 1):
            m = cat["models"][mid]
            extra = " [verify repo first!]" if m.get("verify") else ""
            print(f"      {i}) {mid:<26} {m['disk_gb']} GB - "
                  f"{m.get('why', '')}{extra}")
        try:
            pick = int(input("      choice #: ").strip())
        except (ValueError, EOFError):
            warn("not a number")
            continue
        if pick == 0:
            choices["roles"][role] = None
        elif 1 <= pick <= len(opts):
            mid = opts[pick - 1]
            old = choices["roles"].get(role) or {}
            choices["roles"][role] = {"model": mid,
                                      "mode": fit_mode(cat, mid, hw),
                                      "ctx": old.get("ctx", 16384)}
        print_choices(cat, choices, show_alternatives=False)

def model_file(mid, mmproj=False):
    if not mid:
        return None
    base = MODELS / mid
    if not base.exists():
        return None
    files = sorted(p for p in base.rglob("*.gguf") if p.is_file())
    for f in files:
        is_mm = f.name.lower().startswith("mmproj")
        if is_mm == mmproj:
            return f
    return None

def role_flags(entry, m, model_path, mmproj_path):
    parts = [f"-m {model_path}"]
    if mmproj_path:
        parts.append(f"--mmproj {mmproj_path}")
    ngl = entry.get("ngl")
    if entry["mode"] == "cpu":
        parts.append("-ngl 0")
    elif entry["mode"] == "hybrid":
        parts.append(f"-ngl {ngl if ngl is not None else 99} "
                     f"--n-cpu-moe {entry.get('n_cpu_moe', 99)}")
    else:
        parts.append(f"-ngl {ngl if ngl is not None else 99}")
    parts.append(f"-c {entry.get('ctx', 8192)}")
    kv = entry.get("kv")
    if kv and kv != "f16":  # f16 is the default cache type
        parts.append(f"--cache-type-k {kv} --cache-type-v {kv}")
    if entry.get("threads"):
        parts.append(f"-t {entry['threads']}")
    parts.append("--jinja")
    return " ".join(parts)

def probes():
    h = endpoint_host()
    tag = "" if h == "localhost" else f" @{h}"
    return [
        (f"llama-swap :{P('swap')}{tag}", f"{endpoint_base()}/v1/models"),
        (f"autocomplete :{P('autocomplete')}{tag}", f"{endpoint_base(P('autocomplete'))}/health"),
        (f"embeddings :{P('embeddings')}{tag}", f"{endpoint_base(P('embeddings'))}/health"),
        (f"qdrant :{P('qdrant')}{tag}", f"http://{h}:{P('qdrant')}/collections"),
        (f"openhands :{P('openhands')}", f"http://localhost:{P('openhands')}/"),
        (f"open-webui :{P('webui')}", f"http://localhost:{P('webui')}/"),
        (f"searxng :{P('searxng')}", f"http://localhost:{P('searxng')}/healthz"),
    ]

def sanitize_name(raw):
    name = re.sub(r"[^a-zA-Z0-9_]+", "_", raw).strip("_").lower()
    return re.sub(r"^[0-9]+", "", name) or "project"

def llm_chat(prompt, system=None, max_tokens=2048, temperature=0.2,
             model="coder"):
    msgs = ([{"role": "system", "content": system}] if system else []) + \
        [{"role": "user", "content": prompt}]
    prov, name = parse_model(model)
    if prov:
        return cloud_chat(prov, name, msgs, max_tokens, temperature)
    try:
        http_get(f"{endpoint_base()}/v1/models", timeout=3)
    except Exception:
        die(f"inference endpoint {endpoint_base()} not reachable -> "
            "lai start (or lai connect <server>)")
    r = http_json(f"{endpoint_base()}/v1/chat/completions",
                  {"model": model, "messages": msgs,
                   "max_tokens": max_tokens, "temperature": temperature},
                  timeout=900, headers=auth_headers())
    return r["choices"][0]["message"].get("content") or ""
