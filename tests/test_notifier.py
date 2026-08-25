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
        "key_conclusion": "任务已经完成，关键证据齐全。",
        "next_step": "查看证据后决定下一步。",
        "evidence_paths": ["results/001_done/result.md"],
    }


def structured_brief(event_type: str = "milestone", authority: str = "Reviewer", task_key: str = "001_stage") -> dict:
    return {
        "schema": "ai-bridge.notification_brief.v2",
        "project": "demo",
        "task_key": task_key,
        "event_type": event_type,
        "status": "Stage 3 已通过" if event_type == "milestone" else "BLOCKED",
        "decision_authority": authority,
        "key_conclusion": "CUHK scientific layouts 已通过逐页视觉验收。",
        "next_step": "无需操作，Stage 4 已继续。",
        "action_required": False,
        "evidence_paths": ["results/001_stage/visual_review/VISUAL_REVIEW.json"],
    }


def write_brief(root: Path, brief: dict) -> Path:
    path = root / "results" / str(brief["task_key"]) / "notification_brief.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(brief), encoding="utf-8")
    return path


def write_notification(root: Path, brief: dict, name: str = "stage_3_pass.json") -> Path:
    path = root / "results" / str(brief["task_key"]) / "notifications" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(brief, ensure_ascii=False), encoding="utf-8")
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
        plain = notifier.render_plain(valid_brief())
        decoded_parts = "\n".join(part.get_content() for part in message.iter_parts())

        self.assertTrue(message.is_multipart())
        self.assertIn("完成：001_done", message["Subject"])
        self.assertTrue(plain.startswith("状态：完成（complete）"))
        self.assertIn("结论：任务已经完成", plain)
        self.assertIn("你现在需要做什么：查看证据后决定下一步。", plain)
        self.assertIn("可检查", plain)
        self.assertIn("results/001_done/result.md", plain)
        self.assertNotIn("Conclusion:", plain)
        self.assertNotIn("Next step:", plain)
        self.assertIn("text/plain", text)
        self.assertIn("text/html", text)
        self.assertIn("结论", decoded_parts)
        self.assertNotIn("secret-app-password", text)

    def test_blocked_subject_is_chinese_and_literals_preserved(self) -> None:
        env = {
            "AI_BRIDGE_NOTIFY_SMTP_USER": "sender@example.org",
            "AI_BRIDGE_NOTIFY_FROM": "sender@example.org",
            "AI_BRIDGE_NOTIFY_TO": "recipient@example.org",
            "AI_BRIDGE_NOTIFY_SUBJECT_PREFIX": "[CARE]",
        }
        brief = valid_brief("blocked", "care-ase-faithful")
        brief.update(
            {
                "commit_status": "complete_before_notifier",
                "push_status": "complete_before_notifier",
                "branch": "develop",
                "details": "packet 未记录 Slurm ledger/finalizer_state",
            }
        )
        subject = notifier.subject_for_brief(brief, env)
        plain = notifier.render_plain(brief)

        self.assertEqual(subject, "[CARE] 阻塞：care-ase-faithful")
        self.assertIn("状态：阻塞（blocked）", plain)
        self.assertIn("commit：complete_before_notifier", plain)
        self.assertIn("push：complete_before_notifier", plain)
        self.assertIn("branch：develop", plain)
        self.assertIn("packet 未记录 Slurm ledger/finalizer_state", plain)

    def test_planner_reviewer_structured_notifications_send_through_generic_notifier(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sent = []
            for authority in ["Planner", "Reviewer"]:
                path = write_notification(root, structured_brief(authority=authority, task_key=f"001_{authority.lower()}"))
                result = notifier.send_brief(path, state_path=root / "state.json", env={}, sender=lambda brief, env: sent.append(brief))
                self.assertEqual(result.status, "sent")

            self.assertEqual([brief["decision_authority"] for brief in sent], ["Planner", "Reviewer"])

    def test_milestone_notification_is_non_blocking_and_deduped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = write_notification(root, structured_brief())
            sent = []

            first = notifier.send_brief(path, state_path=root / "state.json", env={}, sender=lambda brief, env: sent.append(brief))
            second = notifier.send_brief(path, state_path=root / "state.json", env={}, sender=lambda brief, env: sent.append(brief))
            plain = notifier.render_plain(structured_brief())

            self.assertEqual(first.status, "sent")
            self.assertEqual(second.status, "duplicate")
            self.assertEqual(len(sent), 1)
            self.assertIn("状态：Stage 3 已通过", plain)
            self.assertIn("事件：里程碑", plain)
            self.assertIn("你现在需要做什么：无需操作，Stage 4 已继续。", plain)

    def test_once_scans_milestone_notifications_after_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = root / "state.json"
            write_brief(root, valid_brief(task_key="001_old"))
            notifier.notifier_once(root=root, state_path=state_path, sender=lambda brief, env: None)
            sent = []
            write_notification(root, structured_brief(task_key="002_stage"))

            results = notifier.notifier_once(root=root, state_path=state_path, sender=lambda brief, env: sent.append(brief))

            self.assertEqual([result.status for result in results], ["sent"])
            self.assertEqual(sent[0]["event_type"], "milestone")

    def test_operational_failure_can_be_sent_by_machine_layer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            brief = structured_brief(event_type="operational_blocked", authority="Watcher", task_key="001_blocked")
            brief["key_conclusion"] = "Reviewed Handoff watcher exhausted bounded Executor attempts."
            brief["next_step"] = "检查 watcher log 后恢复同一 task。"
            path = write_notification(root, brief, "watcher_blocked.json")

            result = notifier.send_brief(path, state_path=root / "state.json", env={}, sender=lambda brief, env: None)

            self.assertEqual(result.status, "sent")
            self.assertIn("运行阻塞", notifier.render_plain(brief))

    def test_executor_cannot_forge_semantic_pass_notification(self) -> None:
        brief = structured_brief(event_type="milestone", authority="Executor")
        brief["status"] = "Stage PASS"

        errors = notifier.validate_brief(brief)

        self.assertTrue(any("semantic notification decision_authority" in error for error in errors))

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
        marker = "PRIVATE_TEST_SECRET_" + "SHOULD_NOT_APPEAR"
        proc = subprocess.run(
            ["git", "grep", "-n", marker],
            cwd=root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(proc.returncode, 1, proc.stdout)

    def test_structured_milestone_template_validates(self) -> None:
        root = Path(__file__).resolve().parents[1]
        brief = notifier.load_json(root / "templates" / "notifier" / "notification_milestone.example.json")

        self.assertEqual(notifier.validate_brief(brief), [])


if __name__ == "__main__":
    unittest.main()
