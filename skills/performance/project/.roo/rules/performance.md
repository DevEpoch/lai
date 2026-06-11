# Performance rules (all modes)

1. Never optimize without a measurement. First produce a number (profiler,
   timer, benchmark, EXPLAIN) showing WHERE time/memory goes.
2. State the budget before changing code: "this path must run in < X ms /
   alloc < Y MB" - from the task, AGENTS.md, or ask once.
3. Optimize the biggest measured cost first; one optimization per change.
4. Prove every win: before/after numbers on the same input, included in the
   summary. No numbers = revert.
5. Prefer algorithmic wins (complexity, batching, caching, indexes) over
   micro-tweaks; never trade readability for an unmeasured gain.
6. Leave the measurement behind as a test or script so the win cannot
   silently regress.
