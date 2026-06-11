# Security scan rules (all modes)

1. Before declaring done on any change touching inputs, auth, files,
   network, queries, or dependencies: scan the changed files with the
   semgrep tool.
2. Triage every finding: fix it, or state explicitly why it is a false
   positive in this context (one sentence, in the summary).
3. Never silence a rule to make the scan pass; narrow the code instead.
4. A task with an open, unexplained finding is NOT done.
