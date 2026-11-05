---
name: audit
description: Audit past agent sessions for wasted effort and playbook misfires - steps that added nothing, loops, rules that were skipped or followed for no benefit - and propose concrete rule changes. Use when the human asks to audit, review or measure a session, a thread, or the playbook itself.
---

# Audit

The playbook is only worth what it measurably saves. This skill keeps
measuring it, one real session at a time.

## Find the transcripts

- **Claude Code**: `~/.claude/projects/<cwd with / replaced by ->/<session-id>.jsonl`.
  The newest files are the most recent sessions.
  Subagent transcripts sit next to it in `<session-id>/subagents/`; the
  summary script adds their tokens.
- **bb**: `bb thread output <id>` for the final report, `bb thread context <id>`
  for usage; Claude Code threads also have a `.jsonl` as above.
- **Codex**: `~/.codex/sessions/`.

Don't read raw transcripts whole. For Claude Code, start with:

```sh
python3 ~/.claude/skills/audit/summarize.py <session.jsonl> [...]
```

It prints duration, tokens, tool calls, skills, subagents, child threads,
failed tool calls and commands repeated 3+ times. Then read only the parts of
the transcript those numbers point to.

## What to look for

1. **Ceremony without payoff**: plan files, triage tables, child threads or
   reviews that didn't change the outcome. Compare their token cost with what
   they caught.
2. **Loops**: the same command or edit repeated, failures retried unchanged.
3. **Rule misses**: work reported red; decisions made silently (caps,
   fallbacks, interpretations not listed under "Decisions"); scope creep;
   status title not kept up to date; questions asked one at a time.
4. **Human attention spent**: every point where the human had to step in,
   repeat themselves or ask "what happened?". This is the main cost the
   playbook exists to cut.
5. **What worked**: steps that caught a real problem. Keep these.

## Output

A table, then at most 3 proposed changes to `AGENTS.md` or a skill, each with
the evidence (session, step) that motivates it:

| Finding | Evidence | Cost | Proposed change |
|---|---|---|---|

Propose, don't edit: the human decides which rules change. Prefer removing a
rule over adding one.
