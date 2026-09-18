from __future__ import annotations

import unittest

from ai_bridge_kit.human_gate import (
    DependencyClass,
    HumanGateState,
    classify_dependency,
    mark_no_reply_boundary,
    open_transcript_gate,
    resume_after_explicit_answer,
)


class HumanGateTests(unittest.TestCase):
    def test_reply_path_uses_plain_text_and_resumes_same_goal_exactly_once(self) -> None:
        record = open_transcript_gate(
            dependency_class=DependencyClass.HUMAN_ONLY,
            goal_id="056_product_delivery_discipline",
            resume_point="W2_RESUME_FIXTURE",
            prompt_identity="prompt-1",
            question="Reply with APPROVE_FIXTURE to continue this exact Goal.",
        )

        self.assertEqual(record.state, HumanGateState.WAITING_FOR_HUMAN)
        self.assertFalse(record.dependent_execution_allowed)
        self.assertFalse(record.used_native_request_user_input)

        resumed = resume_after_explicit_answer(
            record,
            goal_id="056_product_delivery_discipline",
            prompt_identity="prompt-1",
            answer="APPROVE_FIXTURE",
        )

        self.assertEqual(resumed.state, HumanGateState.RESUMED_EXACT_ONCE)
        self.assertEqual(resumed.resume_count, 1)
        self.assertTrue(resumed.dependent_execution_allowed)
        with self.assertRaises(ValueError):
            resume_after_explicit_answer(
                resumed,
                goal_id="056_product_delivery_discipline",
                prompt_identity="prompt-1",
                answer="APPROVE_FIXTURE",
            )

    def test_no_reply_boundary_reports_recoverable_goal_blocked_then_later_resumes(self) -> None:
        record = open_transcript_gate(
            dependency_class=DependencyClass.HUMAN_ONLY,
            goal_id="056_product_delivery_discipline",
            resume_point="W2_RESUME_FIXTURE",
            prompt_identity="prompt-1",
            question="Reply with APPROVE_FIXTURE to continue this exact Goal.",
        )

        blocked, flags = mark_no_reply_boundary(record)

        self.assertEqual(blocked.state, HumanGateState.HUMAN_BLOCKED_RECOVERABLE)
        self.assertFalse(blocked.dependent_execution_allowed)
        self.assertEqual(flags["GOAL_BLOCKED"], "YES")
        self.assertEqual(flags["GOAL_ACHIEVED"], "NO")
        self.assertEqual(flags["COMPLETE"], "NO")
        self.assertEqual(flags["READY_FOR_USER_REVIEW"], "NO")
        self.assertEqual(flags["DEPENDENT_EXECUTION_BLOCKED"], "YES")

        resumed = resume_after_explicit_answer(
            blocked,
            goal_id="056_product_delivery_discipline",
            prompt_identity="prompt-1",
            answer="APPROVE_FIXTURE",
        )
        self.assertEqual(resumed.state, HumanGateState.RESUMED_EXACT_ONCE)
        self.assertTrue(resumed.dependent_execution_allowed)

    def test_agent_resolvable_does_not_prompt_and_unsupported_closes_truthfully(self) -> None:
        agent_resolvable = open_transcript_gate(
            dependency_class=classify_dependency("AGENT_RESOLVABLE"),
            goal_id="056_product_delivery_discipline",
            resume_point="source_discovery",
            prompt_identity="prompt-1",
        )
        self.assertEqual(agent_resolvable.state, HumanGateState.NOT_REQUIRED)
        self.assertTrue(agent_resolvable.dependent_execution_allowed)
        self.assertIsNone(agent_resolvable.question)

        unsupported = open_transcript_gate(
            dependency_class=DependencyClass.UNSUPPORTED_WITH_EVIDENCE,
            goal_id="056_product_delivery_discipline",
            resume_point="provider_probe",
            prompt_identity="prompt-1",
            unsupported_reason="supported interface is absent",
        )
        self.assertEqual(unsupported.state, HumanGateState.UNSUPPORTED_CLOSED)
        self.assertFalse(unsupported.dependent_execution_allowed)
        self.assertEqual(unsupported.unsupported_reason, "supported interface is absent")

    def test_stale_or_empty_answers_do_not_resume(self) -> None:
        record = open_transcript_gate(
            dependency_class=DependencyClass.HUMAN_ONLY,
            goal_id="056_product_delivery_discipline",
            resume_point="W2_RESUME_FIXTURE",
            prompt_identity="prompt-1",
            question="Reply with APPROVE_FIXTURE to continue this exact Goal.",
        )
        with self.assertRaises(ValueError):
            resume_after_explicit_answer(record, goal_id="other", prompt_identity="prompt-1", answer="yes")
        with self.assertRaises(ValueError):
            resume_after_explicit_answer(
                record,
                goal_id="056_product_delivery_discipline",
                prompt_identity="prompt-1",
                answer=" ",
            )


if __name__ == "__main__":
    unittest.main()
