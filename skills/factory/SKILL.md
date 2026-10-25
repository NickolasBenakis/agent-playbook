---
name: factory
description: Put a feature or epic on rails - plan, approve, build in an isolated worktree, self-review, get CI green, open a PR - with only two optional human checkpoints (plan and PR). Use for high-impact work with clear acceptance criteria, or when the human says "factory" or "auto".
---

# Factory

The software delivery lifecycle on rails. The human chooses how much attention
to pay: `checkpoints` (default: approve plan, review PR) or `auto` (approve
nothing, just get the PR or merge if explicitly allowed).

## Stages

Update the session/thread title at each stage: `[factory] <task> — <stage>`.

1. **plan**: read the code, then write a plan file `docs/plans/<slug>.md` (or
   the PR description draft if the repo has no docs folder):
   - problem, approach, files to change, risks
   - task breakdown: each task = one PR, ≤ ~1,200 changed lines
   - finish line per task (tests to add or run, behavior to check)
2. **awaiting-approval** (skip in `auto`): show the plan's task list and stop.
   Ask once. Accept edits to the plan, then continue.
3. **building**: per task, one branch `factory/<slug>-<n>` in an isolated
   worktree. Independent tasks may run in parallel as subagents/child threads;
   dependent tasks run in order, each based on the previous branch.
4. **in-review**: before any human sees it, review your own diff adversarially:
   use `/code-review` if available, otherwise a fresh subagent given only the
   diff and the plan, asked to find correctness bugs. Fix confirmed findings.
5. **ci**: run the repo's test/lint/typecheck locally, push, open a draft PR,
   and watch CI. On red: read the failing log, fix, push again. After 3 failed
   attempts on the same failure, mark `blocked: ci <check name>` and stop.
6. **pr-open**: mark the PR ready. The description includes the task summary,
   the plan link, verification steps, and anything the reviewer must judge.
7. **done**: only merge if the human explicitly allowed merging for this
   task; otherwise the PR being green and ready is done.

## Rules

- Bugs found along the way that aren't part of the task: open a separate small
  PR or write them in the PR description under "Follow-ups". Don't widen scope.
- Never block silently. If you need the human, the title says
  `blocked: <reason>` and your reply's first line says what you need.
- Prefer the repo's conventions over this skill when they conflict.

## In bb

```sh
# one child thread per task, each in its own worktree
bb thread spawn --parent-self --new-environment worktree --base-branch main \
  --title "[factory] <task n> — building" --prompt-file task-n.md
bb thread show <id> --work-status     # PR + CI state
```

The `factory-sweep` automation (see `automations/` in the playbook repo)
nudges stuck threads and red PRs so you don't have to poll.
