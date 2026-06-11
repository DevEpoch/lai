# Project memory rules (all modes)

1. At the start of a non-trivial task, read `.lai/memory.md` - it holds
   project facts that are NOT in the code (why things are the way they are,
   known gotchas, environment quirks, flaky areas).
2. When you discover or decide something durable, append one dated bullet:
   `- YYYY-MM-DD: <fact>. (why: <one clause>)`
   Examples worth recording: "CI runner needs JAVA_HOME set", "vendor API
   rejects parallel calls", "team chose pnpm over npm". Examples NOT worth
   recording: anything visible in the code, one-off task details.
3. Keep it under ~150 lines: when adding, prune bullets that became code,
   docs/adr entries, or stale. Architecture decisions go to `docs/adr/`
   (see the adr rules) - memory.md only points at them.
4. Never store secrets in memory.md - it is committed.
