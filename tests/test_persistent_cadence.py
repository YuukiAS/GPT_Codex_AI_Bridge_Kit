from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from ai_bridge_kit import persistent_run as pr


def timestamp(minutes: float) -> str:
    return (datetime(2026, 10, 21, tzinfo=timezone.utc) + timedelta(minutes=minutes)).isoformat()


def point(minutes: float, **changes):
    return pr.normalize_progress_evidence({
        "run_locator": "public-synthetic-cadence",
        "stage": "fit", "status": "normal", "observed_at": timestamp(minutes),
        "fraction": 0.1, **changes,
    })


class PersistentCadenceTests(unittest.TestCase):
    def test_frequent_fraction_and_count_observations_do_not_spam_or_starve(self):
        for mode in ("fraction", "count"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                source = root / "progress.json"
                reports = []
                for minute in range(0, 66, 5):
                    value = min(0.1 + minute / 50, 0.9)
                    fields = {"fraction": value} if mode == "fraction" else {"completed": int(value * 100), "total": 100}
                    source.write_text(json.dumps(point(minute, **fields)), encoding="utf-8")
                    reports.append(pr.report_progress_file(source, state_root=root / "state"))
                delivered = [(i * 5, r["delivery_reason"]) for i, r in enumerate(reports) if r["delivery_decision"] == "deliver"]
                self.assertEqual(delivered, [(0, "start_or_resume"), (60, "cadence_interval")])
                self.assertTrue(all(r["delivery_decision"] == "suppress" for r in reports[1:12]))
                self.assertEqual(reports[11]["last_logical_delivery_at"], timestamp(0))
                self.assertEqual(reports[11]["normalized"]["observed_at"], timestamp(55))
                self.assertEqual(reports[-1]["last_logical_delivery_at"], timestamp(60))
                history = Path(reports[-1]["history_path"]).read_text().splitlines()
                self.assertEqual(len(history), 14)
                self.assertEqual(pr.latest_report_for_progress(source, state_root=root / "state")["normalized"], reports[-1]["normalized"])

    def test_early_stage_and_exceptional_status_transitions(self):
        baseline = point(0)
        for fields, reason in [({"stage": "evaluate"}, "stage_transition"), *[
            ({"status": status}, "status_" + status) for status in ("stalled", "blocked", "failed", "complete")
        ]]:
            with self.subTest(fields=fields):
                current = point(5, **fields)
                self.assertEqual(pr._delivery_decision(baseline, current, interval_seconds=3600, last_delivered=baseline), ("deliver", reason))
                self.assertEqual(pr._delivery_decision(current, point(10, **fields), interval_seconds=3600, last_delivered=current), ("suppress", "duplicate_or_non_material"))
        # Returning to healthy progress and stalling again is a fresh transition,
        # even though the last delivered status was also stalled.
        self.assertEqual(pr._delivery_decision(point(10), point(15, status="stalled"), interval_seconds=3600,
                                             last_delivered=point(5, status="stalled")), ("deliver", "status_stalled"))

    def test_eta_materiality_uses_last_delivery_and_preserves_threshold(self):
        baseline = point(0, eta=timestamp(120), eta_basis="synthetic rate")
        for finish, expected in [(125, "suppress"), (148, "suppress"), (149, "deliver")]:
            with self.subTest(finish=finish):
                current = point(5, eta=timestamp(finish), eta_basis="synthetic rate")
                self.assertEqual(pr._delivery_decision(point(4, eta=timestamp(125), eta_basis="synthetic rate"), current,
                                                     interval_seconds=3600, last_delivered=baseline)[0], expected)
        near = point(0, eta=timestamp(30), eta_basis="synthetic rate")
        for finish, expected in [(44, "suppress"), (45, "deliver")]:
            self.assertEqual(pr._delivery_decision(near, point(5, eta=timestamp(finish), eta_basis="rate"),
                                                 interval_seconds=3600, last_delivered=near)[0], expected)
        unknown = point(5)
        self.assertEqual(pr._delivery_decision(baseline, unknown, interval_seconds=3600, last_delivered=baseline), ("deliver", "eta_changed"))
        self.assertEqual(pr._delivery_decision(unknown, baseline, interval_seconds=3600, last_delivered=unknown), ("deliver", "eta_changed"))

    def test_early_delivery_restarts_cadence_not_observation(self):
        delivered = point(10, stage="evaluate")
        previous = point(65, stage="evaluate", fraction=0.8)
        for minute, expected in [(69, "suppress"), (70, "deliver")]:
            self.assertEqual(pr._delivery_decision(previous, point(minute, stage="evaluate", fraction=0.9),
                                                 interval_seconds=3600, last_delivered=delivered)[0], expected)

    def test_report_enforces_fifteen_minute_floor_and_reads_old_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "progress.json"
            source.write_text(json.dumps({**point(0), "report_interval_seconds": 1}))
            first = pr.report_progress_file(source, state_root=root / "state")
            self.assertEqual(first["report_interval_seconds"], 900)
            old = json.loads(Path(first["latest_path"]).read_text())
            old.pop("last_logical_delivery")
            old.pop("last_logical_delivery_at")
            Path(first["latest_path"]).write_text(json.dumps(old))
            for minute, expected in [(5, "suppress"), (15, "deliver")]:
                source.write_text(json.dumps({**point(minute, fraction=0.5), "report_interval_seconds": 1}))
                self.assertEqual(pr.report_progress_file(source, state_root=root / "state")["delivery_decision"], expected)

    def test_supervisor_uses_delivery_clock_and_terminal_survives_transport_failure(self):
        for frozen_source in (False, True):
            with self.subTest(frozen_source=frozen_source), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                binding_path = root / "binding.json"
                launch = "a" * 64
                binding = {"launch_id": launch, "session_name": "ai-bridge-pr-" + launch,
                           "working_directory": str(root), "repo_realpath": str(root),
                           "launch_argv": ["synthetic-child"], "run_key": "synthetic",
                           "notification_cadence_minutes": 60, "notify": "ON", "recipient_override": ""}
                pr._atomic_json(binding_path, binding)
                clock = {"minute": 0}

                class Child:
                    pid = 12345
                    poll = None

                    def wait(self, timeout=None):
                        clock["minute"] += 5
                        if clock["minute"] <= 65:
                            raise subprocess.TimeoutExpired("synthetic-child", timeout)
                        return 0

                def observe(active):
                    minute = 0 if frozen_source else clock["minute"]
                    active["last_good_progress"] = point(minute, fraction=min(0.1 + minute / 100, 0.9))

                requests = []

                def failed_delivery(request, **kwargs):
                    requests.append((clock["minute"], request))
                    raise RuntimeError("synthetic SMTP failure; no external call")

                with mock.patch.object(pr.subprocess, "Popen", return_value=Child()) as spawn, \
                     mock.patch.object(pr, "_process_identity", return_value={"state": "synthetic"}), \
                     mock.patch.object(pr, "_utc_now", side_effect=lambda: timestamp(clock["minute"])), \
                     mock.patch.object(pr, "observe_binding_progress", side_effect=observe), \
                     mock.patch("ai_bridge_kit.notifier.deliver_notification", side_effect=failed_delivery):
                    self.assertEqual(pr.supervise_binding(binding_path, launch), 0)
                spawn.assert_called_once()
                self.assertEqual([(minute, request["fact_class"]) for minute, request in requests],
                                 [(0, "runtime_start"), (60, "runtime_progress"), (70, "runtime_terminal")])
                final = json.loads(binding_path.read_text())
                self.assertEqual(final["lifecycle_state"], "TERMINAL")
                self.assertEqual(final["exit_code"], 0)
                self.assertEqual(final["last_logical_delivery_at"], timestamp(60))
                self.assertEqual(final["last_notification"]["status"], "FAILED")


if __name__ == "__main__":
    unittest.main()
