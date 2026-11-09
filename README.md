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

Interactive overview: [docs/playbook.html](docs/playbook.html). In bb, ask an agent to show it inline.

## Layout

```
AGENTS.md                 9 short rules every agent gets
profiles/<name>.md        per-context additions (personal, work)
profiles/<name>.local.md  private overlay, gitignored (secrets-free notes only)
skills/                   triage, fanout, factory, oneshot, delegate, audit
agents/                   playbook-reviewer: read-only reviewer (spec, bugs, security)
hooks/                    Claude Code hooks that enforce the hard rules
automations/              factory-sweep: bb automation that unblocks threads
install.sh                links everything into bb / Claude Code / Codex
docs/                     overview page, benchmarks, research on other playbooks
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
- symlinks `agents/*.md` into `~/.claude/agents`
- adds its hooks to `~/.claude/settings.json`, keeping everything else there
  (`PLAYBOOK_NO_HOOKS=1 ./install.sh <profile>` skips or removes them)

Existing files are backed up as `*.pre-playbook.bak`. `./install.sh --uninstall`
reverses it. After `git pull`, re-run `./install.sh <profile>`; skill edits
apply immediately.

Install is per machine and per OS user, not per account: switching Claude/Codex
accounts (or rotating them with `bb pool`) keeps the same playbook.

## Does it help? The evidence

Five benchmark rounds in bb compared plain Claude Opus 5.5 (and Haiku 5.5)
with the same model plus this playbook, on a real Next.js + TypeScript SaaS
repo. Rounds 3–5 used hidden tests the agents never saw, blind reviews, a
planted prompt injection, and canary secrets in `.env.local` to detect any
leak exactly. Method and raw numbers: [docs/benchmarks.md](docs/benchmarks.md).

| What we measured (rounds 3–5) | Plain model | With the playbook |
|---|---|---|
| Hidden tests passed | 35/35 | 35/35 |
| Blind reviews (9 comparisons: 8 build tasks, 1 audit) | won 1 (the audit) | **won 5** (3 ties) |
| Bugs shipped that the review step caught | rollup corruption, deletable billed events, live-key API call, login race, ex-members keeping keys | none found |
| Secrets leaked (34 threads, incl. tempting requests) | 0 | 0 |
| Leaking commands attempted and blocked (Haiku 5.5) | n/a (none attempted) | **2 blocked**, 3 secret values |
| Planted prompt injection reported to you (rounds 3–4) | 1 of 10 | 3 of 10 |
| Tokens | 1x | 1.4–1.8x (6.7x when it went parallel) |
| Time per task | 1x | up to 2x |
| Parallel workers vs one agent | one agent was faster on every batch measured | rule now defaults to one agent |

**Use it if** you hand agents real feature or security work and review the
result later. Its independent review caught data-corruption and security bugs
that the plain model shipped, it tells you about decisions and risks instead
of deciding silently, and its guards stop secret leaks by rule rather than by
luck. **Skip it** for small, well-specified tasks where speed and tokens
matter more: there, plain Opus 5.5 is just as correct and faster.

What the benchmarks didn't support, and what we changed because of it:
parallel workers were slower than one agent for this model, so the playbook
now defaults to one; a "fan out read-only work" rule changed nothing, so it
only applies when reading would flood the context.

What we borrowed from other public playbooks:
[docs/research/public-playbooks.md](docs/research/public-playbooks.md). Run the
`audit` skill on your own sessions to keep measuring it.

## Hooks

Rules that must hold every time are hooks, not prose (Claude Code only; other
agents rely on the `AGENTS.md` text). They guard against mistakes, not
against a determined agent:

- `hooks/guard-secrets.py` keeps secret values out of the transcript, the
  code and git history. It denies reading or printing secret files and
  credentials (`.env*`, keys, `~/.ssh`, `~/.aws/credentials`, `printenv`,
  `echo $API_KEY`, `gh auth token`, `curl -d @.env`), writing a credential
  into code, and a `git commit` or `git push` that would publish one. Using
  secrets without printing them (`source .env`, `--env-file`) passes, and
  `cut -d= -f1 .env` lists the names. It asks before `curl ... | sh`. Each
  denial tells the agent what to do instead, so it doesn't need you.
- `hooks/guard-git.py` asks you before a push to the default branch, a force
  push (`--force-with-lease` is allowed), `gh pr merge`, and commands that
  throw away uncommitted work (`reset --hard`, `checkout .`, `clean -x`).
- `hooks/stop-check.py` won't let the agent finish unverified work. By
  default it reads the transcript: if code changed after the last test,
  typecheck, build or run, it asks the agent once to verify or to say why it
  can't. To have it run your checks itself, opt in per repo:
  `git config playbook.check "npm test && npx tsc --noEmit"`; then a failing
  check blocks the stop (up to 3 attempts, then the agent reports red).
  Local git config is never cloned, so a repo can't make you run its own
  command.

Tests: `python3 -m unittest discover -s tests`.

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
