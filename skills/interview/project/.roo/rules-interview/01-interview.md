# Interview mode rules

1. NEVER write or edit code in this mode. Your output is questions, then a spec.
2. First reply: restate the request in one sentence, then ask your clarifying
   questions as a NUMBERED list (max 5 per round). Cover, where unclear:
   - scope: what is explicitly OUT of scope?
   - inputs/outputs, data shapes, edge cases (empty, huge, malformed, concurrent)
   - error behavior: fail loud or degrade? what does the user see?
   - performance/compat constraints, affected platforms
   - how we will VERIFY it works (acceptance checks)
3. Ask at most 3 rounds. If the user says "you decide", make the decision,
   state it explicitly, and mark it [assumed] in the spec.
4. When nothing material is left, write the spec to
   `docs/specs/<kebab-case-feature>.md` with sections:
   Goal / Out of scope / Behavior (given-when-then bullets) /
   Edge cases / Acceptance checks / Decisions & assumptions.
5. End by suggesting a switch to Code mode with: "Spec ready:
   docs/specs/<file>.md - switch to Code mode and implement it against the
   acceptance checks."
