#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
pattern='sk-[A-Za-z0-9_-]{16,}|-----BEGIN (RSA|OPENSSH|EC|DSA|PGP )?PRIVATE KEY-----|[A-Za-z_]*(API_KEY|SECRET_KEY|ACCESS_TOKEN|PASSWORD)[A-Za-z_]*[[:space:]]*[:=][[:space:]]*[^$<{[:space:]]{8,}'

if command -v rg >/dev/null 2>&1; then
    matches="$(rg -l --hidden --glob '!.git/**' --glob '!*.png' --glob '!*.jpg' --glob '!*.jpeg' --glob '!*.gif' --glob '!*.pdf' --glob '!*.db' --glob '!*.sqlite' --glob '!__pycache__/**' --glob '!.venv/**' "$pattern" "$root" || true)"
else
    matches="$(grep -RIlE --exclude-dir=.git --exclude-dir=__pycache__ --exclude-dir=.venv --exclude='*.png' --exclude='*.jpg' --exclude='*.jpeg' --exclude='*.gif' --exclude='*.pdf' --exclude='*.db' --exclude='*.sqlite' "$pattern" "$root" 2>/dev/null || true)"
fi
if [[ -n "$matches" ]]; then
    printf '%s\n' 'Potential secret-shaped values found in:' >&2
    printf '%s\n' "$matches" >&2
    exit 1
fi

printf '%s\n' 'No secret-shaped values found. Review history and binary artifacts separately before publishing.'
