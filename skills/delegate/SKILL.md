---
name: delegate
description: Decide whether to hand work to a subagent or child thread, and write the brief - what context to pass, what to leave out, and what to ask back. Use before launching any subagent, reviewer, or bb child thread.
---

# Delegate

A helper knows only what you put in the brief, and you get back only its
summary. Both handoffs lose detail. Delegate when that loss buys something:
time, a clean context, or an unbiased opinion.

## Pick the vehicle

| Need | Use | Why |
|---|---|---|
| Find something across many files | an Explore/read-only subagent | you keep its conclusion, not the file dumps |
| A second opinion on a diff | `playbook-reviewer` with the criteria and a diff file | it can't be anchored on your reasoning |
| Several independent reads or reviews | parallel subagents in one message | cheap; they finish together |
| Read-only work over 3+ separate areas (audit, survey) | one subagent per area, launched together | each reads deeper; you keep conclusions, not dumps |
| Independent builds totalling over ~15 min | a child thread per build, each in its own worktree | ~2 min start-up each, then they run at once |
| A small build, or one that shares files with yours | do it yourself | the handoff costs more than the work |

Two builds that touch the same files are one task: give them to one agent.

## The brief

Write it as if for a capable colleague who just walked in:

1. **Goal and finish line**, as checks ("`npm test` passes, `GET /x?page=2`
   returns the second page").
2. **Pointers, not payloads**: file paths with line ranges, the commands to
   run, the branch to start from. Don't paste file contents or the chat.
3. **What's settled**: decisions already made, approaches ruled out and why,
   so it doesn't redo them.
4. **What to reuse**: existing helpers, tables, patterns and test setup, by
   path. Children that weren't told reinvented existing code.
5. **Constraints**: scope limits, and the playbook rules that bite here
   (Decisions, secrets, no push to the default branch).
6. **What to return**: at most ~15 lines: the result, the evidence (command
   and its outcome), Decisions, open questions. Diffs as a branch or file
   path, not inline.

Never put secret values in a brief; name the variable.

For a verifier or reviewer, pass the task and the artifact only, not your
hypothesis or your reasons: a helper handed a conclusion tends to confirm it.

## When it comes back

A summary can be confidently wrong. Re-run the finish-line check yourself
before you report the work as done, and read the diff of anything you will
put your name on.
