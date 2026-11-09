#!/usr/bin/env python3
"""Claude Code SessionStart hook (plugin install only): load the playbook rules.

A plugin can't add to CLAUDE.md, so this hook hands AGENTS.md to the session
as additional context. Set PLAYBOOK_PROFILE=<name> to append
profiles/<name>.md and profiles/<name>.local.md, as install.sh does.

It prints nothing when install.sh already imports the rules into CLAUDE.md,
so they never load twice.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MARKER = "# agent-playbook (managed by"


def read(path):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return ""


def main():
    config = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")
    if MARKER in read(os.path.join(config, "CLAUDE.md")):
        return 0
    parts = [read(os.path.join(ROOT, "AGENTS.md"))]
    profile = os.path.basename(os.environ.get("PLAYBOOK_PROFILE", "").strip())
    if profile:
        parts.append(read(os.path.join(ROOT, "profiles", profile + ".md")))
        parts.append(read(os.path.join(ROOT, "profiles", profile + ".local.md")))
    text = "\n\n".join(p for p in parts if p)
    if not text:
        return 0
    json.dump({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}}, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
