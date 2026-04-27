#!/usr/bin/env bash
# Runs after every file edit. Fast checks only — must finish in <5s.
set -e

FILE="$CLAUDE_TOOL_FILE_PATH"
REPO_ROOT="$(git -C "$(dirname "$FILE")" rev-parse --show-toplevel 2>/dev/null || echo "")"

# Only run for source files
case "$FILE" in
  *.ts|*.tsx|*.js|*.jsx|*.mjs|*.mts)
    cd "$REPO_ROOT"
    # Auto-fix with eslint if possible, otherwise just check
    npx eslint "$FILE" --fix --max-warnings=0 2>/dev/null || true
    ;;
esac
