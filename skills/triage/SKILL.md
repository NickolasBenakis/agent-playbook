---
name: triage
description: Classify a task or backlog by impact and required human attention, and route each item to the fanout, factory, or oneshot workflow. Use when starting work, when handed a list of tasks, or when unsure which workflow fits.
---

# Triage

Goal: decide, for each item, how much human attention it deserves, and route it.

## Steps

1. List the items. If the human gave a single task, the list has one entry.
2. For each item, estimate quickly (t-shirt sizes, don't over-think):
   - **Impact**: low / high. High = user-facing, revenue, core architecture,
     or on someone's critical path.
   - **Attention**: low / high. High = ambiguous requirements, taste or
     design decisions, risky to get wrong, or needs human domain knowledge.
3. Route:
   - high impact + high attention → `fanout`
   - high impact + low attention → `factory`
   - low impact + low attention → `oneshot`
   - low impact + high attention → recommend dropping it or reshaping it
     until it's low attention, then `oneshot`
4. Output a table, and nothing else unless asked:

   | # | Task | Impact | Attention | Workflow | Finish line |
   |---|------|--------|-----------|----------|-------------|

   "Finish line" is the concrete, checkable definition of done (e.g. "PR open,
   CI green, e2e test for checkout passes").
5. Ask once: "Start these as routed?" If the human says yes, or already
   said to proceed, start each item with its workflow skill (`/factory`,
   `/fanout`, `/oneshot`).
