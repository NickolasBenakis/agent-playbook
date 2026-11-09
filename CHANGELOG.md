# Changelog

Versions follow [semver](https://semver.org): a major version changes a rule
or a workflow's behavior, a minor version adds something you can opt into,
and a patch fixes a bug or the docs. Measured results live in
[docs/benchmarks.md](docs/benchmarks.md).

## 3.1.0 - 2026-11-09

- **Claude Code plugin.** Install with
  `/plugin install agent-playbook --marketplace NickolasBenakis/agent-playbook`
  (Claude Code 2.1.275+).
  A SessionStart hook loads `AGENTS.md` (plus a profile via
  `PLAYBOOK_PROFILE`), so nothing in `~/.claude` is edited. If `install.sh`
  has registered the same hooks and rules, the plugin's copies stand down
  so they don't run twice.
- **Eval suite** in `evals/`: run `claude plugin eval` to compare the
  playbook with the plain model on your machine. First run: +1.00 on a
  leak-tempting request, ties on the other three cases, and a rule 9 miss
  on the planted injection.
- **CI** runs the tests, an install smoke test and plugin validation on
  every push.
- README leads with the evidence, shows a session, and lists what each
  agent supports.

## 3.0.0 - 2026-11-09

- Secret guard hook: keeps `.env*`, keys and credentials out of the agent's
  context, commits and pushes.
- Verification gate: the Stop hook won't let a session end red, or with
  edited code that was never run.
- Rule 9 asks agents to report prompt injections they find.
- Parallel work only when each piece runs 10+ minutes of agent time; one
  agent otherwise (from benchmark round 5).
- `delegate` skill for writing subagent and child-thread briefs.
- Benchmark rounds 3–5 and the evidence section in the README.

## 2.0.0 - 2026-11-05

- Hooks for hard rules: git guard (push to default branch, force push,
  merge) and the Stop check.
- `playbook-reviewer`: a read-only subagent that reviews a diff against the
  acceptance criteria.
- ExecPlan-style record (Progress, Decision Log, Surprises, Follow-ups) for
  factory work.
- `audit` skill: finds wasted steps and rule misses in past sessions.
- Much shorter `AGENTS.md`, from benchmark rounds 1–2.

## 1.0.0 - 2026-10-25

- First release: `triage`, `fanout`, `factory` and `oneshot` workflows,
  profiles, and an installer for bb, Claude Code and Codex.
