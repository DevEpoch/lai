# Docs-first rules (all modes)

1. For questions about a library, framework, or internal system this project
   depends on, FIRST run (via the command tool):
   `python <lai-home>/lai.py docs search "<your question>"`
   (lai-home is where lai.py lives; ask the user once and remember it in
   .lai/memory.md if unknown).
2. Quote what the docs say and cite the source line the tool prints. If the
   index has nothing, say "not in the indexed docs" - then reason from
   general knowledge, clearly labeled as such.
3. When the user shares a useful doc URL or file, suggest indexing it:
   `lai docs add <url-or-file>` - so the whole team's agents benefit.
4. Never invent API signatures. Verify against the docs index or the
   installed package source before writing code against an API.
