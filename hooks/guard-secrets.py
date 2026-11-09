#!/usr/bin/env python3
"""Claude Code PreToolUse hook (matcher: Bash|Read|Grep|Edit|Write|MultiEdit|NotebookEdit).

Keeps secret values out of the agent's context, the code and git history:

- Read/Grep of a file that holds secrets (.env*, keys, ~/.ssh, ~/.aws, ...)
  is denied; `cut -d= -f1 .env` lists the variable names instead. The hook
  looks inside the file itself, so a secret-named file with no credentials in
  it (an `.npmrc` with only settings) passes.
- Bash commands that print or send such a file (cat, grep, head, curl -d @,
  git show HEAD:.env, grep -r over a tree with one), dump the environment
  (printenv, env, echo $API_KEY) or print a credential (gh auth token, ...)
  are denied. Commands that only use secrets (source .env, --env-file,
  cp .env ../wt/, find -name .env, echo .env >> .gitignore) pass.
- Writing a credential into a file that git would commit is denied.
- `git commit` / `git push` are denied when the commit or the commits not yet
  on any remote add a credential.
- `curl ... | sh` asks the human first.

Denying (not asking) keeps the human out of the loop: the reason tells the
agent what to do instead. This is a guard against accidents and prompt
injection, not a sandbox: a determined command can always get around it.
"""
import glob
import json
import os
import re
import subprocess
import sys

from secretscan import MAX_FILE_BYTES, find_secrets, holds_secrets, is_secret_path
from shellwords import walk

SECRET_VAR = re.compile(r"(^|_)(SECRET|TOKEN|PASSWORD|PASSWD|PASS|API_?KEY|APIKEY|PRIVATE_?KEY|ACCESS_?KEY|SECRET_?KEY|"
                        r"CREDENTIALS?|DSN)$|^DATABASE_URL$", re.I)
# Programs that print or send the files they are given.
READERS = {"cat", "tac", "less", "more", "most", "head", "tail", "bat", "batcat", "nl", "strings", "xxd", "od",
           "hexdump", "base64", "base32", "grep", "egrep", "fgrep", "rg", "ag", "ack", "awk", "gawk", "sed", "gsed",
           "sort", "uniq", "cut", "jq", "yq", "diff", "colordiff", "curl", "wget", "http", "https", "nc", "ncat",
           "socat", "scp", "rsync", "sftp", "pbcopy", "xclip", "openssl", "gpg", "column", "fold", "paste", "tr"}
GREPS = {"grep", "egrep", "fgrep", "rg", "ag", "ack"}
NAMES_HINT = ("List the variable names with `cut -d= -f1 <file>` and refer to values by name "
              "(process.env.X, os.environ['X']); load them with `set -a; . <file>; set +a` if a command needs them.")
FULL_COMMAND = ""


def deny(reason):
    return ("deny", f"agent-playbook: {reason}")


def ask(reason):
    return ("ask", f"agent-playbook: {reason}")


def git(cwd, *args):
    try:
        out = subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True, timeout=20)
        return out.stdout if out.returncode == 0 else ""
    except Exception:
        return ""


def is_ignored(path, cwd):
    """True if git would not commit this path (ignored, or not in a repo)."""
    full = os.path.abspath(os.path.join(cwd, path))
    folder = os.path.dirname(full)
    while folder and not os.path.isdir(folder):
        folder = os.path.dirname(folder)
    if not git(folder, "rev-parse", "--git-dir"):
        return True
    return subprocess.run(["git", "-C", folder, "check-ignore", "-q", full], capture_output=True).returncode == 0


def expand(word, cwd):
    if any(c in word for c in "*?["):
        return [os.path.relpath(p, cwd) for p in glob.glob(os.path.join(cwd, os.path.expanduser(word)))] or [word]
    return [word]


# ---- git: scan what would be published -------------------------------------

def added_by_file(diff):
    files, current = {}, None
    for line in diff.splitlines():
        if line.startswith("+++ "):
            current = line[4:].removeprefix("b/")
        elif line.startswith("+") and current:
            files.setdefault(current, []).append(line[1:])
    return {f: "\n".join(lines) for f, lines in files.items()}


def scan_publish(added, what):
    for name, text in added.items():
        found = find_secrets(text, env_file=is_secret_path(name))
        if found:
            return deny(f"{what} would publish a credential ({', '.join(sorted(set(found)))}) in {name}. Move the "
                        "value to an env var or a gitignored file and refer to it by name, then unstage the file "
                        "(`git restore --staged <file>`) or amend. For a deliberate fake (a test fixture), build it "
                        "at runtime so it doesn't look like a real key.")
    return None


def check_commit(cwd, args):
    added = added_by_file(git(cwd, "diff", "--cached"))
    adds_first = re.search(r"\bgit\s+(-C\s+\S+\s+)?add\b[^;&|]*[;&|]+.*\bcommit\b", FULL_COMMAND, re.S)
    if any(a in ("-a", "--all") or (a.startswith("-") and not a.startswith("--") and "a" in a) for a in args) or adds_first:
        added.update(added_by_file(git(cwd, "diff")))
    if adds_first:
        for n in git(cwd, "ls-files", "--others", "--exclude-standard").splitlines():
            p = os.path.join(cwd, n)
            try:
                if os.path.getsize(p) <= MAX_FILE_BYTES:
                    with open(p, errors="ignore") as f:
                        added[n] = f.read()
            except OSError:
                pass
    return scan_publish(added, "this commit")


def check_push(cwd, args):
    positional = [a for a in args if not a.startswith("-")]
    src = positional[1].split(":", 1)[0].lstrip("+") if len(positional) > 1 else "HEAD"
    if not git(cwd, "rev-parse", "--verify", "--quiet", src or "HEAD"):
        return None
    diff = git(cwd, "log", "-p", "--format=", "--max-count=500", src or "HEAD", "--not", "--remotes")
    return scan_publish(added_by_file(diff), "this push")


# ---- Bash -------------------------------------------------------------------

def option(args, short, long):
    """Value of an option given as -x V, -xV, --long=V or --long V."""
    for i, a in enumerate(args):
        if a in (short, long):
            return args[i + 1] if i + 1 < len(args) else None
        if a.startswith(long + "="):
            return a[len(long) + 1:]
        if a.startswith(short) and len(a) > len(short) and not a.startswith("--"):
            return a[len(short):]
    return None


def read_paths(words, cwd):
    """Files a reader is given: skips output redirect targets, -i <key>, the
    destination of scp/rsync, and option names; unwraps @file and opt=@file."""
    out, skip = [], False
    for i, w in enumerate(words[1:], 1):
        if skip:
            skip = False
            continue
        if w in (">", ">>", ">|", "&>", ">&", "&>>") or (w == "-i" and words[0] in ("scp", "sftp", "rsync")):
            skip = True
            continue
        if "=@" in w:
            w = w.split("=@", 1)[1]  # curl -F f=@file, --data-binary=@file
        elif w.startswith("-"):
            continue  # an option, or --exclude=<pattern>: not a file being read
        out.extend(expand(w.lstrip("@"), cwd))
    if os.path.basename(words[0]) in ("scp", "rsync") and out:
        out = out[:-1]
    return out


def recursive_grep_leak(prog, args, cwd):
    """grep -r prints matches from hidden, gitignored files such as .env."""
    if prog not in ("grep", "egrep", "fgrep") or not any(re.fullmatch(r"-[A-Za-z]*[rR][A-Za-z]*|--recursive|"
                                                                       r"--dereference-recursive", a) for a in args):
        return None
    if any(a.startswith("--exclude") and "env" in a for a in args):
        return None
    plain = [a for a in args if not a.startswith("-")]
    for top in (plain[1:] or ["."]):
        base = os.path.join(cwd, os.path.expanduser(top))
        for root, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs if d not in ("node_modules", ".git", "vendor", ".venv", "dist", ".next")]
            if root[len(base):].count(os.sep) >= 2:
                dirs[:] = []
            for name in files:
                if is_secret_path(name) and holds_secrets(os.path.join(root, name)):
                    return os.path.relpath(os.path.join(root, name), cwd)
    return None


def check_bash(words, cwd):
    prog = os.path.basename(words[0])
    args = words[1:]
    plain = [a for a in args if not a.startswith("-")]

    if prog in ("env", "printenv") and not plain:
        return deny("this prints every environment variable, secrets included. "
                    "Check one variable, or test presence with `[ -n \"$NAME\" ] && echo set`.")
    if prog == "printenv" and any(SECRET_VAR.search(a) for a in plain):
        return deny("this prints a secret. Test presence with `[ -n \"$NAME\" ] && echo set`.")
    if (prog == "export" and "-p" in args and not plain) or (prog == "declare" and {"-x", "-p"} & set(args) and not plain) \
            or (prog == "set" and not args):
        return deny("this prints every environment variable, secrets included.")
    if prog in ("echo", "printf", "print"):
        for name in re.findall(r"\$\{?([A-Za-z_][A-Za-z0-9_]*)", " ".join(args)):
            if SECRET_VAR.search(name):
                return deny(f"this prints ${name}. Test presence with `[ -n \"${name}\" ] && echo set` instead.")

    sub = " ".join(plain[:2])
    if (prog == "gh" and (sub == "auth token" or (sub == "auth status" and {"-t", "--show-token"} & set(args)))) \
            or (prog == "security" and plain[:1] and "password" in plain[0] and {"-w", "-g"} & set(args)) \
            or (prog == "gcloud" and re.search(r"print-(access|identity)-token", " ".join(plain))) \
            or (prog == "aws" and sub in ("configure get", "configure export-credentials")) \
            or (prog == "heroku" and plain[:1] == ["auth:token"]) \
            or (prog == "op" and plain[:1] == ["read"]) \
            or (prog == "vault" and plain[:1] in (["read"], ["kv"])) \
            or (prog == "kubectl" and plain[:1] == ["get"] and plain[1:2] and plain[1].startswith("secret")
                and any(a.startswith("-o") or a == "--output" for a in args)):
        return deny("this prints a credential into the transcript. Use it without printing "
                    "(e.g. `GH_TOKEN=$(gh auth token) cmd`), or ask the human to run it.")

    if prog == "git":
        i = 1
        while i < len(words) and words[i].startswith("-"):
            i += 2 if words[i] in ("-C", "-c") else 1
        gsub, gargs = (words[i], words[i + 1:]) if i < len(words) else ("", [])
        if gsub in ("show", "diff", "log", "blame", "cat-file", "grep"):
            for a in gargs:
                path = a.split(":", 1)[1] if ":" in a and not a.startswith("-") else a
                if not a.startswith("-") and is_secret_path(path):
                    return deny(f"`git {gsub}` would print the secret file {path}. {NAMES_HINT}")
        return None

    leak = recursive_grep_leak(prog, args, cwd)
    if leak:
        return deny(f"`grep -r` also searches {leak}, which holds secrets, and would print matching lines. "
                    "Use `rg` (it skips gitignored files) or add `--exclude='.env*'`.")

    if prog not in READERS:
        return None
    if prog == "cut" and option(args, "-d", "--delimiter") == "=" and option(args, "-f", "--fields") == "1":
        return None  # names only
    if prog in GREPS and any(re.fullmatch(r"-[A-Za-z]*[qlLc][A-Za-z]*|--quiet|--count|--files-with-matches", a) for a in args):
        return None
    if prog in ("sed", "gsed") and any(a.startswith("-i") or a == "--in-place" for a in args):
        return None
    for path in read_paths(words, cwd):
        if holds_secrets(path, cwd):
            return deny(f"this would print or send {path}, which holds secrets. {NAMES_HINT} "
                        "If the human asked for the values, ask them to run it themselves.")
    return None


def visit(words, cwd):
    reason = check_bash(words, cwd)
    if reason:
        return reason
    if os.path.basename(words[0]) == "git":
        i, gcwd = 1, cwd
        while i < len(words) and words[i].startswith("-"):
            if words[i] == "-C" and i + 1 < len(words):
                gcwd = os.path.join(cwd, os.path.expanduser(words[i + 1]))
            i += 2 if words[i] in ("-C", "-c") else 1
        gsub, gargs = (words[i], words[i + 1:]) if i < len(words) else ("", [])
        if gsub == "commit" and "--dry-run" not in gargs:
            return check_commit(gcwd, gargs)
        if gsub == "push" and "--dry-run" not in gargs and "-n" not in gargs:
            return check_push(gcwd, gargs)
    return None


PIPE_TO_SHELL = re.compile(r"\b(curl|wget)\b[^;&\n]*\|\s*(sudo\s+)?((ba|z|da|fi)?sh|python3?)\b")


def check_tool(tool, inp, cwd):
    global FULL_COMMAND
    if tool == "Bash":
        command = inp.get("command")
        if not isinstance(command, str):
            return None
        if PIPE_TO_SHELL.search(command):
            return ask("this runs a script straight from the internet. Download it, read it, then run it.")
        FULL_COMMAND = command
        return walk(command, cwd, visit)
    if tool == "Read":
        path = inp.get("file_path")
        if isinstance(path, str) and holds_secrets(path, cwd):
            return deny(f"{path} holds secrets; reading it puts their values in the transcript. {NAMES_HINT}")
        return None
    if tool == "Grep":
        path = inp.get("path") if isinstance(inp.get("path"), str) else "."
        targets = [path]
        if isinstance(inp.get("glob"), str) and os.path.isdir(os.path.join(cwd, path)):
            targets += glob.glob(os.path.join(cwd, path, inp["glob"]))
        if any(holds_secrets(t, cwd) for t in targets):
            return deny(f"searching files that hold secrets prints their values. {NAMES_HINT}")
        return None
    if tool in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
        path = inp.get("file_path") or inp.get("notebook_path") or ""
        if not isinstance(path, str):
            return None
        texts = [inp.get("content"), inp.get("new_string"), inp.get("new_source")]
        texts += [e.get("new_string") for e in inp.get("edits") or [] if isinstance(e, dict)]
        found = sorted({label for t in texts for label in find_secrets(t, env_file=is_secret_path(path))})
        if not found:
            return None
        if is_secret_path(path) and is_ignored(path, cwd):
            return None  # a gitignored secret file is where secrets belong
        return deny(f"this writes a credential ({', '.join(found)}) into {os.path.basename(path) or 'a file'}, "
                    "which git would commit. Read it from an env var instead and put the value in a gitignored "
                    "file such as .env.local. For a test fixture, build a fake value at runtime so it doesn't "
                    "look like a real key.")
    return None


def main():
    data = json.load(sys.stdin)
    if not isinstance(data, dict) or not isinstance(data.get("tool_input"), dict):
        return
    result = check_tool(data.get("tool_name"), data["tool_input"], str(data.get("cwd") or os.getcwd()))
    if result:
        decision, reason = result
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "permissionDecision": decision, "permissionDecisionReason": reason}}))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # a broken guard must not break the session
        print(f"agent-playbook guard-secrets skipped: {e}", file=sys.stderr)
    sys.exit(0)
