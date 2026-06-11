# Skills, Web Research, Prompt Enhancement, Git AI

## Skills

A skill is a reusable instruction pack - markdown rules plus (optionally) a Roo Code
custom mode - stored versioned in [skills/](../skills/) and installed into projects:

```text
lai skill list
lai skill add research              # into the current directory
lai skill add tdd --path ~/myproj   # into another project
```

Installed files are committed with the project, so the whole team gets the skill -
same identity-travels-in-the-repo model as everything else. There is no runtime to
learn: skills land in `.roo/rules*/` and `.roomodes`, which Roo Code already loads.
`lai new` installs `interview`, `review`, `tdd`, and `adr` automatically.

| Skill | What it adds |
| --- | --- |
| `interview` | **Interview mode**: numbered clarifying questions until requirements are unambiguous, writes the spec to `docs/specs/`, hands off to Code mode. Use it for anything fuzzy. |
| `review` | **Reviewer mode**: reads diffs, reports `[BUG/RISK/TEST/STYLE] file:line` findings, never edits. |
| `research` | **Research mode**: search -> fetch -> cross-check -> cite loop, plus `.roo/mcp.json` wiring the web tools (below). |
| `tdd` | Test-first rules injected into the built-in Code mode. |
| `adr` | All modes record architecture decisions to `docs/adr/` and consult them first. |

Write your own: copy a skill folder, edit `skill.json` (+ `mode.json` for a custom
mode), put files under `project/` mirroring where they land. Mode merging into
`.roomodes` and `mcpServers` merging into `.roo/mcp.json` are handled for you.

## Web research (local SearXNG + MCP)

`lai docker` now starts **SearXNG** on <http://localhost:8888> - a self-hosted
metasearch engine (no API keys, no cost, queries anonymized; note that searching
inherently contacts upstream engines). Two consumers:

1. **Agents**: the `research` skill installs `.roo/mcp.json` with two MCP servers -
   `searxng` (web search tool, via `npx -y mcp-searxng`) and `fetch` (URL -> readable
   markdown, via `uvx mcp-server-fetch`). Requirements: Node.js for npx, and
   [uv](https://docs.astral.sh/uv/) for uvx. Roo Code starts them on demand.
2. **Open WebUI**: web-augmented chat answers are pre-wired in the compose file
   (toggle the web-search switch in a chat).

## Prompt enhancement (zero build - it ships in Roo Code)

Roo Code's chat box has an **Enhance Prompt** action (the wand/sparkle icon) that
rewrites your prompt with the configured model before sending. Make it work well
with local models:

1. Roo Settings -> Support Prompts -> **Enhance Prompt**.
2. Replace the default template with
   [config/roo-enhance-prompt.md](../config/roo-enhance-prompt.md) - tuned for
   smaller local models (precision over prose) and pairs with Interview mode for
   genuinely ambiguous requests.
3. Optionally pin enhancement to the `coder` profile (fast) rather than `thinker`.

Workflow: *Enhance* fixes how you asked; *Interview mode* fixes what you actually
want; Code mode implements against the agreed spec.

## Git AI (`lai git`)

Terminal-first git assistance on the local endpoint (stack must be running):

```text
lai git review                 # review working tree vs HEAD
lai git review --base origin/main   # review a branch before the PR
lai git commit                 # generate a conventional commit message from staged changes
lai git commit --apply         # ...and commit with it (asks first)
lai git resolve                # AI-resolve merge conflicts (asks before writing each file)
lai git explain [ref]          # plain-language explanation of a commit or current changes
```

How `resolve` works and its safety rails: conflicts are parsed per hunk
(`<<<<<<< / ======= / >>>>>>>`, diff3 style supported), the model merges each hunk
with surrounding context, lai verifies **no conflict markers remain**, shows a
preview, and writes only after your per-file approval. Originals stay recoverable
via `git checkout --merge -- <file>`. Staging is left to you on purpose - always
read the result; on a 30B-class local model treat it as a strong first draft,
not a verdict.

Large diffs are reviewed per file automatically. The in-IDE equivalent of
`lai git review` is the `review` skill's Reviewer mode.
