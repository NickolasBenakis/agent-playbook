#!/usr/bin/env python3
"""Summarize a Claude Code session transcript (.jsonl) for the audit skill.

Usage: summarize.py <session.jsonl> [more.jsonl ...]

Prints, per file: wall clock, model turns, tokens (the session's own and its
subagents', read from <session>/subagents/), tool calls by name, skills and
subagents used, child threads spawned, failed tool calls, and commands
repeated 3+ times (a sign of a loop). The skill reads this instead of the
raw transcript, which is usually too large to read whole.
"""
import collections
import glob
import json
import os
import sys
from datetime import datetime


def ts(s):
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def subagent_usage(path):
    """Token totals across <session>/subagents/agent-*.jsonl, deduped per request."""
    files = glob.glob(os.path.join(os.path.splitext(path)[0], "subagents", "*.jsonl"))
    usage = {}
    for f in files:
        for line in open(f, errors="replace"):
            try:
                d = json.loads(line)
            except ValueError:
                continue
            msg = d.get("message") or {}
            rid = d.get("requestId") or msg.get("id")
            if d.get("type") == "assistant" and rid and msg.get("usage"):
                usage[(f, rid)] = msg["usage"]
    if not files:
        return None
    t = lambda k: sum((u.get(k) or 0) for u in usage.values())
    return len(files), t("input_tokens") + t("cache_creation_input_tokens"), t("cache_read_input_tokens"), t("output_tokens")


def summarize(path):
    requests = {}
    tools = collections.Counter()
    skills, agents, spawns, errors = [], [], [], []
    commands = collections.Counter()
    tool_names = {}
    first = last = None
    user_prompts = 0

    for line in open(path, errors="replace"):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        t = ts(d.get("timestamp", "")) if d.get("timestamp") else None
        if t:
            first = first or t
            last = t
        msg = d.get("message") or {}
        content = msg.get("content")
        if d.get("type") == "assistant":
            rid = d.get("requestId") or msg.get("id")
            if rid and msg.get("usage"):
                requests[rid] = msg["usage"]
            for block in content or []:
                if block.get("type") != "tool_use":
                    continue
                name, inp = block.get("name"), block.get("input") or {}
                tools[name] += 1
                tool_names[block.get("id")] = name
                if name == "Skill":
                    skills.append(inp.get("skill"))
                elif name in ("Agent", "Task"):
                    agents.append(inp.get("description") or inp.get("subagent_type"))
                elif name == "Bash":
                    cmd = " ".join((inp.get("command") or "").split())
                    commands[cmd[:160]] += 1
                    if "bb thread spawn" in cmd:
                        spawns.append(cmd[:120])
        elif d.get("type") == "user" and not d.get("isMeta"):
            if isinstance(content, str):
                user_prompts += 1
            for block in content if isinstance(content, list) else []:
                if block.get("type") == "tool_result" and block.get("is_error"):
                    text = block.get("content")
                    text = text if isinstance(text, str) else json.dumps(text)
                    errors.append(f"{tool_names.get(block.get('tool_use_id'), '?')}: {' '.join(text.split())[:140]}")
                elif block.get("type") == "text":
                    user_prompts += 1

    def total(key):
        return sum((u.get(key) or 0) for u in requests.values())

    fresh = total("input_tokens") + total("cache_creation_input_tokens")
    out = [f"## {path}"]
    if first and last:
        out.append(f"wall clock: {int((last - first).total_seconds() // 60)} min (includes idle time)")
    out.append(f"user prompts: {user_prompts}, model requests: {len(requests)}")
    out.append(f"tokens: {fresh:,} new input, {total('cache_read_input_tokens'):,} cached input, {total('output_tokens'):,} output")
    sub = subagent_usage(path)
    if sub:
        out.append(f"subagent tokens ({sub[0]} transcripts): {sub[1]:,} new input, {sub[2]:,} cached input, {sub[3]:,} output")
    out.append("tool calls: " + ", ".join(f"{n} {c}" for n, c in tools.most_common()))
    if skills:
        out.append("skills: " + ", ".join(collections.Counter(skills)))
    if agents:
        out.append(f"subagents ({len(agents)}): " + "; ".join(a or "?" for a in agents[:10]))
    if spawns:
        out.append(f"child threads spawned: {len(spawns)}")
    if errors:
        out.append(f"failed tool calls ({len(errors)}):")
        out += [f"  - {e}" for e in errors[:15]]
    repeated = [(c, n) for c, n in commands.most_common() if n >= 3]
    if repeated:
        out.append("commands run 3+ times:")
        out += [f"  - {n}x {c}" for c, n in repeated[:10]]
    return "\n".join(out)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    print("\n\n".join(summarize(p) for p in sys.argv[1:]))
