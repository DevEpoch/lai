# Browser verification rules (all modes)

1. After any UI-affecting change, VERIFY it in the real browser via the
   playwright tools: navigate to the dev server, perform the user flow,
   and check the result in the accessibility tree - "compiles" is not
   "works".
2. Verify the flow the change touches plus one adjacent flow (regressions
   hide next door). Report what you clicked and what you observed.
3. On failure, capture the page state (snapshot/console errors) BEFORE
   touching code again - debug from evidence.
4. Keep sessions short-lived; close the browser when done.
