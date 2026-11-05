# Public agentic playbooks: what to borrow

Survey from November 2026, done after our two benchmark rounds
([benchmarks.md](../benchmarks.md)) showed the playbook gave no quality or
speed gain over plain Claude Opus 5.5 on well-specified tasks. The question:
what do widely used public playbooks do that we could adopt or combine?

Star counts were read from each repo page where possible. Those marked
"third-party" come from aggregator sites that disagree and lag the live repo,
so treat them as rough.

## Candidates

| Playbook | Adoption | What it is | The idea worth borrowing |
|---|---|---|---|
| [Superpowers](https://github.com/obra/superpowers) | ~313k stars, MIT | Skill library: brainstorm → worktree → plan → one fresh subagent per task with review → test-first → finish branch. Claude Code, Codex, Cursor, Gemini CLI, OpenCode. | `diagnosing-superpowers`: a skill that reads a session transcript and finds skill misfires and wasted effort. Self-audit fits our legibility angle. |
| [GitHub Spec Kit](https://github.com/github/spec-kit) | ~148k stars, MIT | Spec-driven: constitution → specify → plan → tasks → implement → `/speckit-converge` | The converge loop: implement and check against the spec until it reports "Converged". A machine-checkable finish line. |
| [OpenSpec](https://github.com/Fission-AI/OpenSpec) | ~74k stars, MIT | Lighter spec layer: one folder per change (proposal, spec deltas, design, tasks), archived when done | A durable per-change record of decisions and follow-ups that doesn't depend on the chat. |
| [BMAD Method](https://github.com/bmad-code-org/BMAD-METHOD) | ~55k stars, MIT (name is trademarked) | Agile role agents (PM, architect, developer, test architect) | Right-sized process: small changes go straight to build, only complex work gets planning. |
| [Claude Code best practices](https://code.claude.com/docs/en/best-practices) | Official (Anthropic) | Short CLAUDE.md, skills for procedures, hooks for hard rules, fresh-subagent review | "If something has to happen every time, make it a hook." Review against the spec and tell the reviewer to skip style, because a reviewer "will always find *something*". |
| [Codex ExecPlans](https://developers.openai.com/cookbook/articles/codex_exec_plans) | Official cookbook (OpenAI), now marked archived | A living plan for multi-hour runs | Required living sections: Progress, Surprises & Discoveries, Decision Log, Outcomes & Retrospective. |
| [HumanLayer RPI](https://github.com/humanlayer/humanlayer) | 12.8k stars, Apache-2.0 | Research → Plan → Implement, now a plugin in their monorepo | Write research and plan to files, then start each phase with a fresh context. |
| [Everything Claude Code](https://github.com/affaan-m/everything-claude-code) | ~150–200k stars (third-party), MIT | A full config collection: agents, hooks, rules | Hook recipes only; the rest is heavy. |
| [AGENTS.md](https://agents.md) and [Gloaguen et al., arXiv 2602.11988](https://arxiv.org/abs/2602.11988) | Standard used by 60k+ repos (secondary figure); ICLR 2026 paper | Cross-tool instruction file, and a study of whether such files help | Keep it tiny: only what's non-standard, and add a line each time the agent makes a mistake. |

Also seen: [anthropics/skills](https://github.com/anthropics/skills) (a
reference for skill format), Claude Squad and Vibe Kanban (parallel worktree
tools).

## Evidence

- **Context files**: Gloaguen et al. found repository context files gave no
  gain or a slight loss in task success while raising cost by over 20%.
  Minimal, human-written files did better than long or generated ones.
- **Short rules on ambiguous tasks**: an Agentic AI Foundation post (July 2026;
  one repo, Copilot CLI, five runs per condition) found a 12-line AGENTS.md cut
  time by ~27% and diff size by ~26% on an ambiguous task, mainly by removing
  the wandering seen in 2 of 5 runs without it. It warns that single-run
  comparisons mislead.
- **Subagents**: Anthropic notes subagents give "parallelism or a fresh pair
  of eyes… but not a smarter answer", which matches our round 2 result.
- **Heavy spec or role workflows**: no controlled study found showing quality
  gains on strong models; reports are anecdotal and point to extra tokens and
  time.

## What we adopted

In priority order, all in the `playbook-v2` change:

1. **Hooks for hard rules** (Claude Code best practices): a Stop hook that
   won't let a session finish while the repo's own check is red, and a git
   guard that asks the human before a push to the default branch, a force push
   or a PR merge. See `hooks/`.
2. **A spec-anchored, read-only reviewer** (Claude Code best practices): the
   `playbook-reviewer` subagent gets read-only tools, reviews the diff against
   the acceptance criteria, and ignores style. See `agents/`.
3. **ExecPlan sections as the status record** (Codex): factory PRs and plan
   files carry Progress, Decision Log, Surprises and Follow-ups.
4. **A much shorter AGENTS.md** (Gloaguen et al., AGENTS.md guidance): the
   always-loaded rules are cut to the essentials; procedures moved into skills.
5. **A transcript-audit skill** (Superpowers): `audit` reads past sessions and
   reports wasted steps and rule misses, so the playbook keeps being measured.

Not adopted: full spec-driven systems (Spec Kit, BMAD, Everything Claude
Code). They add the process our benchmark showed doesn't pay off with a strong
model. The converge loop is already covered by oneshot's finish line.

## Licenses

- Everything in the table is MIT or Apache-2.0; we borrow ideas, not code.
- Claude Squad is AGPL-3.0: don't vendor its code.
- "BMad" and "BMAD-METHOD" are trademarks: don't use the name.
- In anthropics/skills, the docx, pdf, pptx and xlsx skills are
  source-available, not open source.
- Vibe Kanban's company shut down in April 2026; it is now community-maintained
  (Apache-2.0).
