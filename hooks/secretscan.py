"""What counts as a secret: secret files by path, and secret values by pattern.
Used by guard-secrets.py."""
import math
import os
import re

# Files that usually hold secrets. Matched against the basename or the path tail.
_SECRET_NAME = re.compile(
    r"""^(
        \.env(\..+)? | \.envrc | \.dev\.vars | \.secrets? |
        .*\.(pem|key|p12|pfx|jks|keystore|ppk|tfstate|tfvars|kdbx) |
        id_(rsa|dsa|ecdsa|ed25519)(_sk)? |
        \.netrc | _netrc | \.git-credentials | \.npmrc | \.pypirc | \.pgpass | \.my\.cnf |
        credentials(\.json)? | service[-_]?account.*\.json | secrets?\.(json|ya?ml|toml|env) |
        \.credentials\.json | kubeconfig
    )$""", re.X | re.I)
_SECRET_TAIL = re.compile(r"(^|/)(\.ssh(/(?!.*\.pub$|known_hosts|config$)[^/]+)?|\.aws(/(credentials|config))?|"
                          r"\.docker/config\.json|\.kube/config|\.config/gh/hosts\.yml|\.gnupg(/.+)?)$")
# Templates that hold names, not values.
_TEMPLATE = re.compile(r"\.(example|sample|template|dist|defaults?|schema|tpl)$|\.example\.|\.pub$", re.I)
MAX_FILE_BYTES = 1_000_000


def is_secret_path(path):
    """True if the path's name says it usually holds secrets."""
    if not path or not isinstance(path, str):
        return False
    path = os.path.expanduser(path.strip()).rstrip("/")
    name = os.path.basename(path)
    if _TEMPLATE.search(name):
        return False
    return bool(_SECRET_NAME.match(name) or _SECRET_TAIL.search(path))


def holds_secrets(path, cwd="."):
    """True if a secret-named path really holds secrets. Directories under
    ~/.ssh, ~/.aws, ~/.gnupg count; a missing file doesn't; an unreadable one does."""
    if not is_secret_path(path):
        return False
    full = os.path.join(cwd, os.path.expanduser(path))
    if os.path.isdir(full):
        return bool(_SECRET_TAIL.search(full.rstrip("/")))
    if not os.path.exists(full):
        return False
    try:
        if os.path.getsize(full) > MAX_FILE_BYTES:
            return True
        with open(full, errors="ignore") as f:
            text = f.read()
    except OSError:
        return True
    name = os.path.basename(full)
    if re.search(r"\.(pem|key|p12|pfx|jks|keystore|ppk|kdbx)$|^id_", name, re.I):
        return "PRIVATE KEY" in text or "\x00" in text or name.startswith("id_")
    return bool(find_secrets(text, env_file=True))


# Values that are almost always real credentials.
TOKEN_PATTERNS = [
    ("AWS access key", r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    ("GitHub token", r"\bgh[pousr]_[A-Za-z0-9]{36,}\b|\bgithub_pat_[A-Za-z0-9_]{50,}"),
    ("GitLab token", r"\bglpat-[A-Za-z0-9_-]{20,}"),
    ("Anthropic key", r"\bsk-ant-[A-Za-z0-9_-]{20,}"),
    ("OpenAI key", r"\bsk-(?:proj|svcacct|admin)-[A-Za-z0-9_-]{20,}|\bsk-[A-Za-z0-9]{40,}\b"),
    ("Stripe live key", r"\b[sr]k_live_[A-Za-z0-9]{16,}"),
    ("Stripe webhook secret", r"\bwhsec_[A-Za-z0-9]{24,}"),
    ("Slack token", r"\bxox[abposr]-[A-Za-z0-9-]{10,}"),
    ("Slack webhook", r"hooks\.slack\.com/services/T[A-Z0-9]+/B[A-Z0-9]+/[A-Za-z0-9]+"),
    ("Google API key", r"\bAIza[0-9A-Za-z_-]{35}\b"),
    ("npm token", r"\bnpm_[A-Za-z0-9]{36}\b"),
    ("SendGrid key", r"\bSG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}\b"),
    ("Private key", r"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----\s*[A-Za-z0-9+/=]{40,}"),
]
_TOKENS = [(label, re.compile(rx)) for label, rx in TOKEN_PATTERNS]
_FAKE_TOKEN = re.compile(r"example|x{6,}|0{8,}|fake|dummy", re.I)

SECRET_NAME = r"[\w.-]*(?:secret|token|passw(?:or)?d|api[_-]?key|private[_-]?key|access[_-]?key|auth[_-]?key|client[_-]?secret)"
# A secret-named variable assigned a quoted literal that looks random.
_ASSIGN = re.compile(r"(?i)\b(" + SECRET_NAME + r")[\w.-]*[\"']?\s*[:=]\s*[\"']([^\"'\s]{16,})[\"']")
# KEY=value lines in env files (unquoted values allowed).
_ENV_LINE = re.compile(r"(?im)^\s*(?:export\s+)?([A-Z0-9_]*(?:SECRET|TOKEN|PASSWORD|PASSWD|API_?KEY|PRIVATE_?KEY|"
                       r"ACCESS_?KEY|CREDENTIALS?|DSN|DATABASE_URL)[A-Z0-9_]*)\s*=\s*[\"']?([^\s\"'#]{8,})")
_DB_URL = re.compile(r"\b(?:postgres(?:ql)?|mysql|mariadb|mongodb(?:\+srv)?|rediss?|amqps?)://[^:@\s/]+:([^@\s]{8,})@([^/\s:]+)")
_PLACEHOLDER = re.compile(r"x{4,}|\*{3,}|your|example|changeme|change-me|placeholder|dummy|fake|sample|redacted|"
                          r"<|>|\$|\{|\}|%s|process\.env|os\.environ|getenv|env\(|\.\.\.|^https?:|://|^/", re.I)
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "db", "postgres", "mysql", "redis", "mongo", "host.docker.internal"}


def _entropy(s):
    counts = {c: s.count(c) for c in set(s)}
    return -sum(n / len(s) * math.log2(n / len(s)) for n in counts.values())


def _looks_real(value, min_entropy=3.5):
    return (not _PLACEHOLDER.search(value) and not re.fullmatch(r"[A-Z_]+|[a-z_]+", value)
            and _entropy(value) >= min_entropy)


def find_secrets(text, env_file=False):
    """Return labels of secret values found in text (empty list if none)."""
    if not text or not isinstance(text, str):
        return []
    found = [label for label, rx in _TOKENS
             if any(not _FAKE_TOKEN.search(m.group(0)) for m in rx.finditer(text))]
    for m in _ASSIGN.finditer(text):
        if _looks_real(m.group(2)):
            found.append("hard-coded " + re.sub(r"^.*?(secret|token|passw|api|private|access|auth|client)", r"\1",
                                                m.group(1).lower()))
            break
    for m in _DB_URL.finditer(text):
        password, host = m.group(1), m.group(2).lower()
        if host not in _LOCAL_HOSTS and _looks_real(password, 2.5):
            found.append("database URL with password")
            break
    if env_file:
        for m in _ENV_LINE.finditer(text):
            if "://" not in m.group(2) and _looks_real(m.group(2), 2.5):
                found.append(f"{m.group(1)} value")
                break
    return found
