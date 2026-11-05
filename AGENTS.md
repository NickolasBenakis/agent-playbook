# Agent Playbook

These instructions apply to every agent session, whatever the provider or account.

## The one rule: minimize human attention

The human's attention is the scarce resource, not compute or tokens. Every
decision you make should reduce how often the human must look, remember, or
intervene. Concretely:

- Never make the human ask "what were you doing?" Keep status legible (see
  "Status reporting" below).
- Batch questions. Ask only what is genuinely the human's decision, all at once,
  with a recommended option.
- Fix what you can verify yourself (tests, lint, CI, review comments) before
  reporting. Don't hand back work that is red.
- When you finish, say what changed, how it was verified, and the one thing (if
  any) that needs the human.
- Don't add ceremony the model already does well. Strong models plan, test and
  stay in scope on their own; this playbook adds only what they skip: status,
  surfaced decisions, follow-ups and an independent review. Benchmarks on
  well-specified tasks showed no quality or speed gain from extra process,
  only extra tokens (see `docs/benchmarks.md`).

## Pick the workflow before starting work

Classify every task by **impact** and **attention needed**, then use the matching
workflow. If the human didn't say, pick one, state it in one line, and proceed.

Once you've picked a workflow, load and follow its skill (`factory`, `fanout`,
or `oneshot`) before starting the work; the table below is only the routing,
the skill is the procedure. Skip this only for trivial tasks (a one-line fix, a
question, a quick lookup), which you just do directly. Given several tasks at
once, load `triage` first.

| | Low attention | High attention |
|---|---|---|
| **High impact** | `factory` — pipeline with plan + PR checkpoints | `fanout` — human drives, subagents execute |
| **Low impact** | `oneshot` — harness/loop to a verifiable finish line | Don't do it, or downgrade to `oneshot` |

- **fanout**: core product work, ambiguous design, dogfooding sessions. The
  human stays in the main thread; each discrete fix or feature goes to a
  subagent that returns a PR or a diff.
- **factory**: normal feature work with clear acceptance criteria. Plan →
  approve → build in an isolated worktree → self-review → CI green → PR. The
  human looks only at the plan and the final PR (or neither, if they say "auto").
- **oneshot**: experiments, internal tools, migrations, anything off the critical
  path. Define a machine-checkable finish line (tests pass, CI green, script
  output matches), then loop until it is met without involving the human.

Use `/triage` when the classification is unclear.

### Parallel work

Default to doing tasks one after another in the current thread. Parallel child
threads cost about 2.4x the tokens and saved no time on a handful of tasks,
because the slowest child sets the pace. Go parallel only when at least one is
true:

- 5 or more independent tasks;
- a task that will take more than ~30 minutes, or needs its own branch and
  long-running checks;
- the human said they are stepping away, or asked for parallel work.

Then, in bb, spawn child threads
(`bb thread spawn --parent-self --new-environment worktree`) without asking
first; routing to `factory` or `fanout` counts as the request. Base every child
on the branch the human named, and wait with `bb thread wait` or parent
notifications instead of polling.

A child starts with none of your context. Its brief must name the existing
code to reuse (helpers, patterns, tables, test setup) and the conventions to
follow, so it extends the codebase instead of inventing a parallel version.

### Scope, decisions and review

- **Scope**: do exactly the task. If you notice something else worth fixing,
  don't change it; list it under "Follow-ups" in your report or PR description.
- **Decisions**: any choice the human might make differently goes under
  "Decisions" in your report: an ambiguous spec you interpreted, a cap or limit
  you added, a fallback, a dropped edge case. Never bury these in code.
- **Independent review**: before reporting non-trivial work, have a fresh
  subagent (or `/code-review`) review the diff for correctness bugs, especially
  on real-world inputs the tests don't cover. Fix confirmed findings. This is
  the step that most often catches real bugs; don't skip it.

## Status reporting

Anyone glancing at a session should know its state in five seconds:

- Keep the thread/session title in the form `[workflow] <task> — <state>`, where
  state is one of `planning`, `awaiting-approval`, `building`, `in-review`,
  `ci-red`, `blocked: <reason>`, `pr-open: <url>`, `done`.
- One task → one branch → one PR. Put the task summary and verification steps
  in the PR description, so the PR is the record, not the chat.
- When blocked on the human, say so in the first line of your reply, not at the end.

## Engineering defaults

- Work in an isolated worktree/branch for anything beyond a trivial edit.
- Keep PRs reviewable: one concern each, roughly 600–1,200 changed lines at most.
- Run the project's own test/lint/typecheck commands before declaring done.
- Never push to the default branch, force-push shared branches, merge, deploy,
  or touch production data unless the human explicitly said to for this task.
