---
name: wave
description: Run a feature or change through the four-phase wave method — Plan, Implement, Refine, Validate. Use for any change touching 2+ files or any feature with non-obvious design. Triggers on "/wave", "build feature", "implement", or when user describes a multi-step change.
---

# Wave Method

Execute changes in four disciplined phases. Each phase has a single deliverable, a quality gate, and a model assignment. Skipping a phase is forbidden; abbreviating one is allowed when scope is small.

## Wave 1 — PLAN (Opus via `architect` agent)

**Deliverable:** `docs/plans/<slug>.md` — a checkable plan.
**Gate:** human approval. Do not pass without explicit "approved" or `/wave approve`.

Steps:

1. Restate the goal in one sentence. If unclear, ask.
2. If scope is unclear, delegate exploration to `explorer`.
3. Invoke `architect` with the goal and any explorer findings.
4. Present the plan path to the user. Stop.

## Wave 2 — IMPLEMENT (Sonnet via `implementer` agent)

**Deliverable:** code changes that satisfy each plan step's success criterion.
**Gate:** `test-runner` reports PASS after each step.

Steps:

1. Read the approved plan.
2. For each step in order:
   a. Invoke `implementer` with the plan path and step number.
   b. Invoke `test-runner` with the step's verification command.
   c. If PASS → continue. If FAIL → invoke `implementer` once more with the failure output. If FAIL again → stop, report BLOCKED, ask the human.
3. After the last step, run the full suite via `test-runner`: `npm run lint && npm run build`.

## Wave 3 — REFINE (Sonnet via `reviewer` agent)

**Deliverable:** clean diff, no dead code, no TODOs without tickets, no hacks left over from getting things green.
**Gate:** all "Must fix" items resolved.

Steps:

1. Invoke `reviewer` on the diff.
2. For each "Must fix": invoke `implementer` to fix, then `test-runner` to verify.
3. If `reviewer` flags risk in sensitive code (API keys, external calls, auth), escalate to `adversary`.
4. Re-run `reviewer` until verdict is APPROVE.

## Wave 4 — VALIDATE (Opus via `adversary` agent)

**Deliverable:** confidence that the implementation actually solves the original problem.
**Gate:** success criteria from the plan are verified, `adversary` finds no critical/high issues.

Steps:

1. Walk through each success criterion from the plan. Run the literal check (curl, browser, `npm run build`).
2. Invoke `adversary` for a red-team pass on the final diff.
3. Resolve any critical/high findings (back to Wave 2 if needed).
4. Report final status: plan link, diff summary, criteria checked, adversary findings, go/no-go.

## Abbreviation rules

- **One-file, <20 line fix:** plan = one sentence in chat. Skip Wave 4. Still run Wave 3 review.
- **New feature, any size:** all four waves, no exceptions.
- **Anything touching API keys, secrets, or external service calls:** all four waves, Wave 4 mandatory.
- **Refactor (no behavior change):** Plan + Implement + Validate. Skip Wave 3 only if diff is small.

## Anti-patterns

- Compressing the four waves into one prompt. The whole point is the gates.
- Using `architect` (Opus) for the implementation. Wasteful and slower.
- Skipping Wave 4 because "build passes." Build passing means you didn't break what you tested. Validation is whether you solved the actual problem.
- Letting `implementer` make scope decisions. If the plan is wrong, fix the plan, don't ad-lib code.
