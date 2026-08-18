from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from ai_bridge_kit import external_wait


class ExternalWaitContractTests(unittest.TestCase):
    def test_next_action_can_identify_external_wait_without_fixed_state(self) -> None:
        started = datetime(2026, 8, 18, 10, 0, tzinfo=timezone.utc)
        status = external_wait.build_wait_status(
            {
                "state": "REPOSITORY_CUSTOM_WAIT",
                "next_action": "WAIT_SCHEDULED_GPT_PLANNER",
                "external_wait_started_at": started.isoformat(),
            },
            current_identity="target-1",
            now=started + timedelta(minutes=10),
        )

        self.assertEqual(status["operational_status"], "waiting_external_review")
        self.assertEqual(status["external_owner"], "Planner")
        self.assertTrue(status["within_minimum_grace"])
        self.assertFalse(status["may_block"])

    def test_timeout_alone_does_not_block_but_observed_failure_can(self) -> None:
        started = datetime(2026, 8, 18, 10, 0, tzinfo=timezone.utc)
        current = {
            "state": "READY_FOR_GPT_REVIEW",
            "external_wait_started_at": started.isoformat(),
        }
        silence = external_wait.build_wait_status(
            current,
            current_identity="impl-1",
            now=started + timedelta(hours=3),
        )
        failure = external_wait.build_wait_status(
            current,
            current_identity="impl-1",
            external_failure_evidence=["Scheduled GPT automation is disabled"],
            now=started + timedelta(minutes=1),
        )

        self.assertEqual(silence["operational_status"], "waiting_external_review")
        self.assertFalse(silence["within_minimum_grace"])
        self.assertFalse(silence["may_block"])
        self.assertEqual(failure["operational_status"], "external_review_blocked")
        self.assertTrue(failure["may_block"])
        self.assertIn("Scheduled GPT automation is disabled", failure["failure_evidence"])


if __name__ == "__main__":
    unittest.main()
