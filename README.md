# agent-playbook

One place for how your coding agents work, shared across machines, accounts,
and providers ([bb](https://getbb.app), Claude Code, Codex). Based on the
"minimize human attention" idea from Calvin Grunewald's
[My New Agentic Workflow](https://thebuildingmachine.substack.com/): pick a
workflow by impact × attention, then let agents carry the work.

| | Low attention | High attention |
|---|---|---|
| **High impact** | `/factory` | `/fanout` |
| **Low impact** | `/oneshot` | drop it or reshape it |

`/triage` sorts a task list into those cells.

## Layout

```
AGENTS.md                 shared rules every agent gets
profiles/<name>.md        per-context additions (personal, work)
profiles/<name>.local.md  private overlay, gitignored (secrets-free notes only)
skills/                   triage, fanout, factory, oneshot
automations/              factory-sweep: bb automation that unblocks threads
install.sh                links everything into bb / Claude Code / Codex
```

## Install on a machine

```sh
git clone https://github.com/NickolasBenakis/agent-playbook ~/agent-playbook && cd ~/agent-playbook
./install.sh personal      # or: ./install.sh work
```

This:
- builds `.generated/AGENTS.md` = `AGENTS.md` + the profile (+ `.local.md`)
- links it to `~/.bb/AGENTS.md` (all bb threads) and `~/.codex/AGENTS.md`
- adds an `@import` line to `~/.claude/CLAUDE.md` (keeps your existing content)
- symlinks each skill into `~/.agents/skills` and `~/.claude/skills`
  (bb picks skills up from there too)

Existing files are backed up as `*.pre-playbook.bak`. `./install.sh --uninstall`
reverses it. After `git pull`, re-run `./install.sh <profile>`; skill edits
apply immediately.

Install is per machine and per OS user, not per account: switching Claude/Codex
accounts (or rotating them with `bb pool`) keeps the same playbook.

## Factory sweep (optional)

A scheduled bb agent that nudges `[factory]`/`[fanout]` threads with red CI,
open review comments, or stalled work, and reports which threads need you.

```sh
bb project list --include-personal --json     # find a project id
automations/install-factory-sweep.sh <project-id> <model> ['*/30 9-19 * * 1-5'] [timezone]
```

## Using it at work

Keep this repo free of company details. Either fill `profiles/work.md` with
generic rules and put anything specific in `profiles/work.local.md` (not
committed), or fork into a private work repo. Check your employer's policy
before syncing personal config to a work machine.

## Contributing

Issues and PRs welcome, especially new workflow skills and adapters for other
agent tools.

## License

MIT, see [LICENSE](LICENSE).
