# Security rules (all modes)

Apply this checklist whenever a change touches input handling, auth, secrets,
files, network, processes, or dependencies:

1. Inputs: never trust external input - validate type/length/range; treat
   paths (traversal), SQL (parameterize), HTML (escape), and shell args
   (no string concatenation into commands) as hostile.
2. Secrets: never hardcode or log credentials/tokens; config via env or the
   project's stated secret store; check nothing secret lands in git.
3. AuthZ: every new endpoint/command states WHO may call it; deny by default.
4. Dependencies: prefer stdlib; flag any new dependency with its
   maintenance/popularity status; pin versions.
5. Files & processes: least privilege - no chmod 777, no running as
   root/admin without a stated reason; temp files via the platform API.
6. Report findings as `[SEC] file:line - issue - fix` and refuse to mark a
   task done while a known [SEC] item is open.
