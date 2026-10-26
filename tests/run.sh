#!/usr/bin/env bash
# Playbook self-test. Usage: tests/run.sh
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
stale="$repo/skills/factory/intent-stale"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
fails=0

check() {
  local name="$1" expected="$2" actual="$3"
  if [[ "$actual" == *"$expected"* ]]; then
    echo "ok   $name"
  else
    echo "FAIL $name"; echo "     expected: $expected"; echo "     got: $actual"
    fails=$((fails + 1))
  fi
}

# A toy repo: main has two areas, a factory branch depends on one of them.
git init -q -b main "$work/toy"
cd "$work/toy"
git config user.email t@example.com && git config user.name test
mkdir -p src/auth src/billing
echo a > src/auth/login.ts && echo b > src/billing/invoice.ts && echo c > README.md
git add -A && git commit -qm base

git checkout -qb factory/rate-limit-1
mkdir -p .intent
cat > .intent/rate-limit-1.md <<'EOF'
---
task: Rate limit /login to 5 requests per minute
branch: factory/rate-limit-1
depends: src/auth/*
verify: true
---
## Intent
Add a limiter in front of the login handler.
EOF
echo limiter > src/api.ts
git add -A && git commit -qm "rate limit"

run() { "$stale" main 2>&1 || true; }

git checkout -q main && echo b2 > src/billing/invoice.ts && git commit -qam billing
git checkout -q factory/rate-limit-1
check "unrelated change on main is fresh" "rate-limit-1 fresh" "$(run)"

git checkout -q main && echo c2 > src/api.ts && git add -A && git commit -qm "touch branch file"
git checkout -q factory/rate-limit-1
check "change to a file the branch edits is stale" "rate-limit-1 stale src/api.ts" "$(run)"

git checkout -q main && git rm -q src/api.ts && git commit -qm "undo" \
  && echo a2 > src/auth/login.ts && git commit -qam "auth change"
git checkout -q factory/rate-limit-1
check "change to a declared dependency is stale" "src/auth/login.ts" "$(run)"

set +e; "$stale" main >/dev/null 2>&1; code=$?; set -e
check "stale exits 1" "1" "$code"

git checkout -q main && git checkout -qb factory/no-depends
mkdir -p .intent && printf -- '---\ntask: docs\nverify: true\n---\n' > .intent/docs.md
echo d >> README.md && git add -A && git commit -qm docs
check "record without depends still works" "docs fresh" "$(/bin/bash "$stale" main 2>&1 || true)"

git checkout -q main && git checkout -qb factory/no-intent
check "branch without intent records says so" "no intent records" "$(run)"

# Installer still links every skill into a scratch HOME.
HOME="$work/home" "$repo/install.sh" personal >/dev/null
for dir in "$repo"/skills/*/; do
  name="$(basename "$dir")"
  check "install links $name" "$repo/skills/$name" "$(readlink "$work/home/.claude/skills/$name" || true)"
done
rm -rf "$repo/.generated"

[[ $fails -eq 0 ]] && echo "all passed" || { echo "$fails failed"; exit 1; }
