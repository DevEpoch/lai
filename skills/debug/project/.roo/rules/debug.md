# Debugging rules (all modes)

1. REPRODUCE before you touch anything: a command or failing test that shows
   the bug. If you cannot reproduce it, say so - do not fix blind.
2. State your hypothesis out loud before each change: "I believe X because Y;
   if true, Z will show it." Then check Z (log, breakpoint print, assertion).
3. One variable at a time. Never combine a fix attempt with a refactor.
4. Fix the CAUSE, not the symptom: if a null check hides a bad state created
   earlier, find where the bad state is born.
5. Prove the fix with the exact repro from step 1, then run the full test
   command from AGENTS.md.
6. Record gotchas that will bite again in .lai/memory.md (dated bullet).
