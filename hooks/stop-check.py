#!/usr/bin/env python3
"""Claude Code hook: don't hand back work that is red or unverified.

Without configuration (the verification gate): on Stop, if the agent edited
source code this turn and ran nothing that builds, tests, checks or runs code
(npm, pytest, go, make, node, ./script, ...) after its last edit, the stop is
blocked once per turn with a request to verify, or to say in the report why it
can't. Docs and config edits don't count. It reads only the transcript and
runs nothing.

With a check command, the hook runs it itself. Opt-in per repo, with a command
only you can set:

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
import re
import shutil
import subprocess
import sys
import tempfile

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


CODE_EXT = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".py", ".rb", ".go", ".rs", ".java", ".kt", ".kts",
            ".swift", ".c", ".cc", ".cpp", ".h", ".hpp", ".cs", ".php", ".scala", ".sh", ".bash", ".zsh", ".sql",
            ".vue", ".svelte", ".astro", ".ex", ".exs", ".erl", ".lua", ".dart", ".m", ".mm", ".r", ".jl", ".zig",
            ".clj", ".hs", ".ml", ".fs", ".pl", ".tf"}
EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
# Programs that build, test, check or run code. Reading tools (ls, cat, git) don't count.
RUNNERS = {"npm", "pnpm", "yarn", "bun", "npx", "bunx", "deno", "node", "tsx", "ts-node", "python", "python3", "pytest",
           "uv", "poetry", "tox", "nox", "go", "cargo", "rustc", "make", "just", "task", "tsc", "jest", "vitest",
           "mocha", "playwright", "cypress", "eslint", "ruff", "mypy", "pyright", "flake8", "ruby", "rspec", "bundle",
           "rake", "php", "phpunit", "composer", "mvn", "gradle", "dotnet", "swift", "xcodebuild", "mix", "elixir",
           "terraform", "docker", "docker-compose", "bash", "sh", "zsh", "curl", "java", "kotlin", "clang", "gcc"}


def _is_prompt(entry):
    if entry.get("type") != "user" or entry.get("isMeta"):
        return False
    content = (entry.get("message") or {}).get("content")
    if isinstance(content, str):
        return True
    return isinstance(content, list) and not any(isinstance(c, dict) and c.get("type") == "tool_result" for c in content)


def _runs_code(command):
    try:
        from shellwords import segments, unwrap
    except Exception:
        return True
    for words in segments(command):
        words = unwrap(words)
        if words and (os.path.basename(words[0]) in RUNNERS or words[0].startswith("./")):
            return True
    return False


def unverified_edits(transcript_path):
    """(turn id, code files edited after the last command that built, tested or ran code in this turn)."""
    entries = []
    try:
        with open(transcript_path) as f:
            for line in f:
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                if isinstance(e, dict):
                    entries.append(e)
    except OSError:
        return None, []
    start = max((i for i, e in enumerate(entries) if _is_prompt(e)), default=-1)
    turn = str(entries[start].get("uuid") or start) if start >= 0 else "start"
    edited, pending = [], False
    for e in entries[start + 1:]:
        if e.get("type") != "assistant":
            continue
        for c in (e.get("message") or {}).get("content") or []:
            if not isinstance(c, dict) or c.get("type") != "tool_use":
                continue
            inp = c.get("input") or {}
            if c.get("name") in EDIT_TOOLS:
                path = str(inp.get("file_path") or inp.get("notebook_path") or "")
                if os.path.splitext(path)[1].lower() in CODE_EXT:
                    edited.append(os.path.basename(path))
                    pending = True
            elif c.get("name") == "Bash" and pending and _runs_code(str(inp.get("command") or "")):
                pending = False
    return turn, (sorted(set(edited)) if pending else [])


def verification_gate(data):
    turn, files = unverified_edits(str(data.get("transcript_path") or ""))
    if not files:
        return
    # Ask at most once per turn. Our own marker, not stop_hook_active, which other Stop hooks also set.
    marker = os.path.join(tempfile.gettempdir(), f"agent-playbook-gate-{data.get('session_id', 'x')}")
    try:
        with open(marker) as f:
            if f.read() == turn:
                return
    except OSError:
        pass
    with open(marker, "w") as f:
        f.write(turn)
    shown = ", ".join(files[:6]) + (" ..." if len(files) > 6 else "")
    print(json.dumps({"decision": "block", "reason": (
        f"agent-playbook: you changed code ({shown}) and ran no test, typecheck, build or the program "
        "itself after the last edit. Run the checks that cover this change now. If there are none or they "
        "can't run here, say so in your report instead of implying it works.")}))


def main():
    baseline_mode = "--baseline" in sys.argv[1:]
    data = json.load(sys.stdin)
    if not isinstance(data, dict):
        return
    cwd = data.get("cwd") or os.getcwd()
    session = str(data.get("session_id") or "unknown")
    top = git(cwd, "rev-parse", "--show-toplevel")
    if top.returncode != 0:
        if not baseline_mode:
            verification_gate(data)
        return
    root = top.stdout.strip()
    command = git(root, "config", "--get", "playbook.check").stdout.strip()
    if not command:
        if not baseline_mode:
            verification_gate(data)
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
