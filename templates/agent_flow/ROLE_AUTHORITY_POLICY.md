# Role Authority Policy

Agent-Flow uses exactly five logical roles: Planner, Critic, Controller,
Verifier, and Executor.

Planner owns user/product/scientific intent, contract interpretation,
implementation review, typed repair direction, and `PLANNER_PASS_CANDIDATE`.
Planner does not modify implementation or verifier sources.

Critic participates only for required initial audit, required contract review,
and required final audit. Final Critic has no implementation or verifier write
authority and can only emit `CRITIC_FINAL_PASS` or `CRITIC_FINAL_REVISE`.

Controller is mechanical. It reads typed state, classifies changes, routes typed
findings, and executes the minimum control-plane transition. It does not create
domain requirements, thresholds, branch topology, or user scientific/product
choices.

Verifier owns tests, known-bads, mutations, diagnostics, independent oracles,
and verification receipts derived from frozen requirements. Blocking findings
must cite frozen Requirement Ledger entries.

Executor owns implementation and authorized runtime evidence. It cannot edit
the contract, Requirement Ledger, verifier, protected oracle, or Final Critic
artifacts, and cannot self-promote to pass.

