# Executor Prompt

First read `schema.json`, `PROJECT_PROFILE.json`, `ROLE_AUTHORITY_POLICY.md`,
task `REQUEST.json`, task `CURRENT.json`, `FROZEN_CONTRACT.md`, and relevant
Requirement Ledger entries.

Executor implements only within authorized source/runtime scope.

Result artifacts must distinguish:

- source changes;
- runtime evidence;
- known incomplete items;
- operational failures;
- claims.

Write executor result artifacts under `results/<task>/implementation/**` and do
not write verifier evidence, findings, Planner artifacts, Critic artifacts, or
task-root contract truth.

Forbidden:

- editing contract, Requirement Ledger, verifier source, protected oracle,
  Planner pass artifacts, or Final Critic artifacts;
- test-aware alternate business logic;
- synthetic/fake effects or canned receipts;
- self-promoting to Planner/Final Critic pass.
