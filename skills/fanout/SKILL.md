---
name: fanout
description: Human-in-the-loop workflow for high-impact, high-attention work. The main session stays with the human and delegates each discrete fix or feature to a subagent that returns a PR or verified diff. Use for core product work and dogfooding sessions.
---

# Fanout

The human drives; you dispatch. The main session is a control room, not a
workbench: keep its context for decisions and coordination, and push execution
into subagents.

## How to run it

1. As the human dumps work ("this is broken", "add X", "make Y faster"), turn
   each into a self-contained brief:
   - goal and acceptance criteria
   - relevant files, commands, and what's already ruled out
   - branch name `fanout/<short-slug>`
   - finish line: tests/typecheck pass, PR opened (or diff ready if no remote)
2. Launch one subagent per independent item, in parallel, in an isolated
   worktree when the tool supports it. Items that touch the same files go to
   one subagent, sequentially.
3. Keep a running board in your replies, updated whenever it changes:

   | Item | Agent | State | PR |
   |------|-------|-------|----|

4. When a subagent returns, verify its claim (open the diff, check the test
   output) before marking it done. If it failed, re-brief once with what went
   wrong; on a second failure, bring it to the human.
5. Let the human keep going: "fix this with a subagent" should be all it takes.
   Don't ask for confirmation on items that are clearly scoped.

## In bb

Child threads work as subagents and show up in the sidebar:

```sh
bb thread spawn --parent-self --new-environment worktree \
  --title "[fanout] <task> — building" --prompt-file brief.md
bb thread wait <id>            # or rely on parent notifications
```

## Done

Report the board, with every row either `pr-open`, `done`, or `needs-you: <why>`.
