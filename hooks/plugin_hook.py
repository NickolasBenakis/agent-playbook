#!/usr/bin/env python3
"""Entry point for the playbook's hooks when it is installed as a Claude Code plugin.

Usage (from hooks/hooks.json): plugin_hook.py <script.py> [args...]

Runs hooks/<script.py> with the same stdin and arguments. It stands down only
when install.sh has registered this same script in ~/.claude/settings.json
and that registered file still exists, so a user with both installs doesn't
run every guard twice, and a stale or partial script install never leaves
them with no guard at all.
"""
import json
import os
import re
import subprocess
import sys

TAG = "AGENT_PLAYBOOK_HOOK=1"
HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = {"flag-injection.py", "guard-git.py", "guard-secrets.py", "stop-check.py"}


def script_install_runs(script):
    config = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")
    try:
        with open(os.path.join(config, "settings.json")) as f:
            hooks = json.load(f).get("hooks")
    except (OSError, ValueError, AttributeError):
        return False
    if not isinstance(hooks, dict):
        return False
    for groups in hooks.values():
        for group in groups if isinstance(groups, list) else []:
            for hook in (group.get("hooks") or []) if isinstance(group, dict) else []:
                command = str(hook.get("command", "")) if isinstance(hook, dict) else ""
                if TAG not in command:
                    continue
                for path in re.findall(r'"([^"]+\.py)"', command):
                    if os.path.basename(path) == script and os.path.isfile(path):
                        return True
    return False


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in SCRIPTS:
        print(f"plugin_hook.py: unknown hook {sys.argv[1:2]}", file=sys.stderr)
        return 1
    script = sys.argv[1]
    if script_install_runs(script):
        return 0
    return subprocess.run([sys.executable, os.path.join(HERE, script), *sys.argv[2:]], stdin=sys.stdin).returncode


if __name__ == "__main__":
    sys.exit(main())
