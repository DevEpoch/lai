"""Project scaffolding (lai new) and the machine gate (lai gate)."""

from .core import *  # noqa: F401,F403
from .stack import *  # noqa: F401,F403
from .work import *  # noqa: F401,F403

def projects_registry():
    return load_json(PROJECTS_PATH, [])

def register_project(path, stack, last_gate=None):
    reg = [p for p in projects_registry()
           if Path(p["path"]) != Path(path)]
    reg.append({"path": str(path), "stack": stack,
                "name": Path(path).name,
                "last_gate": last_gate,
                "updated": datetime.now().isoformat(timespec="seconds")})
    save_text(PROJECTS_PATH, json.dumps(reg, indent=2))

def render_agents_md(name, stack):
    a = stack.get("agents", {})
    conv = "\n".join(f"- {n}" for n in
                     stack.get("conventions", [])) or \
        "- keep functions small; add a test with every behavior change"
    return f"""# AGENTS.md

## Project

{name} - {stack.get('label', '')}. <add one paragraph: what it is, who uses it>

## Build / test / run

```bash
# build: {a.get('build', '-')}
# test:  {a.get('test', '-')}
# lint:  {a.get('lint', '-')}
# run:   {a.get('run', '-')}
```

Agents: always run the test command before declaring a task done.

## Conventions

{conv}

## Architecture map

- Decisions with rationale live in `docs/adr/` - read the relevant ADR before
  changing cross-cutting behavior; add a new ADR when you make such a change.

## Boundaries for agents

- Never commit secrets; `.lai/local.json` is personal and stays untracked.
"""

def new_project(cat, stack_id, path_str, devcontainer=False):
    """Scaffold a project. Caller has already approved. Raises ValueError."""
    stack = cat.get("stacks", {}).get(stack_id)
    if not stack or stack_id.startswith("_"):
        raise ValueError(f"unknown stack '{stack_id}' - see `lai catalog` "
                         "or the stacks section of catalog.json")
    path = Path(path_str).expanduser().resolve()
    if path.exists() and any(path.iterdir()):
        raise ValueError(f"{path} exists and is not empty")
    name = sanitize_name(path.name)

    missing = [t for t in stack.get("toolchains", [])
               if not shutil.which(t["bin"])]
    for t in missing:
        if stack.get("init_cmds"):
            raise ValueError(f"toolchain '{t['bin']}' not found - install it "
                             f"first: {t['hint']}")
        warn(f"toolchain '{t['bin']}' not found ({t['hint']}) - "
             "scaffolding anyway (files only)")

    path.mkdir(parents=True, exist_ok=True)

    def fill(s):
        return s.replace("{name}", name).replace("{python}", sys.executable)

    for cmd in stack.get("init_cmds", []):
        argv = [fill(x) for x in cmd]
        exe = shutil.which(argv[0])  # resolves npm.cmd etc. on Windows
        if not exe:
            raise ValueError(f"'{argv[0]}' not on PATH")
        info(f"running: {' '.join(argv)}")
        r = subprocess.run([exe] + argv[1:], cwd=str(path), timeout=900)
        if r.returncode != 0:
            raise ValueError(f"generator failed: {' '.join(argv)}")

    for rel, content in stack.get("files", {}).items():
        f = path / fill(rel)
        if not f.exists():
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(fill(content), encoding="utf-8", newline="\n")

    # --- the AI layer -----------------------------------------------------
    (path / "AGENTS.md").write_text(render_agents_md(name, stack),
                                    encoding="utf-8", newline="\n")
    vs = path / ".vscode"
    vs.mkdir(exist_ok=True)
    uc = cat.get("usecases", {}).get(stack.get("usecase", ""), {})
    recs = list(dict.fromkeys(stack.get("extensions", []) +
                              [e.split(" ")[0] for e in
                               uc.get("extensions", [])]))
    if not (vs / "extensions.json").exists():
        (vs / "extensions.json").write_text(
            json.dumps({"recommendations": recs}, indent=2),
            encoding="utf-8", newline="\n")
    if not (vs / "settings.json").exists():
        (vs / "settings.json").write_text(json.dumps({
            "editor.formatOnSave": True,
            "files.trimTrailingWhitespace": True}, indent=2),
            encoding="utf-8", newline="\n")
    lai_dir = path / ".lai"
    lai_dir.mkdir(exist_ok=True)
    (lai_dir / "project.json").write_text(json.dumps({
        "stack": stack_id,
        "usecase": stack.get("usecase", "general"),
        "required_roles": stack.get("required_roles", ["coder"]),
        "min_ctx": stack.get("min_ctx", 8192),
        "toolchains": stack.get("toolchains", []),
        "created": datetime.now().isoformat(timespec="seconds"),
    }, indent=2), encoding="utf-8", newline="\n")
    adr = path / "docs" / "adr"
    adr.mkdir(parents=True, exist_ok=True)
    (adr / "0001-stack-choice.md").write_text(
        f"# ADR 0001: {stack.get('label', stack_id)}\n\n"
        f"Date: {datetime.now():%Y-%m-%d}\n\n"
        f"We scaffolded this project as `{stack_id}` via lai. "
        "Record future architecture decisions as docs/adr/NNNN-*.md.\n",
        encoding="utf-8", newline="\n")
    gi = path / ".gitignore"
    lines = gi.read_text(encoding="utf-8").splitlines() if gi.exists() else []
    for entry in [".lai/local.json"] + stack.get("gitignore", []):
        if entry not in lines:
            lines.append(entry)
    gi.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    if devcontainer:
        dc = path / ".devcontainer"
        dc.mkdir(exist_ok=True)
        (dc / "devcontainer.json").write_text(json.dumps({
            "name": name,
            "image": "mcr.microsoft.com/devcontainers/universal:2",
            "postCreateCommand": "echo 'add toolchain features here'",
        }, indent=2), encoding="utf-8")

    mem = lai_dir / "memory.md"
    if not mem.exists():
        mem.write_text(
            "# Project memory\n\n"
            "<!-- Durable, project-specific knowledge that is NOT derivable "
            "from the code:\n     decisions context, gotchas, environment "
            "quirks, vendor contacts. Agents read\n     this at task start "
            "and append dated bullets (see the memory skill rules).\n"
            "     Committed with the repo - travels to every machine and "
            "teammate. -->\n\n"
            f"- {datetime.now():%Y-%m-%d}: project scaffolded "
            f"(stack: {stack_id}).\n",
            encoding="utf-8", newline="\n")

    for skill_name in ("interview", "review", "tdd", "adr", "memory"):
        try:
            install_skill(skill_name, path)
        except (ValueError, OSError) as e:
            warn(f"skill {skill_name}: {e}")

    if shutil.which("git") and not (path / ".git").exists():
        subprocess.run(["git", "init", "-q"], cwd=str(path))
        subprocess.run(["git", "add", "-A"], cwd=str(path))
        r = subprocess.run(["git", "commit", "-q", "-m",
                            f"scaffold {stack_id} project via lai"],
                           cwd=str(path), capture_output=True, text=True)
        if r.returncode != 0:
            warn("git commit skipped (configure git user.name/user.email)")
    register_project(path, stack_id)
    return path

def gate_project(cat, path_str, fix=False):
    """Check (and optionally fix) that this machine satisfies a project's
    .lai/project.json. Returns (results, project_meta)."""
    path = Path(path_str).expanduser().resolve()
    proj = load_json(path / ".lai" / "project.json")
    if not proj:
        raise ValueError(f"no .lai/project.json under {path} - "
                         "not a lai project (create one with `lai new`, or "
                         "copy the file from another project and edit it)")
    local = load_json(path / ".lai" / "local.json", {})
    preferred = local.get("preferred", {})
    results = []

    def add(item, status, detail=""):
        results.append({"item": item, "status": status, "detail": detail})

    remote = remote_cfg()
    served = None
    if remote:
        try:
            data = http_json(f"{endpoint_base()}/v1/models", timeout=5)
            served = [m.get("id") for m in data.get("data", [])]
        except Exception:
            served = None

    choices = load_json(CHOICES_PATH)
    if not choices and not remote:
        add("machine plan", "FAIL", "no choices saved - run `lai plan`")
        return results, proj

    changed = False
    for role in proj.get("required_roles", []):
        if remote:
            if role in ("autocomplete", "embeddings"):
                try:
                    http_get(f"{endpoint_base(P('autocomplete') if role == 'autocomplete' else P('embeddings'))}/health", timeout=3)
                    add(f"role:{role}", "PASS", f"served by {endpoint_host()}")
                except Exception:
                    add(f"role:{role}", "WARN",
                        f"{endpoint_host()} does not expose this side "
                        "server (enable `lai share on` there)")
            elif served is None:
                add(f"role:{role}", "FAIL",
                    f"team server {endpoint_host()} unreachable")
            elif role in served or f"{role}-longctx" in served:
                add(f"role:{role}", "PASS", f"served by {endpoint_host()}")
            else:
                add(f"role:{role}", "FAIL",
                    f"not served by {endpoint_host()} "
                    "(enable the role there and `lai restart`)")
            continue
        entry = choices["roles"].get(role)
        wanted_mid = preferred.get(role) or (entry or {}).get("model")
        if entry is None or (preferred.get(role)
                             and entry["model"] != preferred[role]):
            if fix:
                target = wanted_mid
                if not target or not fit_mode(cat, target,
                                              choices["hardware"]):
                    cands = [x for x in candidates(cat, role,
                                                   choices["hardware"])
                             if not cat["models"][x].get("verify")]
                    target = cands[0] if cands else None
                if target:
                    try:
                        set_choice(cat, choices, role, target)
                        changed = True
                        add(f"role:{role}", "FIXED", f"enabled {target}")
                        continue
                    except ValueError as e:
                        add(f"role:{role}", "FAIL", str(e))
                        continue
                add(f"role:{role}", "FAIL", "no fitting model on this "
                    "hardware")
                continue
            if entry is None:
                add(f"role:{role}", "FAIL",
                    "required by project, disabled on this machine "
                    "(fix: lai gate --fix)")
                continue
        if not model_file(entry["model"] if entry else wanted_mid):
            add(f"role:{role}", "FAIL" if not fix else "WARN",
                f"model '{wanted_mid}' not downloaded (lai models)")
        else:
            add(f"role:{role}", "PASS", wanted_mid or "")
    if changed:
        save_text(CHOICES_PATH, json.dumps(choices, indent=2))

    min_ctx = proj.get("min_ctx", 0)
    if remote:
        add("context", "PASS", "managed by the team server")
    else:
        coder = choices["roles"].get("coder") or {}
        if coder and coder.get("ctx", 0) >= min_ctx:
            add("context", "PASS", f"{coder.get('ctx')} >= {min_ctx}")
        else:
            add("context", "WARN",
                f"project wants {min_ctx}, machine gives "
                f"{coder.get('ctx', 0)} (hardware-bound)")

    for t in proj.get("toolchains", []):
        if shutil.which(t["bin"]):
            add(f"toolchain:{t['bin']}", "PASS")
        else:
            add(f"toolchain:{t['bin']}", "FAIL", t.get("hint", ""))

    if remote_cfg():
        add("engines", "PASS", f"served remotely by {endpoint_host()}")
    elif find_tool("llama-server", required=False):
        add("engines", "PASS")
    else:
        add("engines", "FAIL", "lai engines")
    try:
        http_get(f"{endpoint_base()}/v1/models", timeout=2)
        add("endpoint", "PASS", f"{endpoint_base()} up")
    except Exception:
        add("endpoint", "WARN",
            f"{endpoint_base()} not responding (lai start / lai connect)")

    uc = (load_json(CHOICES_PATH) or {}).get("usecase")
    if uc and uc != proj.get("usecase"):
        add("use case", "WARN",
            f"machine is '{uc}', project is '{proj.get('usecase')}' "
            "(roles above are what actually matter)")

    summary = {"when": datetime.now().isoformat(timespec="seconds"),
               "pass": sum(r["status"] in ("PASS", "FIXED")
                           for r in results),
               "warn": sum(r["status"] == "WARN" for r in results),
               "fail": sum(r["status"] == "FAIL" for r in results)}
    register_project(path, proj.get("stack", "?"), last_gate=summary)
    return results, proj

def cmd_new(args):
    cat = load_catalog()
    stacks = {k: v for k, v in cat.get("stacks", {}).items()
              if not k.startswith("_")}
    stack_id = getattr(args, "stack", None)
    if not stack_id:
        if not sys.stdin.isatty():
            die("non-interactive: pass --stack and --path")
        info("available stacks:")
        ids = list(stacks)
        for i, k in enumerate(ids, 1):
            print(f"      {i}) {k:<17} {stacks[k]['label']}")
        try:
            stack_id = ids[int(input(c("35", "  ?   stack #: ")).strip()) - 1]
        except (ValueError, IndexError, EOFError):
            die("no stack chosen")
    path = getattr(args, "path", None)
    if not path:
        if not sys.stdin.isatty():
            die("non-interactive: pass --path")
        try:
            path = input(c("35", "  ?   project path: ")).strip()
        except EOFError:
            path = ""
        if not path:
            die("no path given")
    stack = stacks.get(stack_id) or die(f"unknown stack '{stack_id}'")
    gen = " + ".join(" ".join(c) for c in stack.get("init_cmds", [])) \
        or "seed files only"
    if not confirm(f"scaffold '{stack['label']}' at {path} "
                   f"(runs: {gen}; then git init + AI config files)?"):
        return
    try:
        out = new_project(cat, stack_id, path,
                          devcontainer=getattr(args, "devcontainer", False))
    except ValueError as e:
        die(str(e))
    ok(f"project created at {out}")
    uc = stack.get("usecase", "general")
    choices = load_json(CHOICES_PATH)
    if choices and choices.get("usecase") != uc and \
            confirm(f"switch this machine's use case to '{uc}' to match?"):
        apply_usecase(cat, choices, uc)
        save_text(CHOICES_PATH, json.dumps(choices, indent=2))
        cmd_config(args)
    info(f"next: cd {out}  |  gate it on any machine with: lai gate {out}")
    cmd_gate(argparse.Namespace(path=str(out), fix=False, yes=assume_yes()))

def cmd_gate(args):
    cat = load_catalog()
    try:
        results, proj = gate_project(cat, getattr(args, "path", None) or ".",
                                     fix=getattr(args, "fix", False))
    except ValueError as e:
        die(str(e))
    print()
    info(f"gate for stack '{proj.get('stack')}' "
         f"(use case {proj.get('usecase')}):")
    icon = {"PASS": ok, "FIXED": ok, "WARN": warn, "FAIL": fail}
    for r in results:
        icon[r["status"]](f"{r['item']:<22} {r['detail']}")
    fails = [r for r in results if r["status"] == "FAIL"]
    print()
    if fails:
        if getattr(args, "fix", False):
            if any("not downloaded" in r["detail"] for r in fails + results):
                if confirm("download the missing model(s) now?"):
                    cmd_models(args)
                    cmd_config(args)
                    info("re-run `lai gate` to confirm green")
                    return
            die(f"{len(fails)} gate check(s) still failing")
        die(f"{len(fails)} gate check(s) failed - "
            "run `lai gate --fix` to let lai resolve them")
    ok("gate passed - this machine satisfies the project")
