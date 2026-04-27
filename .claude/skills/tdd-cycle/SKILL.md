---
name: tdd-cycle
description: Strict test-driven development cycle — red, green, refactor — for adding new behavior. Use when the user asks to "add a function," "implement X with tests," or works in a module with established TDD discipline. Requires vitest to be configured first (see docs/GOTCHAS.md).
---

# TDD Cycle

> **Prerequisite:** vitest must be configured. If it isn't, stop and follow the setup instructions in `docs/GOTCHAS.md` before proceeding.

For each unit of new behavior:

## RED

1. Write the test first. Make it specific: a single, observable behavior.
2. Run `npx vitest run`. **Confirm it fails for the right reason** — not because of a typo or import error.
3. If it passes immediately, the test is wrong — it's not actually testing the new behavior.

## GREEN

1. Write the minimum code to make the test pass.
2. No premature abstraction. No "while I'm here" edits.
3. Run `npx vitest run`. Confirm green.

## REFACTOR

1. With the test as a safety net, clean up.
2. Run `npx vitest run` after every meaningful change.
3. Stop when the code communicates intent clearly.

## Rules

- One behavior per cycle. If you find yourself writing two tests, do two cycles.
- Never delete a test to make a build pass. If the test is wrong, write down *why* in the commit message.
- Coverage of the new code must be complete before moving on.
- Always use `npm` / `npx` — never pnpm/yarn/bun.
