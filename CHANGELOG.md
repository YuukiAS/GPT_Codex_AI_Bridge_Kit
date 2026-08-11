# Changelog

## 0.3.1

- Change Generic Notifier email subjects and bodies to Chinese-first narrative
  by default while preserving technical literals such as task keys, file paths,
  branch names, and commit/push status values.

## 0.3.0

- Add Generic Notifier with one-shot terminal brief sends, optional polling,
  local dedup/retry state, dry-run, and Gmail SMTP STARTTLS email.
- Add pull-only private notifier config sync from an existing rclone source.
- Add public notifier/private templates and shared Codex config profile docs.
- Keep Lite Handoff backward compatible.
- Keep Agent-Flow v3 as design-only TODO pending CARE closure.
- Record redacted real Gmail notifier E2E receipt in
  `docs/releases/0.3.0_notifier_e2e_redacted.json`.
