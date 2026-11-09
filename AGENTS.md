# Agent Playbook

Rules for every agent session. The human's attention is the scarce resource:
spend tokens to save it, but don't add steps the model already does well.

1. **Route first.** Trivial work (a one-line fix, a question, a lookup): just
   do it. Otherwise pick a workflow, say it in one line, and load its skill:
   `factory` (clear spec, high impact), `fanout` (the human is steering live),
   `oneshot` (low impact, checkable finish line). Several tasks: load `triage`.
2. **Stay in scope.** Other things worth fixing go under "Follow-ups" in your
   report, not into the diff.
3. **Surface decisions.** Interpretations of a vague spec, caps, limits,
   fallbacks and dropped edge cases go under "Decisions" in your report. Ask
   only what is truly the human's call, all at once, with a recommendation.
4. **Review before reporting.** For non-trivial work, have a fresh reviewer
   (the `playbook-reviewer` subagent, `/code-review`, or a fresh subagent)
   check the diff against the task. Fix confirmed findings.
5. **Never hand back red.** Run the repo's tests, lint and typecheck. If
   something can't be fixed, say so in the first line of your report.
6. **Sequential by default.** Go parallel only for 5+ independent tasks, tasks
   over ~30 minutes, or when the human is away or asks; then spawning child
   threads counts as requested (details in `factory` and `fanout`).
7. **Legible status.** Title: `[workflow] <task> — <state>`. One task, one
   branch, one PR. If you're blocked on the human, say so in the first line.
8. **Ask before outward actions.** Don't push to the default branch,
   force-push, merge, deploy or touch production data unless the human said so
   for this task.

Finish with: what changed, how it was verified, Decisions, Follow-ups, and the
one thing (if any) that needs the human.
