#!/usr/bin/env python3
"""Add or remove the playbook's hooks in Claude Code's user settings.

Usage: settings.py install|uninstall <repo-dir> [settings.json]

Our entries are tagged with AGENT_PLAYBOOK_HOOK=1 in the command, so they are
found and replaced even after the repo moves. Every other setting and hook is
kept as is. A symlinked settings.json is written through, not replaced.
"""
import json
import os
import sys

TAG = "AGENT_PLAYBOOK_HOOK=1"

action, repo = sys.argv[1], sys.argv[2]
path = sys.argv[3] if len(sys.argv) > 3 else os.path.expanduser("~/.claude/settings.json")
path = os.path.realpath(path)
hooks_dir = os.path.join(repo, "hooks")


def cmd(script, *args):
    return f'{TAG} python3 "{os.path.join(hooks_dir, script)}"' + "".join(f" {a}" for a in args)


OURS = {
    "PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": cmd("guard-git.py"), "timeout": 10}]}],
    "SessionStart": [{"hooks": [{"type": "command", "command": cmd("stop-check.py", "--baseline"), "timeout": 30}]}],
    "UserPromptSubmit": [{"hooks": [{"type": "command", "command": cmd("stop-check.py", "--baseline"), "timeout": 30}]}],
    "Stop": [{"hooks": [{"type": "command", "command": cmd("stop-check.py"), "timeout": 600,
                         "statusMessage": "agent-playbook: running the repo check"}]}],
}

if not os.path.exists(path):
    if action == "uninstall":
        sys.exit(0)
    settings = {}
else:
    with open(path) as f:
        settings = json.load(f)
if not isinstance(settings.get("hooks"), dict):
    settings["hooks"] = {}
hooks = settings["hooks"]


def is_ours(group):
    return isinstance(group, dict) and any(
        TAG in str(h.get("command", "")) or os.path.join(hooks_dir, "") in str(h.get("command", ""))
        for h in group.get("hooks") or [] if isinstance(h, dict))


changed = False
for event in list(hooks):
    if isinstance(hooks[event], list):
        kept = [g for g in hooks[event] if not is_ours(g)]
        changed |= len(kept) != len(hooks[event])
        hooks[event] = kept
if action == "install":
    for event, groups in OURS.items():
        hooks.setdefault(event, []).extend(groups)
    changed = True
for event in [e for e, v in hooks.items() if v == []]:
    del hooks[event]
if not hooks:
    del settings["hooks"]

if changed:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".agent-playbook.tmp"
    with open(tmp, "w") as f:
        json.dump(settings, f, indent=2)
        f.write("\n")
    os.replace(tmp, path)
    print(f"  {'added' if action == 'install' else 'removed'} playbook hooks in {path}")
