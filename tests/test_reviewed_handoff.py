from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from ai_bridge_kit import bridge_cli
from ai_bridge_kit import reviewed_handoff as rh


class ReviewedHandoffTests(unittest.TestCase):
    def make_project(self, *, git: bool = False) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        tmp = tempfile.TemporaryDirectory()
        target = Path(tmp.name) / "project"
        target.mkdir()
        (target / "src").mkdir()
        (target / "src" / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
        if git:
            subprocess.check_call(["git", "init", "--initial-branch", "main"], cwd=target, stdout=subprocess.DEVNULL)
            subprocess.check_call(["git", "config", "user.email", "test@example.org"], cwd=target)
            subprocess.check_call(["git", "config", "user.name", "Test User"], cwd=target)
            subprocess.check_call(["git", "add", "."], cwd=target)
            subprocess.check_call(["git", "commit", "-m", "initial"], cwd=target, stdout=subprocess.DEVNULL)
        status, _ = rh.install_reviewed_handoff(target)
        self.assertTrue(status.installed)
        rh.init_task(target, "001_feature", objective="Add a reviewed feature")
        return tmp, target

    def write_plan(self, target: Path, task_key: str = "001_feature") -> None:
        template = rh.read_text(rh.reviewed_root(target) / "templates" / "PLAN.md")
        rh.write_text(rh.task_root(target, task_key) / "PLAN.md", template.replace("<TASK_KEY>", task_key))

    def write_final_report(self, target: Path) -> None:
        template = rh.read_text(rh.reviewed_root(target) / "templates" / "FINAL_REPORT.md")
        rh.write_text(rh.result_root(target, "001_feature") / "FINAL_REPORT.md", template)

    def freeze_and_start(self, target: Path) -> None:
        self.write_plan(target)
        rh.apply_transition(target, "001_feature", expected_state="PLAN_REQUESTED", next_state="PLAN_FROZEN")
        rh.apply_transition(target, "001_feature", expected_state="PLAN_FROZEN", next_state="EXECUTING")

    def write_result(self, target: Path, commit: str = "impl-1", ci_status: str = "NOT_REQUIRED") -> None:
        current_path = rh.task_root(target, "001_feature") / "CURRENT.json"
        current = rh.load_json(current_path)
        current["implementation_commit"] = commit
        current["ci_status"] = ci_status
        rh.write_json(current_path, current)
        template = rh.read_text(rh.reviewed_root(target) / "templates" / "RESULT.md")
        text = (
            template.replace("<TASK_KEY>", "001_feature")
            .replace("<COMMIT>", commit)
            .replace("<PASS_OR_NOT_REQUIRED>", ci_status)
        )
        rh.write_text(rh.result_root(target, "001_feature") / "RESULT.md", text)

    def test_bridge_cli_routes_reviewed_handoff_without_touching_legacy_cli(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            target.mkdir()
            self.assertEqual(bridge_cli.main(["reviewed-handoff", "install", "--target", str(target)]), 0)
            self.assertTrue(rh.inspect_reviewed_handoff(target).installed)

    def test_install_and_task_init_are_additive_and_branch_free(self) -> None:
        tmp, target = self.make_project(git=True)
        with tmp:
            current = rh.load_json(rh.task_root(target, "001_feature") / "CURRENT.json")
            self.assertEqual(current["state"], "PLAN_REQUESTED")
            self.assertEqual(current["max_review_rounds"], 2)
            self.assertEqual(current["max_plan_revisions"], 1)
            branches = subprocess.check_output(["git", "branch", "--format", "%(refname:short)"], cwd=target, text=True).splitlines()
            self.assertEqual(branches, ["main"])
            self.assertFalse((target / ".codex").exists())

    def test_install_is_idempotent_without_force(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            readme = rh.reviewed_root(target) / "README.md"
            original = readme.read_text(encoding="utf-8")
            readme.write_text(original + "\nlocal customization\n", encoding="utf-8")
            status, actions = rh.install_reviewed_handoff(target)
            self.assertTrue(status.installed)
            self.assertIn("local customization", readme.read_text(encoding="utf-8"))
            self.assertTrue(any("SKIP existing" in item for item in actions))

    def test_plan_freeze_requires_valid_plan(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            with self.assertRaisesRegex(ValueError, "PLAN_FROZEN requires PLAN.md"):
                rh.apply_transition(target, "001_feature", expected_state="PLAN_REQUESTED", next_state="PLAN_FROZEN")
            rh.write_text(rh.task_root(target, "001_feature") / "PLAN.md", "# not frozen\n")
            with self.assertRaisesRegex(ValueError, "frontmatter"):
                rh.apply_transition(target, "001_feature", expected_state="PLAN_REQUESTED", next_state="PLAN_FROZEN")
            self.write_plan(target)
            current = rh.apply_transition(target, "001_feature", expected_state="PLAN_REQUESTED", next_state="PLAN_FROZEN")
            self.assertEqual(current["state"], "PLAN_FROZEN")

    def test_illegal_state_jump_rejected(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            self.write_plan(target)
            with self.assertRaisesRegex(ValueError, "illegal transition edge"):
                rh.apply_transition(target, "001_feature", expected_state="PLAN_REQUESTED", next_state="READY_FOR_GPT_REVIEW")

    def test_ready_for_review_requires_result_locator_and_ci_when_required(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            self.freeze_and_start(target)
            with self.assertRaisesRegex(ValueError, "RESULT.md"):
                rh.apply_transition(target, "001_feature", expected_state="EXECUTING", next_state="READY_FOR_GPT_REVIEW")

        tmp, target = self.make_project()
        with tmp:
            root = rh.task_root(target, "001_feature")
            current = rh.load_json(root / "CURRENT.json")
            current["ci_required"] = True
            current["ci_status"] = "PENDING"
            rh.write_json(root / "CURRENT.json", current)
            self.freeze_and_start(target)
            self.write_result(target, commit="impl-ci", ci_status="PENDING")
            with self.assertRaisesRegex(ValueError, "ci_status=PASS"):
                rh.apply_transition(target, "001_feature", expected_state="EXECUTING", next_state="READY_FOR_GPT_REVIEW")
            self.write_result(target, commit="impl-ci", ci_status="PASS")
            advanced = rh.apply_transition(target, "001_feature", expected_state="EXECUTING", next_state="READY_FOR_GPT_REVIEW")
            self.assertEqual(advanced["state"], "READY_FOR_GPT_REVIEW")

    def test_review_record_first_revise_then_second_revise_human_gate(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            self.freeze_and_start(target)
            self.write_result(target, commit="impl-1")
            rh.apply_transition(target, "001_feature", expected_state="EXECUTING", next_state="READY_FOR_GPT_REVIEW")
            current = rh.record_review(target, "001_feature", decision="REVISE", body="Fix regression.")
            self.assertEqual(current["state"], "REVISE")
            self.assertEqual(current["review_round"], 1)
            rh.apply_transition(target, "001_feature", expected_state="REVISE", next_state="EXECUTING")
            self.write_result(target, commit="impl-2")
            rh.apply_transition(target, "001_feature", expected_state="EXECUTING", next_state="READY_FOR_GPT_REVIEW")
            with self.assertRaisesRegex(ValueError, "FINAL_REPORT"):
                rh.record_review(target, "001_feature", decision="REVISE", body="Still broken.")
            self.write_final_report(target)
            current = rh.record_review(target, "001_feature", decision="REVISE", body="Still broken.")
            self.assertEqual(current["state"], "AWAIT_HUMAN_DECISION")
            self.assertTrue(current["review_limit_reached"])
            self.assertEqual(current["review_round"], 2)
            with self.assertRaisesRegex(ValueError, "READY_FOR_GPT_REVIEW"):
                rh.record_review(target, "001_feature", decision="REVISE", body="third")
            self.assertEqual(rh.validate_task(target, "001_feature"), [])

    def test_blocked_review_requires_final_report(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            self.freeze_and_start(target)
            self.write_result(target)
            rh.apply_transition(target, "001_feature", expected_state="EXECUTING", next_state="READY_FOR_GPT_REVIEW")
            with self.assertRaisesRegex(ValueError, "FINAL_REPORT"):
                rh.record_review(target, "001_feature", decision="BLOCKED", body="External dependency unavailable.")
            self.write_final_report(target)
            current = rh.record_review(target, "001_feature", decision="BLOCKED", body="External dependency unavailable.")
            self.assertEqual(current["state"], "BLOCKED")
            self.assertEqual(rh.validate_task(target, "001_feature"), [])

    def test_manual_pass_transition_cannot_bypass_review_record(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            self.freeze_and_start(target)
            self.write_result(target)
            rh.apply_transition(target, "001_feature", expected_state="EXECUTING", next_state="READY_FOR_GPT_REVIEW")
            with self.assertRaisesRegex(ValueError, "review record"):
                rh.apply_transition(target, "001_feature", expected_state="READY_FOR_GPT_REVIEW", next_state="PASS")

    def test_pass_requires_final_report_before_human_gate(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            self.freeze_and_start(target)
            self.write_result(target)
            rh.apply_transition(target, "001_feature", expected_state="EXECUTING", next_state="READY_FOR_GPT_REVIEW")
            current = rh.record_review(target, "001_feature", decision="PASS", body="Plan satisfied.")
            self.assertEqual(current["state"], "PASS")
            with self.assertRaisesRegex(ValueError, "FINAL_REPORT"):
                rh.apply_transition(target, "001_feature", expected_state="PASS", next_state="AWAIT_HUMAN_DECISION")
            self.write_final_report(target)
            current = rh.apply_transition(target, "001_feature", expected_state="PASS", next_state="AWAIT_HUMAN_DECISION")
            self.assertEqual(current["state"], "AWAIT_HUMAN_DECISION")
            self.assertEqual(rh.validate_task(target, "001_feature"), [])

    def test_only_one_scheduled_plan_revision_is_allowed(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            self.freeze_and_start(target)
            current_path = rh.task_root(target, "001_feature") / "CURRENT.json"
            current = rh.load_json(current_path)
            current["state"] = "NEEDS_GPT_PLANNER"
            rh.write_json(current_path, current)
            current = rh.apply_transition(target, "001_feature", expected_state="NEEDS_GPT_PLANNER", next_state="PLAN_FROZEN")
            self.assertEqual(current["plan_revision"], 1)
            rh.apply_transition(target, "001_feature", expected_state="PLAN_FROZEN", next_state="EXECUTING")
            current = rh.load_json(current_path)
            current["state"] = "NEEDS_GPT_PLANNER"
            rh.write_json(current_path, current)
            plan = rh.plan_transition(target, "001_feature")
            self.assertEqual(plan["next_state"], "AWAIT_HUMAN_DECISION")
            self.write_final_report(target)
            current = rh.apply_transition(target, "001_feature", expected_state="NEEDS_GPT_PLANNER", next_state="AWAIT_HUMAN_DECISION")
            self.assertEqual(current["state"], "AWAIT_HUMAN_DECISION")

    def test_reviewed_handoff_contains_no_agent_flow_provenance_machinery(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            schema = rh.load_json(rh.reviewed_root(target) / "schema.json")
            flags = schema["anti_overengineering"]
            self.assertFalse(flags["semantic_hash_identity"])
            self.assertFalse(flags["requirement_ledger"])
            self.assertFalse(flags["role_receipt_graph"])
            self.assertFalse(flags["stable_review_snapshot"])
            current = rh.load_json(rh.task_root(target, "001_feature") / "CURRENT.json")
            forbidden = {"review_target_id", "request_nonce", "requirement_ledger_sha256", "bundle_sha256", "source_snapshot"}
            self.assertTrue(forbidden.isdisjoint(current))

    def test_core_validate_detects_review_round_drift(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            self.freeze_and_start(target)
            self.write_result(target)
            rh.apply_transition(target, "001_feature", expected_state="EXECUTING", next_state="READY_FOR_GPT_REVIEW")
            rh.record_review(target, "001_feature", decision="REVISE", body="repair")
            current_path = rh.task_root(target, "001_feature") / "CURRENT.json"
            current = rh.load_json(current_path)
            current["review_round"] = 0
            rh.write_json(current_path, current)
            lines, code = rh.validate_reviewed_handoff(target)
            self.assertEqual(code, 1)
            self.assertIn("CURRENT.review_round", "\n".join(lines))


if __name__ == "__main__":
    unittest.main()
