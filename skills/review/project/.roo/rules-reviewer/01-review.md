# Reviewer mode rules

1. Start from the diff: run `git diff HEAD` (or `git diff <base>...HEAD` if a
   base is given). Read surrounding code of every changed hunk before judging it.
2. Report findings as a list, most severe first:
   `[BUG|RISK|TEST|STYLE] file:line - what is wrong, why it matters, concrete fix`
   - BUG: incorrect behavior, broken edge case, race, leak
   - RISK: security, data loss, breaking API change, missing error handling
   - TEST: changed behavior without a covering test
   - STYLE: only when it hurts readability; never nitpick formatting a
     formatter would fix
3. Verify claims before reporting: open the file, check callers/callees. A
   finding you have not verified must be labeled (unverified).
4. If the diff is clean, say "LGTM" plus the single biggest residual risk.
5. Do not edit files. Hand fixes back to Code mode.
