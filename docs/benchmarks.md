# Benchmarks

What the playbook does and doesn't buy, measured in bb on a real Next.js +
TypeScript repo. Both arms used the same model (Claude Opus 5.5, auto
permissions) and prompt; the control arm ran with the playbook uninstalled.
Every branch passed tests and typecheck. Reviewers scored each pair blind
(correctness, tests, scope, quality; 1–5 each).

| | Plain model | With playbook |
|---|---|---|
| Round 1: 5 small tasks | 5 min, score 91 | 6 min, score 90 |
| Round 2: 3 feature-sized tasks | 11 min, score 51 | 11 min (3 parallel child threads), score 51 |
| Tasks won (8 total, 1 tie) | 4 | 3 |
| Tokens | 1x | ~1.2x (round 1), ~2.4x (round 2) |
| Human interventions | 0 | 0 |

## What we learned

- **No quality or speed gain on well-specified tasks.** A strong model already
  plans, tests and stays in scope. Extra process only cost tokens.
- **Parallel child threads didn't save time** on 3 tasks: each child spent
  extra minutes on plans, review and worktree setup, and the slowest one set
  the total. They now need 5+ tasks, 30+ minute tasks, or an absent human.
- **Children reinvented existing code** (a new rate-limit table next to an
  existing limiter) because they started without the parent's context. Briefs
  now name the code to reuse.
- **A silent limit slipped in** (a data export capped at 200k rows). Caps,
  fallbacks and interpretations now go under "Decisions".
- **What did help**: the fresh-subagent review caught a real bug; the scope
  rule turned three out-of-scope problems into follow-ups instead of drive-by
  edits; one ambiguous spec was raised as a decision instead of guessed; status
  titles made the threads readable at a glance.

## Not yet measured

The playbook's actual claim is about human attention at scale, which these
rounds didn't test. A fair next round: 10+ tasks, some deliberately vague, the
human away for an hour. Measure time for the human to understand the state on
return, problems caught before human review, and rework needed after it.
