# Refactoring rules (all modes)

1. A refactor changes structure, never behavior. If behavior must change,
   that is a separate task and a separate commit.
2. Before the first edit: confirm the test suite is green and covers the
   code you will move. Missing coverage? Add pinning tests FIRST.
3. Climb in small rungs: rename -> extract -> move -> inline, running the
   tests after every rung. Never a single giant diff.
4. Keep a mechanical-change log in the task summary: "renamed X->Y (N
   call sites), extracted Z" - reviewers verify shape, not re-read logic.
5. Update every caller, test, doc, and string reference - grep for the old
   names before declaring done (`git grep <oldname>` must return nothing).
6. If the ladder breaks midway, revert to the last green rung - never push
   through a red suite "to fix it later".
