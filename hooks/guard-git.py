#!/usr/bin/env python3
"""Claude Code PreToolUse hook (matcher: Bash).

Asks the human before commands the playbook says need explicit permission:
pushing to the default branch, force-pushing (other than --force-with-lease),
merging a PR with `gh pr merge`, and commands that destroy uncommitted work
(`reset --hard`, `checkout .`/`restore .` on a dirty tree, `clean -x`).
Everything else passes silently.
Asking (not denying) keeps the human in charge: one click approves it.

This is a guard against mistakes, not a security boundary: a determined
command can always hide a push (scripts, aliases, eval).
"""
import json
import os
import subprocess
import sys

from shellwords import walk


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


def dirty(cwd):
    return bool(git_out(cwd, "status", "--porcelain", "--untracked-files=no"))


def check(words, cwd):
    prog = os.path.basename(words[0])
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
    sub, args = (words[i], words[i + 1:]) if i < len(words) else (None, [])
    if sub == "push":
        return check_push(args, git_cwd)
    if sub == "reset" and "--hard" in args and dirty(git_cwd):
        return "discards uncommitted changes (reset --hard on a dirty tree)"
    if sub == "clean" and any(a.startswith("-") and not a.startswith("--") and "x" in a.lower() for a in args) \
            and not any(a in ("-n", "--dry-run") for a in args):
        return "deletes ignored files such as .env (git clean -x)"
    if sub in ("checkout", "restore") and args[-1:] == ["."] and dirty(git_cwd) \
            and (sub == "checkout" or not {"--staged", "-S"} & set(args) or {"--worktree", "-W"} & set(args)):
        return "discards uncommitted changes"
    return None


def main():
    data = json.load(sys.stdin)
    if not isinstance(data, dict) or not isinstance(data.get("tool_input"), dict):
        return
    command = data["tool_input"].get("command")
    if not isinstance(command, str) or not any(w in command for w in ("push", "merge", "reset", "clean", "checkout", "restore")):
        return
    reason = walk(command, str(data.get("cwd") or os.getcwd()), check)
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
