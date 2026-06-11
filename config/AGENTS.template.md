# AGENTS.md

<!-- Copy this file to the root of each repo as AGENTS.md and fill it in.
     Roo Code, Continue, Aider, and OpenHands all read it automatically.
     Keep it short: every line here is in every agent prompt. -->

## Project

One paragraph: what this project is and who uses it.

## Build / test / run

```bash
# build:        e.g.  cargo build --workspace   |  go build ./...   |  npm run build
# test:         e.g.  cargo nextest run         |  go test ./...    |  npm test
# lint/format:  e.g.  cargo clippy && cargo fmt |  golangci-lint run
# run locally:  e.g.  cargo run -p server
```

Agents: always run the test command before declaring a task done.

## Conventions

- Error handling: <e.g. thiserror in libraries, anyhow at binary boundaries>
- Logging: <e.g. tracing, no println!>
- Naming / layout: <e.g. one crate per bounded context under crates/>
- Commits: <e.g. conventional commits, imperative mood>

## Architecture map

- `src/<area>/` - <what lives here>
- `crates/<name>/` - <what lives here>
- Durable project facts (gotchas, env quirks) live in `.lai/memory.md` - read it
  at task start, append dated bullets (see .roo/rules/memory.md).
- Decisions with rationale live in `docs/adr/` - read the relevant ADR before
  changing cross-cutting behavior; add a new ADR when you make such a change.

## Boundaries for agents

- Do not edit: <generated code paths, vendored deps, migrations older than X>
- Never commit secrets; config comes from <.env.example / vault / etc.>
