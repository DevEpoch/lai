"""The lai agent: chat that recognizes skills by itself and uses tools
(read/list/search/write/run) when the model decides it needs them.
Works with ANY local model - tool calls ride a fenced ```tool block,
no function-calling chat template required."""

from .core import *  # noqa: F401,F403
from .work import list_skills, skill_dirs  # noqa: F401

MAX_STEPS = 8
MAX_TOOL_OUT = 6000  # chars of tool output fed back per step

TOOL_SPEC = """You can use tools. To use one, reply with ONLY a fenced
block like this (one tool per turn, then wait for the result):
```tool
{"tool": "read_file", "args": {"path": "src/app.py"}}
```
Tools:
- list_files {"pattern": "**/*.py"}  -> project file list
- read_file  {"path": "..."}         -> file content
- search     {"regex": "..."}        -> grep across the project
- write_file {"path": "...", "content": "..."} -> create/overwrite a file
- run_check  {"what": "gate"|"tests"} -> run the project gate or test suite
When you have everything you need, answer normally (no tool block)."""

AGENT_SYS = """You are lai, a precise local AI pair-programmer working
INSIDE the user's project at {root}. Nothing leaves this machine.
{skill}
{tools}"""

SKIP_DIRS = {".git", "node_modules", "dist", "out", "build", ".venv",
             "__pycache__", ".idea", "target", "bin", "obj", ".lai"}


def _confine(root, rel):
    p = os.path.realpath(str(Path(root) / str(rel)))
    r = os.path.realpath(str(root))
    if p != r and not p.startswith(r + os.sep):
        raise ValueError(f"path escapes the project: {rel}")
    return Path(p)


def _walk(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames
                       if d not in SKIP_DIRS and not d.startswith(".")]
        for f in filenames:
            yield Path(dirpath) / f


def t_list_files(root, pattern="**/*"):
    out = []
    for f in _walk(root):
        rel = f.relative_to(root).as_posix()
        if fnmatch_path(rel, pattern):
            out.append(rel)
        if len(out) >= 400:
            out.append("... (truncated at 400)")
            break
    return "\n".join(out) or "(no matches)"


def fnmatch_path(rel, pattern):
    import fnmatch as _fn
    return _fn.fnmatch(rel, pattern) or _fn.fnmatch(Path(rel).name, pattern)


def t_read_file(root, path):
    f = _confine(root, path)
    if not f.is_file():
        return f"(not a file: {path})"
    if f.stat().st_size > 200_000:
        return f"(too big: {f.stat().st_size} bytes)"
    return f.read_text(encoding="utf-8", errors="replace")


def t_search(root, regex):
    try:
        rx = re.compile(regex)
    except re.error as e:
        return f"(bad regex: {e})"
    hits = []
    for f in _walk(root):
        if f.stat().st_size > 400_000:
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if rx.search(line):
                hits.append(f"{f.relative_to(root).as_posix()}:{i}: "
                            f"{line.strip()[:160]}")
                if len(hits) >= 120:
                    return "\n".join(hits + ["... (truncated at 120)"])
    return "\n".join(hits) or "(no matches)"


def t_write_file(root, path, content):
    f = _confine(root, path)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(str(content), encoding="utf-8", newline="\n")
    return f"wrote {path} ({len(str(content))} chars)"


def t_run_check(root, what="tests"):
    if what == "gate":
        cli = [sys.executable, str(ROOT / "lai.py"), "gate",
               "--path", str(root)]
    elif what == "tests":
        cli = [sys.executable, "-m", "unittest", "discover", "-s", "tests"] \
            if (Path(root) / "tests").is_dir() else None
        if cli is None:
            return "(no tests/ folder in this project)"
    else:
        return f"(unknown check: {what})"
    r = subprocess.run(cli, cwd=str(root), capture_output=True, text=True,
                       timeout=600)
    return ((r.stdout or "") + (r.stderr or ""))[-MAX_TOOL_OUT:]


TOOLS = {"list_files": t_list_files, "read_file": t_read_file,
         "search": t_search, "write_file": t_write_file,
         "run_check": t_run_check}

TOOL_RE = re.compile(r"```tool\s*\n(\{.*?\})\s*\n?```", re.DOTALL)


def parse_tool_call(text):
    """First ```tool block in a reply -> (name, args) or None."""
    m = TOOL_RE.search(text or "")
    if not m:
        return None
    try:
        d = json.loads(m.group(1))
        name = d.get("tool")
        if name in TOOLS:
            return name, (d.get("args") or {})
    except ValueError:
        pass
    return None


def auto_skill(question, project=None):
    """Match the request against installed skill descriptions - the
    best-scoring skill's rules ride along in the system prompt."""
    words = set(re.findall(r"[a-z؀-ۿ]{3,}", question.lower()))
    best, score = None, 1  # need at least 2 overlapping words
    for name, meta in list_skills(project).items():
        hay = set(re.findall(r"[a-z؀-ۿ]{3,}",
                             f"{name} {meta.get('description', '')}"
                             f" {meta.get('keywords', '')}".lower()))
        s = len(words & hay)
        if s > score:
            best, score = name, s
    if not best:
        return "", None
    parts = [f"Active skill: {best}"]
    for base in skill_dirs(project):
        rules = base / best / "project" / ".roo" / "rules"
        if rules.is_dir():
            for f in sorted(rules.glob("*.md")):
                parts.append(f.read_text(encoding="utf-8",
                                         errors="replace")[:4000])
    return "\n".join(parts), best


def _llm(msgs, model="coder", max_tokens=2048):
    prov, name = parse_model(model)
    if prov:
        return cloud_chat(prov, name, msgs, max_tokens, 0.2)
    r = http_json(f"{endpoint_base()}/v1/chat/completions",
                  {"model": model, "messages": msgs,
                   "max_tokens": max_tokens, "temperature": 0.2},
                  timeout=900, headers=auth_headers())
    return r["choices"][0]["message"].get("content", "")


def run_agent(root, question, model="coder", history=None):
    """Generator of events: {"type": "skill"|"text"|"tool"|"done", ...}.
    Drives the tool loop until the model answers without a tool call."""
    root = Path(root).resolve()
    skill_text, skill_name = auto_skill(question, str(root))
    if skill_name:
        yield {"type": "skill", "name": skill_name}
    msgs = [{"role": "system",
             "content": AGENT_SYS.format(root=root.as_posix(),
                                         skill=skill_text,
                                         tools=TOOL_SPEC)}]
    msgs += list(history or [])
    msgs.append({"role": "user", "content": question})
    for _ in range(MAX_STEPS):
        reply = _llm(msgs, model=model)
        msgs.append({"role": "assistant", "content": reply})
        call = parse_tool_call(reply)
        if not call:
            yield {"type": "text", "text": reply}
            break
        name, args = call
        pre = TOOL_RE.sub("", reply).strip()
        if pre:
            yield {"type": "text", "text": pre}
        yield {"type": "tool", "name": name, "args": args}
        try:
            result = str(TOOLS[name](root, **args))[:MAX_TOOL_OUT]
        except (TypeError, ValueError, OSError,
                subprocess.TimeoutExpired) as e:
            result = f"(tool error: {e})"
        msgs.append({"role": "user",
                     "content": f"```tool-result {name}\n{result}\n```"})
    else:
        yield {"type": "text",
               "text": "(stopped: too many tool steps - ask me to "
                       "continue)"}
    yield {"type": "done"}


TASK_RE = re.compile(
    r"^\s*(?:[-*]\s*\[(?P<done>[ xX])\]|(?P<num>\d+)[.)]|[-*])\s+"
    r"(?P<text>\S.*)$")


def parse_tasks(md):
    """Checklist / numbered / bullet lines -> [{line, text, done, box}]."""
    out = []
    for i, line in enumerate(md.splitlines()):
        m = TASK_RE.match(line)
        if m and len(m.group("text")) > 2:
            out.append({"line": i, "text": m.group("text").strip(),
                        "done": (m.group("done") or " ").lower() == "x",
                        "box": m.group("done") is not None})
    return out


def mark_done(md, line_no):
    """Tick a checkbox line (or convert the bullet/number to one)."""
    lines = md.splitlines()
    t = TASK_RE.match(lines[line_no])
    if t:
        indent = lines[line_no][:len(lines[line_no])
                                - len(lines[line_no].lstrip())]
        lines[line_no] = f"{indent}- [x] {t.group('text')}"
    return "\n".join(lines) + ("\n" if md.endswith("\n") else "")


def _verify(root):
    """Green/skip/red after each task. Returns (ok, detail)."""
    out = t_run_check(root, "tests")
    if out.startswith("(no tests"):
        return True, "no tests - skipped"
    ok = "\nOK" in out or out.strip().endswith("OK")
    return ok, out[-1500:]


def run_tasks(root, task_file, model="coder"):
    """Do every unchecked task in an md file, one fresh agent run per
    task, verifying (tests) and ticking the checkbox after each. The
    deterministic loop lives HERE - the model only ever sees one task."""
    root = Path(root).resolve()
    f = _confine(root, Path(task_file).name) if not Path(task_file).is_file() \
        else Path(task_file).resolve()
    md = f.read_text(encoding="utf-8", errors="replace")
    tasks = parse_tasks(md)
    todo = [t for t in tasks if not t["done"]]
    yield {"type": "plan", "total": len(tasks), "todo": len(todo)}
    done_notes = []
    for n, t in enumerate(todo, 1):
        yield {"type": "task", "n": n, "total": len(todo),
               "text": t["text"]}
        remaining = "\n".join("- " + x["text"] for x in todo[n:])
        q = (f"Work ONLY on this one task, then answer with a one-line "
             f"summary of what you changed:\nTASK: {t['text']}\n"
             + (f"Already done before this:\n"
                + "\n".join(done_notes[-5:]) + "\n" if done_notes else "")
             + (f"Do NOT touch these later tasks yet:\n{remaining}"
                if remaining else ""))
        last_text = ""
        for ev in run_agent(root, q, model=model):
            if ev["type"] == "text":
                last_text = ev["text"]
            if ev["type"] != "done":
                yield ev
        ok, detail = _verify(root)
        yield {"type": "verify", "ok": ok, "detail": detail[-400:]}
        if not ok:  # one repair attempt, then stop honestly
            for ev in run_agent(root,
                                "The checks fail after your last change. "
                                "Fix ONLY this:\n" + detail, model=model):
                if ev["type"] != "done":
                    yield ev
            ok, detail = _verify(root)
            yield {"type": "verify", "ok": ok, "detail": detail[-400:]}
            if not ok:
                yield {"type": "halt", "after": n - 1,
                       "text": f"stopped at task {n}: checks still red - "
                               "fix manually, then rerun to resume"}
                return
        md = mark_done(md, t["line"])
        f.write_text(md, encoding="utf-8", newline="\n")
        done_notes.append(f"- {t['text']}: {last_text[:160]}")
        yield {"type": "task_done", "n": n}
    yield {"type": "all_done", "count": len(todo)}


TASKFILE_RE = re.compile(r"[\w./\\-]+\.md\b")
TASK_INTENT_RE = re.compile(
    r"\b(do|run|finish|complete|execute|work)\b[\s\S]{0,80}"
    r"\b(task|checklist|todo)s?\b"
    r"|انجام|اجرا|تکمیل|أكمل|نفذ", re.IGNORECASE)


def detect_taskfile(root, text):
    """'do all the tasks in plan.md' -> the md path, else None."""
    m = TASKFILE_RE.search(text or "")
    if not (m and TASK_INTENT_RE.search(text)):
        return None
    try:
        f = _confine(root, m.group(0))
    except ValueError:
        return None
    if f.is_file() and any(not t["done"] for t in parse_tasks(
            f.read_text(encoding="utf-8", errors="replace"))):
        return f
    return None


def smart_run(root, text, model="coder", history=None):
    """One front door for every chat surface: a task-list request runs
    the checklist runner; anything else runs the single-shot agent."""
    f = detect_taskfile(root, text)
    if f:
        yield {"type": "text",
               "text": f"Running the checklist in {f.name} - one task "
                       "at a time, tests after each, boxes ticked live."}
        yield from run_tasks(root, str(f), model=model)
    else:
        yield from run_agent(root, text, model=model, history=history)


def cmd_tasks(args):
    """lai tasks plan.md [--path DIR] [--model M] - run every unchecked
    task, one by one, verified, resumable (rerun = continue)."""
    root = Path(getattr(args, "path", None) or ".").resolve()
    for ev in run_tasks(root, args.file,
                        model=getattr(args, "model", None) or "coder"):
        k = ev["type"]
        if k == "plan":
            info(f"{ev['todo']} of {ev['total']} tasks still open")
        elif k == "task":
            print()
            info(f"task {ev['n']}/{ev['total']}: {ev['text']}")
        elif k == "tool":
            info(f"  tool: {ev['name']}")
        elif k == "text":
            print(ev["text"])
        elif k == "verify":
            (ok if ev["ok"] else warn)(f"checks: "
                                       f"{'green' if ev['ok'] else 'RED'}")
        elif k == "halt":
            die(ev["text"])
        elif k == "all_done":
            ok(f"ALL {ev['count']} TASKS DONE - checklist is fully ticked")


def cmd_agent(args):
    """lai agent "question" [--path DIR] [--model coder] - one-shot
    agent run in the terminal; the VS Code chat uses the same loop."""
    root = Path(getattr(args, "path", None) or ".").resolve()
    q = " ".join(getattr(args, "question", []) or [])
    if not q:
        die('usage: lai agent "review this project and list problems"')
    for ev in smart_run(root, q, model=getattr(args, "model", None)
                        or "coder"):
        if ev["type"] == "skill":
            info(f"skill: {ev['name']}")
        elif ev["type"] == "tool":
            info(f"tool: {ev['name']} {json.dumps(ev['args'])[:120]}")
        elif ev["type"] == "task":
            info(f"task {ev['n']}/{ev['total']}: {ev['text']}")
        elif ev["type"] == "verify":
            (ok if ev["ok"] else warn)(
                f"checks: {'green' if ev['ok'] else 'RED'}")
        elif ev["type"] in ("halt", "all_done"):
            (warn if ev["type"] == "halt" else ok)(
                ev.get("text") or f"ALL {ev.get('count')} TASKS DONE")
        elif ev["type"] == "text":
            print(ev["text"])
