---
name: debug-systematically
description: Structured debugging for non-obvious bugs. Use when the user reports a bug they couldn't fix in 10 minutes, or describes intermittent or environment-dependent failures.
---

# Systematic Debug

The mistake people make is jumping to "fix" before they understand. We slow down on purpose.

## 1. Reproduce

- Get a deterministic repro. If it's intermittent, narrow until it's deterministic — different inputs, different env vars, different route.
- Write the repro down (curl command, steps, URL). It is your contract.
- For Next.js: note whether the bug is server-side (SSR/RSC) or client-side. Check both browser console and terminal output.

## 2. Bisect

- Find the boundary: the smallest change between "works" and "broken." Git bisect, input bisect, or commenting out code.
- The boundary is your suspect.

## 3. Form a hypothesis

- Write it as: "I think X happens because Y, and the evidence is Z."
- If you can't write that sentence, you don't have a hypothesis — you have a guess.

## 4. Test the hypothesis

- Add the *minimum* observation needed: one `console.log`, one early return, one assertion.
- Confirm or reject. If rejected, back to step 3.

## 5. Fix

- The fix is the smallest change that makes the repro pass and doesn't break neighbors.
- Run `npm run lint && npm run build` after the fix.
- Add a regression test using the repro from step 1 (if vitest is configured).

## Anti-patterns

- Changing five things at once.
- Fixing what looks wrong nearby.
- Calling it fixed when "it works on my machine."
- Removing the symptom (the error message) instead of the cause.
- Assuming the bug is in your code — check Next.js 16 breaking changes in `docs/GOTCHAS.md` first.
