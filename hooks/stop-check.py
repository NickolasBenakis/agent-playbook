#!/usr/bin/env python3
"""Claude Code hook: don't hand back work that is red.

Opt-in per repo, with a command only you can set:

    git config playbook.check "npm test && npx tsc --noEmit"

(Local git config is never cloned, so a repo can't opt you in to running its
own command.)

- On SessionStart and UserPromptSubmit (`--baseline`) it records a fingerprint
  of the working tree, tracked and untracked files included.
- On Stop it runs the check only if the agent changed the tree during this
  turn and the tree differs from the last passing run. A failure blocks the
  stop and feeds back the output tail, so the agent keeps fixing. After 3
  failed attempts in one turn it lets the agent stop, with a note to report
  the work as red.
"""
import json
import os
import shutil
import subprocess
import sys

MAX_ATTEMPTS = 3
TIMEOUT_SECONDS = 540
TAIL_LINES = 40


def git(cwd, *args, env=None):
    return subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True, timeout=60, env=env)


def fingerprint(root, state_dir):
    """Hash of the whole working tree (tracked + untracked, respecting .gitignore)."""
    index = os.path.join(state_dir, "index")
    real_index = git(root, "rev-parse", "--git-path", "index").stdout.strip()
    real_index = os.path.join(root, real_index)
    if os.path.isfile(real_index):
        shutil.copyfile(real_index, index)  # speeds up `add` via cached stat info
    elif os.path.exists(index):
        os.remove(index)
    env = dict(os.environ, GIT_INDEX_FILE=index)
    git(root, "add", "-A", env=env)
    return git(root, "write-tree", env=env).stdout.strip() or None


def main():
    baseline_mode = "--baseline" in sys.argv[1:]
    data = json.load(sys.stdin)
    if not isinstance(data, dict):
        return
    cwd = data.get("cwd") or os.getcwd()
    session = str(data.get("session_id") or "unknown")
    top = git(cwd, "rev-parse", "--show-toplevel")
    if top.returncode != 0:
        return
    root = top.stdout.strip()
    command = git(root, "config", "--get", "playbook.check").stdout.strip()
    if not command:
        return

    git_dir = git(root, "rev-parse", "--absolute-git-dir").stdout.strip()
    state_dir = os.path.join(git_dir, "agent-playbook")
    os.makedirs(state_dir, exist_ok=True)
    state_path = os.path.join(state_dir, "stop-check.json")
    try:
        with open(state_path) as f:
            state = json.load(f)
    except Exception:
        state = {}
    sessions = state.setdefault("sessions", {})
    me = sessions.setdefault(session, {})

    def save():
        with open(state_path, "w") as f:
            json.dump(state, f)

    fp = fingerprint(root, state_dir)
    if baseline_mode:
        me.update(baseline=fp, attempts=0)
        save()
        return
    if fp is None or fp == me.get("baseline") or fp == state.get("passed"):
        return  # agent changed nothing this turn, or this tree already passed

    try:
        run = subprocess.run(command, shell=True, cwd=root, capture_output=True, text=True, timeout=TIMEOUT_SECONDS)
        ok, output = run.returncode == 0, (run.stdout + run.stderr)
    except subprocess.TimeoutExpired:
        ok, output = False, f"check timed out after {TIMEOUT_SECONDS}s"

    if ok:
        state["passed"] = fp
        me["attempts"] = 0
        save()
        return
    me["attempts"] = me.get("attempts", 0) + 1
    save()
    tail = "\n".join(output.strip().splitlines()[-TAIL_LINES:])
    if me["attempts"] >= MAX_ATTEMPTS:
        print(json.dumps({
            "systemMessage": f"agent-playbook: `{command}` still fails after {MAX_ATTEMPTS} attempts; "
            "letting the agent stop. Its report should say the work is red.",
        }))
        return
    print(json.dumps({
        "decision": "block",
        "reason": (
            f"agent-playbook: the repo check `{command}` fails after your changes "
            f"(attempt {me['attempts']} of {MAX_ATTEMPTS}). Fix it before finishing, or, if it "
            "can't be fixed within this task, say so in the first line of your report.\n\n" + tail
        ),
    }))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # never break the session because of this hook
        print(f"agent-playbook stop-check skipped: {e}", file=sys.stderr)
    sys.exit(0)
