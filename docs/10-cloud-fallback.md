# Cloud Fallback (optional, explicit, minimal)

Local models are the default for everything - that is the point of this project.
But sometimes one task genuinely exceeds local quality (a gnarly architecture
review, a huge refactor plan). For those, lai supports **explicit-use** cloud
fallbacks:

```text
lai cloud add openrouter      # or: openai | anthropic   (key prompted or --key)
lai cloud list                # what is configured + usage examples
lai cloud remove openai
```

Keys live in `state/secrets.json` - gitignored, never committed, never sent
anywhere except the provider you chose.

## How they are used (and not used)

Cloud runs ONLY when you write a prefixed model id - never by default, never
silently:

```text
lai chat --model or:qwen/qwen3-coder-480b     # OpenRouter
/model an:claude-sonnet-4-6                   # switch mid-chat (Anthropic)
lai git review --base origin/main --model oa:gpt-5
lai bench --quality --model or:...            # score a cloud model vs local
```

`lai choices` shows a hint line when keys exist, so suggestions stay aware of
the fallback without ever auto-selecting it.

## Minimizing spend, maximizing value

- Keep autocomplete, embeddings, RAG, and routine agent loops local - they are
  high-volume and local handles them well. Cloud is for **single, hard,
  judgment-heavy calls** (a review of a big diff, a plan for a thorny feature).
- `lai bench --quality --model or:<x>` tells you whether a cloud model
  actually beats your local coder on the suite before you pay for habit.
- OpenRouter is the best first key: one key, every major model, and it serves
  many open models at near-zero cost - good for A/B-ing successors before
  adding them to the catalog.
- IDE: Roo Code and Continue support OpenRouter/OpenAI/Anthropic providers
  natively - add a second profile there with the same key if you want cloud
  in the IDE too; keep the local profile as the default one.
