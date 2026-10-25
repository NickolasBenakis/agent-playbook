---
name: oneshot
description: Low-attention workflow for experiments, internal tools, prototypes, and mechanical migrations. Define a machine-checkable finish line, then loop autonomously until it is met. Use when work is off the critical path and the model's judgment can stand in for the human's.
---

# Oneshot

Spend model intelligence instead of human attention. The human should be able
to start this and forget it until the result is ready.

## Steps

1. **Finish line first.** Write down, before any code, a check a script can
   evaluate: a test suite passes, a CLI command prints the expected output,
   CI is green, a parity check between old and new implementation passes.
   If no such check exists, the first task is building it.
2. **Scaffold** in a new branch or directory `oneshot/<slug>`, isolated from
   critical-path code.
3. **Loop**: implement → run the finish-line check → read failures → fix.
   Don't ask the human questions; make a reasonable choice and note it in
   `DECISIONS.md` in the working directory.
4. **Large mechanical work** (ports, migrations, codemods): build a small
   harness instead of brute-forcing it:
   - enumerate units of work in dependency order (e.g. walk the import graph)
   - hand each unit to a subagent with a self-contained brief
   - a check that fails if the new side falls behind the old (counts,
     parity tests)
5. **Stop conditions**: finish line met → report. Same failure 3 times, or the
   approach is clearly wrong → stop and report what you learned and what you'd
   try next. Never loop indefinitely.

## Tools

- Claude Code: `/loop` (self-paced) or a workflow script for fan-out.
- bb: a child thread in a worktree; or `bb automation create --in 1m ...` to
  run it off the main thread entirely.

## Done

One message: what was built, where it is, the finish-line result, and the
contents of `DECISIONS.md`.
