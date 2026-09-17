# AGENTS.md

This file is the repository-level instruction surface for Codex and other
agents. Fill in project-specific facts as they become stable; do not invent
facts only to satisfy this scaffold.

## Source Of Truth

- Start with the user's current request.
- Then read this file and the task named by the user.
- For Lite Handoff execution rules, read `prompts/AGENT_RULES.md`.
- For GPT planning or review rules, read `prompts/CHATGPT_RULES.md`.

## Project Scope

- Define the product, research, or library purpose here.
- Name any durable non-goals, protected data, or human-approval boundaries.
- Link deeper architecture, design, operations, testing, or release docs instead
  of copying their full contents into this root file.

## Development And Git

- Record the canonical branch, integration path, and ordinary commit policy for
  this repository.
- Preserve unrelated user work. Do not reset, clean, force-push, rewrite
  history, or change remotes unless the current user request explicitly permits
  it.

## Testing And Acceptance

- Name the smallest reliable checks for routine changes.
- Name any final user-visible, rendered, device, release, or external-service
  evidence required before reporting completion.

## Version And Release

- If this repository has an explicit local versioning policy, link it here.
- Otherwise follow the Lite fallback policy in `prompts/AGENT_RULES.md`.
- Keep version, source, changelog, package metadata, and user-facing release
  identity truthful before claiming release-ready status.

## Deeper Documentation

- Add stable locators for architecture, design, runtime operations, safety,
  data handling, testing, deployment, and release docs as the project matures.
