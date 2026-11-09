"""Shared helpers for the playbook's Bash hooks: split a command line into
simple commands (respecting quotes and here-documents) and strip wrappers, so
`cd x && sudo git push` reads as `git push` run in x."""
import os
import re
import shlex

WRAPPERS = {"sudo", "command", "exec", "nohup", "time", "env", "nice", "timeout", "xargs"}
SHELLS = {"bash", "sh", "zsh", "dash"}
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
SEPARATORS = {";", "&&", "||", "|", "&", "\n", "|&", ";;", "(", ")"}
HEREDOC = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")


def strip_heredocs(command):
    """Drop here-document bodies: they are data, not commands."""
    out, ends = [], []
    for line in command.split("\n"):
        if ends:
            if line.strip() == ends[0]:
                ends.pop(0)
            continue
        out.append(line)
        ends.extend(m.group(2) for m in HEREDOC.finditer(line))
    return "\n".join(out)


def tokens(command):
    lex = shlex.shlex(strip_heredocs(command), posix=True, punctuation_chars=";&|()<>\n")
    lex.whitespace = " \t\r"
    lex.whitespace_split = True
    try:
        return list(lex)
    except ValueError:  # unbalanced quotes: fall back to a rough split
        return re.split(r"\s+|(?=[;&|\n])", command)


def segments(command):
    """Yield the words of each simple command. Redirections stay as words
    ('>', '>>', '<', '2', ...)."""
    words = []
    for tok in tokens(command):
        if tok in SEPARATORS:
            if words:
                yield words
            words = []
        elif tok:
            words.append(tok)
    if words:
        yield words


def unwrap(words):
    """Drop env assignments and wrappers like sudo, timeout 60, env X=1, nice -n 5."""
    while words:
        w = words[0]
        if ASSIGNMENT.match(w):
            words = words[1:]
        elif os.path.basename(w) in WRAPPERS:
            rest = [x for x in words[1:] if not x.startswith("-") and not ASSIGNMENT.match(x)]
            if not rest:
                break  # a bare `env` or `env -0` is itself the command
            words = words[1:]
            while words and (words[0].startswith("-") or re.match(r"^\d+[smhd]?$", words[0])
                             or ASSIGNMENT.match(words[0])):
                words = words[1:]
        else:
            break
    return words


def shell_script(words):
    """For `bash -c "..."` return the inner script, else None."""
    if os.path.basename(words[0]) not in SHELLS:
        return None
    for i, w in enumerate(words[1:-1], 1):
        if w.startswith("-") and "c" in w:
            return words[i + 1]
    return None


def walk(command, cwd, visit, depth=0):
    """Call visit(words, cwd) for every simple command, following cd/pushd and
    recursing into `bash -c`. Returns the first non-None result."""
    for words in segments(command):
        if words[0] in ("cd", "pushd") and len(words) > 1:
            cwd = os.path.join(cwd, os.path.expanduser(words[1]))
            continue
        words = unwrap(words)
        if not words:
            continue
        inner = shell_script(words)
        if inner is not None:
            if depth < 3:
                result = walk(inner, cwd, visit, depth + 1)
                if result:
                    return result
            continue
        result = visit(words, cwd)
        if result:
            return result
    return None
