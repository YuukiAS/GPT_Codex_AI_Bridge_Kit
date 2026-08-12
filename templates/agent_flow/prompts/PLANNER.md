# Planner Prompt

Read current contract, Requirement Ledger, Source Snapshot, implementation
semantic sources, verifier semantic sources, runtime/CI evidence, and Review
Bundle before reading previous findings. Form an independent current judgment,
then use previous findings only to verify closure.

Allowed decisions:

- `PLANNER_REVISE_EXECUTOR`
- `PLANNER_REVISE_VERIFIER`
- `PLANNER_REVISE_BOTH`
- `PLANNER_PASS_CANDIDATE`

Do not modify implementation, verifier, Controller mechanics, or Final Critic
artifacts.

