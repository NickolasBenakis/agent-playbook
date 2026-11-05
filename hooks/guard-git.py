#!/usr/bin/env python3
"""Claude Code PreToolUse hook (matcher: Bash).

Asks the human before commands the playbook says need explicit permission:
pushing to the default branch, force-pushing (other than --force-with-lease),
and merging a PR with `gh pr merge`. Everything else passes silently.
Asking (not denying) keeps the human in charge: one click approves it.

This is a guard against mistakes, not a security boundary: a determined
command can always hide a push (scripts, aliases, eval).
"""
import json
import os
import re
import shlex
import subprocess
import sys

WRAPPERS = {"sudo", "command", "exec", "nohup", "time", "env", "nice", "timeout", "xargs"}
SHELLS = {"bash", "sh", "zsh", "dash"}


def git_out(cwd, *args):
    try:
        return subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:
        return ""


def default_branches(cwd):
    names = {"main", "master"}
    ref = git_out(cwd, "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD")
    if ref:
        names.add(ref.rsplit("/", 1)[-1])
    return names


def segments(command):
    """Split a command line into simple commands on ; && || | & and newlines."""
    for part in re.split(r"&&|\|\||[;|&\n]", command):
        try:
            words = shlex.split(part, comments=True)
        except ValueError:
            words = part.split()
        if words:
            yield words


def unwrap(words):
    """Drop env assignments and wrappers like sudo, timeout 60, env X=1, nice -n 5."""
    while words:
        w = words[0]
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", w):
            words = words[1:]
        elif os.path.basename(w) in WRAPPERS:
            words = words[1:]
            while words and (words[0].startswith("-") or re.match(r"^\d+[smhd]?$", words[0])
                             or re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", words[0])):
                words = words[1:]
        else:
            break
    return words


def check_push(args, cwd):
    flags = [a for a in args if a.startswith("-")]
    positional = [a for a in args if not a.startswith("-")]
    for f in flags:
        if f in ("-f", "--force") or (not f.startswith("--") and "f" in f[1:]):
            return "force-pushes"
        if f in ("--mirror", "--all"):
            return "pushes every branch"
    protected = default_branches(cwd)
    branch = git_out(cwd, "branch", "--show-current")
    refspecs = positional[1:]  # the first positional is the remote
    for spec in refspecs:
        if spec.startswith("+"):
            return "force-pushes"
        dest = spec.split(":", 1)[-1].removeprefix("refs/heads/")
        if dest in protected or (dest == "HEAD" and branch in protected):
            return f"pushes to the default branch ({dest})"
    if not refspecs and branch in protected:
        return f"pushes the default branch ({branch})"
    return None


def check(words, cwd, depth=0):
    words = unwrap(words)
    if not words:
        return None
    prog = os.path.basename(words[0])
    if prog in SHELLS and depth < 3:
        for i, w in enumerate(words[1:-1], 1):
            if w.startswith("-") and "c" in w:
                return scan(words[i + 1], cwd, depth + 1)
        return None
    if prog == "gh":
        rest = [w for w in words[1:] if not w.startswith("-")]
        # drop values of global flags like -R owner/repo
        for i, w in enumerate(words[1:], 1):
            if w in ("-R", "--repo") and i + 1 < len(words) and words[i + 1] in rest:
                rest.remove(words[i + 1])
        if rest[:2] == ["pr", "merge"]:
            return "merges a pull request"
        return None
    if prog != "git":
        return None
    i, git_cwd = 1, cwd
    while i < len(words) and words[i].startswith("-"):
        if words[i] in ("-C", "-c") and i + 1 < len(words):
            if words[i] == "-C":
                git_cwd = os.path.join(cwd, os.path.expanduser(words[i + 1]))
            i += 2
        else:
            i += 1
    if i < len(words) and words[i] == "push":
        return check_push(words[i + 1:], git_cwd)
    return None


def scan(command, cwd, depth=0):
    for words in segments(command):
        if words[0] in ("cd", "pushd") and len(words) > 1:
            cwd = os.path.join(cwd, os.path.expanduser(words[1]))
            continue
        reason = check(words, cwd, depth)
        if reason:
            return reason
    return None


def main():
    data = json.load(sys.stdin)
    if not isinstance(data, dict) or not isinstance(data.get("tool_input"), dict):
        return
    command = data["tool_input"].get("command")
    if not isinstance(command, str) or ("push" not in command and "merge" not in command):
        return
    reason = scan(command, str(data.get("cwd") or os.getcwd()))
    if reason:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": f"agent-playbook: this command {reason}. "
                "The playbook needs the human's explicit OK for this task.",
            }
        }))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # a broken guard must not break the session
        print(f"agent-playbook guard-git skipped: {e}", file=sys.stderr)
    sys.exit(0)
