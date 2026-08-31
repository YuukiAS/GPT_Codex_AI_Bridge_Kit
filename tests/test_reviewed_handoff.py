from __future__ import annotations

import contextlib
from datetime import datetime, timedelta, timezone
import io
import subprocess
import tempfile
import unittest
from pathlib import Path

from ai_bridge_kit import bridge_cli
from ai_bridge_kit import reviewed_handoff as rh
from ai_bridge_kit import text_review
from ai_bridge_kit import visual_review


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

    def write_legacy_final_report(self, target: Path, *, body: str | None = None) -> None:
        text = body or (
            "---\n"
            "schema: AI_BRIDGE_REVIEWED_FINAL_REPORT_V1\n"
            "task_key: 001_feature\n"
            "final_decision: AWAIT_HUMAN_DECISION\n"
            "---\n\n"
            "# Final Report\n\n"
            "## What 027 achieved\n\n"
            "The historical terminal task completed its frozen implementation work and left a user-readable outcome summary with concrete repository artifacts.\n\n"
            "## What improved after Review 1\n\n"
            "The report explains the repair work, the reviewer-facing evidence, and the preserved behavior that mattered for the completed task.\n\n"
            "## Review-limit handling\n\n"
            "The automatic loop ended under the older V1 section shape, but the frontmatter and substantive content still make the terminal decision auditable.\n\n"
            "## User-checkable artifacts\n\n"
            "The user can inspect the result directory, review artifacts, and implementation notes without reconstructing the task from logs.\n"
        )
        rh.write_text(rh.result_root(target, "001_feature") / "FINAL_REPORT.md", text)

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

    def require_visual_review(self, target: Path) -> None:
        current_path = rh.task_root(target, "001_feature") / "CURRENT.json"
        current = rh.load_json(current_path)
        current["visual_review_required"] = True
        current["visual_review_manifest_path"] = "results/001_feature/visual_review/visual_inputs.json"
        current["visual_review_evidence_path"] = "results/001_feature/visual_review/VISUAL_REVIEW.json"
        rh.write_json(current_path, current)

    def require_text_review(self, target: Path) -> None:
        current_path = rh.task_root(target, "001_feature") / "CURRENT.json"
        current = rh.load_json(current_path)
        current["text_review_required"] = True
        current["text_review_manifest_path"] = "results/001_feature/text_review/text_inputs.json"
        current["text_review_evidence_path"] = "results/001_feature/text_review/TEXT_REVIEW.json"
        rh.write_json(current_path, current)

    def require_ci(self, target: Path) -> None:
        current_path = rh.task_root(target, "001_feature") / "CURRENT.json"
        current = rh.load_json(current_path)
        current["ci_required"] = True
        current["ci_status"] = "PENDING"
        rh.write_json(current_path, current)

    def write_visual_input_manifest(self, target: Path, implementation_commit: str) -> None:
        visual_dir = rh.result_root(target, "001_feature") / "visual_review"
        image = visual_dir / "primary.png"
        image.parent.mkdir(parents=True, exist_ok=True)
        image.write_bytes(
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?"
            b"\x00\x05\xfe\x02\xfeA\xe2U\xa7\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        manifest = {
            "schema": visual_review.VISUAL_INPUT_MANIFEST_SCHEMA,
            "task_key": "001_feature",
            "workflow_type": "reviewed_handoff",
            "review_kind": "synthetic",
            "privacy_policy": "PUBLIC_SAFE_ONLY",
            "rubric": {"instructions": "Synthetic visual fixture must pass."},
            "identity_bindings": {"implementation_commit": implementation_commit},
            "inputs": [{"logical_id": "primary", "path": "results/001_feature/visual_review/primary.png"}],
        }
        visual_review.write_json(visual_dir / "visual_inputs.json", manifest)

    def write_visual_review(self, target: Path, implementation_commit: str, decision: str = "PASS") -> None:
        self.write_visual_input_manifest(target, implementation_commit)
        visual_dir = rh.result_root(target, "001_feature") / "visual_review"
        manifest = rh.load_json(visual_dir / "visual_inputs.json")
        normalized = visual_review.normalize_manifest(target, manifest)
        artifact = visual_review.assemble_visual_review(
            manifest=normalized,
            model_output={
                "overall_decision": decision,
                "item_reviews": [{"item_id": "primary", "decision": decision, "summary": "ok", "observations": [], "requirement_ids": []}],
                "blocking_findings": [],
                "non_blocking_notes": [],
            },
            model="gpt-test",
        )
        visual_review.write_json(visual_dir / "VISUAL_REVIEW.json", artifact)

    def write_text_input_manifest(self, target: Path, implementation_commit: str, plaintext_sha: str | None = None) -> None:
        text_dir = rh.result_root(target, "001_feature") / "text_review"
        text_dir.mkdir(parents=True, exist_ok=True)
        payload = text_dir / "payload.age"
        payload.write_bytes(b"synthetic encrypted private text")
        manifest = {
            "schema": text_review.TEXT_INPUT_MANIFEST_SCHEMA,
            "task_key": "001_feature",
            "workflow_type": "reviewed_handoff",
            "review_kind": "user-facing-text",
            "privacy_policy": text_review.PRIVATE_TEXT_POLICY,
            "external_upload_authorization": "Synthetic test authorization.",
            "rubric": {"instructions": "Synthetic text fixture must satisfy reader-facing prose requirements."},
            "identity_bindings": {"implementation_commit": implementation_commit},
            "input": {
                "logical_id": "primary_text",
                "encrypted_payload_path": "results/001_feature/text_review/payload.age",
                "ciphertext_sha256": text_review.file_sha256(payload),
                "plaintext_sha256": plaintext_sha or ("a" * 64),
                "plaintext_size_bytes": 123,
                "mime_type": "text/markdown; charset=utf-8",
                "source_basename": "final.md",
            },
        }
        text_review.write_json(text_dir / "text_inputs.json", manifest)

    def write_text_review(self, target: Path, implementation_commit: str, decision: str = "PASS") -> None:
        self.write_text_input_manifest(target, implementation_commit)
        text_dir = rh.result_root(target, "001_feature") / "text_review"
        manifest = text_review.normalize_manifest(target, rh.load_json(text_dir / "text_inputs.json"))
        artifact = text_review.assemble_text_review(
            manifest=manifest,
            model_output={
                "overall_decision": decision,
                "item_reviews": [{"item_id": "primary_text", "decision": decision, "summary": "ok", "requirement_ids": []}],
                "blocking_findings": []
                if decision == "PASS"
                else [
                    {
                        "finding_id": "TXT-001",
                        "requirement_id": "REQ_TEXT",
                        "severity": "blocking",
                        "summary": "Text artifact does not satisfy the frozen requirement.",
                        "evidence": "Synthetic evidence.",
                        "recommendation": "Revise the text artifact.",
                    }
                ],
                "non_blocking_notes": [],
            },
            model="gpt-test",
        )
        text_review.write_json(text_dir / "TEXT_REVIEW.json", artifact)

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

    def test_task_init_can_require_text_review_without_changing_state_graph(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            target.mkdir()
            status, _ = rh.install_reviewed_handoff(target)
            self.assertTrue(status.installed)
            rh.init_task(target, "001_feature", objective="Review private text", text_review_required=True)
            current = rh.load_json(rh.task_root(target, "001_feature") / "CURRENT.json")
            self.assertTrue(current["text_review_required"])
            self.assertEqual(current["text_review_manifest_path"], "results/001_feature/text_review/text_inputs.json")
            self.assertEqual(current["text_review_evidence_path"], "results/001_feature/text_review/TEXT_REVIEW.json")

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

    def test_plan_freeze_rejects_missing_out_of_scope_section(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            self.write_plan(target)
            plan_path = rh.task_root(target, "001_feature") / "PLAN.md"
            plan_text = plan_path.read_text(encoding="utf-8")
            plan_path.write_text(plan_text.replace("\n## Out of scope\n\nList tempting adjacent improvements that Reviewer must not turn into blocking scope.\n", "\n"), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "PLAN.md missing required section: ## Out of scope"):
                rh.apply_transition(target, "001_feature", expected_state="PLAN_REQUESTED", next_state="PLAN_FROZEN")

    def test_legacy_terminal_final_report_does_not_block_repository_validation(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            self.write_plan(target)
            current_path = rh.task_root(target, "001_feature") / "CURRENT.json"
            current = rh.load_json(current_path)
            current["state"] = "AWAIT_HUMAN_DECISION"
            current["human_gate_reason"] = "PLANNER_DECISION"
            current["next_action"] = "PRESENT_FINAL_REPORT"
            rh.write_json(current_path, current)
            self.write_legacy_final_report(target)

            lines, code = rh.validate_reviewed_handoff(target)

            self.assertEqual(code, 0, "\n".join(lines))
            self.assertTrue(any("legacy V1 section shape" in line for line in lines))

    def test_malformed_or_empty_legacy_final_report_still_fails(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            self.write_plan(target)
            current_path = rh.task_root(target, "001_feature") / "CURRENT.json"
            current = rh.load_json(current_path)
            current["state"] = "AWAIT_HUMAN_DECISION"
            current["human_gate_reason"] = "PLANNER_DECISION"
            current["next_action"] = "PRESENT_FINAL_REPORT"
            rh.write_json(current_path, current)
            self.write_legacy_final_report(
                target,
                body=(
                    "---\n"
                    "schema: AI_BRIDGE_REVIEWED_FINAL_REPORT_V1\n"
                    "task_key: 001_feature\n"
                    "final_decision: AWAIT_HUMAN_DECISION\n"
                    "---\n\n"
                    "# Final Report\n\n"
                    "## What 027 achieved\n\n"
                ),
            )

            lines, code = rh.validate_reviewed_handoff(target)

            self.assertEqual(code, 1)
            self.assertIn("legacy report", "\n".join(lines))

    def test_planner_decision_human_gate_allows_historical_stale_review(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            self.write_plan(target)
            self.write_result(target, commit="impl-old", ci_status="PASS")
            review_path = rh.result_root(target, "001_feature") / "REVIEW_1.md"
            rh.write_text(
                review_path,
                (
                    "---\n"
                    f"schema: {rh.REVIEW_SCHEMA}\n"
                    "task_key: 001_feature\n"
                    "review_round: 1\n"
                    "decision: REVISE\n"
                    "implementation_commit: impl-old\n"
                    "---\n\n"
                    "Historical review for an earlier implementation.\n"
                ),
            )
            self.write_result(target, commit="impl-new", ci_status="PASS")
            current_path = rh.task_root(target, "001_feature") / "CURRENT.json"
            current = rh.load_json(current_path)
            current["state"] = "AWAIT_HUMAN_DECISION"
            current["human_gate_reason"] = "PLANNER_DECISION"
            current["next_action"] = "PRESENT_FINAL_REPORT"
            current["review_round"] = 1
            current["last_review_decision"] = "REVISE"
            current["implementation_commit"] = "impl-new"
            current["ci_status"] = "PASS"
            rh.write_json(current_path, current)
            self.write_final_report(target)

            lines, code = rh.validate_reviewed_handoff(target)

            self.assertEqual(code, 0, "\n".join(lines))

    def test_review_limit_human_gate_still_rejects_stale_review(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            self.write_plan(target)
            self.write_result(target, commit="impl-old", ci_status="PASS")
            review_path = rh.result_root(target, "001_feature") / "REVIEW_1.md"
            rh.write_text(
                review_path,
                (
                    "---\n"
                    f"schema: {rh.REVIEW_SCHEMA}\n"
                    "task_key: 001_feature\n"
                    "review_round: 1\n"
                    "decision: REVISE\n"
                    "implementation_commit: impl-old\n"
                    "---\n\n"
                    "Reviewer-bound closure cannot use stale review identity.\n"
                ),
            )
            self.write_result(target, commit="impl-new", ci_status="PASS")
            current_path = rh.task_root(target, "001_feature") / "CURRENT.json"
            current = rh.load_json(current_path)
            current["state"] = "AWAIT_HUMAN_DECISION"
            current["human_gate_reason"] = "REVIEW_LIMIT"
            current["next_action"] = "PRESENT_FINAL_REPORT"
            current["review_round"] = 1
            current["last_review_decision"] = "REVISE"
            current["review_limit_reached"] = True
            current["max_review_rounds"] = 1
            current["implementation_commit"] = "impl-new"
            current["ci_status"] = "PASS"
            rh.write_json(current_path, current)
            self.write_final_report(target)

            errors = rh.validate_task(target, "001_feature")

            self.assertIn("latest review must be bound to CURRENT implementation_commit", errors)

    def test_new_terminal_transition_still_requires_current_final_report_template(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            self.write_plan(target)
            current_path = rh.task_root(target, "001_feature") / "CURRENT.json"
            current = rh.load_json(current_path)
            current["state"] = "NEEDS_GPT_PLANNER"
            current["next_action"] = "RUN_GPT_PLANNER"
            rh.write_json(current_path, current)
            self.write_legacy_final_report(target)

            with self.assertRaisesRegex(ValueError, "What this task solved"):
                rh.apply_transition(
                    target,
                    "001_feature",
                    expected_state="NEEDS_GPT_PLANNER",
                    next_state="AWAIT_HUMAN_DECISION",
                )

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

    def test_visual_review_pending_does_not_consume_review_round(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            self.require_visual_review(target)
            self.freeze_and_start(target)
            self.write_result(target, commit="impl-visual")
            self.write_visual_input_manifest(target, implementation_commit="impl-visual")
            ready = rh.apply_transition(target, "001_feature", expected_state="EXECUTING", next_state="READY_FOR_GPT_REVIEW")
            self.assertEqual(ready["state"], "READY_FOR_GPT_REVIEW")
            plan = rh.plan_transition(target, "001_feature")
            self.assertEqual(plan["next_action"], "WAIT_FOR_VISUAL_REVIEW_EVIDENCE")
            wait = rh.reviewed_external_wait_status(target, "001_feature")
            self.assertEqual(wait["operational_status"], "waiting_visual_review_evidence")
            self.assertEqual(wait["wait_owner"], "Visual Review")
            with self.assertRaisesRegex(ValueError, "visual review evidence pending"):
                rh.record_review(target, "001_feature", decision="PASS", body="Looks good.")
            current = rh.load_json(rh.task_root(target, "001_feature") / "CURRENT.json")
            self.assertEqual(current["review_round"], 0)

    def test_text_review_pending_does_not_consume_review_round(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            self.require_text_review(target)
            self.freeze_and_start(target)
            self.write_result(target, commit="impl-text")
            self.write_text_input_manifest(target, implementation_commit="impl-text")
            ready = rh.apply_transition(target, "001_feature", expected_state="EXECUTING", next_state="READY_FOR_GPT_REVIEW")
            self.assertEqual(ready["state"], "READY_FOR_GPT_REVIEW")
            plan = rh.plan_transition(target, "001_feature")
            self.assertEqual(plan["next_action"], "WAIT_FOR_TEXT_REVIEW_EVIDENCE")
            wait = rh.reviewed_external_wait_status(target, "001_feature")
            self.assertEqual(wait["operational_status"], "waiting_text_review_evidence")
            self.assertEqual(wait["wait_owner"], "Text Review")
            with self.assertRaisesRegex(ValueError, "text review evidence pending"):
                rh.record_review(target, "001_feature", decision="PASS", body="Looks good.")
            current = rh.load_json(rh.task_root(target, "001_feature") / "CURRENT.json")
            self.assertEqual(current["review_round"], 0)

    def test_visual_input_manifest_can_be_published_before_github_visual_review(self) -> None:
        tmp, target = self.make_project(git=True)
        with tmp:
            self.require_visual_review(target)
            self.freeze_and_start(target)
            (target / "src" / "app.py").write_text("VALUE = 2\n", encoding="utf-8")
            subprocess.check_call(["git", "add", "src/app.py"], cwd=target)
            subprocess.check_call(["git", "commit", "-m", "implementation"], cwd=target, stdout=subprocess.DEVNULL)
            implementation_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=target, text=True).strip()
            self.write_result(target, commit=implementation_commit)
            self.write_visual_input_manifest(target, implementation_commit=implementation_commit)

            current = rh.apply_transition(target, "001_feature", expected_state="EXECUTING", next_state="READY_FOR_GPT_REVIEW")

            self.assertEqual(current["state"], "READY_FOR_GPT_REVIEW")
            self.assertEqual(rh.validate_task(target, "001_feature"), [])
            self.assertFalse((rh.result_root(target, "001_feature") / "visual_review" / "VISUAL_REVIEW.json").exists())
            wait = rh.reviewed_external_wait_status(target, "001_feature")
            self.assertEqual(wait["operational_status"], "waiting_visual_review_evidence")
            self.assertFalse(wait["may_block"])
            self.assertEqual(rh.load_json(rh.task_root(target, "001_feature") / "CURRENT.json")["review_round"], 0)

    def test_ci_required_visual_task_waits_for_ci_before_visual_review(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            self.require_ci(target)
            self.require_visual_review(target)
            self.freeze_and_start(target)
            self.write_result(target, commit="impl-ci-visual", ci_status="PENDING")
            self.write_visual_input_manifest(target, implementation_commit="impl-ci-visual")

            current = rh.apply_transition(target, "001_feature", expected_state="EXECUTING", next_state="WAITING_FOR_CI")

            self.assertEqual(current["state"], "WAITING_FOR_CI")
            self.assertEqual(current["ci_status"], "PENDING")
            self.assertEqual(rh.validate_task(target, "001_feature"), [])
            wait = rh.reviewed_external_wait_status(target, "001_feature")
            self.assertEqual(wait["operational_status"], "waiting_for_ci")
            self.assertEqual(wait["wait_owner"], "CI")
            self.assertEqual(rh.load_json(rh.task_root(target, "001_feature") / "CURRENT.json")["review_round"], 0)

    def test_ci_pass_then_visual_task_waits_for_visual_evidence(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            self.require_ci(target)
            self.require_visual_review(target)
            self.freeze_and_start(target)
            self.write_result(target, commit="impl-ci-visual", ci_status="PENDING")
            self.write_visual_input_manifest(target, implementation_commit="impl-ci-visual")
            rh.apply_transition(target, "001_feature", expected_state="EXECUTING", next_state="WAITING_FOR_CI")

            current = rh.apply_transition(target, "001_feature", expected_state="WAITING_FOR_CI", next_state="READY_FOR_GPT_REVIEW")

            self.assertEqual(current["state"], "READY_FOR_GPT_REVIEW")
            self.assertEqual(current["ci_status"], "PASS")
            self.assertEqual(rh.validate_task(target, "001_feature"), [])
            wait = rh.reviewed_external_wait_status(target, "001_feature")
            self.assertEqual(wait["operational_status"], "waiting_visual_review_evidence")
            self.assertEqual(wait["wait_owner"], "Visual Review")
            with self.assertRaisesRegex(ValueError, "visual review evidence pending"):
                rh.record_review(target, "001_feature", decision="PASS", body="Must wait for visual evidence.")
            self.assertEqual(rh.load_json(rh.task_root(target, "001_feature") / "CURRENT.json")["review_round"], 0)

    def test_visual_review_pending_requires_published_input_manifest(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            self.require_visual_review(target)
            self.freeze_and_start(target)
            self.write_result(target, commit="impl-visual")
            with self.assertRaisesRegex(ValueError, "visual review input manifest missing"):
                rh.apply_transition(target, "001_feature", expected_state="EXECUTING", next_state="READY_FOR_GPT_REVIEW")

    def test_current_visual_review_can_be_consumed_by_reviewer(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            self.require_visual_review(target)
            self.freeze_and_start(target)
            self.write_result(target, commit="impl-visual")
            self.write_visual_input_manifest(target, implementation_commit="impl-visual")
            rh.apply_transition(target, "001_feature", expected_state="EXECUTING", next_state="READY_FOR_GPT_REVIEW")
            self.write_visual_review(target, implementation_commit="impl-visual")
            current = rh.record_review(target, "001_feature", decision="PASS", body="Plan and visual evidence satisfied.")
            self.assertEqual(current["state"], "PASS")
            self.assertEqual(current["review_round"], 1)

    def test_current_text_review_can_be_consumed_by_reviewer(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            self.require_text_review(target)
            self.freeze_and_start(target)
            self.write_result(target, commit="impl-text")
            self.write_text_input_manifest(target, implementation_commit="impl-text")
            rh.apply_transition(target, "001_feature", expected_state="EXECUTING", next_state="READY_FOR_GPT_REVIEW")
            self.write_text_review(target, implementation_commit="impl-text")
            current = rh.record_review(target, "001_feature", decision="PASS", body="Plan and text evidence satisfied.")
            self.assertEqual(current["state"], "PASS")
            self.assertEqual(current["review_round"], 1)

    def test_text_review_revise_blocks_reviewer_pass(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            self.require_text_review(target)
            self.freeze_and_start(target)
            self.write_result(target, commit="impl-text")
            self.write_text_input_manifest(target, implementation_commit="impl-text")
            rh.apply_transition(target, "001_feature", expected_state="EXECUTING", next_state="READY_FOR_GPT_REVIEW")
            self.write_text_review(target, implementation_commit="impl-text", decision="REVISE")
            with self.assertRaisesRegex(ValueError, "GPT review PASS requires text review PASS evidence, found REVISE"):
                rh.record_review(target, "001_feature", decision="PASS", body="Cannot pass over text failure.")
            current = rh.record_review(target, "001_feature", decision="REVISE", body="Text Review found a blocker.")
            self.assertEqual(current["state"], "REVISE")
            self.assertEqual(current["review_round"], 1)

    def test_stale_visual_review_is_rejected(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            self.require_visual_review(target)
            self.freeze_and_start(target)
            self.write_result(target, commit="impl-current")
            self.write_visual_input_manifest(target, implementation_commit="impl-current")
            rh.apply_transition(target, "001_feature", expected_state="EXECUTING", next_state="READY_FOR_GPT_REVIEW")
            self.write_visual_review(target, implementation_commit="impl-old")
            with self.assertRaisesRegex(ValueError, "identity binding mismatch"):
                rh.record_review(target, "001_feature", decision="PASS", body="Cannot use stale visual evidence.")

    def test_stale_text_review_is_rejected(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            self.require_text_review(target)
            self.freeze_and_start(target)
            self.write_result(target, commit="impl-current")
            self.write_text_input_manifest(target, implementation_commit="impl-current")
            rh.apply_transition(target, "001_feature", expected_state="EXECUTING", next_state="READY_FOR_GPT_REVIEW")
            self.write_text_review(target, implementation_commit="impl-old")
            with self.assertRaisesRegex(ValueError, "text review input manifest implementation_commit must match CURRENT|identity binding mismatch"):
                rh.record_review(target, "001_feature", decision="PASS", body="Cannot use stale text evidence.")

        tmp, target = self.make_project()
        with tmp:
            self.require_text_review(target)
            self.freeze_and_start(target)
            self.write_result(target, commit="impl-current")
            self.write_text_input_manifest(target, implementation_commit="impl-current", plaintext_sha="b" * 64)
            rh.apply_transition(target, "001_feature", expected_state="EXECUTING", next_state="READY_FOR_GPT_REVIEW")
            self.write_text_review(target, implementation_commit="impl-current")
            manifest_path = rh.result_root(target, "001_feature") / "text_review" / "text_inputs.json"
            manifest = rh.load_json(manifest_path)
            manifest["input"]["plaintext_sha256"] = "c" * 64
            rh.write_json(manifest_path, manifest)
            with self.assertRaisesRegex(ValueError, "reviewed_input_identity is stale|plaintext_artifact_sha256 mismatch"):
                rh.record_review(target, "001_feature", decision="PASS", body="Cannot use old plaintext evidence.")

    def test_visual_pass_states_require_current_pass_evidence(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            self.require_visual_review(target)
            self.freeze_and_start(target)
            self.write_result(target, commit="impl-visual")
            self.write_visual_input_manifest(target, implementation_commit="impl-visual")
            rh.apply_transition(target, "001_feature", expected_state="EXECUTING", next_state="READY_FOR_GPT_REVIEW")
            self.remote_write_review_transaction(target, decision="PASS", body="Claimed pass without visual evidence.")
            current_path = rh.task_root(target, "001_feature") / "CURRENT.json"
            current = rh.load_json(current_path)
            current["state"] = "PASS"
            current["next_action"] = "PRESENT_FINAL_REPORT"
            rh.write_json(current_path, current)

            errors = rh.validate_task(target, "001_feature")
            self.assertTrue(any("PASS requires visual review PASS evidence" in error for error in errors), errors)

        tmp, target = self.make_project()
        with tmp:
            self.require_visual_review(target)
            self.freeze_and_start(target)
            self.write_result(target, commit="impl-current")
            self.write_visual_input_manifest(target, implementation_commit="impl-current")
            rh.apply_transition(target, "001_feature", expected_state="EXECUTING", next_state="READY_FOR_GPT_REVIEW")
            self.write_visual_review(target, implementation_commit="impl-old")
            self.remote_write_review_transaction(target, decision="PASS", body="Claimed pass with stale visual evidence.")
            current_path = rh.task_root(target, "001_feature") / "CURRENT.json"
            current = rh.load_json(current_path)
            current["state"] = "PASS"
            current["next_action"] = "PRESENT_FINAL_REPORT"
            rh.write_json(current_path, current)

            errors = rh.validate_task(target, "001_feature")
            self.assertTrue(any("identity binding mismatch" in error for error in errors), errors)

        tmp, target = self.make_project()
        with tmp:
            self.require_visual_review(target)
            self.freeze_and_start(target)
            self.write_result(target, commit="impl-current")
            self.write_visual_review(target, implementation_commit="impl-current")
            rh.apply_transition(target, "001_feature", expected_state="EXECUTING", next_state="READY_FOR_GPT_REVIEW")
            current = rh.record_review(target, "001_feature", decision="PASS", body="Fresh visual evidence satisfied.")
            self.assertEqual(current["state"], "PASS")
            self.assertEqual(rh.validate_task(target, "001_feature"), [])

    def test_text_pass_states_require_current_pass_evidence(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            self.require_text_review(target)
            self.freeze_and_start(target)
            self.write_result(target, commit="impl-text")
            self.write_text_input_manifest(target, implementation_commit="impl-text")
            rh.apply_transition(target, "001_feature", expected_state="EXECUTING", next_state="READY_FOR_GPT_REVIEW")
            self.remote_write_review_transaction(target, decision="PASS", body="Claimed pass without text evidence.")
            current_path = rh.task_root(target, "001_feature") / "CURRENT.json"
            current = rh.load_json(current_path)
            current["state"] = "PASS"
            current["next_action"] = "PRESENT_FINAL_REPORT"
            rh.write_json(current_path, current)

            errors = rh.validate_task(target, "001_feature")
            self.assertTrue(any("PASS requires text review PASS evidence" in error for error in errors), errors)

    def test_pass_human_gate_requires_current_visual_pass_evidence(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            self.require_visual_review(target)
            self.freeze_and_start(target)
            self.write_result(target, commit="impl-visual")
            self.write_visual_input_manifest(target, implementation_commit="impl-visual")
            rh.apply_transition(target, "001_feature", expected_state="EXECUTING", next_state="READY_FOR_GPT_REVIEW")
            current = self.remote_write_review_transaction(target, decision="PASS", body="Claimed pass without visual evidence.")
            self.assertEqual(current["state"], "AWAIT_HUMAN_DECISION")

            errors = rh.validate_task(target, "001_feature")
            self.assertTrue(any("PASS human gate requires visual review PASS evidence" in error for error in errors), errors)

    def test_visual_pending_is_allowed_for_ci_failures_and_non_pass_terminal_states(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            self.require_ci(target)
            self.require_visual_review(target)
            self.freeze_and_start(target)
            self.write_result(target, commit="impl-ci-visual-1", ci_status="PENDING")
            self.write_visual_input_manifest(target, implementation_commit="impl-ci-visual-1")
            rh.apply_transition(target, "001_feature", expected_state="EXECUTING", next_state="WAITING_FOR_CI")

            current = rh.record_review(target, "001_feature", decision="REVISE", body="CI failed before Terra evidence existed.")
            self.assertEqual(current["state"], "REVISE")
            self.assertEqual(current["review_round"], 1)
            self.assertEqual(rh.validate_task(target, "001_feature"), [])

            rh.apply_transition(target, "001_feature", expected_state="REVISE", next_state="EXECUTING")
            self.write_result(target, commit="impl-ci-visual-2", ci_status="PENDING")
            self.write_visual_input_manifest(target, implementation_commit="impl-ci-visual-2")
            rh.apply_transition(target, "001_feature", expected_state="EXECUTING", next_state="WAITING_FOR_CI")
            self.write_final_report(target)
            current = rh.record_review(target, "001_feature", decision="REVISE", body="CI failed again before Terra evidence existed.")
            self.assertEqual(current["state"], "AWAIT_HUMAN_DECISION")
            self.assertEqual(current["human_gate_reason"], "REVIEW_LIMIT")
            self.assertEqual(current["review_round"], 2)
            self.assertEqual(rh.validate_task(target, "001_feature"), [])

        tmp, target = self.make_project()
        with tmp:
            self.require_visual_review(target)
            self.freeze_and_start(target)
            self.write_result(target, commit="impl-blocked")
            self.write_visual_input_manifest(target, implementation_commit="impl-blocked")
            rh.apply_transition(target, "001_feature", expected_state="EXECUTING", next_state="READY_FOR_GPT_REVIEW")
            self.write_final_report(target)
            current = rh.record_review(target, "001_feature", decision="BLOCKED", body="External service failed.")
            self.assertEqual(current["state"], "BLOCKED")
            self.assertEqual(rh.validate_task(target, "001_feature"), [])

    def test_invalid_visual_manifest_and_evidence_still_fail_closed(self) -> None:
        for state in ["WAITING_FOR_CI", "READY_FOR_GPT_REVIEW", "REVISE", "BLOCKED", "AWAIT_HUMAN_DECISION"]:
            tmp, target = self.make_project()
            with tmp, self.subTest(state=state):
                self.require_ci(target)
                self.require_visual_review(target)
                self.freeze_and_start(target)
                self.write_result(target, commit="impl-bad-visual", ci_status="PENDING")
                self.write_visual_input_manifest(target, implementation_commit="wrong-impl")
                current_path = rh.task_root(target, "001_feature") / "CURRENT.json"
                current = rh.load_json(current_path)
                current["state"] = state
                current["implementation_commit"] = "impl-bad-visual"
                current["ci_status"] = "PASS" if state == "READY_FOR_GPT_REVIEW" else "PENDING"
                current["next_action"] = {
                    "WAITING_FOR_CI": "WAIT_FOR_GITHUB_CI",
                    "READY_FOR_GPT_REVIEW": "WAIT_FOR_VISUAL_REVIEW_EVIDENCE",
                    "REVISE": "RUN_CODEX_REPAIR",
                    "BLOCKED": "PRESENT_FINAL_REPORT",
                    "AWAIT_HUMAN_DECISION": "PRESENT_FINAL_REPORT",
                }[state]
                if state == "AWAIT_HUMAN_DECISION":
                    current["human_gate_reason"] = "REVIEW_LIMIT"
                if state in {"BLOCKED", "AWAIT_HUMAN_DECISION"}:
                    self.write_final_report(target)
                rh.write_json(current_path, current)

                errors = rh.validate_task(target, "001_feature")
                self.assertTrue(any("visual review input manifest implementation_commit must match CURRENT" in error for error in errors), errors)

        tmp, target = self.make_project()
        with tmp:
            self.require_visual_review(target)
            self.freeze_and_start(target)
            self.write_result(target, commit="impl-current")
            self.write_visual_input_manifest(target, implementation_commit="impl-current")
            rh.apply_transition(target, "001_feature", expected_state="EXECUTING", next_state="READY_FOR_GPT_REVIEW")
            visual_dir = rh.result_root(target, "001_feature") / "visual_review"
            rh.write_json(visual_dir / "VISUAL_REVIEW.json", {"schema": "broken"})
            errors = rh.validate_task(target, "001_feature")
            self.assertTrue(any("missing required field" in error or "schema" in error for error in errors), errors)

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
        self.assertIn("按当前 `automation/reviewed_handoff/templates/PLAN.md` 自检", prompt)
        self.assertIn("`## Out of scope`", prompt)
        self.assertIn("不得写 `CURRENT=PLAN_FROZEN`", prompt)
        self.assertIn("artifact-only commit 不代表新 workflow state", prompt)
        self.assertIn("本地 watcher 只以 `CURRENT.json` 作为 routing source of truth", prompt)
        self.assertNotIn("reviewed-handoff transition apply", prompt)
        self.assertNotIn("reviewed-handoff review record", prompt)

    def test_scheduled_prompt_requires_final_report_preflight_before_terminal_current(self) -> None:
        prompt = rh.read_text(Path("templates/reviewed_handoff/prompts/REVIEWER_SCHEDULED_TASK.md"))

        self.assertIn("automation/reviewed_handoff/templates/FINAL_REPORT.md", prompt)
        self.assertIn("以运行时当前 template 为 source of truth", prompt)
        self.assertIn("不允许凭记忆猜 headings", prompt)
        self.assertIn("重新读取刚写出的 `FINAL_REPORT.md`", prompt)
        self.assertIn("全部 required H2 headings", prompt)
        self.assertIn("只有 FINAL_REPORT preflight 通过后，才允许最后写 `CURRENT.json`", prompt)
        self.assertIn("`PASS`", prompt)
        self.assertIn("`BLOCKED`", prompt)
        self.assertIn("`AWAIT_HUMAN_DECISION`", prompt)
        self.assertIn("`REVIEW_LIMIT` human gate", prompt)
        self.assertIn("`PLANNER_DECISION` human gate", prompt)
        self.assertIn("`PASS -> AWAIT_HUMAN_DECISION`", prompt)
        self.assertIn("`## New capabilities / behavior`", prompt)
        self.assertIn("`## Example usage`", prompt)

    def test_prompts_require_text_review_for_private_user_facing_artifacts(self) -> None:
        planner = rh.read_text(Path("templates/reviewed_handoff/prompts/PLANNER.md"))
        executor = rh.read_text(Path("templates/reviewed_handoff/prompts/CODEX_EXECUTOR.md"))
        reviewer = rh.read_text(Path("templates/reviewed_handoff/prompts/REVIEWER_SCHEDULED_TASK.md"))

        self.assertIn("Text Review transport", planner)
        self.assertIn("host-local private", planner)
        self.assertIn("ai-bridge text-review encrypt", executor)
        self.assertIn("不要提交 plaintext", executor)
        self.assertIn("TEXT_REVIEW.json", reviewer)
        self.assertIn("plaintext SHA-256", reviewer)
        self.assertIn("不得把明显 failure 推给 human gate", reviewer)

    def test_executor_prompt_routes_production_plugin_replay_to_bridge_wrapper(self) -> None:
        prompt = rh.read_text(Path("templates/reviewed_handoff/prompts/CODEX_EXECUTOR.md"))

        self.assertIn("ai-bridge plugin-replay", prompt)
        self.assertIn("fresh production Codex runtime", prompt)
        self.assertIn("不要自行拼 raw nested `codex exec`", prompt)
        self.assertIn("普通代码实现、普通测试和普通 Reviewed Handoff", prompt)

    def test_planner_prompt_requires_final_report_preflight_for_terminal_human_gate(self) -> None:
        prompt = rh.read_text(Path("templates/reviewed_handoff/prompts/PLANNER.md"))

        self.assertIn("automation/reviewed_handoff/templates/FINAL_REPORT.md", prompt)
        self.assertIn("以运行时当前 template 为 source of truth", prompt)
        self.assertIn("不允许凭记忆猜 headings", prompt)
        self.assertIn("重新读取刚写出的 `FINAL_REPORT.md`", prompt)
        self.assertIn("全部 required H2 headings", prompt)
        self.assertIn("只有 FINAL_REPORT preflight 通过后，才允许最后写 terminal `CURRENT.json`", prompt)
        self.assertIn("`PLANNER_DECISION` human gate", prompt)
        self.assertIn("`## New capabilities / behavior`", prompt)
        self.assertIn("`## Example usage`", prompt)

    def test_planner_prompt_requires_plan_template_self_check_before_freeze(self) -> None:
        prompt = rh.read_text(Path("templates/reviewed_handoff/prompts/PLANNER.md"))

        self.assertIn("写 `CURRENT.state=PLAN_FROZEN` 前", prompt)
        self.assertIn("按当前 `automation/reviewed_handoff/templates/PLAN.md` 自检", prompt)
        self.assertIn("`## Out of scope`", prompt)
        self.assertIn("若 PLAN 不合法，保持 `CURRENT` 不进入 `PLAN_FROZEN`", prompt)

    def test_reviewed_handoff_state_graph_matches_schema(self) -> None:
        expected = {
            "PLAN_REQUESTED": {"PLAN_FROZEN", "BLOCKED"},
            "PLAN_FROZEN": {"EXECUTING", "BLOCKED"},
            "EXECUTING": {"WAITING_FOR_CI", "READY_FOR_GPT_REVIEW", "NEEDS_GPT_PLANNER", "BLOCKED"},
            "WAITING_FOR_CI": {"READY_FOR_GPT_REVIEW", "REVISE", "BLOCKED"},
            "NEEDS_GPT_PLANNER": {"PLAN_FROZEN", "AWAIT_HUMAN_DECISION", "BLOCKED"},
            "READY_FOR_GPT_REVIEW": {"REVISE", "PASS", "BLOCKED"},
            "REVISE": {"EXECUTING", "NEEDS_GPT_PLANNER", "AWAIT_HUMAN_DECISION", "BLOCKED"},
            "PASS": {"AWAIT_HUMAN_DECISION"},
            "AWAIT_HUMAN_DECISION": {"REVISE", "NEEDS_GPT_PLANNER"},
            "BLOCKED": set(),
        }
        schema = rh.load_json(Path("templates/reviewed_handoff/schema.json"))

        self.assertEqual(rh.ALLOWED_TRANSITIONS, expected)
        self.assertEqual({key: set(value) for key, value in schema["allowed_transitions"].items()}, expected)

    def test_human_reject_after_pass_can_route_to_revise_without_resetting_review_budget(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            self.write_plan(target)
            self.write_result(target, commit="impl-pass", ci_status="PASS")
            self.remote_write_review_transaction(target, decision="PASS", body="Reviewer pass history must remain intact.")

            current = rh.record_human_decision(
                target,
                "001_feature",
                decision="REJECT",
                route="REVISE",
                body="The current artifact violates the frozen requirement.",
            )

            self.assertEqual(current["state"], "REVISE")
            self.assertEqual(current["next_action"], "RUN_CODEX_REPAIR")
            self.assertEqual(current["review_round"], 1)
            self.assertEqual(current["max_review_rounds"], 2)
            self.assertEqual(current["last_review_decision"], "PASS")
            self.assertEqual(current["human_rejection"]["route"], "REVISE")
            latest, _path, errors = rh.latest_review_metadata(target, "001_feature")
            self.assertEqual(errors, [])
            self.assertEqual((latest or {}).get("decision"), "PASS")
            self.assertEqual(rh.validate_task(target, "001_feature"), [])

            executing = rh.apply_transition(target, "001_feature", expected_state="REVISE", next_state="EXECUTING")
            self.assertEqual(executing["state"], "EXECUTING")
            self.assertEqual(executing["review_round"], 1)
            self.assertEqual(rh.validate_task(target, "001_feature"), [])

            ready = rh.apply_transition(target, "001_feature", expected_state="EXECUTING", next_state="READY_FOR_GPT_REVIEW")
            self.assertEqual(ready["state"], "READY_FOR_GPT_REVIEW")
            second_review = rh.record_review(target, "001_feature", decision="PASS", body="Human rejection repair satisfied.")
            self.assertEqual(second_review["review_round"], 2)
            self.assertTrue((rh.result_root(target, "001_feature") / "REVIEW_2.md").exists())

    def test_human_reject_after_pass_can_route_to_planner_without_resetting_budgets(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            self.write_plan(target)
            self.write_result(target, commit="impl-pass", ci_status="PASS")
            self.remote_write_review_transaction(target, decision="PASS", body="Reviewer pass history must remain intact.")

            current = rh.record_human_decision(
                target,
                "001_feature",
                decision="REJECT",
                route="NEEDS_GPT_PLANNER",
                body="The frozen Plan omitted the actual user-facing acceptance condition.",
            )

            self.assertEqual(current["state"], "NEEDS_GPT_PLANNER")
            self.assertEqual(current["next_action"], "RUN_GPT_PLANNER")
            self.assertEqual(current["review_round"], 1)
            self.assertEqual(current["plan_revision"], 0)
            self.assertEqual(current["last_review_decision"], "PASS")
            self.assertEqual(current["human_rejection"]["route"], "NEEDS_GPT_PLANNER")
            self.assertEqual(rh.validate_task(target, "001_feature"), [])

    def test_human_reject_budget_exhaustion_cannot_reopen(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            self.write_plan(target)
            self.write_result(target, commit="impl-pass", ci_status="PASS")
            current_path = rh.task_root(target, "001_feature") / "CURRENT.json"
            current = rh.load_json(current_path)
            current["max_review_rounds"] = 1
            rh.write_json(current_path, current)
            self.remote_write_review_transaction(target, decision="PASS", body="Pass at final review budget.")

            with self.assertRaisesRegex(ValueError, "review budget exhausted"):
                rh.record_human_decision(target, "001_feature", decision="REJECT", route="REVISE", body="Reject.")

        tmp, target = self.make_project()
        with tmp:
            self.write_plan(target)
            self.write_result(target, commit="impl-pass", ci_status="PASS")
            current_path = rh.task_root(target, "001_feature") / "CURRENT.json"
            current = rh.load_json(current_path)
            current["plan_revision"] = 1
            rh.write_json(current_path, current)
            self.remote_write_review_transaction(target, decision="PASS", body="Pass after planner budget was used.")

            with self.assertRaisesRegex(ValueError, "plan revision budget exhausted"):
                rh.record_human_decision(
                    target,
                    "001_feature",
                    decision="REJECT",
                    route="NEEDS_GPT_PLANNER",
                    body="Reject.",
                )

    def test_human_reject_requires_pass_gate_and_cannot_bypass_transaction(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            self.write_plan(target)
            self.write_result(target, commit="impl-pass", ci_status="PASS")
            self.remote_write_review_transaction(target, decision="PASS", body="Reviewer pass history.")

            with self.assertRaisesRegex(ValueError, "reviewed-handoff human record"):
                rh.apply_transition(target, "001_feature", expected_state="AWAIT_HUMAN_DECISION", next_state="REVISE")

            current_path = rh.task_root(target, "001_feature") / "CURRENT.json"
            current = rh.load_json(current_path)
            current["human_gate_reason"] = "REVIEW_LIMIT"
            rh.write_json(current_path, current)
            with self.assertRaisesRegex(ValueError, "only valid after a PASS human gate"):
                rh.record_human_decision(target, "001_feature", decision="REJECT", route="REVISE", body="Reject.")

    def test_bridge_cli_routes_human_decision_record(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            self.write_plan(target)
            self.write_result(target, commit="impl-pass", ci_status="PASS")
            self.remote_write_review_transaction(target, decision="PASS", body="Reviewer pass history.")

            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(
                    bridge_cli.main(
                        [
                            "reviewed-handoff",
                            "human",
                            "record",
                            "--target",
                            str(target),
                            "--task-key",
                            "001_feature",
                            "--decision",
                            "REJECT",
                            "--route",
                            "REVISE",
                            "--body",
                            "User found a frozen-plan violation.",
                        ]
                    ),
                    0,
                )

            current = rh.load_json(rh.task_root(target, "001_feature") / "CURRENT.json")
            self.assertEqual(current["state"], "REVISE")
            self.assertEqual(current["review_round"], 1)

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

    def test_external_review_silence_under_and_over_two_hours_is_waiting_not_blocked(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            self.freeze_and_start(target)
            self.write_result(target, commit="2c54c52f287be94c5919bc5886fb52804f94fc49")
            rh.apply_transition(target, "001_feature", expected_state="EXECUTING", next_state="READY_FOR_GPT_REVIEW")
            current_path = rh.task_root(target, "001_feature") / "CURRENT.json"
            current = rh.load_json(current_path)
            started = datetime(2026, 8, 18, 10, 0, tzinfo=timezone.utc)
            current["external_wait_started_at"] = started.isoformat()
            rh.write_json(current_path, current)

            early = rh.reviewed_external_wait_status(target, "001_feature", now=started + timedelta(minutes=119))
            late = rh.reviewed_external_wait_status(target, "001_feature", now=started + timedelta(minutes=121))

            self.assertEqual(early["operational_status"], "waiting_external_review")
            self.assertEqual(early["external_owner"], "Reviewer")
            self.assertTrue(early["within_minimum_grace"])
            self.assertFalse(early["may_block"])
            self.assertEqual(late["operational_status"], "waiting_external_review")
            self.assertFalse(late["within_minimum_grace"])
            self.assertFalse(late["may_block"])
            self.assertEqual(rh.load_json(current_path)["review_round"], 0)
            self.assertEqual(rh.load_json(current_path)["state"], "READY_FOR_GPT_REVIEW")

    def test_stale_review_does_not_trigger_repeat_revise(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            self.freeze_and_start(target)
            new_commit = "2c54c52f287be94c5919bc5886fb52804f94fc49"
            old_commit = "846e3d96c2037e3efc1bb9e325f61ea8097ae32d"
            self.write_result(target, commit=new_commit)
            rh.apply_transition(target, "001_feature", expected_state="EXECUTING", next_state="READY_FOR_GPT_REVIEW")
            rh.write_text(
                rh.result_root(target, "001_feature") / "REVIEW_1.md",
                "---\n"
                f"schema: {rh.REVIEW_SCHEMA}\n"
                "task_key: 001_feature\n"
                "review_round: 1\n"
                "decision: REVISE\n"
                f"implementation_commit: {old_commit}\n"
                "---\n\n"
                "Old Planner/Reviewer decision for an earlier implementation.\n",
            )
            current_path = rh.task_root(target, "001_feature") / "CURRENT.json"
            current = rh.load_json(current_path)
            current["review_round"] = 1
            current["last_review_decision"] = "REVISE"
            rh.write_json(current_path, current)

            status = rh.reviewed_external_wait_status(target, "001_feature")
            plan = rh.plan_transition(target, "001_feature")

            self.assertEqual(status["operational_status"], "waiting_external_review")
            self.assertTrue(status["stale_decision"])
            self.assertFalse(status["fresh_decision"])
            self.assertEqual(status["current_identity"], new_commit)
            self.assertEqual(status["latest_decision_identity"], old_commit)
            self.assertEqual(plan["next_action"], "WAIT_SCHEDULED_GPT_REVIEW")
            self.assertNotIn("next_state", plan)
            self.assertEqual(rh.load_json(current_path)["review_round"], 1)
            self.assertEqual(rh.load_json(current_path)["state"], "READY_FOR_GPT_REVIEW")

    def test_fresh_review_normally_routes_repair(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            self.freeze_and_start(target)
            current_commit = "2c54c52f287be94c5919bc5886fb52804f94fc49"
            self.write_result(target, commit=current_commit)
            rh.apply_transition(target, "001_feature", expected_state="EXECUTING", next_state="READY_FOR_GPT_REVIEW")

            current = rh.record_review(target, "001_feature", decision="REVISE", body="Fresh review for current implementation.")
            plan = rh.plan_transition(target, "001_feature")

            self.assertEqual(current["review_round"], 1)
            self.assertEqual(current["state"], "REVISE")
            self.assertEqual(plan["next_state"], "EXECUTING")
            self.assertEqual(plan["next_action"], "RUN_CODEX_REPAIR")

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
