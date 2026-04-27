---
name: refactor-safely
description: Refactor existing code without changing behavior. Use when the user asks to "clean up," "extract," "rename," or "restructure" code. Forbids any change that alters observable behavior.
---

# Safe Refactor

## Pre-flight (mandatory)

1. Confirm tests exist for the code being refactored. If they don't — **stop** — write characterization tests first, then refactor. (If vitest isn't configured yet, run `npm run build` as the baseline instead and proceed very carefully.)
2. Run the baseline: `npm run lint && npm run build`. Note what passes.
3. Commit (or stash) before touching anything. Refactors must be reversible in one command.

## During

- Make one refactor at a time. Rename → commit. Extract → commit. Move → commit.
- Run `npm run build` after every commit. If anything goes red, revert that commit and try smaller.
- Never combine a refactor with a behavior change in the same commit.

## After

- Diff against baseline: no test was added, removed, or modified to make a refactor pass. (If you needed to update a test, the refactor changed behavior — that's a bug, not a refactor.)
- Run `npm run lint && npm run build`. All green.
- Commit message: `refactor(<area>): <what>` — never `feat:` or `fix:`.

## Hard rules

- A refactor that requires touching tests is not a refactor.
- A refactor that "couldn't be split into commits" is too big.
