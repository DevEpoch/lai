"""The localhost management dashboard (lai ui)."""

from .core import *  # noqa: F401,F403
from .stack import *  # noqa: F401,F403
from .work import *  # noqa: F401,F403
from .projects import *  # noqa: F401,F403
from .stack import _port_status  # noqa: F401  (underscore: not star-exported)

def cmd_ui(args):
    import http.server
    import webbrowser
    from urllib.parse import urlparse, parse_qs

    ensure_dirs()
    dist = ROOT / "ui" / "dist"
    ui_file = dist / "index.html" if (dist / "index.html").exists() \
        else CONFIG / "ui.html"
    if not ui_file.exists():
        die(f"missing {ui_file}")
    jobs = {}

    def job_running(name):
        p = jobs.get(name)
        return p is not None and p.poll() is None

    def start_job(name, cli, logname):
        if job_running(name):
            return False
        log = open(LOGS / logname, "ab")
        jobs[name] = subprocess.Popen(
            [sys.executable, str(ROOT / "lai.py")] + cli,
            stdout=log, stderr=subprocess.STDOUT, cwd=str(ROOT))
        return True

    def dir_size_gb(path):
        if not path.exists():
            return 0.0
        return sum(f.stat().st_size for f in path.rglob("*")
                   if f.is_file()) / 2 ** 30

    def overview():
        cat = load_json(CATALOG_PATH, {})
        choices = load_json(CHOICES_PATH)
        last_q = None
        for f in sorted(BENCH_DIR.glob("quality-*.json"), reverse=True):
            last_q = load_json(f)
            break
        return {
            "choices": choices,
            "usecases": {k: {"label": v.get("label", "")}
                         for k, v in cat.get("usecases", {}).items()
                         if not k.startswith("_")},
            "models_meta": {k: {"disk_gb": v.get("disk_gb"),
                                "why": v.get("why", "")}
                            for k, v in cat.get("models", {}).items()},
            "stacks": {k: {"label": v.get("label", "")}
                       for k, v in cat.get("stacks", {}).items()
                       if not k.startswith("_")},
            "remote": remote_cfg(),
            "lai_version": VERSION,
            "skills": {k: v.get("description", "")
                       for k, v in list_skills().items()},
            "versions": load_json(VERSIONS_PATH, {}),
            "running": {"download": job_running("download"),
                        "bench": job_running("bench"),
                        "setup": job_running("setup")},
            "last_quality": last_q,
            "logs": sorted(f.name[:-4] for f in LOGS.glob("*.log")),
        }

    def downloads_state():
        cat = load_json(CATALOG_PATH, {})
        choices = load_json(CHOICES_PATH)
        items = []
        if choices and cat:
            for mid, m in wanted_models(cat, choices,
                                        include_downloaded=True):
                items.append({"id": mid, "expected_gb": m["disk_gb"],
                              "have_gb": round(dir_size_gb(MODELS / mid), 2),
                              "done": bool(model_file(mid))})
        return {"running": job_running("download"), "items": items}

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt, *a):  # silence per-request console spam
            pass

        def _send(self, obj, code=200, ctype="application/json"):
            body = obj if isinstance(obj, bytes) else json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            try:
                u = urlparse(self.path)
                if u.path in ("/", "/index.html"):
                    self._send(ui_file.read_bytes(),
                               ctype="text/html; charset=utf-8")
                elif u.path.startswith("/assets/"):
                    f = (dist / u.path.lstrip("/")).resolve()
                    if dist.exists() and str(f).startswith(str(dist)) \
                            and f.is_file():
                        ctypes_map = {".js": "application/javascript",
                                      ".css": "text/css",
                                      ".svg": "image/svg+xml",
                                      ".woff2": "font/woff2"}
                        self._send(f.read_bytes(),
                                   ctype=ctypes_map.get(f.suffix,
                                                        "application/octet-stream"))
                    else:
                        self._send({"error": "not found"}, 404)
                elif u.path == "/api/ports":
                    self._send({"ports": [
                        {"name": n, "default": DEFAULT_PORTS[n],
                         "current": P(n), "status": _port_status(n, P(n))}
                        for n in DEFAULT_PORTS]})
                elif u.path == "/api/cloudcfg":
                    recs = (load_json(CATALOG_PATH) or {}).get("cloud", {})
                    prefs = cloud_prefs()
                    keys = cloud_keys()
                    self._send({"providers": [
                        {"id": prov, "prefix": spec["prefix"],
                         "has_key": bool(keys.get(prov)),
                         "default_model": (prefs.get(prov) or {}).get("model", ""),
                         "params": (prefs.get(prov) or {}).get("params", {}),
                         "recommended": (recs.get(prov) or {}).get("recommended", [])}
                        for prov, spec in CLOUD.items()]})
                elif u.path == "/icon.svg":
                    self._send((ROOT / "assets" / "icon.svg").read_bytes(),
                               ctype="image/svg+xml")
                elif u.path == "/api/overview":
                    self._send(overview())
                elif u.path == "/api/status":
                    out = []
                    for name, url in probes():
                        try:
                            http_get(url, timeout=1.5)
                            out.append({"name": name, "up": True})
                        except Exception:
                            out.append({"name": name, "up": False})
                    self._send(out)
                elif u.path == "/api/candidates":
                    cat = load_json(CATALOG_PATH, {})
                    choices = load_json(CHOICES_PATH)
                    hw = choices["hardware"] if choices \
                        else detect_hw(interactive=False)
                    self._send({"candidates": {
                        r: candidates(cat, r, hw) for r in ROLES}})
                elif u.path == "/api/downloads":
                    self._send(downloads_state())
                elif u.path == "/api/projects":
                    self._send({"projects": projects_registry()})
                elif u.path == "/api/logs":
                    name = parse_qs(u.query).get("name", [""])[0]
                    if not re.fullmatch(r"[\w.-]+", name or ""):
                        self._send({"error": "bad name"}, 400)
                        return
                    f = LOGS / f"{name}.log"
                    lines = f.read_text(encoding="utf-8",
                                        errors="replace").splitlines()[-80:] \
                        if f.exists() else []
                    self._send({"text": "\n".join(lines)})
                else:
                    self._send({"error": "not found"}, 404)
            except (Exception, SystemExit) as e:
                self._send({"error": str(e) or "internal error"}, 500)

        def do_POST(self):
            try:
                u = urlparse(self.path)
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length) or b"{}") \
                    if length else {}
                ns = argparse.Namespace(yes=True, all=False, quality=False,
                                        model=None, vram_gb=None,
                                        use_case=None, off=False,
                                        remove=False, verify=False)
                if u.path == "/api/plan":
                    cat = load_catalog()
                    hw = detect_hw(interactive=False)
                    tier = match_tier(cat, hw)
                    if not tier:
                        self._send({"error": "no tier matches"}, 400)
                        return
                    choices = build_choices(cat, tier, hw)
                    apply_usecase(cat, choices,
                                  body.get("usecase") or "general")
                    save_text(CHOICES_PATH, json.dumps(choices, indent=2))
                    self._send({"ok": True})
                elif u.path == "/api/set":
                    cat = load_catalog()
                    choices = load_choices()
                    try:
                        warnings = set_choice(cat, choices, body.get("role"),
                                              body.get("model"),
                                              force=body.get("force", False))
                    except ValueError as e:
                        self._send({"error": str(e),
                                    "needs_force": "does NOT fit" in str(e)},
                                   400)
                        return
                    save_text(CHOICES_PATH, json.dumps(choices, indent=2))
                    self._send({"ok": True, "warnings": warnings})
                elif u.path == "/api/config":
                    cmd_config(ns)
                    self._send({"ok": True})
                elif u.path in ("/api/start", "/api/stop", "/api/restart"):
                    {"/api/start": cmd_start, "/api/stop": cmd_stop,
                     "/api/restart": cmd_restart}[u.path](ns)
                    self._send({"ok": True})
                elif u.path == "/api/download":
                    if body.get("action") == "pause":
                        p = jobs.get("download")
                        if p and p.poll() is None:
                            p.terminate()
                        self._send({"ok": True})
                    else:
                        started = start_job("download", ["models", "--yes"],
                                            "download-ui.log")
                        self._send({"ok": started})
                elif u.path == "/api/bench":
                    cli = ["bench", "--yes"]
                    if body.get("quality"):
                        cli.append("--quality")
                    started = start_job("bench", cli, "bench-ui.log")
                    self._send({"ok": started} if started else
                               {"error": "a benchmark is already running"},
                               200 if started else 409)
                elif u.path == "/api/new":
                    cat = load_catalog()
                    try:
                        out = new_project(cat, body.get("stack"),
                                          body.get("path"),
                                          devcontainer=body.get(
                                              "devcontainer", False))
                        self._send({"ok": True, "path": str(out)})
                    except ValueError as e:
                        self._send({"error": str(e)}, 400)
                elif u.path == "/api/gate":
                    cat = load_catalog()
                    try:
                        results, proj = gate_project(
                            cat, body.get("path"),
                            fix=body.get("fix", False))
                        if body.get("fix"):
                            cmd_config(ns)
                        self._send({"results": results,
                                    "stack": proj.get("stack")})
                    except ValueError as e:
                        self._send({"error": str(e)}, 400)
                elif u.path == "/api/easy":
                    started = start_job("setup", ["go", "--yes"],
                                        "setup-ui.log")
                    self._send({"ok": started})
                elif u.path == "/api/chat":
                    try:
                        r = http_json(
                            f"{endpoint_base()}/v1/chat/completions",
                            {"model": body.get("model", "coder"),
                             "messages": body.get("messages", []),
                             "max_tokens": 2048, "temperature": 0.4},
                            timeout=900, headers=auth_headers())
                        self._send({"reply": r["choices"][0]["message"]
                                    .get("content", "")})
                    except Exception:
                        self._send({"error": "Your AI is not ready yet - "
                                    "it may still be downloading or "
                                    "starting. Check the Home screen "
                                    "progress."}, 503)
                elif u.path == "/api/skill":
                    try:
                        actions = install_skill(body.get("name"),
                                                body.get("path"),
                                                force=body.get("force",
                                                               False))
                        self._send({"ok": True, "actions": actions})
                    except ValueError as e:
                        self._send({"error": str(e)}, 400)
                elif u.path == "/api/ports":
                    if body.get("action") == "set":
                        if body.get("name") not in DEFAULT_PORTS:
                            self._send({"error": "unknown port name"}, 400)
                            return
                        set_port(body["name"], int(body["port"]))
                        cmd_config(ns)
                        self._send({"ok": True})
                    else:  # fix: move every conflicting port to a free one
                        moved = {}
                        for n in DEFAULT_PORTS:
                            if "CONFLICT" in _port_status(n, P(n)):
                                newp = next_free_port(P(n))
                                set_port(n, newp)
                                moved[n] = newp
                        if moved:
                            cmd_config(ns)
                        self._send({"ok": True, "moved": moved})
                elif u.path == "/api/cloudcfg":
                    sec = load_json(SECRETS_PATH) or {}
                    cl = sec.setdefault("cloud", {})
                    act, prov = body.get("action"), body.get("provider")
                    if prov not in CLOUD:
                        self._send({"error": "unknown provider"}, 400)
                        return
                    if act == "add" and body.get("key"):
                        cl[prov] = body["key"]
                        save_text(SECRETS_PATH, json.dumps(sec, indent=2))
                    elif act == "remove":
                        cl.pop(prov, None)
                        save_text(SECRETS_PATH, json.dumps(sec, indent=2))
                    elif act == "use" and body.get("model"):
                        prefs = cloud_prefs()
                        prefs[prov] = {"model": body["model"],
                                       "params": body.get("params")
                                       or {"max_tokens": 1024}}
                        save_cloud_prefs(prefs)
                    self._send({"ok": True})
                elif u.path == "/api/verify":
                    cat = load_catalog()
                    results = []
                    for mid, m in cat["models"].items():
                        try:
                            http_get("https://huggingface.co/api/models/"
                                     + m["repo"], timeout=15)
                            status = "ok"
                        except Exception as e:
                            status = "gated" if getattr(e, "code", None) \
                                in (401, 403) else "missing"
                        results.append({"id": mid, "repo": m["repo"],
                                        "status": status})
                    self._send({"results": results})
                else:
                    self._send({"error": "not found"}, 404)
            except (Exception, SystemExit) as e:
                self._send({"error": str(e) or
                            "failed - see the lai ui console"}, 500)

    addr = ("127.0.0.1", args.port or P("ui"))
    try:
        server = http.server.ThreadingHTTPServer(addr, Handler)
    except OSError:
        try:
            http_get(f"http://{addr[0]}:{addr[1]}/api/overview", timeout=2)
            ok(f"dashboard already running at http://{addr[0]}:{addr[1]}")
            if not getattr(args, "no_browser", False):
                webbrowser.open(f"http://{addr[0]}:{addr[1]}")
            return
        except Exception:
            die(f"port {addr[1]} is taken by another app -> "
                "lai ports set ui <free port>")
    url = f"http://{addr[0]}:{addr[1]}"
    ok(f"UI running at {url}  (Ctrl+C to stop; localhost only)")
    if not getattr(args, "no_browser", False):
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
        info("UI stopped")
