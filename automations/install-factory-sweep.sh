#!/usr/bin/env bash
# Creates the factory-sweep bb automation for one project.
# Usage: automations/install-factory-sweep.sh <project-id> <model> [cron] [timezone]
#   bb project list --include-personal --json   # find the project id
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "usage: $0 <project-id> <model> [cron='*/30 9-19 * * 1-5'] [timezone=system]" >&2
  exit 1
fi

project="$1"
model="$2"
cron="${3:-*/30 9-19 * * 1-5}"
system_tz="$(readlink /etc/localtime 2>/dev/null | sed 's|.*/zoneinfo/||')"
tz="${4:-${system_tz:-UTC}}"
provider="${PROVIDER:-claude-code}"
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

bb automation create \
  --project "$project" \
  --name "factory-sweep" \
  --cron "$cron" --timezone "$tz" \
  --provider "$provider" --model "$model" --reasoning low \
  --prompt "$(cat "$here/factory-sweep.md")"
