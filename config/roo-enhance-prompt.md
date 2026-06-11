Rewrite the user's prompt below into a sharper instruction for a LOCAL coding
model (smaller than cloud frontier models - it needs precision, not prose):

- If the prompt is not in English, translate it to English first (keep code
  identifiers, paths, and error messages exactly as written).
- State the concrete goal in the first sentence.
- Name the exact files/functions/symbols involved if they can be inferred.
- List constraints explicitly (language version, style, what must NOT change).
- Specify the verification step ("done when <test/command> passes").
- Remove pleasantries and hedging; keep every technical detail.
- If the request is genuinely ambiguous, keep it short and ADD one line:
  "Open questions:" followed by the 1-3 questions that block implementation
  (the user may switch to Interview mode to settle them).

Reply with ONLY the improved prompt - no commentary, no quotes.

User's prompt:

${userInput}
