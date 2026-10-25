#!/usr/bin/env bash
# Installs the playbook for bb, Claude Code, and Codex on this machine.
# Usage: ./install.sh <profile>      e.g. ./install.sh personal | ./install.sh work
#        ./install.sh --uninstall
#
# Re-run after `git pull` to pick up profile changes; skills are symlinked, so
# edits to skills/ take effect immediately.
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
built="$repo/.generated/AGENTS.md"
marker="# agent-playbook (managed by $repo/install.sh)"
skill_roots=("$HOME/.agents/skills" "$HOME/.claude/skills")

# Replace target with a symlink to source, backing up a real file once.
link() {
  local source="$1" target="$2"
  mkdir -p "$(dirname "$target")"
  if [[ -L "$target" ]]; then
    rm "$target"
  elif [[ -e "$target" ]]; then
    mv "$target" "$target.pre-playbook.bak"
    echo "  backed up $target -> $target.pre-playbook.bak"
  fi
  ln -s "$source" "$target"
  echo "  $target -> $source"
}

unlink_ours() {
  local target="$1"
  if [[ -L "$target" && "$(readlink "$target")" == "$repo"/* ]]; then
    rm "$target"
    echo "  removed $target"
    [[ -e "$target.pre-playbook.bak" ]] && mv "$target.pre-playbook.bak" "$target" && echo "  restored $target"
  fi
  return 0
}

claude_md="$HOME/.claude/CLAUDE.md"

if [[ "${1:-}" == "--uninstall" ]]; then
  unlink_ours "$HOME/.bb/AGENTS.md"
  unlink_ours "$HOME/.codex/AGENTS.md"
  for root in "${skill_roots[@]}"; do
    for dir in "$repo"/skills/*/; do unlink_ours "$root/$(basename "$dir")"; done
  done
  if [[ -f "$claude_md" ]] && grep -qF "$marker" "$claude_md"; then
    grep -vF -e "$marker" -e "@$built" "$claude_md" > "$claude_md.tmp" && mv "$claude_md.tmp" "$claude_md"
    echo "  removed import from $claude_md"
  fi
  exit 0
fi

profile="${1:-}"
if [[ -z "$profile" || ! -f "$repo/profiles/$profile.md" ]]; then
  echo "usage: $0 <profile> | --uninstall" >&2
  echo "profiles: $(ls "$repo/profiles" | grep -v '\.local\.md$' | sed 's/\.md$//' | tr '\n' ' ')" >&2
  exit 1
fi

echo "Building instructions ($profile)"
mkdir -p "$repo/.generated"
{
  cat "$repo/AGENTS.md"
  echo
  cat "$repo/profiles/$profile.md"
  local_overlay="$repo/profiles/$profile.local.md"
  if [[ -f "$local_overlay" ]]; then echo; cat "$local_overlay"; fi
} > "$built"
echo "$profile" > "$repo/.generated/profile"

echo "Instructions"
link "$built" "$HOME/.bb/AGENTS.md"       # every bb thread, any provider
link "$built" "$HOME/.codex/AGENTS.md"    # Codex outside bb
# Claude Code outside bb: import into CLAUDE.md rather than replacing it.
mkdir -p "$(dirname "$claude_md")"
touch "$claude_md"
if ! grep -qF "$marker" "$claude_md"; then
  printf '\n%s\n@%s\n' "$marker" "$built" >> "$claude_md"
  echo "  added import to $claude_md"
fi

echo "Skills"
for root in "${skill_roots[@]}"; do
  for dir in "$repo"/skills/*/; do
    link "${dir%/}" "$root/$(basename "$dir")"
  done
done

echo "Done. Start a new session to load the playbook."
