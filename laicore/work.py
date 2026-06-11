"""Daily work tools: skills, git AI, terminal chat, docs RAG."""

from .core import *  # noqa: F401,F403

SKILLS_DIR = ROOT / "skills"

def skill_dirs(project=None):
    """Skill libraries, in lookup order: lai's own, then the project's."""
    dirs = [SKILLS_DIR]
    proj = Path(project or ".").resolve() / ".lai" / "skills"
    if proj.exists():
        dirs.append(proj)
    return dirs


def list_skills(project=None):
    out = {}
    for base in skill_dirs(project):
        if not base.exists():
            continue
        scope = "project" if ".lai" in str(base) else "built-in"
        for d in sorted(base.iterdir()):
            meta = load_json(d / "skill.json")
            if meta:
                out[d.name] = dict(meta, scope=scope)
    return out

def install_skill(name, project_path, force=False):
    """Copy a skill into a project. Returns list of actions taken."""
    src = None
    for base in skill_dirs(project_path):
        if load_json(base / name / "skill.json"):
            src = base / name  # project-local definition wins
    meta = load_json((src or SKILLS_DIR / name) / "skill.json")
    if not meta:
        raise ValueError(f"unknown skill '{name}' - see `lai skill list`")
    dest = Path(project_path).expanduser().resolve()
    if not dest.is_dir():
        raise ValueError(f"not a directory: {dest}")
    actions = []

    proj_files = src / "project"
    if proj_files.exists():
        for f in proj_files.rglob("*"):
            if not f.is_file():
                continue
            rel = f.relative_to(proj_files)
            target = dest / rel
            if rel.as_posix() == ".roo/mcp.json" and target.exists():
                merged = load_json(target, {})
                merged.setdefault("mcpServers", {}).update(
                    load_json(f, {}).get("mcpServers", {}))
                target.write_text(json.dumps(merged, indent=2),
                                  encoding="utf-8", newline="\n")
                actions.append(f"merged {rel.as_posix()}")
                continue
            if target.exists() and not force:
                actions.append(f"kept existing {rel.as_posix()} "
                               "(use --force to overwrite)")
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(f, target)
            actions.append(f"wrote {rel.as_posix()}")

    if meta.get("mode"):
        mode = load_json(src / meta["mode"])
        if mode:
            modes_file = dest / ".roomodes"
            data = load_json(modes_file, {"customModes": []})
            data.setdefault("customModes", [])
            data["customModes"] = [m for m in data["customModes"]
                                   if m.get("slug") != mode["slug"]]
            data["customModes"].append(mode)
            modes_file.write_text(json.dumps(data, indent=2),
                                  encoding="utf-8", newline="\n")
            actions.append(f"registered mode '{mode['slug']}' in .roomodes")
    return actions

SKILL_GEN_PROMPT = (
    "Write concise agent rules (markdown, numbered list, max 10 rules) for "
    "a coding-agent skill named '{name}'. The skill purpose: {desc}. "
    "Rules must be imperative, verifiable, and specific - the style of a "
    "strict senior engineer. No preamble; output ONLY the markdown starting "
    "with '# {name} rules'.")


def cmd_skill(args):
    skills = list_skills(getattr(args, "path", "."))
    if args.action == "list" or not args.action:
        print()
        for name, meta in skills.items():
            tag = c("90", "[" + meta.get("scope", "built-in") + "] ")
            print(f"  {c('1', name.ljust(12))} {tag}"
                  f"{meta.get('description', '')}")
        print(c("90", "\n  add to a project:   lai skill add <name> "
                      "[--path <project>]"))
        print(c("90", "  create your own:    lai skill new <name> "
                      "[--ai description] [--project <path>]"))
        return
    if args.action == "new":
        if not args.name:
            die("usage: lai skill new <name> [--ai description] "
                "[--project <path>]")
        name = sanitize_name(args.name).replace("_", "-")
        proj = getattr(args, "project", None)
        base = (Path(proj).resolve() / ".lai" / "skills" / name) if proj \
            else SKILLS_DIR / name
        if (base / "skill.json").exists():
            die(f"skill '{name}' already exists at {base}")
        desc = getattr(args, "ai", None)
        if desc:
            info(f"asking your local model to draft the '{name}' rules...")
            body = llm_chat(SKILL_GEN_PROMPT.format(name=name, desc=desc),
                            temperature=0.3)
            body = re.sub(r"^```[^\n]*\n|```\s*$", "", body.strip(),
                          flags=re.M).strip() + "\n"
            description = desc
        else:
            body = (f"# {name} rules\n\n"
                    "1. <write the first rule - imperative and "
                    "verifiable>\n2. <...>\n")
            description = f"Custom skill: {name} (edit me)"
        rules = base / "project" / ".roo" / "rules" / f"{name}.md"
        rules.parent.mkdir(parents=True, exist_ok=True)
        rules.write_text(body, encoding="utf-8", newline="\n")
        (base / "skill.json").write_text(json.dumps(
            {"description": description}, indent=2),
            encoding="utf-8", newline="\n")
        ok(f"skill '{name}' created at {base}")
        if desc:
            print(c("90", "  --- generated rules "
                          "(REVIEW before trusting them) ---"))
            print(body)
        where = "this project (committed - the whole team gets it)" \
            if proj else "the lai skill library"
        extra = "" if proj else " --path <project>"
        info(f"lives in {where}. Install into a project: "
             f"lai skill add {name}{extra}")
        return
    if args.action == "add":
        if not args.name:
            die("usage: lai skill add <name> [--path <project>]")
        try:
            actions = install_skill(args.name, args.path or ".",
                                    force=getattr(args, "force", False))
        except ValueError as e:
            die(str(e))
        for a in actions:
            ok(a)
        info("reload the VS Code window so Roo Code picks up new modes/rules")
        return
    die(f"unknown action '{args.action}' - use: list | add")

def git_out(argv, allow_fail=False):
    r = subprocess.run(["git"] + argv, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0 and not allow_fail:
        die(f"git {' '.join(argv)}: {r.stderr.strip() or r.stdout.strip()}")
    return r.stdout

DIFF_LIMIT = 24000  # chars per model request; beyond this we go per-file

CONFLICT_RE = re.compile(
    r"<<<<<<<[^\n]*\n(.*?)(?:\|\|\|\|\|\|\|[^\n]*\n.*?)?=======\n(.*?)"
    r">>>>>>>[^\n]*\n?", re.S)

def split_conflicts(text):
    """-> list of ('text', s) and ('conflict', ours, theirs) segments."""
    parts, last = [], 0
    for m in CONFLICT_RE.finditer(text):
        parts.append(("text", text[last:m.start()]))
        parts.append(("conflict", m.group(1), m.group(2)))
        last = m.end()
    parts.append(("text", text[last:]))
    return parts

def _extract_fenced(reply):
    m = re.search(r"```[^\n]*\n(.*?)```", reply, re.S)
    return m.group(1) if m else reply.strip() + "\n"

def _git_review(args):
    base = getattr(args, "base", None)
    diff_args = [f"{base}...HEAD"] if base else ["HEAD"]
    diff = git_out(["diff"] + diff_args)
    if not diff.strip():
        ok("nothing to review (working tree matches " +
           (base or "HEAD") + ")")
        return
    system = ("You are a strict senior code reviewer. Report findings as "
              "'[BUG|RISK|TEST|STYLE] file:line - problem, why it matters, "
              "concrete fix', most severe first. If clean, reply 'LGTM' "
              "plus the biggest residual risk. No praise, no filler.")
    if len(diff) <= DIFF_LIMIT:
        chunks = [("all changes", diff)]
    else:
        files = git_out(["diff", "--name-only"] + diff_args).split()
        info(f"large diff - reviewing {len(files)} files individually")
        chunks = [(f, git_out(["diff"] + diff_args + ["--", f])[:DIFF_LIMIT])
                  for f in files]
    mdl = getattr(args, "model", None) or "coder"
    for label, chunk in chunks:
        info(f"reviewing {label}...")
        print(llm_chat(f"Review this diff:\n\n```diff\n{chunk}\n```",
                       system=system, model=mdl))
        print()

def _git_commit(args):
    diff = git_out(["diff", "--cached"])
    if not diff.strip():
        die("nothing staged - `git add` your changes first")
    msg = llm_chat(
        "Write a git commit message for this staged diff. Format: "
        "conventional commit subject line (<=72 chars, imperative), blank "
        "line, then 1-4 body bullets explaining WHY. Reply with the message "
        f"only.\n\n```diff\n{diff[:DIFF_LIMIT]}\n```",
        temperature=0.3,
        model=getattr(args, "model", None) or "coder").strip()
    msg = re.sub(r"^```[^\n]*\n|```$", "", msg, flags=re.M).strip()
    print("\n" + msg + "\n")
    if getattr(args, "apply", False) and confirm("commit with this message?"):
        tmp = RUN / "commitmsg.txt"
        tmp.write_text(msg + "\n", encoding="utf-8")
        git_out(["commit", "-F", str(tmp)])
        tmp.unlink(missing_ok=True)
        ok("committed")
    elif not getattr(args, "apply", False):
        info("use `lai git commit --apply` to commit with it")

def _git_resolve(args):
    files = [f for f in git_out(
        ["diff", "--name-only", "--diff-filter=U"]).split() if f]
    if not files:
        ok("no merge conflicts found")
        return
    info(f"{len(files)} conflicted file(s): {', '.join(files)}")
    for fname in files:
        path = Path(fname)
        text = path.read_text(encoding="utf-8", errors="replace")
        parts = split_conflicts(text)
        n = sum(1 for p in parts if p[0] == "conflict")
        if n == 0 or n > 20:
            warn(f"{fname}: {n} conflicts - skipping "
                 "(resolve manually)" if n else f"{fname}: no markers found")
            continue
        info(f"{fname}: resolving {n} conflict(s)...")
        out, idx = [], 0
        for i, p in enumerate(parts):
            if p[0] == "text":
                out.append(p[1])
                continue
            idx += 1
            before = parts[i - 1][1][-600:] if i > 0 else ""
            after = parts[i + 1][1][:400] if i + 1 < len(parts) else ""
            reply = llm_chat(
                model=getattr(args, "model", None) or "coder",
                prompt="Resolve this git merge conflict. Combine the INTENT of "
                "both sides; if they are alternatives, prefer the side "
                "consistent with the surrounding context. Reply with ONLY "
                "the merged replacement text in a fenced code block (no "
                "conflict markers, no commentary).\n\n"
                f"Context before:\n```\n{before}\n```\n"
                f"OURS (current branch):\n```\n{p[1]}\n```\n"
                f"THEIRS (incoming):\n```\n{p[2]}\n```\n"
                f"Context after:\n```\n{after}\n```")
            merged = _extract_fenced(reply)
            if merged and not merged.endswith("\n"):
                merged += "\n"
            preview = "\n        ".join(merged.splitlines()[:8])
            print(c("90", f"      conflict {idx}/{n} ->\n        {preview}"))
            out.append(merged)
        resolved = "".join(out)
        if CONFLICT_RE.search(resolved) or "<<<<<<<" in resolved:
            fail(f"{fname}: resolution still contains markers - not written")
            continue
        if confirm(f"write resolved {fname}? (original recoverable via "
                   f"`git checkout --merge -- {fname}`)"):
            path.write_text(resolved, encoding="utf-8", newline="")
            ok(f"{fname} written - review it, then: git add {fname}")

def _git_explain(args):
    ref = getattr(args, "ref", None)
    if ref:
        content = git_out(["show", ref, "--stat", "--patch"])[:DIFF_LIMIT]
        what = f"commit {ref}"
    else:
        content = git_out(["diff", "HEAD"])[:DIFF_LIMIT]
        what = "the current uncommitted changes"
        if not content.strip():
            ok("working tree is clean")
            return
    print(llm_chat(
        f"Explain {what} in plain language for a teammate: what changed, "
        "why it probably changed, and any risks or follow-ups to watch. "
        f"Be concrete and brief.\n\n```\n{content}\n```",
        model=getattr(args, "model", None) or "coder"))

def cmd_git(args):
    git_out(["rev-parse", "--is-inside-work-tree"])  # dies if not a repo
    {"review": _git_review, "commit": _git_commit,
     "resolve": _git_resolve, "explain": _git_explain}[args.action](args)

DOCS_REG = STATE / "docs.json"

def _html_to_text(html):
    html = re.sub(r"(?is)<(script|style|nav|footer)[^>]*>.*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    for ent, ch in (("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
                    ("&quot;", '"'), ("&#39;", "'"), ("&nbsp;", " ")):
        text = text.replace(ent, ch)
    return re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]+", " ", text)).strip()

def _chunk(text, size=1500, overlap=1):
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks, cur = [], []
    for p in paras:
        cur.append(p)
        if sum(len(x) for x in cur) >= size:
            chunks.append("\n\n".join(cur))
            cur = cur[-overlap:]
    if cur and (not chunks or "\n\n".join(cur) != chunks[-1]):
        chunks.append("\n\n".join(cur))
    return [ch[:4000] for ch in chunks]

def _embed(texts):
    out = []
    for i in range(0, len(texts), 16):
        r = http_json(f"{endpoint_base(P('embeddings'))}/v1/embeddings",
                      {"model": "embeddings", "input": texts[i:i + 16]},
                      timeout=300, headers=auth_headers())
        out += [d["embedding"] for d in r["data"]]
    return out

def _qdrant(path, payload=None, method=None):
    return http_json(f"http://{endpoint_host()}:{P('qdrant')}{path}", payload,
                     timeout=60, method=method)

def _docs_collection(project):
    name = sanitize_name(Path(project or ".").resolve().name) or "global"
    return f"lai-docs-{name}"

def cmd_docs(args):
    if args.action == "list":
        for e in load_json(DOCS_REG, []):
            print(f"  {e['collection']:<28} {e['chunks']:>4} chunks  "
                  f"{e['source']}")
        return
    coll = _docs_collection(getattr(args, "project", None))
    if args.action == "search":
        if not args.target:
            die("usage: lai docs search \"<query>\" [--project <path>]")
        vec = _embed([args.target])[0]
        r = _qdrant(f"/collections/{coll}/points/search",
                    {"vector": vec, "limit": 5, "with_payload": True})
        for hit in r.get("result", []):
            p = hit.get("payload", {})
            print(f"\n--- {hit.get('score', 0):.3f}  {p.get('source', '')}")
            print(p.get("text", "")[:600])
        return
    if args.action != "add" or not args.target:
        die("usage: lai docs add <url|file> | search \"<q>\" | list")

    src = args.target
    info(f"reading {src} ...")
    if re.match(r"https?://", src):
        status, raw = http_get(src, timeout=60)
        text = _html_to_text(raw.decode("utf-8", errors="replace"))
    elif src.lower().endswith((".pdf", ".docx", ".pptx")):
        text = None
        try:  # docling: layout/table-aware, handles office docs + scans
            from docling.document_converter import DocumentConverter
            info("parsing with docling (layout-aware)...")
            text = (DocumentConverter().convert(src)
                    .document.export_to_markdown())
        except ImportError:
            pass
        if text is None and src.lower().endswith(".pdf"):
            try:
                from pypdf import PdfReader
            except ImportError:
                die("PDF support needs pypdf (basic) or docling (best) - "
                    f"{sys.executable} -m pip install pypdf")
            text = "\n\n".join(page.extract_text() or ""
                               for page in PdfReader(src).pages)
        elif text is None:
            die("docx/pptx parsing needs docling - "
                f"{sys.executable} -m pip install docling")
    else:
        text = Path(src).read_text(encoding="utf-8", errors="replace")
    chunks = _chunk(text)
    if not chunks:
        die("no extractable text found")
    info(f"{len(chunks)} chunks -> embedding (local) ...")
    try:
        vectors = _embed(chunks)
    except Exception as e:
        die(f"embeddings endpoint {endpoint_base(P('embeddings'))} failed ({e}) "
            "- is the stack running?")
    try:
        existing = _qdrant("/collections")["result"]["collections"]
        if coll not in [col["name"] for col in existing]:
            _qdrant(f"/collections/{coll}",
                    {"vectors": {"size": len(vectors[0]),
                                 "distance": "Cosine"}}, method="PUT")
        import hashlib
        points = []
        for i, (chunk, vec) in enumerate(zip(chunks, vectors)):
            h = hashlib.md5(f"{src}#{i}".encode()).hexdigest()
            points.append({"id": f"{h[:8]}-{h[8:12]}-{h[12:16]}-"
                                 f"{h[16:20]}-{h[20:32]}",
                           "vector": vec,
                           "payload": {"text": chunk, "source": src}})
        for i in range(0, len(points), 64):
            _qdrant(f"/collections/{coll}/points",
                    {"points": points[i:i + 64]}, method="PUT")
    except Exception as e:
        die(f"qdrant failed ({e}) - is it running? -> lai docker")
    reg = [e for e in load_json(DOCS_REG, [])
           if not (e["source"] == src and e["collection"] == coll)]
    reg.append({"source": src, "collection": coll, "chunks": len(chunks),
                "when": datetime.now().isoformat(timespec="seconds")})
    save_text(DOCS_REG, json.dumps(reg, indent=2))
    ok(f"indexed {len(chunks)} chunks into '{coll}'")
    info('query: lai docs search "your question" '
         '(agents can run this via their command tool)')

def _stream_chat(model, msgs):
    prov, name = parse_model(model)
    if prov == "anthropic":  # different SSE schema - print non-streamed
        reply = cloud_chat(prov, name, msgs, max_tokens=4096)
        print(reply)
        return reply
    payload = {"model": name if prov else model, "messages": msgs,
               "stream": True, "max_tokens": 4096, "temperature": 0.3}
    hdrs = {"User-Agent": "lai", "Content-Type": "application/json"}
    if prov:
        key = cloud_keys().get(prov)
        if not key:
            die(f"no {prov} key -> lai cloud add {prov}")
        url = f"{CLOUD[prov]['base']}/chat/completions"
        hdrs["Authorization"] = f"Bearer {key}"
    else:
        url = f"{endpoint_base()}/v1/chat/completions"
        hdrs.update(auth_headers())
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers=hdrs)
    out = []
    try:
        with urllib.request.urlopen(req, timeout=900) as resp:
            for raw in resp:
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    delta = json.loads(data)["choices"][0]["delta"] \
                        .get("content", "")
                except (ValueError, KeyError, IndexError):
                    continue
                if delta:
                    print(delta, end="", flush=True)
                    out.append(delta)
    except KeyboardInterrupt:
        print(c("90", "\n(interrupted)"))
    print()
    return "".join(out)

POLISH_PROMPT = (
    "Rewrite the user's message below as a precise English instruction for "
    "a coding model: translate to English if it is in another language "
    "(keep code identifiers and paths unchanged), state the goal first, "
    "make constraints explicit, remove filler. If something essential is "
    "genuinely unclear, append a final line 'Open questions: ...' with at "
    "most 2 questions. Reply with ONLY the rewritten instruction.\n\n")

def cmd_chat(args):
    model = getattr(args, "model", None) or "coder"
    served = []
    if not parse_model(model)[0]:
        try:
            data = http_json(f"{endpoint_base()}/v1/models", timeout=3)
            served = [m.get("id") for m in data.get("data", [])]
        except Exception:
            die(f"endpoint {endpoint_base()} not reachable -> lai start "
                "(or lai connect <server>)")
    polish = bool(getattr(args, "polish", False))
    msgs = [{"role": "system", "content":
             "You are a concise expert pair-programmer in a terminal. "
             "Prefer code blocks. State assumptions explicitly. "
             "If a request is ambiguous, ask one sharp question first."}]
    print()
    info(f"lai chat - model '{model}' on {endpoint_base()}"
         + (f" (serving: {', '.join(served)})" if served else ""))
    info("@path/to/file includes a file | /model <id> (or:/oa:/an: for "
         "cloud) | /polish | /clear | /exit")
    if polish:
        info("polish ON: messages are translated to English and sharpened "
             "locally before the main model sees them")
    print()
    while True:
        try:
            line = input(c("35", "you> ")).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        if line in ("/exit", "/quit", "/q"):
            break
        if line == "/clear":
            msgs = msgs[:1]
            ok("history cleared")
            continue
        if line.startswith("/model"):
            model = (line.split(None, 1) + [model])[1].strip() or model
            prov = parse_model(model)[0]
            ok(f"model -> {model}" + (f" (cloud: {prov})" if prov else ""))
            continue
        if line == "/polish":
            polish = not polish
            ok(f"polish {'ON' if polish else 'OFF'}")
            continue
        if line.startswith("/"):
            info("commands: /model <id> | /polish | /clear | /exit")
            continue
        content = line
        if polish:
            try:
                better = llm_chat(POLISH_PROMPT + line, max_tokens=400,
                                  temperature=0).strip()
                if better:
                    print(c("90", f"polished> {better}"))
                    content = better
            except SystemExit:
                warn("polish step unavailable - sending as-is")
        for token in re.findall(r"@([\w./\\~-]+)", line):
            p = Path(token).expanduser()
            if p.is_file() and p.stat().st_size < 200_000:
                content += (f"\n\n--- {token} ---\n```\n"
                            f"{p.read_text(encoding='utf-8', errors='replace')}\n```")
                info(f"attached {token}")
        msgs.append({"role": "user", "content": content})
        print(c("36", f"{model}> "), end="", flush=True)
        reply = _stream_chat(model, msgs)
        msgs.append({"role": "assistant", "content": reply})
        if len(msgs) > 25:  # keep the system prompt + recent turns
            msgs = msgs[:1] + msgs[-20:]
