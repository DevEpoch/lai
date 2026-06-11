# Projects & Team Workflow

The problem this solves: a project's AI setup must follow the *project*, not the
machine - across teammates, operating systems, and reinstalls - without anyone
switching settings per project.

## The model: identity vs. capability

**Identity travels in the repo.** These files are committed and auto-loaded by the
tools the moment the folder opens - zero runtime involvement from lai:

| File | Read by | Holds |
| --- | --- | --- |
| `AGENTS.md` | Roo Code, Cline, Aider, OpenHands (industry convention) | build/test/run commands, conventions, boundaries |
| `.vscode/extensions.json` | VS Code (prompts to install) | recommended extensions for the stack |
| `.vscode/settings.json` | VS Code (auto-applied) | workspace settings |
| `.lai/project.json` | `lai gate` | the **team contract** (below) |
| `docs/adr/*.md` | humans + agents | architecture decisions with rationale |

**Capability lives on each machine** - which models are downloaded, which roles are
enabled, how much VRAM exists. This cannot travel in git.

**`lai gate` reconciles the two.**

## The team contract: `.lai/project.json` (committed)

```json
{
  "stack": "wordpress-theme",
  "usecase": "web",
  "required_roles": ["coder", "vision", "autocomplete", "embeddings"],
  "min_ctx": 16384,
  "toolchains": [{"bin": "php", "hint": "winget install PHP.PHP | brew install php"}]
}
```

## Personal overrides: `.lai/local.json` (gitignored)

Each developer may keep preferences that never reach the repo:

```json
{
  "preferred": {"coder": "devstral-small"}
}
```

The gate honors a preference when it fits that developer's hardware; otherwise it
falls back to the best fitting model. Team contract wins on *what* is required;
the developer wins on *which* model fills it.

## Creating a project

```text
lai new                                      # interactive: pick stack, enter path
lai new --stack go-service --path ~/api      # scripted
lai new --stack flutter-app --path ~/app --devcontainer
```

What happens, in order:

1. Toolchain check (`go`, `cargo`, `npm`, `flutter`...) - missing toolchains stop
   generator-based stacks with an install hint; file-only stacks (e.g. wordpress-theme)
   proceed with a warning.
2. The **ecosystem's own generator** runs (`go mod init`, `cargo init`,
   `npm create vite . -- --template react-ts`, `flutter create .`). lai never
   reimplements scaffolds that ecosystems maintain; seed files exist only where no
   generator does.
3. The AI layer is written (table above), `.gitignore` gets the stack's entries plus
   `.lai/local.json`, and the project is git-initialized and committed.
4. lai offers to switch this machine's use case to match, and runs the gate.

Stacks are catalog data (`stacks` in [config/catalog.json](../config/catalog.json)) -
nine ship by default (Go CLI/service, Rust, C++/CMake, Vite+React, Node API,
WordPress theme, Flutter, Python ML). Add your team's own stack once, everyone
scaffolds identically.

## Onboarding a machine (the 2-minute clone story)

```text
git clone <repo> && cd <repo>
lai gate          # report: roles, models, context, toolchains, endpoint
lai gate --fix    # enable missing roles, offer model downloads, regenerate config
```

Gate output is honest per item: `PASS` / `FIXED` / `WARN` (e.g. context lower than the
project wants because the hardware can't) / `FAIL` (with the exact command to resolve).
The same works from the UI: Projects card -> **Gate** / **Fix** buttons, with a
status badge per project.

Different hardware on different teammates is expected: the contract pins *roles and
conventions*, while each machine's tier decides *how* a role is served (a 24 GB
desktop runs the coder fully on GPU; a 6 GB laptop runs the same model hybrid;
an M3 Mac runs it on Metal). Code review sees identical conventions either way.

## Existing repositories

Copy a `.lai/project.json` from any scaffolded project (or write one - it is five
keys), add an `AGENTS.md` from [config/AGENTS.template.md](../config/AGENTS.template.md),
and `lai gate` works the same.

## CI as a gate consumer

`lai gate` exits non-zero on failures, so a CI step can enforce the contract on
runners that host self-hosted agents:

```yaml
- run: python /opt/local-ai-env/lai.py gate . || echo "machine not AI-ready"
```
