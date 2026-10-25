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

## Pick the workflow before starting work

Classify every task by **impact** and **attention needed**, then use the matching
workflow. If the human didn't say, pick one, state it in one line, and proceed.

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
