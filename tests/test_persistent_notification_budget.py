from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from ai_bridge_kit import notifier, persistent_run as pr
from tests import test_notifier, test_persistent_run
from tests.test_persistent_progress_truth import at


class PersistentNotificationBudgetTests(unittest.TestCase):
    """Production start/supervisor/reservation/Notifier, fake external boundaries."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", str(self.repo)], check=True, capture_output=True)
        machine, self.config = test_notifier.NotifierTests().machine_config(self.root)
        self.state = machine
        goal = self.repo / "GOAL.md"
        goal.write_text("Persistent execution: REQUIRED\nBackend: tmux\nGoal source: GOAL.md\n"
                        "Run/session key: budget\nWorking directory: .\n"
                        f"Launch argv: {json.dumps([sys.executable, '-c', 'import time; time.sleep(.1)'])}\n"
                        "Progress mode: count\nProgress owner: bridge-child\nProgress source locator: bridge-state\n"
                        "Expected progress update seconds: 300\nNotify: ON\nRecipient override: NONE\n"
                        "Notification cadence minutes: 60\nExternal notification attempt cap: 6\n")
        self.tmux = test_persistent_run.FakeTmux()
        with mock.patch.object(notifier, "require_notifier_ready"):
            started = pr.start_persistent_run(self.repo, "GOAL.md", state_root=machine, runner=self.tmux,
                        expected_goal_sha256=hashlib.sha256(goal.read_bytes()).hexdigest())
        self.path = Path(started["binding_path"])
        self.initial = json.loads(self.path.read_text())
        self.captured = []
        self.helper_count = 0
        self.smtp_count = 0

    def run_chain(self, *, fail=False, crash=False, unknown=False):
        now = [0]
        actual_popen = subprocess.Popen

        def child_popen(argv, **kwargs):
            child = actual_popen(argv, **kwargs)
            self.child_pid = child.pid

            class ControlledWait:
                pid = child.pid
                poll = child.poll

                def wait(adapter, timeout=None):
                    if now[0] < 7 * 300:
                        now[0] += 300
                        # Real production producer publication; every stage is material.
                        with mock.patch.object(pr, "_utc_now", return_value=at(now[0])):
                            pr.update_run_progress(stage=f"stage-{now[0]}", completed=now[0] // 300, total=12,
                                                   env=kwargs["env"])
                        raise subprocess.TimeoutExpired(argv, timeout)
                    return child.wait(timeout=5)

            return ControlledWait()

        def smtp(*_args, **_kwargs):
            self.smtp_count += 1
            if unknown:
                raise SystemExit("synthetic helper lost during transport")
            if fail:
                raise OSError("synthetic SMTP unknown")

        def helper_popen(argv, **_kwargs):
            self.helper_count += 1
            directory = Path(argv[argv.index("--event-dir") + 1])
            claim = notifier.load_json(directory / "claim.json")
            saved = json.loads(self.path.read_text())
            self.assertTrue(any(s["source_event_id"] == claim["request"]["source_event_id"]
                                for s in saved["notification_slots"]))
            self.captured.append((copy.deepcopy(claim), directory))
            if crash:
                # Even a helper that dies before recording an attempt consumes its slot.
                return SimpleNamespace(wait=lambda **_: 1, returncode=1)
            try:
                notifier.deliver_event_inline(directory, config=self.config, state_root=self.state,
                    expression_runner=lambda *_a, **_k: SimpleNamespace(returncode=0, stdout='{"plugins": []}'),
                    sender=smtp)
            except SystemExit:
                class LostHelper:
                    returncode = -15
                    waits = 0

                    def wait(helper, **kwargs):
                        helper.waits += 1
                        if helper.waits == 1:
                            raise subprocess.TimeoutExpired(argv, kwargs["timeout"])
                        return -15

                    def terminate(helper):
                        pass

                return LostHelper()
            return SimpleNamespace(wait=lambda **_: 0, returncode=0)

        real_delivery = notifier.deliver_notification

        def delivery(request, **kwargs):
            # Readiness/config are fixtures; all budget/claim/helper guards are production.
            return real_delivery(request, **kwargs, config=self.config, require_ready=False,
                                 config_root=self.state, popen=helper_popen)

        with mock.patch.object(pr, "_utc_now", side_effect=lambda: at(now[0])), \
             mock.patch.object(pr.subprocess, "Popen", side_effect=child_popen), \
             mock.patch.object(notifier, "deliver_notification", side_effect=delivery):
            self.assertEqual(pr.supervise_binding(self.path, self.initial["launch_id"], observation_seconds=.01), 0)
        final = json.loads(self.path.read_text())
        self.assertEqual(final["child_pid"], self.child_pid)
        self.assertEqual(final["lifecycle_state"], "TERMINAL")
        self.assertEqual(final["exit_code"], 0)
        self.assertEqual(final["notification_general_slots_used"], 5)
        self.assertTrue(final["notification_terminal_slot_used"])
        self.assertEqual(len(final["notification_slots"]), 6)
        self.assertGreaterEqual(final["notification_suppressed_count"], 1)
        self.assertEqual(self.helper_count, 6)
        self.assertEqual([c[0]["budget_permit"]["slot_id"] for c in self.captured], [1, 2, 3, 4, 5, 6])
        self.assertEqual(self.captured[-1][0]["request"]["fact_class"], "runtime_terminal")
        self.assertNotIn("budget_permit", self.captured[-1][0]["request"])
        return final

    def test_five_general_plus_terminal_and_no_seventh_helper_with_real_child(self):
        final = self.run_chain()
        self.assertEqual(self.smtp_count, 6)
        for claim, directory in self.captured:
            with mock.patch.object(notifier, "_run_delivery_helper") as helper:
                result = notifier.retry_event(claim["event_key"], state_root=self.state,
                                               confirm_possible_duplicate=True)
                self.assertEqual(result.status, "NOT_RETRYABLE")
                helper.assert_not_called()
        before = self.path.read_bytes()
        self.tmux.sessions.clear()
        goal = self.repo / "GOAL.md"
        resumed = pr.start_persistent_run(self.repo, "GOAL.md", state_root=self.state, runner=self.tmux,
                         expected_goal_sha256=hashlib.sha256(goal.read_bytes()).hexdigest())
        self.assertEqual(resumed["status"], "ALREADY_TERMINAL")
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(final["progress_snapshot"]["normalized"]["completed"], 7)

    def test_failure_unknown_and_crashed_helper_never_refund_or_retry(self):
        self.run_chain(fail=True, crash=True)
        self.assertEqual(self.smtp_count, 0)
        claim, directory = self.captured[0]
        self.assertEqual(notifier.retry_event(claim["event_key"], state_root=self.state).status, "NOT_RETRYABLE")
        # Claim already exists after helper loss: same delivery cannot re-enter helper.
        with mock.patch.object(notifier, "_run_delivery_helper") as helper:
            result = notifier.deliver_notification(claim["request"], repo_identity=str(self.repo),
                budget_permit=claim["budget_permit"], state_root=self.state, config=self.config, require_ready=False)
            self.assertEqual(result.status, "in_progress_or_requires_retry")
            helper.assert_not_called()

    def test_transport_unknown_retains_all_slots_and_child_exit(self):
        self.run_chain(unknown=True)
        self.assertEqual(self.smtp_count, 6)
        for claim, directory in self.captured:
            self.assertEqual(notifier.load_json(directory / "latest.json")["stage"], "DELIVERY_UNKNOWN")
            self.assertEqual(notifier.retry_event(claim["event_key"], state_root=self.state).status, "NOT_RETRYABLE")

    def test_transport_failure_retains_all_slots_and_child_exit(self):
        self.run_chain(fail=True)
        self.assertEqual(self.smtp_count, 6)
        for claim, directory in self.captured:
            self.assertEqual(notifier.load_json(directory / "latest.json")["stage"], "FAILED")
            self.assertEqual(notifier.retry_event(claim["event_key"], state_root=self.state).status, "NOT_RETRYABLE")

    def test_missing_wrong_identity_slot_goal_or_locator_blocks_before_helper(self):
        self.run_chain()
        claim, _ = self.captured[0]
        permit = claim["budget_permit"]
        for wrong in [None, {**permit, "launch_id": "0" * 64}, {**permit, "goal_sha256": "0" * 64},
                      {**permit, "slot_id": 6}, {**permit, "binding_locator": str(self.root / "fake.json")},
                      {**permit, "no_retry": False}]:
            with self.subTest(permit=wrong), mock.patch.object(notifier, "_run_delivery_helper") as helper:
                result = notifier.deliver_notification(claim["request"], repo_identity=str(self.repo),
                    budget_permit=wrong, state_root=self.state, config=self.config, require_ready=False)
                self.assertEqual(result.status, "NOTIFICATION_BUDGET_UNVERIFIABLE")
                helper.assert_not_called()


if __name__ == "__main__":
    unittest.main()
