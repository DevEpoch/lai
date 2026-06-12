# 11 - The lai agent: code like Claude Code, fully local

`lai` has an agent loop: the model reads, searches, and edits your
project files itself, picks the right skill for each request, and runs
your tests - on YOUR machine, with nothing leaving it.

## Three ways in, one engine

| Surface | How |
|---|---|
| VS Code | open the sidebar chat, or `lai: Open Chat as Editor Tab` for the Claude-Code-style panel beside your code |
| Terminal | `lai agent "review this project and list problems"` or just `lai` (interactive session - questions go to the agent) |
| Dashboard | `POST /api/agent` (used by the UI) |

Ask things like: "review the entire project", "write documentation for
this folder", "find the problems in the error handling", "rename X to Y
everywhere".

## What happens under the hood

1. **Skill auto-match** - your request is scored against installed
   skills (built-in + the project's `.lai/skills`); the winner's rules
   ride along in the system prompt. You see `* skill: review` in chat.
2. **Tool loop** - the model uses tools when it decides it needs them
   (you see every call): `list_files`, `read_file`, `search`,
   `edit_file` (exact-text replace - the safe way to change code),
   `write_file` (new files), `run_check` (gate or tests). Up to 8 steps
   per request, every path confined to the project root.
3. **Any model works** - tool calls travel in fenced ```` ```tool ````
   JSON blocks, so no special function-calling template is needed.

## Task lists: "do all of these one by one"

Write a markdown checklist and say so - in any chat surface, in
English, Persian, or Arabic:

```
do all the tasks in plan.md
```

or run it directly:

```
lai tasks plan.md
```

The runner is deterministic Python, not model willpower: one FRESH
agent run per task (clean context every time), your tests run after
each task, one repair attempt if they go red - then an honest stop.
Each finished task is ticked `- [x]` in the file itself, live, so
progress survives interruption: rerun and it resumes from the first
unchecked box. Numbered and bullet lists work too.

## Honest differences from Claude Code / Codex

- Replies arrive per agent step, not per token (chunked streaming).
- No arbitrary shell execution - the agent can run your gate and your
  tests, nothing else. Deliberate: there is no approval UI yet.
- Quality per step is your local model's. The harness guarantees
  order, verification, confinement, and honest stops - not brilliance.
  Qwen3-Coder-30B-class models drive the loop well; tiny models don't.
