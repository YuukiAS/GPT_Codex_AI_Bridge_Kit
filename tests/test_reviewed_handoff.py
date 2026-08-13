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

    def remote_write_review_transaction(self, target: Path, *, decision: str, body: str = "Remote GPT review.") -> dict:
        root = rh.task_root(target, "001_feature")
        result_dir = rh.result_root(target, "001_feature")
        current = rh.load_json(root / "CURRENT.json")
        next_round = int(current.get("review_round", 0)) + 1
        commit = str(current.get("implementation_commit") or "")
        review_path = result_dir / f"REVIEW_{next_round}.md"
        header = (
            "---\n"
            f"schema: {rh.REVIEW_SCHEMA}\n"
            "task_key: 001_feature\n"
            f"review_round: {next_round}\n"
            f"decision: {decision}\n"
            f"implementation_commit: {commit}\n"
            "---\n\n"
        )
        rh.write_text(review_path, header + body.rstrip() + "\n")
        current["review_round"] = next_round
        current["last_review_decision"] = decision
        if current.get("state") == "WAITING_FOR_CI" and decision == "REVISE":
            current["ci_status"] = "FAIL"
        if decision == "PASS":
            self.write_final_report(target)
            current["state"] = "AWAIT_HUMAN_DECISION"
            current["human_gate_reason"] = "PASS"
            current["next_action"] = "PRESENT_FINAL_REPORT"
        elif decision == "BLOCKED":
            self.write_final_report(target)
            current["state"] = "BLOCKED"
            current["next_action"] = "PRESENT_FINAL_REPORT"
        elif next_round >= int(current.get("max_review_rounds", 2)):
            self.write_final_report(target)
            current["state"] = "AWAIT_HUMAN_DECISION"
            current["review_limit_reached"] = True
            current["human_gate_reason"] = "REVIEW_LIMIT"
            current["next_action"] = "PRESENT_FINAL_REPORT"
        else:
            current["state"] = "REVISE"
            current["next_action"] = "RUN_CODEX_REPAIR"
        rh.write_json(root / "CURRENT.json", current)
        return current

    def remote_write_planner_transaction(self, target: Path, *, needs_user: bool = False) -> dict:
        root = rh.task_root(target, "001_feature")
        current = rh.load_json(root / "CURRENT.json")
        if needs_user:
            self.write_final_report(target)
            current["state"] = "AWAIT_HUMAN_DECISION"
            current["human_gate_reason"] = "PLANNER_DECISION"
            current["next_action"] = "PRESENT_FINAL_REPORT"
        else:
            self.write_plan(target)
            current["plan_revision"] = int(current.get("plan_revision", 0)) + 1
            current["state"] = "PLAN_FROZEN"
            current["next_action"] = "RUN_CODEX_EXECUTOR"
        rh.write_json(root / "CURRENT.json", current)
        return current

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
            with self.assertRaisesRegex(ValueError, "WAITING_FOR_CI"):
                rh.apply_transition(target, "001_feature", expected_state="EXECUTING", next_state="READY_FOR_GPT_REVIEW")
            waiting = rh.apply_transition(target, "001_feature", expected_state="EXECUTING", next_state="WAITING_FOR_CI")
            self.assertEqual(waiting["state"], "WAITING_FOR_CI")
            self.assertEqual(waiting["ci_status"], "PENDING")
            advanced = rh.apply_transition(target, "001_feature", expected_state="WAITING_FOR_CI", next_state="READY_FOR_GPT_REVIEW")
            self.assertEqual(advanced["state"], "READY_FOR_GPT_REVIEW")
            self.assertEqual(advanced["ci_status"], "PASS")

    def test_ci_failure_uses_normal_review_round_budget(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            root = rh.task_root(target, "001_feature")
            current = rh.load_json(root / "CURRENT.json")
            current["ci_required"] = True
            current["ci_status"] = "PENDING"
            rh.write_json(root / "CURRENT.json", current)
            self.freeze_and_start(target)
            self.write_result(target, commit="impl-ci-1", ci_status="PENDING")
            rh.apply_transition(target, "001_feature", expected_state="EXECUTING", next_state="WAITING_FOR_CI")
            current = rh.record_review(target, "001_feature", decision="REVISE", body="CI failed: unit job failed.")
            self.assertEqual(current["state"], "REVISE")
            self.assertEqual(current["ci_status"], "FAIL")
            self.assertEqual(current["review_round"], 1)

            rh.apply_transition(target, "001_feature", expected_state="REVISE", next_state="EXECUTING")
            self.write_result(target, commit="impl-ci-2", ci_status="PENDING")
            rh.apply_transition(target, "001_feature", expected_state="EXECUTING", next_state="WAITING_FOR_CI")
            with self.assertRaisesRegex(ValueError, "FINAL_REPORT"):
                rh.record_review(target, "001_feature", decision="REVISE", body="CI still failed.")
            self.write_final_report(target)
            current = rh.record_review(target, "001_feature", decision="REVISE", body="CI still failed.")
            self.assertEqual(current["state"], "AWAIT_HUMAN_DECISION")
            self.assertTrue(current["review_limit_reached"])
            self.assertEqual(current["review_round"], 2)

    def test_waiting_for_ci_pending_has_no_side_effect_plan(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            root = rh.task_root(target, "001_feature")
            current = rh.load_json(root / "CURRENT.json")
            current["ci_required"] = True
            current["ci_status"] = "PENDING"
            rh.write_json(root / "CURRENT.json", current)
            self.freeze_and_start(target)
            self.write_result(target, commit="impl-ci", ci_status="PENDING")
            rh.apply_transition(target, "001_feature", expected_state="EXECUTING", next_state="WAITING_FOR_CI")
            before = rh.load_json(root / "CURRENT.json")
            plan = rh.plan_transition(target, "001_feature")
            after = rh.load_json(root / "CURRENT.json")
            self.assertEqual(plan["next_action"], "WAIT_FOR_CI")
            self.assertNotIn("next_state", plan)
            self.assertEqual(before, after)

    def test_scheduled_prompt_uses_github_transactions_not_local_transition_cli(self) -> None:
        prompt = rh.read_text(Path("templates/reviewed_handoff/prompts/REVIEWER_SCHEDULED_TASK.md"))
        self.assertIn("GitHub connector", prompt)
        self.assertIn("先写 GPT 拥有的 artifact", prompt)
        self.assertIn("最后写 `automation/reviewed_handoff/tasks/<task_key>/CURRENT.json`", prompt)
        self.assertIn("artifact-only commit 不代表新 workflow state", prompt)
        self.assertIn("本地 watcher 只以 `CURRENT.json` 作为 routing source of truth", prompt)
        self.assertNotIn("reviewed-handoff transition apply", prompt)
        self.assertNotIn("reviewed-handoff review record", prompt)

    def test_remote_ci_pass_transaction_matches_valid_ready_state(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            root = rh.task_root(target, "001_feature")
            current = rh.load_json(root / "CURRENT.json")
            current["ci_required"] = True
            current["ci_status"] = "PENDING"
            rh.write_json(root / "CURRENT.json", current)
            self.freeze_and_start(target)
            self.write_result(target, commit="impl-ci", ci_status="PENDING")
            rh.apply_transition(target, "001_feature", expected_state="EXECUTING", next_state="WAITING_FOR_CI")
            current = rh.load_json(root / "CURRENT.json")
            current["ci_status"] = "PASS"
            current["state"] = "READY_FOR_GPT_REVIEW"
            current["next_action"] = "WAIT_SCHEDULED_GPT_REVIEW"
            rh.write_json(root / "CURRENT.json", current)
            self.assertEqual(rh.validate_task(target, "001_feature"), [])

    def test_remote_ci_fail_transactions_use_review_budget(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            root = rh.task_root(target, "001_feature")
            current = rh.load_json(root / "CURRENT.json")
            current["ci_required"] = True
            current["ci_status"] = "PENDING"
            rh.write_json(root / "CURRENT.json", current)
            self.freeze_and_start(target)
            self.write_result(target, commit="impl-ci-1", ci_status="PENDING")
            rh.apply_transition(target, "001_feature", expected_state="EXECUTING", next_state="WAITING_FOR_CI")
            current = self.remote_write_review_transaction(target, decision="REVISE", body="CI failed.")
            self.assertEqual(current["state"], "REVISE")
            self.assertEqual(current["ci_status"], "FAIL")
            self.assertEqual(current["review_round"], 1)
            self.assertEqual(rh.validate_task(target, "001_feature"), [])

            rh.apply_transition(target, "001_feature", expected_state="REVISE", next_state="EXECUTING")
            self.write_result(target, commit="impl-ci-2", ci_status="PENDING")
            rh.apply_transition(target, "001_feature", expected_state="EXECUTING", next_state="WAITING_FOR_CI")
            current = self.remote_write_review_transaction(target, decision="REVISE", body="CI failed again.")
            self.assertEqual(current["state"], "AWAIT_HUMAN_DECISION")
            self.assertEqual(current["review_round"], 2)
            self.assertTrue(current["review_limit_reached"])
            self.assertEqual(current["human_gate_reason"], "REVIEW_LIMIT")
            self.assertEqual(rh.validate_task(target, "001_feature"), [])

    def test_remote_ci_unavailable_routes_blocked_with_final_report(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            root = rh.task_root(target, "001_feature")
            current = rh.load_json(root / "CURRENT.json")
            current["ci_required"] = True
            current["ci_status"] = "PENDING"
            rh.write_json(root / "CURRENT.json", current)
            self.freeze_and_start(target)
            self.write_result(target, commit="impl-ci", ci_status="PENDING")
            rh.apply_transition(target, "001_feature", expected_state="EXECUTING", next_state="WAITING_FOR_CI")
            before = rh.load_json(root / "CURRENT.json")
            self.write_final_report(target)
            current = dict(before)
            current["state"] = "BLOCKED"
            current["next_action"] = "PRESENT_FINAL_REPORT"
            current["runner_failure"] = {"source": "github_checks", "reason": "status_unavailable"}
            rh.write_json(root / "CURRENT.json", current)
            self.assertEqual(rh.validate_task(target, "001_feature"), [])
            self.assertEqual(rh.load_json(root / "CURRENT.json")["ci_status"], "PENDING")

    def test_remote_reviewer_pass_and_revise_transactions_validate(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            self.freeze_and_start(target)
            self.write_result(target, commit="impl-pass")
            rh.apply_transition(target, "001_feature", expected_state="EXECUTING", next_state="READY_FOR_GPT_REVIEW")
            current = self.remote_write_review_transaction(target, decision="PASS", body="Plan satisfied.")
            self.assertEqual(current["state"], "AWAIT_HUMAN_DECISION")
            self.assertEqual(current["human_gate_reason"], "PASS")
            self.assertEqual(rh.validate_task(target, "001_feature"), [])

        tmp, target = self.make_project()
        with tmp:
            self.freeze_and_start(target)
            self.write_result(target, commit="impl-revise")
            rh.apply_transition(target, "001_feature", expected_state="EXECUTING", next_state="READY_FOR_GPT_REVIEW")
            current = self.remote_write_review_transaction(target, decision="REVISE", body="Needs minimal repair.")
            self.assertEqual(current["state"], "REVISE")
            self.assertEqual(current["review_round"], 1)
            self.assertEqual(rh.validate_task(target, "001_feature"), [])

            rh.apply_transition(target, "001_feature", expected_state="REVISE", next_state="EXECUTING")
            self.write_result(target, commit="impl-revise-2")
            rh.apply_transition(target, "001_feature", expected_state="EXECUTING", next_state="READY_FOR_GPT_REVIEW")
            current = self.remote_write_review_transaction(target, decision="REVISE", body="Still not closed.")
            self.assertEqual(current["state"], "AWAIT_HUMAN_DECISION")
            self.assertTrue(current["review_limit_reached"])
            self.assertEqual(current["human_gate_reason"], "REVIEW_LIMIT")
            self.assertEqual(rh.validate_task(target, "001_feature"), [])

    def test_remote_planner_transactions_validate_revision_and_human_gate(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            self.freeze_and_start(target)
            rh.apply_transition(target, "001_feature", expected_state="EXECUTING", next_state="NEEDS_GPT_PLANNER")
            current = self.remote_write_planner_transaction(target)
            self.assertEqual(current["state"], "PLAN_FROZEN")
            self.assertEqual(current["plan_revision"], 1)
            self.assertEqual(rh.validate_task(target, "001_feature"), [])

            rh.apply_transition(target, "001_feature", expected_state="PLAN_FROZEN", next_state="EXECUTING")
            rh.apply_transition(target, "001_feature", expected_state="EXECUTING", next_state="NEEDS_GPT_PLANNER")
            current = self.remote_write_planner_transaction(target, needs_user=True)
            self.assertEqual(current["state"], "AWAIT_HUMAN_DECISION")
            self.assertEqual(current["human_gate_reason"], "PLANNER_DECISION")
            self.assertEqual(rh.validate_task(target, "001_feature"), [])

    def test_generic_reviewed_handoff_prompts_do_not_contain_ai_skills_policy(self) -> None:
        checked = [
            Path("templates/reviewed_handoff/prompts/PLANNER.md"),
            Path("templates/reviewed_handoff/prompts/REVIEWER_SCHEDULED_TASK.md"),
            Path("docs/V0_5_REVIEWED_HANDOFF_IMPLEMENTATION_SPEC.md"),
        ]
        banned = [
            "AI_Skills_Collection",
            "marketplacePluginBudget",
            "venue-templates",
            "registry.json",
            "skill/plugin",
            "plugin/skill",
        ]
        for path in checked:
            text = rh.read_text(path)
            for term in banned:
                self.assertNotIn(term, text, f"{term} leaked into {path}")

    def test_result_frontmatter_cannot_override_current_ci_truth(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            root = rh.task_root(target, "001_feature")
            current = rh.load_json(root / "CURRENT.json")
            current["ci_required"] = True
            current["ci_status"] = "PENDING"
            rh.write_json(root / "CURRENT.json", current)
            self.freeze_and_start(target)
            self.write_result(target, commit="impl-ci", ci_status="PENDING")
            result_path = rh.result_root(target, "001_feature") / "RESULT.md"
            text = result_path.read_text(encoding="utf-8")
            result_path.write_text(text.replace("implementation_commit: impl-ci", "implementation_commit: impl-ci\nci_status: PASS"), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "WAITING_FOR_CI"):
                rh.apply_transition(target, "001_feature", expected_state="EXECUTING", next_state="READY_FOR_GPT_REVIEW")
            current = rh.load_json(root / "CURRENT.json")
            self.assertEqual(current["ci_status"], "PENDING")

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

    def test_all_terminal_states_require_final_report(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            root = rh.task_root(target, "001_feature")
            self.freeze_and_start(target)
            current_path = root / "CURRENT.json"
            current = rh.load_json(current_path)
            current["state"] = "BLOCKED"
            current["runner_failure"] = {"event": "test"}
            rh.write_json(current_path, current)
            self.assertTrue(any("FINAL_REPORT" in error for error in rh.validate_task(target, "001_feature")))
            self.write_final_report(target)
            self.assertEqual(rh.validate_task(target, "001_feature"), [])

    def test_only_one_scheduled_plan_revision_is_allowed(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            self.freeze_and_start(target)
            current_path = rh.task_root(target, "001_feature") / "CURRENT.json"
            rh.apply_transition(target, "001_feature", expected_state="EXECUTING", next_state="NEEDS_GPT_PLANNER")
            current = rh.apply_transition(target, "001_feature", expected_state="NEEDS_GPT_PLANNER", next_state="PLAN_FROZEN")
            self.assertEqual(current["plan_revision"], 1)
            rh.apply_transition(target, "001_feature", expected_state="PLAN_FROZEN", next_state="EXECUTING")
            rh.apply_transition(target, "001_feature", expected_state="EXECUTING", next_state="NEEDS_GPT_PLANNER")
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
            forbidden = {
                "review_target_id",
                "request_nonce",
                "requirement_ledger_sha256",
                "bundle_sha256",
                "source_snapshot",
                "role_receipt_id",
                "planner_thread_id",
                "executor_thread_id",
                "reviewer_thread_id",
            }
            self.assertTrue(forbidden.isdisjoint(current))

    def test_reviewed_handoff_e2e_revise_repair_pass(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            self.write_plan(target)
            rh.apply_transition(target, "001_feature", expected_state="PLAN_REQUESTED", next_state="PLAN_FROZEN")
            rh.apply_transition(target, "001_feature", expected_state="PLAN_FROZEN", next_state="EXECUTING")
            self.write_result(target, commit="impl-1")
            rh.apply_transition(target, "001_feature", expected_state="EXECUTING", next_state="READY_FOR_GPT_REVIEW")
            rh.record_review(target, "001_feature", decision="REVISE", body="Plan item not complete.")
            rh.apply_transition(target, "001_feature", expected_state="REVISE", next_state="EXECUTING")
            self.write_result(target, commit="impl-2")
            rh.apply_transition(target, "001_feature", expected_state="EXECUTING", next_state="READY_FOR_GPT_REVIEW")
            rh.record_review(target, "001_feature", decision="PASS", body="Plan satisfied.")
            self.write_final_report(target)
            final = rh.apply_transition(target, "001_feature", expected_state="PASS", next_state="AWAIT_HUMAN_DECISION")
            self.assertEqual(final["state"], "AWAIT_HUMAN_DECISION")
            self.assertEqual(rh.validate_task(target, "001_feature"), [])

    def test_material_planner_question_replans_once_then_resumes(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            self.write_plan(target)
            rh.apply_transition(target, "001_feature", expected_state="PLAN_REQUESTED", next_state="PLAN_FROZEN")
            rh.apply_transition(target, "001_feature", expected_state="PLAN_FROZEN", next_state="EXECUTING")
            rh.apply_transition(target, "001_feature", expected_state="EXECUTING", next_state="NEEDS_GPT_PLANNER")
            current = rh.apply_transition(target, "001_feature", expected_state="NEEDS_GPT_PLANNER", next_state="PLAN_FROZEN")
            self.assertEqual(current["plan_revision"], 1)
            resumed = rh.apply_transition(target, "001_feature", expected_state="PLAN_FROZEN", next_state="EXECUTING")
            self.assertEqual(resumed["state"], "EXECUTING")

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
