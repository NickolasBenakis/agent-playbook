---
name: factory
description: Put a feature or epic on rails - plan, approve, build in an isolated worktree, self-review, get CI green, open a PR - with only two optional human checkpoints (plan and PR). Use for high-impact work with clear acceptance criteria, or when the human says "factory" or "auto".
---

# Factory

The software delivery lifecycle on rails. The human chooses how much attention
to pay: `checkpoints` (default: approve plan, review PR) or `auto` (approve
nothing, just get the PR, or merge if explicitly allowed).

## The record

One living record per task, kept current as you work: the PR description, or
`docs/plans/<slug>.md` when a plan file is warranted (see stage 1). It has
these sections, so anyone can see the state without reading the chat:

- **Goal and finish line**: what done means, as checks.
- **Progress**: timestamped steps done and next.
- **Decision Log**: each interpretation, cap, fallback or trade-off, with why.
- **Surprises**: what the code or tests revealed that the plan didn't expect.
- **Follow-ups**: things worth doing that are out of scope.
- **Verification**: the commands run and what a reviewer can run to check it.

## Stages

Keep the title as `[factory] <task> — <state>`, where state is one of
`planning`, `awaiting-approval`, `building`, `in-review`, `ci-red`,
`blocked: <reason>`, `pr-open: <url>`, `done`.

1. **planning**: read the code. If the spec is clear and the change fits in
   one PR, write a short plan (approach, files, finish line) into the record
   and move on. Write `docs/plans/<slug>.md` only when the spec is ambiguous,
   the work splits into several PRs (each ≤ ~1,200 changed lines), or the
   human asked to approve a plan.
2. **awaiting-approval** (skip in `auto`): show the task list and stop. Ask
   once. Accept edits to the plan, then continue.
3. **building**: per task, one branch `factory/<slug>-<n>` in an isolated
   worktree. Tasks run in order unless the parallel rule below applies;
   dependent tasks always run in order, each based on the previous branch.
4. **in-review**: before any human sees it, get an independent review: the
   `playbook-reviewer` subagent (give it the acceptance criteria and a diff
   file: `git diff <base>...HEAD > "$TMPDIR/review.diff"`), `/code-review`, or
   a fresh subagent with only the diff and the criteria. Fix confirmed
   findings; log rejected ones in the Decision Log.
5. **ci**: run the repo's test/lint/typecheck locally, push the branch, open a
   draft PR, and watch CI. On red: read the failing log, fix, push again. After
   3 failed attempts on the same failure, mark `blocked: ci <check name>`.
6. **pr-open**: mark the PR ready with the record as its description.
7. **done**: merge only if the human explicitly allowed it for this task;
   otherwise a green, ready PR is done.

## Parallel work

Run tasks in parallel only for 5+ independent tasks, tasks over ~30 minutes,
or when the human is away or asked for it. On 3 well-specified tasks,
parallel child threads cost ~2.4x the tokens and saved no time.

A child starts with none of your context. Its brief must include the goal and
finish line, the branch to base on, the existing code to reuse (helpers,
tables, patterns, test setup) and conventions to follow, and the instruction
to keep the record sections above.

In bb, one child thread per task:

```sh
bb thread spawn --parent-self --new-environment worktree --base-branch <branch> \
  --title "[factory] <task n> — building" --prompt-file task-n.md
bb thread wait <id>                     # or rely on parent notifications
bb thread show <id> --work-status       # PR + CI state
```

The `factory-sweep` automation (see `automations/`) nudges stuck threads and
red PRs so you don't have to poll.

## Rules

- Never block silently. If you need the human, the title says
  `blocked: <reason>` and your reply's first line says what you need.
- Prefer the repo's conventions over this skill when they conflict.
