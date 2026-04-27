#!/usr/bin/env bash
# Runs at session end. Full quality gate.
set -e

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$REPO_ROOT"

echo "→ Running lint..."
npm run lint

echo "→ Running build (includes TypeScript typecheck)..."
npm run build

# Run tests only if vitest is configured
if grep -q '"vitest"' package.json 2>/dev/null; then
  echo "→ Running tests..."
  npx vitest run
fi

echo "✓ All gates green"
