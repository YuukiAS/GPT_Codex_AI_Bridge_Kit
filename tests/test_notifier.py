from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ai_bridge_kit import notifier


def valid_brief(status: str = "complete", task_key: str = "001_done") -> dict:
    return {
        "schema": "ai-bridge.notification_brief.v1",
        "project": "demo",
        "task_key": task_key,
        "terminal_status": status,
        "key_conclusion": "Done.",
        "next_step": "Review evidence.",
        "evidence_paths": ["results/001_done/result.md"],
    }


def write_brief(root: Path, brief: dict) -> Path:
    path = root / "results" / str(brief["task_key"]) / "notification_brief.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(brief), encoding="utf-8")
    return path


class NotifierTests(unittest.TestCase):
    def test_send_terminal_brief_statuses(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sent = []

            def sender(brief, env):
                sent.append((brief, env))

            for status in ["complete", "blocked", "awaiting_human"]:
                path = write_brief(root, valid_brief(status, task_key=f"001_{status}"))
                result = notifier.send_brief(path, state_path=root / "state.json", env={}, sender=sender)
                self.assertEqual(result.status, "sent")

            self.assertEqual(len(sent), 3)

    def test_duplicate_brief_does_not_send_twice(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = write_brief(root, valid_brief())
            sent = []
            sender = lambda brief, env: sent.append(brief)

            first = notifier.send_brief(path, state_path=root / "state.json", env={}, sender=sender)
            second = notifier.send_brief(path, state_path=root / "state.json", env={}, sender=sender)

            self.assertEqual(first.status, "sent")
            self.assertEqual(second.status, "duplicate")
            self.assertEqual(len(sent), 1)

    def test_invalid_nonterminal_brief_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = write_brief(root, valid_brief("running"))
            result = notifier.send_brief(path, state_path=root / "state.json", env={}, sender=lambda brief, env: None)

            self.assertEqual(result.status, "invalid")
            self.assertIn("terminal_status", result.message)

    def test_smtp_failure_not_marked_sent_and_can_retry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = write_brief(root, valid_brief())

            failed = notifier.send_brief(
                path,
                state_path=root / "state.json",
                env={},
                sender=lambda brief, env: (_ for _ in ()).throw(OSError("smtp down")),
            )
            self.assertEqual(failed.status, "failed")
            state = json.loads((root / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["sent"], {})

            sent = []
            retried = notifier.send_brief(path, state_path=root / "state.json", env={}, sender=lambda brief, env: sent.append(brief))
            self.assertEqual(retried.status, "sent")
            self.assertEqual(len(sent), 1)

    def test_dry_run_does_not_send_or_write_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = write_brief(root, valid_brief())
            state_path = root / "state.json"
            result = notifier.send_brief(path, state_path=state_path, dry_run=True, sender=lambda brief, env: None)

            self.assertEqual(result.status, "dry_run")
            self.assertFalse(state_path.exists())

    def test_send_test_calls_backend_interface(self) -> None:
        sent = []
        result = notifier.send_test(env={}, sender=lambda brief, env: sent.append(brief))

        self.assertEqual(result.status, "sent")
        self.assertEqual(sent[0]["task_key"], "send_test")

    def test_once_first_start_baselines_without_backfill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_brief(root, valid_brief())
            sent = []
            results = notifier.notifier_once(root=root, state_path=root / "state.json", sender=lambda brief, env: sent.append(brief))

            self.assertEqual(results, [])
            self.assertEqual(sent, [])
            state = json.loads((root / "state.json").read_text(encoding="utf-8"))
            self.assertTrue(state["baseline_initialized"])
            self.assertEqual(len(state["baseline_events"]), 1)

    def test_once_after_baseline_sends_new_brief(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = root / "state.json"
            write_brief(root, valid_brief(task_key="001_old"))
            notifier.notifier_once(root=root, state_path=state_path, sender=lambda brief, env: None)
            sent = []
            write_brief(root, valid_brief(task_key="002_new"))

            results = notifier.notifier_once(root=root, state_path=state_path, sender=lambda brief, env: sent.append(brief))

            self.assertEqual([result.status for result in results], ["sent"])
            self.assertEqual(len(sent), 1)

    def test_run_is_not_default_install_requirement_and_tmux_not_needed(self) -> None:
        parser = notifier.build_parser()
        command_names = parser.format_help()

        self.assertIn("run", command_names)
        self.assertNotIn("tmux", command_names.lower())

    def test_generic_notifier_does_not_require_slurm_or_care_routes(self) -> None:
        brief = valid_brief()
        errors = notifier.validate_brief(brief)
        source = Path(notifier.__file__).read_text(encoding="utf-8")

        self.assertEqual(errors, [])
        self.assertNotIn("route_A", source)
        self.assertNotIn("route_B", source)
        self.assertNotIn("route_C", source)
        self.assertNotIn("Slurm", source)

    def test_dedup_digest_is_only_notifier_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = write_brief(root, valid_brief())
            notifier.send_brief(path, state_path=root / "state.json", env={}, sender=lambda brief, env: None)
            state_text = (root / "state.json").read_text(encoding="utf-8")

            self.assertIn("sent", state_text)
            self.assertNotIn("review_target_id", state_text)
            self.assertNotIn("provenance", state_text)
            self.assertNotIn("ledger", state_text.lower())

    def test_email_message_plain_plus_html_without_secret(self) -> None:
        env = {
            "AI_BRIDGE_NOTIFY_SMTP_USER": "sender@example.org",
            "AI_BRIDGE_NOTIFY_SMTP_PASSWORD": "secret-app-password",
            "AI_BRIDGE_NOTIFY_FROM": "sender@example.org",
            "AI_BRIDGE_NOTIFY_TO": "recipient@example.org",
        }
        message = notifier.build_email_message(valid_brief(), env)
        text = message.as_string()

        self.assertTrue(message.is_multipart())
        self.assertIn("text/plain", text)
        self.assertIn("text/html", text)
        self.assertNotIn("secret-app-password", text)

    def test_cli_send_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = write_brief(root, valid_brief())
            with contextlib.redirect_stdout(io.StringIO()) as output:
                code = notifier.main(["send", str(path), "--dry-run"])

            self.assertEqual(code, 0)
            self.assertIn("dry_run", output.getvalue())

    def test_private_secret_fixture_not_in_tracked_files(self) -> None:
        root = Path(__file__).resolve().parents[1]
        proc = subprocess.run(
            ["git", "grep", "-n", "PRIVATE_TEST_SECRET_SHOULD_NOT_APPEAR"],
            cwd=root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(proc.returncode, 1, proc.stdout)


if __name__ == "__main__":
    unittest.main()
