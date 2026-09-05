# Mechanism Gate Template

Use this file as the single generic Goal Fidelity and evidence-gate pattern.
Project-specific repositories should define their own domain gates in
`AGENTS.md`, project rules, or skills, then reference those gates from task
frontmatter.

## Gate Name

`<gate-name>`

## Mechanism Class

`<bugfix | feature | refactor | documentation | release | audit | experiment | other>`

## Positive Completion

- What original user-visible, repository-visible, product, scientific, or
  operational result must actually be achieved?
- Which observable outcome would make the user say the requested task, not a
  nearby easier task, is complete?
- Which mechanics are only supporting evidence? Tests, CI, file existence,
  command success, green validators, or lack of bad patterns do not by
  themselves prove completion unless the requested task is exactly that
  mechanism.

## Claim Scope

- What claim may be made if only smoke tests pass?
- What claim may be made if evidence uses synthetic/toy data instead of the
  requested real data?
- What claim may be made if only helper code, local output, or a partial artifact
  was exercised rather than the production/user-facing entry?
- The final result must not claim more than the evidence directly supports.

## Non-Substitutable Semantics

- Which data, method, model/source, scale, execution entry, renderer, artifact,
  budget, or quality bar makes this the same task?
- Codex must not silently replace those semantics with weaker, cheaper, toy,
  synthetic, proxy, helper-only, handmade, reduced-scale, random/untrained, or
  blacklist-only work.
- A fallback only earns original completion credit when the GPT-authored task or
  Plan explicitly states it is equivalent and names the evidence required to
  prove that equivalence. Otherwise it is diagnostic or partial evidence only.

## Required Evidence

- Direct positive-completion evidence:
- File or diff evidence:
- Command evidence with exit status:
- Test or validation evidence:
- Artifact or manifest evidence:
- User-facing, Text Review, Visual Review, or human-gate evidence when needed:
- Claim-scope limit if evidence is partial:

## Known Forbidden Substitutes

- Workarounds that look similar but do not satisfy the goal.
- Cosmetic edits that do not affect the required behavior.
- Evidence from unrelated files, stale logs, unreviewed self-assessment, or a
  narrower helper path.
- `没有命中 blacklist != goal completed.`

## Promotion Gate

Promotion is allowed only when the actual positive completion result is
supported by evidence, all non-substitutable semantics are preserved or
explicitly authorized as equivalent, every final claim stays within evidence
scope, and the auditor decision is `AUDITED_GO` or the task explicitly waives
review.

## Failure Escalation Policy

- What can the execution controller try within this task?
- What degraded, diagnostic, fallback, proxy, or partial path may be recorded
  only as incomplete evidence?
- What must stop and return `NEEDS_GPT_PLANNER`?
- What requires human approval?
