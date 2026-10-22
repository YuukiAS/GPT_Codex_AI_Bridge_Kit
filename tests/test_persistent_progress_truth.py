from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from ai_bridge_kit import persistent_run as pr
from tests import test_persistent_run


def at(seconds):
    return (datetime(2026, 10, 22, tzinfo=timezone.utc) + timedelta(seconds=seconds)).isoformat()


class PersistentProgressTruthTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", str(self.repo)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.goal = self.repo / "GOAL.md"
        self.goal.write_text("Persistent execution: REQUIRED\nBackend: tmux\nGoal source: GOAL.md\n"
                             "Run/session key: evidence\nWorking directory: .\n"
                             f"Launch argv: {json.dumps([sys.executable, '-c', 'raise SystemExit(0)'])}\n"
                             "Progress mode: count\nProgress owner: bridge-child\nProgress source locator: bridge-state\n"
                             "Expected progress update seconds: 300\nNotify: OFF\nRecipient override: NONE\n"
                             "Notification cadence minutes: 60\nExternal notification attempt cap: 6\n")
        self.digest = hashlib.sha256(self.goal.read_bytes()).hexdigest()
        self.tmux = test_persistent_run.FakeTmux()
        started = pr.start_persistent_run(self.repo, "GOAL.md", expected_goal_sha256=self.digest,
                                          state_root=self.root / "state", runner=self.tmux)
        self.path = Path(started["binding_path"])
        self.binding = json.loads(self.path.read_text())
        self.binding["child_started_at"] = at(0)
        self.binding["lifecycle_state"] = "RUNNING"
        self.source = Path(self.binding["progress_source_path"])
        self.env = {"AI_BRIDGE_PROGRESS_PATH": str(self.source), "AI_BRIDGE_PROGRESS_OWNER": "bridge-child",
                    "AI_BRIDGE_PROGRESS_MODE": "count", "AI_BRIDGE_RUN_KEY": "evidence",
                    "AI_BRIDGE_RUNTIME_ID": self.binding["launch_id"]}

    def publish(self, seconds, completed, total=12, stage="inspect"):
        with mock.patch.object(pr, "_utc_now", return_value=at(seconds)):
            payload = pr.update_run_progress(stage=stage, completed=completed, total=total, env=self.env)
            pr.observe_binding_progress(self.binding)
        return payload

    def observe(self, seconds):
        with mock.patch.object(pr, "_utc_now", return_value=at(seconds)):
            pr.observe_binding_progress(self.binding)
        return self.binding["progress_snapshot"]

    def test_controlled_clock_true_producer_eta_is_four_hundred_seconds(self):
        self.publish(0, 2)
        self.assertEqual(self.binding["last_good_progress"]["eta"], "UNKNOWN")
        self.publish(300, 5)
        self.assertEqual(self.binding["last_good_progress"]["eta"], "UNKNOWN")
        self.publish(600, 8)
        current = self.binding["last_good_progress"]
        self.assertEqual(current["eta"], at(1000))
        self.assertEqual(current["eta_low"], at(1000))
        self.assertEqual(current["eta_high"], at(1000))
        self.assertEqual(self.binding["progress_history"][-1]["eta"], current["eta"])
        self.assertEqual(len(self.binding["progress_history"]), 3)
        self.observe(601)
        self.assertEqual(len(self.binding["progress_history"]), 3)
        pr._atomic_json(self.path, self.binding)
        # A caller/source edit cannot change read-only status or manufacture a point.
        self.source.write_text('{"fake":true}')
        before = self.path.read_bytes()
        result = pr.status_persistent_run(self.repo, "GOAL.md", expected_goal_sha256=self.digest,
                                          state_root=self.root / "state", runner=self.tmux)
        self.assertEqual(result["progress"], self.binding["progress_snapshot"])
        self.assertEqual(result["progress"]["normalized"]["eta"], at(1000))
        self.assertEqual(self.path.read_bytes(), before)

    def test_plateau_is_live_producer_not_business_blocked_and_resets_warmup(self):
        for seconds, completed in [(0, 2), (300, 5), (600, 8)]:
            self.publish(seconds, completed)
        self.publish(900, 8)
        self.assertEqual(self.binding["progress_snapshot"]["state"], "AVAILABLE")
        self.assertEqual(self.binding["last_good_progress"]["eta_basis"], "VALID_PLATEAU")
        self.assertEqual(self.binding["last_good_progress"]["status"], "normal")
        self.assertEqual(self.binding["last_good_progress"]["eta"], "UNKNOWN")
        self.publish(1200, 9, stage="evaluate")
        self.assertEqual(self.binding["last_good_progress"]["eta"], "UNKNOWN")
        self.publish(1500, 10, total=20, stage="evaluate")
        self.assertEqual(self.binding["last_good_progress"]["eta"], "UNKNOWN")
        self.publish(1800, 1, total=20, stage="evaluate")
        self.assertEqual(self.binding["last_good_progress"]["eta"], "UNKNOWN")

    def test_repeated_read_does_not_refresh_source_and_overdue_keeps_last_good(self):
        for seconds, completed in [(0, 2), (300, 5), (600, 8)]:
            self.publish(seconds, completed)
        good = copy.deepcopy(self.binding["last_good_progress"])
        self.assertEqual(self.observe(1500)["state"], "AVAILABLE")
        overdue = self.observe(1501)
        self.assertEqual(overdue["state"], "PROGRESS_SOURCE_OVERDUE")
        self.assertEqual(overdue["source_published_at"], at(600))
        self.assertEqual(overdue["normalized"]["eta"], "UNKNOWN")
        self.assertEqual(self.binding["last_good_progress"], good)
        self.assertEqual(len(self.binding["progress_history"]), 3)
        self.publish(1502, 9)
        self.assertEqual(self.binding["progress_snapshot"]["state"], "AVAILABLE")
        self.assertEqual(self.binding["last_good_progress"]["eta"], "UNKNOWN")

    def test_future_wrong_run_backward_sequence_and_bad_sources_cannot_add_points(self):
        payload = self.publish(0, 2)
        good = copy.deepcopy(self.binding["last_good_progress"])
        cases = [{**payload, "observed_at": at(601)}, {**payload, "runtime_id": "b" * 64},
                 {**payload, "run_key": "other"}, {**payload, "completed": 15},
                 {**payload, "publication_sequence": -1}, {**payload, "observed_at": at(-1)},
                 {**payload, "eta": {}}, None]
        for raw in cases:
            with self.subTest(raw=raw):
                self.source.write_text(json.dumps(raw) if raw is not None else '{"half":')
                self.assertEqual(self.observe(600)["state"], "UNAVAILABLE")
                self.assertEqual(self.binding["last_good_progress"], good)
                self.assertEqual(len(self.binding["progress_history"]), 1)
        self.source.unlink()
        self.assertEqual(self.observe(600)["state"], "UNAVAILABLE")
        self.assertEqual(self.observe(901)["state"], "PROGRESS_SOURCE_OVERDUE")
        self.publish(902, 5)
        self.assertEqual(self.binding["progress_snapshot"]["state"], "AVAILABLE")

    def test_publication_sequence_must_increase_and_not_replace_observer_time(self):
        raw = self.publish(0, 2)
        raw.update(publication_sequence=1, publication_id="sequence-1", observed_at=at(300), completed=5)
        self.source.write_text(json.dumps(raw))
        self.observe(300)
        self.assertEqual(len(self.binding["progress_history"]), 2)
        raw.update(publication_id="sequence-2", observed_at=at(600), completed=8)
        self.source.write_text(json.dumps(raw))
        self.assertEqual(self.observe(600)["state"], "UNAVAILABLE")
        self.assertEqual(len(self.binding["progress_history"]), 2)
        raw["publication_sequence"] = 2
        self.source.write_text(json.dumps(raw))
        self.assertEqual(self.observe(600)["normalized"]["eta"], at(1000))

    def test_new_contract_requires_producer_interval_or_concrete_none_reason(self):
        original = self.goal.read_text()
        variants = [original.replace("Expected progress update seconds: 300", "Expected progress update seconds: UNKNOWN"),
                    original.replace("Progress owner: bridge-child", "Progress owner: project-native")
                            .replace("Progress source locator: bridge-state", "Progress source locator: progress.json"),
                    original.replace("Progress mode: count", "Progress mode: none")
                            .replace("Progress owner: bridge-child", "Progress owner: none")
                            .replace("Progress source locator: bridge-state", "Progress source locator: NONE")]
        for index, variant in enumerate(variants):
            with self.subTest(index=index):
                self.goal.write_text(variant)
                state = self.root / f"new-state-{index}"
                with self.assertRaises(pr.PersistentRunError):
                    pr.start_persistent_run(self.repo, "GOAL.md", state_root=state, runner=test_persistent_run.FakeTmux(),
                             expected_goal_sha256=hashlib.sha256(self.goal.read_bytes()).hexdigest())
                self.assertFalse(state.exists())

    def test_missing_source_from_start_becomes_overdue_and_fifo_is_nonblocking(self):
        self.assertEqual(self.observe(900)["state"], "UNAVAILABLE")
        self.assertEqual(self.observe(901)["state"], "PROGRESS_SOURCE_OVERDUE")
        os.mkfifo(self.source)
        self.assertIn("regular", self.observe(600)["reason"])

    def test_running_and_terminal_with_last_progress_are_durable_before_notification(self):
        events = []

        class Child:
            pid = 12345

            def wait(child):
                self.publish(600, 12)
                return 0

        # Use the real nonfatal notification wrapper, mock only its external call.

        def failing_external(request, **kwargs):
            saved = json.loads(self.path.read_text())
            events.append(request["fact_class"])
            self.assertEqual(saved["lifecycle_state"], "RUNNING" if request["fact_class"] == "runtime_start" else "TERMINAL")
            if request["fact_class"] == "runtime_terminal":
                self.assertEqual(saved["exit_code"], 0)
                self.assertEqual(saved["progress_snapshot"]["normalized"]["completed"], 12)
            raise RuntimeError("synthetic transport failure")

        self.binding["notify"] = "ON"
        pr._atomic_json(self.path, self.binding)
        with mock.patch.object(pr, "_utc_now", return_value=at(600)), \
             mock.patch.object(pr.subprocess, "Popen", return_value=Child()), \
             mock.patch.object(pr, "_process_identity", return_value={}), \
             mock.patch("ai_bridge_kit.notifier.deliver_notification", side_effect=failing_external):
            self.assertEqual(pr.supervise_binding(self.path, self.binding["launch_id"]), 0)
        self.assertEqual(events, ["runtime_start", "runtime_terminal"])
        final = json.loads(self.path.read_text())
        self.assertEqual(final["exit_code"], 0)
        self.assertEqual(final["last_notification"]["status"], "FAILED")


if __name__ == "__main__":
    unittest.main()
