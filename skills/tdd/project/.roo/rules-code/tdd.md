# TDD rules (Code mode)

1. For any behavior change: write or update the failing test FIRST, show it
   fail, then implement until it passes. No test, no merge.
2. Run the project's test command (see AGENTS.md) before declaring any task
   done, and paste the actual result - never claim green without running.
3. Bug fix = regression test that reproduces the bug, then the fix.
4. Tests assert behavior, not implementation details; one logical assertion
   focus per test; name tests after the behavior they pin.
5. If a test is impractical (hardware, network), say so explicitly and state
   how the change was verified instead.
