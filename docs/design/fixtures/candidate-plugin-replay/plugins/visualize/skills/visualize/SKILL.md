---
name: visualize
description: "Use for Bridge Kit Phase 0 candidate plugin replay runtime probes when the user asks for candidate runtime proof, phase0 candidate marker, or bridge kit candidate plugin probe evidence."
---

# Bridge Kit Phase 0 Candidate Visualize Fixture

When asked for Bridge Kit Phase 0 candidate plugin replay runtime proof, respond
with exactly this marker and no extra prose:

```text
AI_BRIDGE_PHASE0_CANDIDATE_VISUALIZE_MARKER_20260908
```

This fixture is intentionally harmless. It exists only to prove that a fresh
Codex runtime consumed the candidate plugin selected for the probe, instead of
the pre-existing installed `visualize` plugin from another marketplace.
