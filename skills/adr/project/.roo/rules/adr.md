# ADR rules (all modes)

1. Before changing cross-cutting behavior (storage, auth, public APIs, build,
   dependencies, concurrency model), check `docs/adr/` for an existing
   decision. Do not silently contradict one - flag the conflict instead.
2. When you make such a decision (or the user makes one in chat), record it:
   `docs/adr/NNNN-short-title.md` with: Context / Decision / Alternatives
   considered / Consequences. Number sequentially, keep it under a page.
3. Decisions live in ADRs, not in chat history. If it matters next month,
   write it down now.
