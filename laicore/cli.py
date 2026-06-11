"""Argument parsing and command dispatch."""

from .core import *  # noqa: F401,F403
from .stack import *  # noqa: F401,F403
from .work import *  # noqa: F401,F403
from .projects import *  # noqa: F401,F403
from .webui import cmd_ui  # noqa: F401

DESCRIPTION = """lai - Local AI programming environment manager.

Cross-platform (Windows / Linux / macOS) manager for a fully local AI coding
stack: llama.cpp + llama-swap + open models + Qdrant + OpenHands.

All recommendations live in an editable table: config/catalog.json.
Edit it anytime, then `lai plan` to re-evaluate.

Usage:  python lai.py <command> [--yes]   (or the lai.ps1 / lai.sh wrappers)

Commands:
  go         EASIEST START: sets everything up with one question,
             then opens your AI - made for absolute beginners
  check      report hardware, dependencies, and install state
  plan       detect hardware, match a catalog tier, review/edit the choices
  choices    show current choices and the alternatives that fit this machine
  set        change one choice, e.g.:  lai set coder devstral-small
  catalog    show the hardware->recommendation table (config/catalog.json)
  setup      plan + engines + models + config + ide (each step asks approval)
  engines    download llama.cpp and llama-swap for this OS/GPU
  models     download the chosen GGUF models from Hugging Face
  config     (re)generate runtime configs from the saved choices
  ide        install the Continue config into ~/.continue/
  docker     start Qdrant + OpenHands via docker compose
  start/stop/restart/status   manage the inference stack
  bench      run llama-bench, compare against the tier's targets
             (--quality runs a task-solving suite instead - use it to
              compare models after catalog updates)
  validate   end-to-end smoke tests (chat, tools, FIM, embeddings, RAG)
  apikey     generate/remove an API key required on all model endpoints
  autostart  install a login service (Startup/systemd/launchd) + watchdog
  watchdog   start the stack and auto-restart it if it dies (foreground)
  update     self-update lai over git: only changed files move, shows the
             CHANGELOG delta first; --policy ask|auto|never; --list and
             --to <version> switch between releases (no update server)
  upgrade    check llama.cpp / llama-swap releases against installed
  refresh    look for NEW models + catalog updates; notifies you; can run
             on a schedule (lai refresh --schedule weekly)
  ui         open the management dashboard in your browser (localhost)
  new        scaffold a project (stack + path) with the AI layer included
  gate       verify/fix that this machine satisfies a project's .lai/ config
  skill      list reusable agent skills / install one into a project
  git        AI git helper: review | commit | resolve (conflicts) | explain
  connect    use a team server's models instead of local ones (--off undoes)
  share      on|off - serve this machine's models to the LAN team
  tune       timed trials of runtime flags; locks in the fastest config
  docs       index documentation (url/file/pdf) into per-project RAG;
             `docs search "q"` queries it (agents call it via commands)
  chat       streaming chat REPL in the terminal (@file attach, /model,
             /polish translates+sharpens non-English prompts first)
  shortcut   Desktop/app-menu launcher that opens the dashboard (--remove)
  cloud      add/remove OpenRouter/OpenAI/Anthropic keys - explicit-use
             fallbacks via or:/oa:/an: model prefixes; local stays default
  hftoken    store a free Hugging Face token (faster model downloads)
  ports      show/set service ports; `ports check --fix` finds conflicts
             with other apps and moves lai to free ports (with approval)
  vscode     install the bundled VS Code companion extension
  info       one-screen summary of the whole environment
  selftest   run the offline test suite (tests/)

Anything that installs or downloads software asks for approval first;
pass --yes (or -y) to approve automatically.
"""

def cmd_info(args):
    cat = load_json(CATALOG_PATH, {})
    choices = load_json(CHOICES_PATH)
    print()
    info(f"lai {VERSION} | endpoint: {endpoint_base()}"
         + (f" (team server)" if remote_cfg() else " (local)"))
    if choices:
        roles = ", ".join(f"{r}={e['model']}" if e else f"{r}=-"
                          for r, e in choices["roles"].items())
        info(f"tier {choices['tier']} | use case "
             f"{choices.get('usecase', '-')} | {roles}")
    else:
        warn("no plan yet -> lai plan")
    up = 0
    for name, url in probes():
        try:
            http_get(url, timeout=1.5)
            up += 1
        except Exception:
            pass
    info(f"services up: {up}/{len(probes())} (details: lai status)")
    info(f"projects: {len(projects_registry())} (lai new / lai gate) | "
         f"skills: {len(list_skills())} (lai skill list)")
    ck = [p for p in cloud_keys() if cloud_keys().get(p)]
    info("cloud fallbacks: " + (", ".join(ck) if ck else
                                "none (lai cloud add <provider>)"))
    print(c("90", "\n  work:    chat | git review/commit/resolve/explain | "
                  "docs add/search | bench --quality"))
    print(c("90", "  manage:  ui | plan | choices | set | tune | models | "
                  "start/stop/status"))
    print(c("90", "  team:    share on | connect <host> | gate | new | "
                  "skill add | apikey | cloud add\n"))

def main():
    parser = argparse.ArgumentParser(
        prog="lai", description=DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-V", "--version", action="version",
                        version=f"lai {VERSION}")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("-y", "--yes", action="store_true",
                        help="approve all install/download prompts")
    sub = parser.add_subparsers(dest="cmd")
    commands = {
        "check": cmd_check, "plan": cmd_plan, "choices": cmd_choices,
        "set": cmd_set, "catalog": cmd_catalog, "setup": cmd_setup,
        "engines": cmd_engines, "models": cmd_models, "config": cmd_config,
        "ide": cmd_ide, "docker": cmd_docker, "start": cmd_start,
        "stop": cmd_stop, "restart": cmd_restart, "status": cmd_status,
        "bench": cmd_bench, "validate": cmd_validate, "apikey": cmd_apikey,
        "autostart": cmd_autostart, "watchdog": cmd_watchdog,
        "upgrade": cmd_upgrade, "update": cmd_update, "ui": cmd_ui, "new": cmd_new,
        "gate": cmd_gate, "skill": cmd_skill, "git": cmd_git,
        "connect": cmd_connect, "share": cmd_share, "tune": cmd_tune,
        "docs": cmd_docs, "chat": cmd_chat, "shortcut": cmd_shortcut,
        "cloud": cmd_cloud, "info": cmd_info, "hftoken": cmd_hftoken, "ports": cmd_ports, "go": cmd_go, "refresh": cmd_refresh, "selftest": cmd_selftest,
        "vscode": cmd_vscode,
    }
    for name in commands:
        sp = sub.add_parser(name, parents=[common])
        if name in ("plan", "setup", "check"):
            sp.add_argument("--vram-gb", type=float, default=None,
                            help="override detected GPU VRAM (GB)")
        if name in ("plan", "setup"):
            sp.add_argument("--use-case", default=None,
                            help="use-case overlay id (see `lai catalog`), "
                                 "e.g. web, mobile, systems, scripts")
        if name == "models":
            sp.add_argument("--all", action="store_true",
                            help="download every catalog model, not just "
                                 "the chosen ones")
        if name == "set":
            sp.add_argument("role", help="one of: " + ", ".join(ROLES))
            sp.add_argument("model", help="catalog model id, or 'none'")
        if name == "catalog":
            sp.add_argument("--verify", action="store_true",
                            help="check every repo against the HF API")
            sp.add_argument("--update", action="store_true",
                            help="pull the latest published catalog "
                                 "(diff + approval + backup)")
            sp.add_argument("--url", default=None,
                            help="catalog URL override for --update")
        if name == "connect":
            sp.add_argument("host", nargs="?", default=None,
                            help="team server host[:port]")
            sp.add_argument("--key", default=None,
                            help="API key of the team server")
            sp.add_argument("--off", action="store_true",
                            help="disconnect, back to local serving")
        if name == "share":
            sp.add_argument("state", choices=["on", "off"])
        if name == "docs":
            sp.add_argument("action", choices=["add", "search", "list"])
            sp.add_argument("target", nargs="?", default=None,
                            help="url/file (add) or query (search)")
            sp.add_argument("--project", default=".",
                            help="project dir -> per-project collection")
        if name == "chat":
            sp.add_argument("--model", default=None,
                            help="model id; or:/oa:/an: prefixes go to "
                                 "cloud (default: coder, local)")
            sp.add_argument("--polish", action="store_true",
                            help="translate+sharpen each message locally "
                                 "before the main model sees it")
        if name == "cloud":
            sp.add_argument("action", choices=["add", "remove", "list",
                                              "models", "use"])
            sp.add_argument("provider", nargs="?", default=None,
                            help=", ".join(CLOUD))
            sp.add_argument("model_id", nargs="?", default=None,
                            help="(use) the model id to make default")
            sp.add_argument("--key", default=None)
            sp.add_argument("--max-tokens", default=None, dest="max_tokens")
            sp.add_argument("--temperature", default=None)
            sp.add_argument("--param", action="append", default=None,
                            help="extra provider/model setting k=v "
                                 "(repeatable), e.g. reasoning_effort=low")
        if name == "update":
            sp.add_argument("--check", action="store_true",
                            help="show what would change, do not apply")
            sp.add_argument("--policy", default=None,
                            choices=["ask", "auto", "never"],
                            help="set the standing update behavior")
            sp.add_argument("--list", dest="list_versions",
                            action="store_true",
                            help="show released versions")
            sp.add_argument("--to", default=None,
                            help="switch to a version tag (or main)")
        if name == "refresh":
            sp.add_argument("--quiet", action="store_true",
                            help="no console output; OS notification only "
                                 "on findings (used by the schedule)")
            sp.add_argument("--schedule", default=None,
                            choices=["daily", "weekly", "off"],
                            help="install/remove an automatic check")
        if name == "ports":
            sp.add_argument("action", nargs="?", default="show",
                            choices=["show", "set", "check"])
            sp.add_argument("name", nargs="?", default=None)
            sp.add_argument("value", nargs="?", default=None)
            sp.add_argument("--fix", action="store_true",
                            help="(check) move conflicting ports to free ones")
        if name == "hftoken":
            sp.add_argument("--key", default=None,
                            help="the hf_... token (prompted if omitted)")
            sp.add_argument("--off", action="store_true",
                            help="remove the stored token")
        if name == "shortcut":
            sp.add_argument("--remove", action="store_true",
                            help="remove the OS shortcuts")
        if name == "bench":
            sp.add_argument("--quality", action="store_true",
                            help="run the task-solving quality suite instead "
                                 "of tokens/sec")
            sp.add_argument("--model", default=None,
                            help="llama-swap model id to quality-test "
                                 "(default: coder)")
        if name == "apikey":
            sp.add_argument("--off", action="store_true",
                            help="remove the API key")
        if name == "autostart":
            sp.add_argument("--remove", action="store_true",
                            help="uninstall the login autostart")
        if name == "ui":
            sp.add_argument("--port", type=int, default=None,
                            help="UI port (default 8090, localhost only)")
            sp.add_argument("--no-browser", action="store_true",
                            dest="no_browser",
                            help="serve without opening a browser")
        if name == "new":
            sp.add_argument("--stack", default=None,
                            help="stack id (see `lai catalog` stacks)")
            sp.add_argument("--path", default=None,
                            help="directory to create the project in")
            sp.add_argument("--devcontainer", action="store_true",
                            help="also write a .devcontainer/ skeleton")
        if name == "gate":
            sp.add_argument("path", nargs="?", default=".",
                            help="project directory (default: current)")
            sp.add_argument("--fix", action="store_true",
                            help="enable missing roles / offer downloads")
        if name == "skill":
            sp.add_argument("action", nargs="?", default="list",
                            choices=["list", "add", "new"])
            sp.add_argument("name", nargs="?", default=None,
                            help="skill name (for add)")
            sp.add_argument("--path", default=".",
                            help="project directory (default: current)")
            sp.add_argument("--force", action="store_true",
                            help="overwrite existing files")
            sp.add_argument("--ai", default=None,
                            help="(new) let the local model draft the "
                                 "rules from this description")
            sp.add_argument("--project", default=None,
                            help="(new) create inside a project "
                                 "(.lai/skills/ - travels with the repo)")
        if name == "git":
            sp.add_argument("action",
                            choices=["review", "commit", "resolve",
                                     "explain"])
            sp.add_argument("ref", nargs="?", default=None,
                            help="commit ref (for explain)")
            sp.add_argument("--base", default=None,
                            help="review against this base ref "
                                 "(e.g. origin/main)")
            sp.add_argument("--apply", action="store_true",
                            help="(commit) actually create the commit")
            sp.add_argument("--model", default=None,
                            help="model id; or:/oa:/an: prefixes use a "
                                 "cloud fallback for this run only")
    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        sys.exit(1)
    set_assume_yes(getattr(args, "yes", False))
    ensure_dirs()
    try:
        commands[args.cmd](args)
    except KeyboardInterrupt:
        print()
        die("interrupted")
