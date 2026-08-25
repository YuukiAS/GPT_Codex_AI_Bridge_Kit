from __future__ import annotations

import contextlib
import io
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ai_bridge_kit import agent_flow
from ai_bridge_kit import visual_review
from ai_bridge_kit.cli import main


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class FakeRuntimeAdapter(agent_flow.RuntimeAdapter):
    name = "fake"

    def launch_role(self, request: agent_flow.RoleLaunchRequest) -> agent_flow.RoleReceipt:
        return agent_flow.RoleReceipt(
            role=request.role,
            session_id=f"{request.role.lower()}-session",
            runtime_adapter=self.name,
            worktree_id=f"{request.role.lower()}-worktree",
            base_task_nonce=request.request_nonce,
            allowed_write_scope=request.allowed_write_scope,
            start_or_resume_status="started",
            produced_commit="",
            produced_evidence_id=f"{request.role.lower()}-evidence",
            commit_kind="no_commit",
        )


class AgentFlowTests(unittest.TestCase):
    def make_project(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        tmp = tempfile.TemporaryDirectory()
        target = Path(tmp.name) / "toy"
        target.mkdir()
        write(target / "src" / "calc.py", "def add(a, b):\n    return a + b\n")
        write(target / "tests" / "test_calc.py", "from src.calc import add\n\ndef test_add():\n    assert add(1, 2) == 3\n")
        write(target / "README.md", "# Toy\n")
        state, _ = agent_flow.install_agent_flow(target)
        self.assertEqual(state, "configured")
        agent_flow.init_task(target, "001_toy")
        root = agent_flow.task_root(target, "001_toy")
        write(root / "FROZEN_CONTRACT.md", "# Frozen Contract\n\nREQ_EXAMPLE_001: add returns sum.\n")
        agent_flow.write_json(
            root / "REQUIREMENT_LEDGER.json",
            {
                "schema": "AI_BRIDGE_REQUIREMENT_LEDGER_V1",
                "requirements": [
                    {
                        "requirement_id": "REQ_EXAMPLE_001",
                        "source": {
                            "path": "automation/agent_flow/tasks/001_toy/FROZEN_CONTRACT.md",
                            "clause": "add returns sum",
                        },
                        "type": "IMPLEMENTATION",
                        "blocking": True,
                        "owner_role": "Executor",
                        "verifier_authority": "test_calc checks add",
                        "threshold": None,
                        "threshold_provenance": None,
                        "change_requires_contract_review": False,
                    }
                ],
            },
        )
        return tmp, target

    def snapshot_and_bundle(self, target: Path) -> dict[str, str]:
        snapshot = agent_flow.snapshot(target, "001_toy")
        evidence_path = agent_flow.result_root(target, "001_toy") / "verification" / "unit.json"
        agent_flow.write_json(
            evidence_path,
            {
                "schema": "AI_BRIDGE_EVIDENCE_V1",
                "evidence_id": "unit-add",
                "status": "PASS",
                "review_target_id": snapshot["review_target_id"],
            },
        )
        bundle = {
            "schema": "AI_BRIDGE_REVIEW_BUNDLE_V1",
            "task_key": "001_toy",
            "review_target_id": snapshot["review_target_id"],
            "frozen_contract_sha256": snapshot["frozen_contract_sha256"],
            "requirement_ledger_sha256": snapshot["requirement_ledger_sha256"],
            "implementation_semantic_digest_sha256": snapshot["implementation_semantic_digest_sha256"],
            "verifier_semantic_digest_sha256": snapshot["verifier_semantic_digest_sha256"],
            "required_evidence": [
                {
                    "evidence_id": "unit-add",
                    "kind": "unit_test",
                    "path": "results/001_toy/verification/unit.json",
                    "sha256": agent_flow.file_sha256(evidence_path),
                    "status": "PASS",
                    "required": True,
                    "target_sensitive": True,
                    "review_target_id": snapshot["review_target_id"],
                }
            ],
        }
        bundle["bundle_sha256"] = agent_flow.bundle_digest(bundle)
        agent_flow.write_json(agent_flow.result_root(target, "001_toy") / "REVIEW_BUNDLE.json", bundle)
        agent_flow.write_current_findings(target, "001_toy", [], snapshot["review_target_id"])
        return snapshot

    def enable_visual_policy(self, target: Path) -> None:
        profile = agent_flow.load_project_profile(target)
        profile["optional_visual_source_policy"] = {
            "enabled": True,
            "manifest_path": "results/001_toy/visual_review/visual_inputs.json",
            "evidence_path": "results/001_toy/visual_review/VISUAL_REVIEW.json",
            "privacy_policy": "PUBLIC_SAFE_ONLY",
        }
        agent_flow.write_json(agent_flow.agent_root(target) / "PROJECT_PROFILE.json", profile)

    def write_agent_visual_review(self, target: Path, snapshot: dict[str, str], *, review_target_id: str | None = None) -> dict:
        visual_dir = agent_flow.result_root(target, "001_toy") / "visual_review"
        image = visual_dir / "primary.png"
        image.parent.mkdir(parents=True, exist_ok=True)
        image.write_bytes(
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?"
            b"\x00\x05\xfe\x02\xfeA\xe2U\xa7\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        request = agent_flow.load_json(agent_flow.task_root(target, "001_toy") / "REQUEST.json")
        bindings = {
            "request_nonce": request["request_nonce"],
            "review_target_id": review_target_id or snapshot["review_target_id"],
            "frozen_contract_sha256": snapshot["frozen_contract_sha256"],
            "requirement_ledger_sha256": snapshot["requirement_ledger_sha256"],
            "implementation_semantic_digest_sha256": snapshot["implementation_semantic_digest_sha256"],
            "verifier_semantic_digest_sha256": snapshot["verifier_semantic_digest_sha256"],
        }
        manifest = {
            "schema": visual_review.VISUAL_INPUT_MANIFEST_SCHEMA,
            "task_key": "001_toy",
            "workflow_type": "agent_flow",
            "review_kind": "synthetic",
            "privacy_policy": "PUBLIC_SAFE_ONLY",
            "rubric": {"instructions": "Synthetic visual fixture must pass."},
            "identity_bindings": bindings,
            "inputs": [{"logical_id": "primary", "path": "results/001_toy/visual_review/primary.png"}],
        }
        normalized = visual_review.normalize_manifest(target, manifest)
        artifact = visual_review.assemble_visual_review(
            manifest=normalized,
            model_output={
                "overall_decision": "PASS",
                "item_reviews": [{"item_id": "primary", "decision": "PASS", "summary": "ok", "observations": [], "requirement_ids": []}],
                "blocking_findings": [],
                "non_blocking_notes": [],
            },
            model="gpt-test",
        )
        visual_review.write_json(visual_dir / "VISUAL_REVIEW.json", artifact)
        return artifact

    def add_visual_review_to_bundle(self, target: Path, snapshot: dict[str, str], artifact: dict) -> None:
        path = agent_flow.result_root(target, "001_toy") / "visual_review" / "VISUAL_REVIEW.json"
        bundle_path = agent_flow.result_root(target, "001_toy") / "REVIEW_BUNDLE.json"
        bundle = agent_flow.load_json(bundle_path)
        bundle["required_evidence"].append(
            {
                "evidence_id": artifact["evidence_id"],
                "kind": "visual_review",
                "path": "results/001_toy/visual_review/VISUAL_REVIEW.json",
                "sha256": agent_flow.file_sha256(path),
                "status": artifact["status"],
                "required": True,
                "target_sensitive": True,
                "review_target_id": snapshot["review_target_id"],
            }
        )
        bundle["bundle_sha256"] = agent_flow.bundle_digest(bundle)
        agent_flow.write_json(bundle_path, bundle)

    def write_planner_and_final_pass(self, target: Path, snapshot: dict[str, str]) -> None:
        root = agent_flow.task_root(target, "001_toy")
        request = agent_flow.load_json(root / "REQUEST.json")
        bundle = agent_flow.load_json(agent_flow.result_root(target, "001_toy") / "REVIEW_BUNDLE.json")
        planner_review_path = agent_flow.result_root(target, "001_toy") / "planner_reviews" / "pass.md"
        write(planner_review_path, "Planner pass candidate for current target.\n")
        agent_flow.write_json(
            root / "PLANNER_PASS_CANDIDATE.json",
            {
                "schema": "AI_BRIDGE_PLANNER_PASS_CANDIDATE_V1",
                "role": "Planner",
                "task_key": "001_toy",
                "request_nonce": request["request_nonce"],
                "review_target_id": snapshot["review_target_id"],
                "artifact_path": "results/001_toy/planner_reviews/pass.md",
                "artifact_sha256": agent_flow.file_sha256(planner_review_path),
                "decision": "PLANNER_PASS_CANDIDATE",
                "touched_paths": ["automation/agent_flow/tasks/001_toy/PLANNER_PASS_CANDIDATE.json", "results/001_toy/planner_reviews/pass.md"],
            },
        )
        critic_review_path = agent_flow.result_root(target, "001_toy") / "critic_reviews" / "final.md"
        write(critic_review_path, "Final Critic pass for current target.\n")
        agent_flow.write_json(
            root / "FINAL_CRITIC_AUDIT.json",
            {
                "schema": "AI_BRIDGE_FINAL_CRITIC_AUDIT_V1",
                "role": "Critic",
                "task_key": "001_toy",
                "request_nonce": request["request_nonce"],
                "review_target_id": snapshot["review_target_id"],
                "artifact_path": "results/001_toy/critic_reviews/final.md",
                "artifact_sha256": agent_flow.file_sha256(critic_review_path),
                "frozen_contract_sha256": snapshot["frozen_contract_sha256"],
                "requirement_ledger_sha256": snapshot["requirement_ledger_sha256"],
                "review_bundle_sha256": bundle["bundle_sha256"],
                "planner_pass_candidate_artifact": "PLANNER_PASS_CANDIDATE.json",
                "decision": "CRITIC_FINAL_PASS",
                "blocking_findings": [],
                "audit_checks": {
                    "contract_not_silently_weakened": True,
                    "requirement_ledger_not_expanded_by_runtime_roles": True,
                    "planner_blocking_requirements_closed": True,
                    "verifier_no_uncited_blocking_requirement_or_threshold": True,
                    "executor_no_test_aware_alternate_behavior": True,
                    "review_bundle_bound_to_current_target": True,
                    "required_evidence_passed": True,
                    "ci_passed_when_required": True,
                    "no_unresolved_contract_ambiguity_or_contradiction": True,
                },
                "touched_paths": [],
            },
        )

    def write_critic_freeze(self, target: Path, critic_mode: str = "REQUIRED_INITIAL") -> None:
        root = agent_flow.task_root(target, "001_toy")
        request = agent_flow.load_json(root / "REQUEST.json")
        critic_review_path = agent_flow.result_root(target, "001_toy") / "critic_reviews" / "freeze.md"
        write(critic_review_path, "Critic froze contract and ledger.\n")
        agent_flow.write_json(
            root / "CRITIC_FREEZE.json",
            {
                "schema": "AI_BRIDGE_CRITIC_FREEZE_V1",
                "role": "Critic",
                "task_key": "001_toy",
                "request_nonce": request["request_nonce"],
                "decision": "PLAN_FROZEN",
                "critic_mode": critic_mode,
                "artifact_path": "results/001_toy/critic_reviews/freeze.md",
                "artifact_sha256": agent_flow.file_sha256(critic_review_path),
                "frozen_contract_sha256": agent_flow.file_sha256(root / "FROZEN_CONTRACT.md"),
                "requirement_ledger_sha256": agent_flow.file_sha256(root / "REQUIREMENT_LEDGER.json"),
                "touched_paths": [
                    "automation/agent_flow/tasks/001_toy/CRITIC_FREEZE.json",
                    "automation/agent_flow/tasks/001_toy/FROZEN_CONTRACT.md",
                    "automation/agent_flow/tasks/001_toy/REQUIREMENT_LEDGER.json",
                    "results/001_toy/critic_reviews/freeze.md",
                ],
            },
        )

    def write_role_receipt(self, target: Path, role: str, session: str | None = None, worktree: str | None = None) -> None:
        root = agent_flow.task_root(target, "001_toy")
        request = agent_flow.load_json(root / "REQUEST.json")
        profile = agent_flow.load_project_profile(target)
        adapter = FakeRuntimeAdapter()
        receipt = adapter.launch_role(
            agent_flow.RoleLaunchRequest(
                role=role,
                task_key="001_toy",
                request_nonce=request["request_nonce"],
                review_target_id=None,
                base_ref="HEAD",
                allowed_write_scope=profile["role_write_scopes"][role],
                worktree_policy="detached",
            )
        ).to_json()
        snapshot_path = root / "SOURCE_SNAPSHOT.json"
        if snapshot_path.exists():
            receipt["base_review_target_id"] = agent_flow.load_json(snapshot_path)["review_target_id"]
        if session:
            receipt["session_id"] = session
        if worktree:
            receipt["worktree_id"] = worktree
        agent_flow.write_json(agent_flow.role_receipt_path(target, "001_toy", role), receipt)

    def write_controller_receipt(self, target: Path) -> None:
        self.write_role_receipt(target, "Controller")

    def write_verifier_freeze(self, target: Path) -> None:
        root = agent_flow.task_root(target, "001_toy")
        manifest = agent_flow.load_json(root / "VERIFIER_SOURCE_MANIFEST.json")
        agent_flow.write_json(
            root / "VERIFIER_FREEZE.json",
            {
                "schema": "AI_BRIDGE_VERIFIER_FREEZE_V1",
                "task_key": "001_toy",
                "request_nonce": agent_flow.load_json(root / "REQUEST.json")["request_nonce"],
                "review_target_id": agent_flow.load_json(root / "SOURCE_SNAPSHOT.json")["review_target_id"],
                "verifier_semantic_digest_sha256": manifest["semantic_digest_sha256"],
                "verifier_evidence_id": "verifier-evidence",
            },
        )
        self.write_role_receipt(target, "Verifier")

    def write_executor_result(self, target: Path) -> None:
        agent_flow.write_json(
            agent_flow.result_root(target, "001_toy") / "implementation" / "executor_result.json",
            {
                "schema": "AI_BRIDGE_EXECUTOR_RESULT_V1",
                "task_key": "001_toy",
                "request_nonce": agent_flow.load_json(agent_flow.task_root(target, "001_toy") / "REQUEST.json")["request_nonce"],
                "review_target_id": agent_flow.load_json(agent_flow.task_root(target, "001_toy") / "SOURCE_SNAPSHOT.json")["review_target_id"],
                "status": "complete",
                "touched_paths": ["src/calc.py", "results/001_toy/implementation/executor_result.json"],
            },
        )

    def apply_next(self, target: Path, expected_state: str, expected_next: str) -> dict[str, object]:
        plan = agent_flow.plan_transition(target, "001_toy")
        self.assertTrue(plan["valid"], plan)
        self.assertEqual(plan.get("state"), expected_state)
        self.assertEqual(plan.get("next_state"), expected_next)
        return agent_flow.apply_transition(
            target,
            "001_toy",
            expected_state=expected_state,
            next_state=expected_next,
            next_action=str(plan.get("next_action", "")),
        )

    def test_install_status_validate_and_task_init_do_not_create_branch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            target.mkdir()
            state, _ = agent_flow.install_agent_flow(target)
            self.assertEqual(state, "configured")
            self.assertEqual(agent_flow.inspect_agent_flow(target).state, "configured")
            actions = agent_flow.init_task(target, "001_example")
            self.assertTrue(any("REQUEST.json" in action for action in actions))
            request = agent_flow.load_json(agent_flow.task_root(target, "001_example") / "REQUEST.json")
            current = agent_flow.load_json(agent_flow.task_root(target, "001_example") / "CURRENT.json")
            self.assertEqual(request["status"], "PLAN_REQUESTED")
            self.assertFalse(request["contract_frozen"])
            self.assertIsNone(current["frozen_contract_sha256"])
            self.assertFalse((target / ".git" / "refs" / "heads" / "develop").exists())

    def test_install_force_preserves_custom_project_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            target.mkdir()
            agent_flow.install_agent_flow(target)
            profile_path = agent_flow.agent_root(target) / "PROJECT_PROFILE.json"
            profile = agent_flow.load_json(profile_path)
            profile["project_objective"] = "custom objective"
            agent_flow.write_json(profile_path, profile)
            agent_flow.install_agent_flow(target, force=True)
            self.assertEqual(agent_flow.load_json(profile_path)["project_objective"], "custom objective")

    def test_existing_cli_commands_and_agent_flow_cli_are_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["init", "--target", str(target)]), 0)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["validate", "--target", str(target)]), 0)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["agent-flow", "install", "--target", str(target)]), 0)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["agent-flow", "status", "--target", str(target)]), 0)

    def test_snapshot_uses_canonical_manifests_and_ignores_receipts_current_docs(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            first = self.snapshot_and_bundle(target)
            write(target / "results" / "001_toy" / "receipts" / "controller.json", "{}\n")
            current_path = agent_flow.task_root(target, "001_toy") / "CURRENT.json"
            current = agent_flow.load_json(current_path)
            current["last_change_class"] = "CURRENT_OR_ROUTING_ONLY_CHANGED"
            agent_flow.write_json(current_path, current)
            write(target / "docs" / "note.md", "documentation only\n")
            second = agent_flow.snapshot(target, "001_toy")
            self.assertEqual(first["review_target_id"], second["review_target_id"])
            self.assertNotIn("paths", second)
            self.assertNotIn("source_snapshot_sha256", second)
            self.assertNotIn("bundle_sha256", second)
            self.assertTrue((agent_flow.task_root(target, "001_toy") / "IMPLEMENTATION_SOURCE_MANIFEST.json").exists())
            self.assertTrue((agent_flow.task_root(target, "001_toy") / "VERIFIER_SOURCE_MANIFEST.json").exists())

    def test_snapshot_uses_tracked_content_when_git_is_available(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            subprocess.check_call(["git", "init", "--initial-branch", "main"], cwd=target, stdout=subprocess.DEVNULL)
            subprocess.check_call(["git", "add", "."], cwd=target, stdout=subprocess.DEVNULL)
            first = agent_flow.snapshot(target, "001_toy")
            write(target / "src" / "untracked_local.py", "def local_only():\n    return 'ignore'\n")
            second = agent_flow.snapshot(target, "001_toy")
            self.assertEqual(first["review_target_id"], second["review_target_id"])

    def test_implementation_or_verifier_source_changes_alter_review_target(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            first = agent_flow.snapshot(target, "001_toy")
            write(target / "src" / "calc.py", "def add(a, b):\n    return a + b + 0\n")
            second = agent_flow.snapshot(target, "001_toy")
            self.assertNotEqual(first["review_target_id"], second["review_target_id"])
            write(target / "tests" / "test_calc.py", "from src.calc import add\n\ndef test_add():\n    assert add(2, 2) == 4\n")
            third = agent_flow.snapshot(target, "001_toy")
            self.assertNotEqual(second["review_target_id"], third["review_target_id"])

    def test_change_classification_and_incremental_invalidation(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            profile = agent_flow.load_project_profile(target)
            cases = {
                "automation/agent_flow/tasks/001_toy/FROZEN_CONTRACT.md": "CONTRACT_CHANGED",
                "automation/agent_flow/tasks/001_toy/REQUIREMENT_LEDGER.json": "REQUIREMENT_LEDGER_CHANGED",
                "src/calc.py": "IMPLEMENTATION_SOURCE_CHANGED",
                "tests/test_calc.py": "VERIFIER_SOURCE_CHANGED",
                "pyproject.toml": "RUNTIME_ENVIRONMENT_CHANGED",
                ".github/workflows/ci.yml": "CI_WORKFLOW_CHANGED",
                "automation/agent_flow/schema.json": "CONTROL_PLANE_ONLY_CHANGED",
                "results/001_toy/receipts/a.json": "RECEIPT_OR_MANIFEST_ONLY_CHANGED",
                "automation/agent_flow/tasks/001_toy/CURRENT.json": "CURRENT_OR_ROUTING_ONLY_CHANGED",
                "docs/design.md": "DOC_ONLY_CHANGED",
            }
            for path, expected in cases.items():
                self.assertEqual(agent_flow.classify_paths([path], profile), expected)
            multi = agent_flow.classify_changes(["src/calc.py", "tests/test_calc.py"], profile)
            self.assertEqual(
                multi["change_classes"],
                ["IMPLEMENTATION_SOURCE_CHANGED", "VERIFIER_SOURCE_CHANGED"],
            )
            self.assertTrue(multi["invalidation_plan"]["heavy_verifier_required"])
            plan = agent_flow.invalidation_plan("CONTROL_PLANE_ONLY_CHANGED")
            self.assertFalse(plan["executor_restart"])
            self.assertFalse(plan["verifier_restart"])
            self.assertFalse(plan["heavy_verifier_required"])
            self.assertTrue(plan["lightweight_validation_only"])
            self.assertFalse(agent_flow.invalidation_plan("DOC_ONLY_CHANGED")["heavy_verifier_required"])
            self.assertTrue(agent_flow.invalidation_plan("IMPLEMENTATION_SOURCE_CHANGED")["heavy_verifier_required"])

    def test_second_heavy_verifier_for_same_target_requires_reason(self) -> None:
        current = {"heavy_verifier_runs": [{"review_target_id": "abc"}]}
        with self.assertRaises(ValueError):
            agent_flow.assert_heavy_verifier_reason(current, "abc", None)
        with self.assertRaises(ValueError):
            agent_flow.assert_heavy_verifier_reason(current, "abc", "CONTROL_PLANE_ONLY_CHANGED")
        agent_flow.assert_heavy_verifier_reason(current, "abc", "IMPLEMENTATION_SOURCE_CHANGED")

    def test_verifier_cannot_create_uncited_blocking_threshold(self) -> None:
        with self.assertRaises(ValueError):
            agent_flow.validate_requirement_ledger({"requirements": "not-a-list"})
        finding = {
            "finding_id": "F1",
            "classification": "VERIFIER_CONTRACT_DRIFT",
            "blocking": True,
            "requirement_ids": ["REQ_EXAMPLE_001"],
            "threshold": 1e-6,
            "threshold_provenance": "verifier_preference",
        }
        errors = agent_flow.validate_finding(finding, {"REQ_EXAMPLE_001"})
        self.assertTrue(any("threshold" in error for error in errors))
        ledger = {
            "requirements": [
                {
                    "requirement_id": "REQ_EXAMPLE_001",
                    "source": {"path": "automation/agent_flow/tasks/001_toy/FROZEN_CONTRACT.md"},
                    "threshold": 0.5,
                    "threshold_authority": "contract clause x",
                }
            ]
        }
        ok = {
            "finding_id": "F_OK",
            "classification": "IMPLEMENTATION_BUG",
            "blocking": True,
            "owner_role": "Executor",
            "requirement_ids": ["REQ_EXAMPLE_001"],
            "summary": "threshold failed",
            "observed_evidence": "unit",
            "required_repair": "fix",
            "required_regression_evidence": "test",
            "forbidden_workaround": "weaken threshold",
            "created_against_review_target_id": "target",
            "threshold": 0.5,
            "threshold_provenance": "requirement_ledger",
        }
        self.assertEqual(agent_flow.validate_finding_against_ledger(ok, agent_flow.ledger_requirements_by_id(ledger), "target"), [])
        diagnostic = {
            "finding_id": "F2",
            "classification": "DIAGNOSTIC_ANOMALY",
            "blocking": False,
            "threshold": 999,
        }
        self.assertEqual(agent_flow.validate_finding(diagnostic, set()), [])

    def test_controller_cannot_turn_verifier_fail_into_user_choice(self) -> None:
        with self.assertRaises(ValueError):
            agent_flow.route_findings(
                [
                    {
                        "finding_id": "F1",
                        "classification": "SCIENTIFIC_OR_PRODUCT_CHOICE_REQUIRED",
                        "blocking": True,
                        "planner_classified": False,
                    }
                ],
                controller_originated=True,
            )
        tmp, target = self.make_project()
        with tmp:
            snapshot = self.snapshot_and_bundle(target)
            request = agent_flow.load_json(agent_flow.task_root(target, "001_toy") / "REQUEST.json")
            choice_text = agent_flow.result_root(target, "001_toy") / "planner_reviews" / "choice.md"
            write(choice_text, "Planner classified this as user scientific/product choice.\n")
            agent_flow.write_json(
                agent_flow.result_root(target, "001_toy") / "planner_reviews" / "choice.json",
                {
                    "schema": "AI_BRIDGE_PLANNER_REVIEW_V1",
                    "role": "Planner",
                    "task_key": "001_toy",
                    "request_nonce": request["request_nonce"],
                    "decision": "SCIENTIFIC_OR_PRODUCT_CHOICE_REQUIRED",
                    "finding_id": "F2",
                    "review_target_id": snapshot["review_target_id"],
                    "artifact_path": "results/001_toy/planner_reviews/choice.md",
                    "artifact_sha256": agent_flow.file_sha256(choice_text),
                    "touched_paths": ["results/001_toy/planner_reviews/choice.json", "results/001_toy/planner_reviews/choice.md"],
                },
            )
            routed = agent_flow.route_findings(
                [
                    {
                        "finding_id": "F2",
                        "classification": "SCIENTIFIC_OR_PRODUCT_CHOICE_REQUIRED",
                        "blocking": True,
                        "created_against_review_target_id": snapshot["review_target_id"],
                        "planner_classification_artifact": "results/001_toy/planner_reviews/choice.json",
                    }
                ],
                target=target,
                task_key="001_toy",
            )
            self.assertEqual(routed["target_role"], "User")

    def test_project_adapter_returns_typed_evidence_without_authority_expansion(self) -> None:
        result = agent_flow.normalize_adapter_result(
            adapter_name="toy",
            evidence=[{"kind": "unit", "path": "results/001_toy/verification/unit.json"}],
            findings=[
                {
                    "finding_id": "F1",
                    "classification": "IMPLEMENTATION_BUG",
                    "blocking": True,
                    "requirement_ids": ["REQ_EXAMPLE_001"],
                }
            ],
        )
        self.assertEqual(result["schema"], "AI_BRIDGE_PROJECT_ADAPTER_RESULT_V1")
        potential = agent_flow.normalize_adapter_result(
            adapter_name="toy",
            findings=[{"finding_id": "F_POTENTIAL", "classification": "POTENTIAL_SCIENTIFIC_OR_PRODUCT_CHOICE", "blocking": False}],
        )
        self.assertEqual(potential["findings"][0]["classification"], "POTENTIAL_SCIENTIFIC_OR_PRODUCT_CHOICE")
        with self.assertRaises(ValueError):
            agent_flow.normalize_adapter_result(
                adapter_name="bad",
                findings=[
                    {
                        "finding_id": "F2",
                        "classification": "SCIENTIFIC_OR_PRODUCT_CHOICE_REQUIRED",
                        "blocking": True,
                    }
                ],
            )

    def test_exact_role_receipt_rejects_resume_last(self) -> None:
        errors = agent_flow.validate_role_receipt(
            {
                "role": "Verifier",
                "resume_strategy": "last",
                "runtime_adapter": "codex",
                "allowed_write_scope": ["tests/**"],
                "start_or_resume_status": "resumed",
            }
        )
        self.assertTrue(any("resume --last" in error for error in errors))
        self.assertTrue(any("session_id" in error for error in errors))
        omitted_kind_errors = agent_flow.validate_role_receipt(
            {
                "role": "Executor",
                "session_id": "thread-123",
                "runtime_adapter": "codex",
                "allowed_write_scope": ["src/**"],
                "start_or_resume_status": "started",
                "worktree_id": "executor-wt",
                "produced_commit": "abc123",
                "produced_evidence_id": "executor-evidence",
                "base_task_nonce": "nonce",
            },
            allow_fake_test=False,
        )
        self.assertTrue(any("commit_kind" in error for error in omitted_kind_errors))
        self.assertEqual(
            agent_flow.validate_role_receipt(
                {
                    "role": "Verifier",
                    "session_id": "thread-123",
                    "runtime_adapter": "codex",
                    "allowed_write_scope": ["tests/**"],
                    "start_or_resume_status": "resumed",
                    "worktree_id": "verifier-wt",
                    "produced_commit": "abc123",
                    "produced_evidence_id": "verifier-evidence",
                    "base_task_nonce": "nonce",
                    "commit_kind": "fake-test",
                },
                allow_fake_test=True,
            ),
            [],
        )

    def test_executor_test_aware_alternate_path_is_rejected(self) -> None:
        errors = agent_flow.validate_executor_result(
            {
                "test_aware_alternate_path": True,
                "touched_paths": ["src/calc.py", "tests/test_calc.py"],
            }
        )
        self.assertTrue(any("test-aware" in error for error in errors))
        self.assertTrue(any("forbidden authority path" in error for error in errors))

    def test_typed_routes_keep_ordinary_bug_out_of_critic(self) -> None:
        self.assertEqual(
            agent_flow.route_findings(
                [{"finding_id": "F1", "classification": "IMPLEMENTATION_BUG", "blocking": True}]
            )["target_role"],
            "Executor",
        )
        self.assertEqual(
            agent_flow.route_findings(
                [{"finding_id": "F2", "classification": "CONTRACT_AMBIGUITY", "blocking": True}]
            )["target_role"],
            "Planner",
        )

    def test_fake_verifier_freeze_is_rejected(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            root = agent_flow.task_root(target, "001_toy")
            current = agent_flow.load_json(root / "CURRENT.json")
            current["state"] = "VERIFIER_FROZEN"
            current["worktree_fast_forwarded"] = True
            agent_flow.write_json(root / "CURRENT.json", current)
            errors = agent_flow.validate_task_state(target, "001_toy")
            self.assertTrue(any("verifier-owned freeze receipt" in error for error in errors))

    def test_review_bundle_is_current_small_and_target_bound(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            self.snapshot_and_bundle(target)
            bundle, _ = agent_flow.validate_review_bundle(target, "001_toy")
            self.assertNotIn("historical_runtime_manifest", bundle)
            bundle["required_evidence"][0]["review_target_id"] = "wrong"
            agent_flow.write_json(agent_flow.result_root(target, "001_toy") / "REVIEW_BUNDLE.json", bundle)
            with self.assertRaises(ValueError):
                agent_flow.validate_review_bundle(target, "001_toy")

    def test_final_critic_gate_and_no_write_authority(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            root = agent_flow.task_root(target, "001_toy")
            snapshot = self.snapshot_and_bundle(target)
            current = agent_flow.load_json(root / "CURRENT.json")
            current["state"] = "AWAIT_HUMAN_DECISION"
            agent_flow.write_json(root / "CURRENT.json", current)
            self.assertTrue(any("FINAL_CRITIC" in error for error in agent_flow.validate_task_state(target, "001_toy")))
            agent_flow.write_json(root / "FINAL_CRITIC_AUDIT.json", {"decision": "CRITIC_FINAL_PASS", "touched_paths": ["src/calc.py"]})
            self.assertTrue(any("missing schema" in error or "touched_paths" in error for error in agent_flow.validate_task_state(target, "001_toy")))
            self.write_planner_and_final_pass(target, snapshot)
            current = agent_flow.load_json(root / "CURRENT.json")
            current["terminal_policy"] = "human_gate"
            agent_flow.write_json(root / "CURRENT.json", current)
            bundle_path = agent_flow.result_root(target, "001_toy") / "REVIEW_BUNDLE.json"
            bundle = agent_flow.load_json(bundle_path)
            bundle["required_evidence"].append({"id": "late", "target_sensitive": False})
            agent_flow.write_json(bundle_path, bundle)
            self.assertTrue(any("bundle_sha256 is stale" in error for error in agent_flow.validate_task_state(target, "001_toy")))
            bundle["bundle_sha256"] = agent_flow.bundle_digest(bundle)
            agent_flow.write_json(bundle_path, bundle)
            self.assertTrue(any("review_bundle_sha256 mismatch" in error for error in agent_flow.validate_task_state(target, "001_toy")))
            self.write_planner_and_final_pass(target, snapshot)
            self.assertEqual(agent_flow.validate_task_state(target, "001_toy"), [])

    def test_agent_flow_validate_consumes_role_and_authority_artifacts(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            snapshot = self.snapshot_and_bundle(target)
            receipts = agent_flow.result_root(target, "001_toy") / "receipts"
            base = {
                "runtime_adapter": "fake",
                "allowed_write_scope": ["automation/agent_flow/tasks/**/CURRENT.json"],
                "start_or_resume_status": "started",
                "produced_commit": "commit",
                "produced_evidence_id": "evidence",
                "base_task_nonce": agent_flow.load_json(agent_flow.task_root(target, "001_toy") / "REQUEST.json")["request_nonce"],
            }
            agent_flow.write_json(receipts / "controller_role_receipt.json", {**base, "role": "Controller", "session_id": "same", "worktree_id": "controller", "touched_paths": ["src/calc.py"]})
            agent_flow.write_json(receipts / "verifier_role_receipt.json", {**base, "role": "Verifier", "session_id": "same", "worktree_id": "controller"})
            agent_flow.write_json(receipts / "executor_role_receipt.json", {**base, "role": "Executor", "session_id": "exec", "worktree_id": "exec"})
            agent_flow.write_current_findings(
                target,
                "001_toy",
                [
                    {
                        "finding_id": "F_BAD",
                        "classification": "IMPLEMENTATION_BUG",
                        "blocking": True,
                        "owner_role": "Executor",
                        "requirement_ids": ["REQ_EXAMPLE_001"],
                        "summary": "bad",
                        "observed_evidence": "unit",
                        "required_repair": "fix",
                        "required_regression_evidence": "test",
                        "forbidden_workaround": "fake",
                        "created_against_review_target_id": "stale",
                    }
                ],
                "stale",
            )
            lines, code = agent_flow.validate_agent_flow(target)
            self.assertEqual(code, 1)
            text = "\n".join(lines)
            self.assertIn("Controller touched forbidden", text)
            self.assertIn("shares session", text)
            self.assertIn("not bound to current review_target_id", text)
            self.assertIn(snapshot["review_target_id"], agent_flow.canonical_json(agent_flow.load_json(agent_flow.task_root(target, "001_toy") / "SOURCE_SNAPSHOT.json")))

    def test_generic_schema_has_no_care_required_fields(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            lines, code = agent_flow.validate_agent_flow(target)
            self.assertEqual(code, 0, "\n".join(lines))
            profile_text = agent_flow.canonical_json(agent_flow.load_project_profile(target))
            for token in ["CARE", "MyoPS", "nnU-Net", "Slurm", "route_portfolio", "dataset_split"]:
                self.assertNotIn(token, profile_text)

    def test_visual_review_binds_current_review_target_and_bundle(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            self.enable_visual_policy(target)
            snapshot = self.snapshot_and_bundle(target)
            artifact = self.write_agent_visual_review(target, snapshot)
            self.add_visual_review_to_bundle(target, snapshot, artifact)
            status = agent_flow.agent_flow_visual_review_status(target, "001_toy", agent_flow.load_project_profile(target))
            self.assertEqual(status["status"], "PASS")
            bundle, errors = agent_flow.validate_review_bundle(target, "001_toy")
            self.assertEqual(errors, [])
            self.assertTrue(any(item["kind"] == "visual_review" for item in bundle["required_evidence"]))

    def test_stale_visual_review_target_is_rejected(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            self.enable_visual_policy(target)
            snapshot = self.snapshot_and_bundle(target)
            artifact = self.write_agent_visual_review(target, snapshot, review_target_id="old-target")
            self.add_visual_review_to_bundle(target, snapshot, artifact)
            with self.assertRaisesRegex(ValueError, "identity binding mismatch"):
                agent_flow.validate_review_bundle(target, "001_toy")
            status = agent_flow.agent_flow_visual_review_status(target, "001_toy", agent_flow.load_project_profile(target))
            self.assertEqual(status["status"], "INVALID")

    def test_visual_evidence_only_change_does_not_require_heavy_verifier(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            profile = agent_flow.load_project_profile(target)
            change_class = agent_flow.classify_paths(["results/001_toy/visual_review/VISUAL_REVIEW.json"], profile)
            self.assertEqual(change_class, "RECEIPT_OR_MANIFEST_ONLY_CHANGED")
            plan = agent_flow.invalidation_plan(change_class, review_target_id="target-1")
            self.assertFalse(plan["new_semantic_target_required"])
            self.assertFalse(plan["heavy_verifier_required"])
            self.assertTrue(plan["lightweight_validation_only"])

    def test_optional_visual_source_policy_disabled_preserves_existing_flow(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            profile = agent_flow.load_project_profile(target)
            self.assertFalse(profile["optional_visual_source_policy"]["enabled"])
            snapshot = self.snapshot_and_bundle(target)
            status = agent_flow.agent_flow_visual_review_status(target, "001_toy", profile)
            self.assertEqual(status["status"], "NOT_REQUIRED")
            bundle, errors = agent_flow.validate_review_bundle(target, "001_toy")
            self.assertEqual(errors, [])
            self.assertFalse(any(item.get("kind") == "visual_review" for item in bundle["required_evidence"]))
            self.assertIn("review_target_id", snapshot)

    def test_detached_worktree_plan_does_not_create_branch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            target.mkdir()
            plan = agent_flow.worktree_plan(target, "Verifier")
            self.assertFalse(plan["branch_created"])
            self.assertIn("--detach", plan["command"])

    def test_terminal_notifier_brief_only_for_terminal_user_states(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            root = agent_flow.task_root(target, "001_toy")
            self.assertIsNone(agent_flow.terminal_notification_brief(target, "001_toy"))
            snapshot = self.snapshot_and_bundle(target)
            self.write_planner_and_final_pass(target, snapshot)
            current = agent_flow.load_json(root / "CURRENT.json")
            current["state"] = "AWAIT_HUMAN_DECISION"
            current["terminal_policy"] = "human_gate"
            agent_flow.write_json(root / "CURRENT.json", current)
            brief = agent_flow.write_terminal_brief(target, "001_toy")
            self.assertIsNotNone(brief)
            self.assertEqual(brief["schema"], "ai-bridge.notification_brief.v1")
            self.assertTrue((agent_flow.result_root(target, "001_toy") / "notification_brief.json").exists())

    def test_adversarial_transition_edges_are_rejected(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            for illegal in ["AWAIT_HUMAN_DECISION", "PLANNER_PASS_CANDIDATE"]:
                with self.assertRaisesRegex(ValueError, "illegal transition edge"):
                    agent_flow.apply_transition(target, "001_toy", expected_state="PLAN_REQUESTED", next_state=illegal)
            root = agent_flow.task_root(target, "001_toy")
            write(root / "PLANNER_DRAFT.md", "# Draft\n")
            self.apply_next(target, "PLAN_REQUESTED", "PLAN_READY_FOR_CRITIC")
            self.write_critic_freeze(target)
            self.apply_next(target, "PLAN_READY_FOR_CRITIC", "PLAN_FROZEN")
            self.write_controller_receipt(target)
            self.apply_next(target, "PLAN_FROZEN", "CONTROLLER_INITIALIZING")
            self.snapshot_and_bundle(target)
            self.apply_next(target, "CONTROLLER_INITIALIZING", "VERIFIER_RUNNING")
            with self.assertRaisesRegex(ValueError, "illegal transition edge"):
                agent_flow.apply_transition(target, "001_toy", expected_state="VERIFIER_RUNNING", next_state="PLANNER_PASS")
            self.write_verifier_freeze(target)
            self.apply_next(target, "VERIFIER_RUNNING", "VERIFIER_FROZEN")
            self.write_role_receipt(target, "Executor")
            self.apply_next(target, "VERIFIER_FROZEN", "EXECUTOR_RUNNING")
            with self.assertRaisesRegex(ValueError, "illegal transition edge"):
                agent_flow.apply_transition(target, "001_toy", expected_state="EXECUTOR_RUNNING", next_state="READY_FOR_CRITIC_FINAL_AUDIT")

    def test_final_critic_waits_for_real_artifact(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            root = agent_flow.task_root(target, "001_toy")
            write(root / "PLANNER_DRAFT.md", "# Draft\n")
            self.apply_next(target, "PLAN_REQUESTED", "PLAN_READY_FOR_CRITIC")
            self.write_critic_freeze(target)
            self.apply_next(target, "PLAN_READY_FOR_CRITIC", "PLAN_FROZEN")
            self.write_controller_receipt(target)
            self.apply_next(target, "PLAN_FROZEN", "CONTROLLER_INITIALIZING")
            snapshot = self.snapshot_and_bundle(target)
            self.apply_next(target, "CONTROLLER_INITIALIZING", "VERIFIER_RUNNING")
            self.write_verifier_freeze(target)
            self.apply_next(target, "VERIFIER_RUNNING", "VERIFIER_FROZEN")
            self.write_role_receipt(target, "Executor")
            self.apply_next(target, "VERIFIER_FROZEN", "EXECUTOR_RUNNING")
            self.write_executor_result(target)
            self.apply_next(target, "EXECUTOR_RUNNING", "EVIDENCE_RUNNING")
            self.apply_next(target, "EVIDENCE_RUNNING", "READY_FOR_PLANNER_REVIEW")
            self.apply_next(target, "READY_FOR_PLANNER_REVIEW", "WAITING_FOR_EXTERNAL_GPT")
            planner_review_path = agent_flow.result_root(target, "001_toy") / "planner_reviews" / "pass.md"
            write(planner_review_path, "Planner pass candidate only.\n")
            request = agent_flow.load_json(root / "REQUEST.json")
            agent_flow.write_json(
                root / "PLANNER_PASS_CANDIDATE.json",
                {
                    "schema": "AI_BRIDGE_PLANNER_PASS_CANDIDATE_V1",
                    "role": "Planner",
                    "task_key": "001_toy",
                    "request_nonce": request["request_nonce"],
                    "review_target_id": snapshot["review_target_id"],
                    "artifact_path": "results/001_toy/planner_reviews/pass.md",
                    "artifact_sha256": agent_flow.file_sha256(planner_review_path),
                    "decision": "PLANNER_PASS_CANDIDATE",
                    "touched_paths": [],
                },
            )
            self.apply_next(target, "WAITING_FOR_EXTERNAL_GPT", "PLANNER_PASS_CANDIDATE")
            self.apply_next(target, "PLANNER_PASS_CANDIDATE", "READY_FOR_CRITIC_FINAL_AUDIT")
            plan = agent_flow.plan_transition(target, "001_toy")
            self.assertNotIn("next_state", plan)
            self.assertEqual(plan["next_action"], "RUN_OR_WAIT_FINAL_CRITIC")
            self.assertEqual(plan["operational_status"], "waiting_external_review")
            self.assertEqual(plan["external_owner"], "Final Critic")

    def test_planner_wait_is_not_blocked_before_or_after_two_hours(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            root = agent_flow.task_root(target, "001_toy")
            snapshot = self.snapshot_and_bundle(target)
            current = agent_flow.load_json(root / "CURRENT.json")
            started = datetime(2026, 8, 18, 10, 0, tzinfo=timezone.utc)
            current["state"] = "WAITING_FOR_EXTERNAL_GPT"
            current["current_review_target_id"] = snapshot["review_target_id"]
            current["next_action"] = "RUN_PLANNER_REVIEW"
            current["external_wait_started_at"] = started.isoformat()
            agent_flow.write_json(root / "CURRENT.json", current)

            early = agent_flow.agent_flow_external_wait_status(target, "001_toy", now=started + timedelta(minutes=30))
            late = agent_flow.agent_flow_external_wait_status(target, "001_toy", now=started + timedelta(minutes=121))
            plan = agent_flow.plan_transition(target, "001_toy")

            self.assertEqual(early["operational_status"], "waiting_external_review")
            self.assertTrue(early["within_minimum_grace"])
            self.assertFalse(early["may_block"])
            self.assertEqual(late["operational_status"], "waiting_external_review")
            self.assertFalse(late["within_minimum_grace"])
            self.assertFalse(late["may_block"])
            self.assertEqual(plan["next_action"], "WAIT_FOR_PLANNER_REVIEW_ARTIFACT")
            self.assertNotIn("next_state", plan)

    def test_stale_agent_flow_planner_findings_do_not_route_repair(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            root = agent_flow.task_root(target, "001_toy")
            snapshot = self.snapshot_and_bundle(target)
            current = agent_flow.load_json(root / "CURRENT.json")
            current["state"] = "WAITING_FOR_EXTERNAL_GPT"
            current["current_review_target_id"] = snapshot["review_target_id"]
            current["next_action"] = "RUN_PLANNER_REVIEW"
            agent_flow.write_json(root / "CURRENT.json", current)
            agent_flow.write_current_findings(
                target,
                "001_toy",
                [
                    {
                        "finding_id": "F_OLD",
                        "classification": "IMPLEMENTATION_BUG",
                        "blocking": True,
                        "owner_role": "Executor",
                        "requirement_ids": ["REQ_EXAMPLE_001"],
                        "summary": "old finding",
                        "observed_evidence": "old review",
                        "required_repair": "old repair",
                        "required_regression_evidence": "old evidence",
                        "forbidden_workaround": "old workaround",
                        "created_against_review_target_id": "old-target",
                    }
                ],
                "old-target",
            )

            status = agent_flow.agent_flow_external_wait_status(target, "001_toy")
            plan = agent_flow.plan_transition(target, "001_toy")

            self.assertEqual(status["operational_status"], "waiting_external_review")
            self.assertTrue(status["stale_decision"])
            self.assertEqual(plan["next_action"], "WAIT_FOR_PLANNER_REVIEW_ARTIFACT")
            self.assertNotIn("next_state", plan)

    def test_agent_flow_critic_wait_is_external_wait(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            root = agent_flow.task_root(target, "001_toy")
            snapshot = self.snapshot_and_bundle(target)
            request = agent_flow.load_json(root / "REQUEST.json")
            planner_review_path = agent_flow.result_root(target, "001_toy") / "planner_reviews" / "pass.md"
            write(planner_review_path, "Planner pass candidate for current target.\n")
            agent_flow.write_json(
                root / "PLANNER_PASS_CANDIDATE.json",
                {
                    "schema": "AI_BRIDGE_PLANNER_PASS_CANDIDATE_V1",
                    "role": "Planner",
                    "task_key": "001_toy",
                    "request_nonce": request["request_nonce"],
                    "review_target_id": snapshot["review_target_id"],
                    "artifact_path": "results/001_toy/planner_reviews/pass.md",
                    "artifact_sha256": agent_flow.file_sha256(planner_review_path),
                    "decision": "PLANNER_PASS_CANDIDATE",
                    "touched_paths": [],
                },
            )
            current = agent_flow.load_json(root / "CURRENT.json")
            current["state"] = "READY_FOR_CRITIC_FINAL_AUDIT"
            current["current_review_target_id"] = snapshot["review_target_id"]
            current["next_action"] = "RUN_OR_WAIT_FINAL_CRITIC"
            agent_flow.write_json(root / "CURRENT.json", current)

            plan = agent_flow.plan_transition(target, "001_toy")

            self.assertEqual(plan["operational_status"], "waiting_external_review")
            self.assertEqual(plan["external_owner"], "Final Critic")
            self.assertFalse(plan["may_block"])
            self.assertNotIn("next_state", plan)

    def test_old_nonce_and_old_target_artifacts_rejected(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            root = agent_flow.task_root(target, "001_toy")
            write(root / "PLANNER_DRAFT.md", "# Draft\n")
            self.apply_next(target, "PLAN_REQUESTED", "PLAN_READY_FOR_CRITIC")
            self.write_critic_freeze(target)
            freeze = agent_flow.load_json(root / "CRITIC_FREEZE.json")
            freeze["request_nonce"] = "old"
            agent_flow.write_json(root / "CRITIC_FREEZE.json", freeze)
            with self.assertRaisesRegex(ValueError, "request_nonce mismatch"):
                agent_flow.apply_transition(target, "001_toy", expected_state="PLAN_READY_FOR_CRITIC", next_state="PLAN_FROZEN")
            freeze["request_nonce"] = agent_flow.load_json(root / "REQUEST.json")["request_nonce"]
            agent_flow.write_json(root / "CRITIC_FREEZE.json", freeze)
            self.apply_next(target, "PLAN_READY_FOR_CRITIC", "PLAN_FROZEN")
            self.write_controller_receipt(target)
            self.apply_next(target, "PLAN_FROZEN", "CONTROLLER_INITIALIZING")
            snapshot = self.snapshot_and_bundle(target)
            self.write_planner_and_final_pass(target, snapshot)
            candidate = agent_flow.load_json(root / "PLANNER_PASS_CANDIDATE.json")
            candidate["review_target_id"] = "old-target"
            agent_flow.write_json(root / "PLANNER_PASS_CANDIDATE.json", candidate)
            self.assertTrue(any("current_review_target_id" in error or "current review_target_id" in error or "not bound" in error for error in agent_flow.validate_planner_pass_candidate(target, "001_toy")))
            self.write_planner_and_final_pass(target, snapshot)
            final = agent_flow.load_json(root / "FINAL_CRITIC_AUDIT.json")
            final["review_target_id"] = "old-target"
            agent_flow.write_json(root / "FINAL_CRITIC_AUDIT.json", final)
            self.assertTrue(any("review_target_id mismatch" in error for error in agent_flow.validate_final_critic_artifact(target, "001_toy")))

    def test_required_evidence_file_and_sha_are_enforced(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            self.snapshot_and_bundle(target)
            bundle_path = agent_flow.result_root(target, "001_toy") / "REVIEW_BUNDLE.json"
            evidence_path = agent_flow.result_root(target, "001_toy") / "verification" / "unit.json"
            evidence_path.unlink()
            with self.assertRaisesRegex(ValueError, "required evidence file missing"):
                agent_flow.validate_review_bundle(target, "001_toy")
            self.snapshot_and_bundle(target)
            bundle = agent_flow.load_json(bundle_path)
            bundle["required_evidence"][0]["sha256"] = "bad"
            bundle["bundle_sha256"] = agent_flow.bundle_digest(bundle)
            agent_flow.write_json(bundle_path, bundle)
            with self.assertRaisesRegex(ValueError, "required evidence sha256 mismatch"):
                agent_flow.validate_review_bundle(target, "001_toy")

    def test_current_finding_must_validate_before_route(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            snapshot = self.snapshot_and_bundle(target)
            agent_flow.write_current_findings(
                target,
                "001_toy",
                [
                    {
                        "finding_id": "F_BAD",
                        "classification": "IMPLEMENTATION_BUG",
                        "blocking": True,
                        "owner_role": "Executor",
                        "requirement_ids": ["REQ_EXAMPLE_001"],
                        "summary": "bad",
                        "observed_evidence": "unit",
                        "required_repair": "fix",
                        "required_regression_evidence": "test",
                        "forbidden_workaround": "fake",
                        "created_against_review_target_id": "old",
                    }
                ],
                snapshot["review_target_id"],
            )
            with self.assertRaisesRegex(ValueError, "not bound to current review_target_id"):
                agent_flow.route_current_findings(target, "001_toy")

    def test_role_git_commit_diff_must_match_touched_paths(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            subprocess.check_call(["git", "init", "--initial-branch", "main"], cwd=target, stdout=subprocess.DEVNULL)
            subprocess.check_call(["git", "config", "user.email", "test@example.org"], cwd=target)
            subprocess.check_call(["git", "config", "user.name", "Test User"], cwd=target)
            subprocess.check_call(["git", "add", "."], cwd=target, stdout=subprocess.DEVNULL)
            subprocess.check_call(["git", "commit", "-m", "initial"], cwd=target, stdout=subprocess.DEVNULL)
            write(target / "src" / "calc.py", "def add(a, b):\n    return a + b + 0\n")
            subprocess.check_call(["git", "add", "src/calc.py"], cwd=target, stdout=subprocess.DEVNULL)
            subprocess.check_call(["git", "commit", "-m", "executor change"], cwd=target, stdout=subprocess.DEVNULL)
            commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=target, text=True).strip()
            self.snapshot_and_bundle(target)
            receipt = {
                "role": "Executor",
                "session_id": "exec",
                "runtime_adapter": "fake",
                "worktree_id": "exec-wt",
                "base_task_nonce": agent_flow.load_json(agent_flow.task_root(target, "001_toy") / "REQUEST.json")["request_nonce"],
                "base_review_target_id": agent_flow.load_json(agent_flow.task_root(target, "001_toy") / "SOURCE_SNAPSHOT.json")["review_target_id"],
                "allowed_write_scope": ["src/**"],
                "start_or_resume_status": "started",
                "produced_commit": commit,
                "produced_evidence_id": "exec-evidence",
                "commit_kind": "git",
                "touched_paths": ["README.md"],
            }
            errors = agent_flow.validate_role_commit_diff(target, "Executor", receipt)
            self.assertTrue(any("do not match produced_commit diff" in error for error in errors))

    def test_tracked_semantic_changes_after_snapshot_are_rejected(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            subprocess.check_call(["git", "init", "--initial-branch", "main"], cwd=target, stdout=subprocess.DEVNULL)
            subprocess.check_call(["git", "config", "user.email", "test@example.org"], cwd=target)
            subprocess.check_call(["git", "config", "user.name", "Test User"], cwd=target)
            subprocess.check_call(["git", "add", "."], cwd=target, stdout=subprocess.DEVNULL)
            subprocess.check_call(["git", "commit", "-m", "initial"], cwd=target, stdout=subprocess.DEVNULL)
            snapshot = self.snapshot_and_bundle(target)
            root = agent_flow.task_root(target, "001_toy")
            current = agent_flow.load_json(root / "CURRENT.json")
            current["state"] = "READY_FOR_PLANNER_REVIEW"
            current["current_review_target_id"] = snapshot["review_target_id"]
            agent_flow.write_json(root / "CURRENT.json", current)
            write(target / "src" / "calc.py", "def add(a, b):\n    return a + b + 1\n")
            self.assertTrue(any("implementation semantic digest is stale" in error or "IMPLEMENTATION_SOURCE_MANIFEST" in error for error in agent_flow.validate_task_state(target, "001_toy")))

            self.snapshot_and_bundle(target)
            current = agent_flow.load_json(root / "CURRENT.json")
            current["state"] = "VERIFIER_FROZEN"
            agent_flow.write_json(root / "CURRENT.json", current)
            self.write_verifier_freeze(target)
            write(target / "tests" / "test_calc.py", "from src.calc import add\n\ndef test_add():\n    assert add(1, 2) == 4\n")
            self.assertTrue(any("verifier semantic digest is stale" in error or "VERIFIER_SOURCE_MANIFEST" in error for error in agent_flow.validate_task_state(target, "001_toy")))

    def test_contract_and_ledger_changes_after_snapshot_are_rejected(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            snapshot = self.snapshot_and_bundle(target)
            root = agent_flow.task_root(target, "001_toy")
            current = agent_flow.load_json(root / "CURRENT.json")
            current["state"] = "READY_FOR_PLANNER_REVIEW"
            current["current_review_target_id"] = snapshot["review_target_id"]
            agent_flow.write_json(root / "CURRENT.json", current)
            write(root / "FROZEN_CONTRACT.md", "# Frozen Contract\n\nREQ_EXAMPLE_001: add returns numeric sum.\n")
            self.assertTrue(any("frozen_contract_sha256 is stale" in error for error in agent_flow.validate_task_state(target, "001_toy")))

            snapshot = self.snapshot_and_bundle(target)
            current = agent_flow.load_json(root / "CURRENT.json")
            current["state"] = "VERIFIER_FROZEN"
            current["current_review_target_id"] = snapshot["review_target_id"]
            agent_flow.write_json(root / "CURRENT.json", current)
            self.write_verifier_freeze(target)
            ledger = agent_flow.load_json(root / "REQUIREMENT_LEDGER.json")
            ledger["requirements"][0]["verifier_authority"] = "updated authority text"
            agent_flow.write_json(root / "REQUIREMENT_LEDGER.json", ledger)
            errors = agent_flow.validate_task_state(target, "001_toy")
            self.assertTrue(any("requirement_ledger_sha256 is stale" in error for error in errors))

    def test_evidence_artifact_status_is_authoritative(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            snapshot = self.snapshot_and_bundle(target)
            evidence_path = agent_flow.result_root(target, "001_toy") / "verification" / "unit.json"
            agent_flow.write_json(
                evidence_path,
                {
                    "schema": "AI_BRIDGE_EVIDENCE_V1",
                    "evidence_id": "unit-add",
                    "status": "FAIL",
                    "review_target_id": snapshot["review_target_id"],
                },
            )
            bundle_path = agent_flow.result_root(target, "001_toy") / "REVIEW_BUNDLE.json"
            bundle = agent_flow.load_json(bundle_path)
            bundle["required_evidence"][0]["status"] = "PASS"
            bundle["required_evidence"][0]["sha256"] = agent_flow.file_sha256(evidence_path)
            bundle["bundle_sha256"] = agent_flow.bundle_digest(bundle)
            agent_flow.write_json(bundle_path, bundle)
            with self.assertRaisesRegex(ValueError, "artifact status mismatch"):
                agent_flow.validate_review_bundle(target, "001_toy")

    def test_ci_required_uses_ci_evidence_artifact(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            profile_path = agent_flow.agent_root(target) / "PROJECT_PROFILE.json"
            profile = agent_flow.load_json(profile_path)
            profile["requires_ci"] = True
            profile["ci"]["required"] = True
            agent_flow.write_json(profile_path, profile)
            snapshot = self.snapshot_and_bundle(target)
            root = agent_flow.task_root(target, "001_toy")
            current = agent_flow.load_json(root / "CURRENT.json")
            current["state"] = "READY_FOR_PLANNER_REVIEW"
            current["current_review_target_id"] = snapshot["review_target_id"]
            agent_flow.write_json(root / "CURRENT.json", current)
            self.assertTrue(any("CI evidence artifact" in error for error in agent_flow.validate_task_state(target, "001_toy")))

            ci_path = agent_flow.result_root(target, "001_toy") / "verification" / "ci.json"
            agent_flow.write_json(
                ci_path,
                {"schema": "AI_BRIDGE_CI_EVIDENCE_V1", "evidence_id": "ci-main", "status": "FAIL", "review_target_id": snapshot["review_target_id"]},
            )
            bundle_path = agent_flow.result_root(target, "001_toy") / "REVIEW_BUNDLE.json"
            bundle = agent_flow.load_json(bundle_path)
            bundle["required_evidence"].append(
                {
                    "evidence_id": "ci-main",
                    "kind": "ci",
                    "path": "results/001_toy/verification/ci.json",
                    "sha256": agent_flow.file_sha256(ci_path),
                    "status": "PASS",
                    "required": True,
                    "target_sensitive": True,
                    "review_target_id": snapshot["review_target_id"],
                }
            )
            bundle["bundle_sha256"] = agent_flow.bundle_digest(bundle)
            agent_flow.write_json(bundle_path, bundle)
            self.assertTrue(any("artifact status mismatch" in error for error in agent_flow.validate_task_state(target, "001_toy")))

    def test_legacy_findings_materialize_to_authoritative_artifact(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            snapshot = self.snapshot_and_bundle(target)
            path = agent_flow.current_findings_path(target, "001_toy")
            path.unlink()
            current_path = agent_flow.task_root(target, "001_toy") / "CURRENT.json"
            current = agent_flow.load_json(current_path)
            current["open_findings"] = [
                {
                    "finding_id": "F_IMPL",
                    "classification": "IMPLEMENTATION_BUG",
                    "blocking": True,
                    "owner_role": "Executor",
                    "requirement_ids": ["REQ_EXAMPLE_001"],
                    "summary": "bad",
                    "observed_evidence": "unit",
                    "required_repair": "fix",
                    "required_regression_evidence": "test",
                    "forbidden_workaround": "fake",
                    "created_against_review_target_id": snapshot["review_target_id"],
                }
            ]
            current["findings_ref"] = None
            current["findings_sha256"] = None
            agent_flow.write_json(current_path, current)
            routed = agent_flow.route_current_findings(target, "001_toy")
            self.assertEqual(routed["target_role"], "Executor")
            self.assertTrue(path.exists())
            self.assertNotIn("open_findings", agent_flow.load_json(current_path))

    def test_role_provenance_and_machine_review_authority_are_enforced(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            snapshot = self.snapshot_and_bundle(target)
            request = agent_flow.load_json(agent_flow.task_root(target, "001_toy") / "REQUEST.json")
            receipt = {
                "role": "Executor",
                "session_id": "exec",
                "runtime_adapter": "fake",
                "worktree_id": "exec-wt",
                "base_task_nonce": request["request_nonce"],
                "allowed_write_scope": ["src/**"],
                "start_or_resume_status": "started",
                "produced_commit": "abc",
                "produced_evidence_id": "evidence",
                "commit_kind": "fake-test",
            }
            self.assertTrue(any("fake-test" in error for error in agent_flow.validate_role_receipt(receipt, request_nonce=request["request_nonce"], review_target_id=snapshot["review_target_id"], allow_fake_test=False)))
            receipt["commit_kind"] = "git"
            self.assertTrue(any("base_review_target_id missing" in error for error in agent_flow.validate_role_receipt(receipt, request_nonce=request["request_nonce"], review_target_id=snapshot["review_target_id"])))

            planner_review = agent_flow.result_root(target, "001_toy") / "planner_reviews" / "bad.md"
            write(planner_review, "bad\n")
            artifact = {
                "role": "Planner",
                "task_key": "001_toy",
                "request_nonce": request["request_nonce"],
                "review_target_id": snapshot["review_target_id"],
                "artifact_path": "results/001_toy/planner_reviews/bad.md",
                "artifact_sha256": agent_flow.file_sha256(planner_review),
                "decision": "PLANNER_PASS_CANDIDATE",
                "touched_paths": ["src/calc.py"],
            }
            self.assertTrue(any("outside allowed_write_scope" in error for error in agent_flow.validate_machine_review_artifact(target, "001_toy", artifact, role="Planner", decision="PLANNER_PASS_CANDIDATE", review_target_required=True)))

            critic_review = agent_flow.result_root(target, "001_toy") / "critic_reviews" / "bad.md"
            write(critic_review, "bad\n")
            critic_artifact = {
                "role": "Critic",
                "task_key": "001_toy",
                "request_nonce": request["request_nonce"],
                "artifact_path": "results/001_toy/critic_reviews/bad.md",
                "artifact_sha256": agent_flow.file_sha256(critic_review),
                "decision": "PLAN_FROZEN",
                "touched_paths": ["src/calc.py"],
            }
            self.assertTrue(any("outside allowed_write_scope" in error for error in agent_flow.validate_machine_review_artifact(target, "001_toy", critic_artifact, role="Critic", decision="PLAN_FROZEN", review_target_required=False)))

    def test_integration_requires_valid_git_receipt_and_exact_diff(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            subprocess.check_call(["git", "init", "--initial-branch", "main"], cwd=target, stdout=subprocess.DEVNULL)
            subprocess.check_call(["git", "config", "user.email", "test@example.org"], cwd=target)
            subprocess.check_call(["git", "config", "user.name", "Test User"], cwd=target)
            subprocess.check_call(["git", "add", "."], cwd=target, stdout=subprocess.DEVNULL)
            subprocess.check_call(["git", "commit", "-m", "initial"], cwd=target, stdout=subprocess.DEVNULL)
            snapshot = self.snapshot_and_bundle(target)
            current_path = agent_flow.task_root(target, "001_toy") / "CURRENT.json"
            current = agent_flow.load_json(current_path)
            current["integration_branch"] = "main"
            agent_flow.write_json(current_path, current)
            request = agent_flow.load_json(agent_flow.task_root(target, "001_toy") / "REQUEST.json")
            bad = {
                "role": "Executor",
                "session_id": "exec",
                "runtime_adapter": "fake",
                "worktree_id": "exec-wt",
                "base_task_nonce": request["request_nonce"],
                "base_review_target_id": snapshot["review_target_id"],
                "allowed_write_scope": ["src/**"],
                "start_or_resume_status": "started",
                "produced_commit": "notasha",
                "produced_evidence_id": "evidence",
                "commit_kind": "external",
                "touched_paths": [],
            }
            with self.assertRaisesRegex(ValueError, "commit_kind=git"):
                agent_flow.integration_plan(target, "001_toy", "Executor", bad)

            write(target / "src" / "calc.py", "def add(a, b):\n    return a + b + 0\n")
            subprocess.check_call(["git", "add", "src/calc.py"], cwd=target, stdout=subprocess.DEVNULL)
            subprocess.check_call(["git", "commit", "-m", "executor change"], cwd=target, stdout=subprocess.DEVNULL)
            commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=target, text=True).strip()
            good = {**bad, "commit_kind": "git", "produced_commit": commit, "touched_paths": ["src/calc.py"]}
            plan = agent_flow.integration_plan(target, "001_toy", "Executor", good)
            self.assertEqual(plan["role_commit"], commit)

    def test_controller_restart_recovers_executor_commit_before_integration_publication(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            subprocess.check_call(["git", "init", "--initial-branch", "main"], cwd=target, stdout=subprocess.DEVNULL)
            subprocess.check_call(["git", "config", "user.email", "test@example.org"], cwd=target)
            subprocess.check_call(["git", "config", "user.name", "Test User"], cwd=target)
            subprocess.check_call(["git", "add", "."], cwd=target, stdout=subprocess.DEVNULL)
            subprocess.check_call(["git", "commit", "-m", "initial"], cwd=target, stdout=subprocess.DEVNULL)
            snapshot = self.snapshot_and_bundle(target)
            current_path = agent_flow.task_root(target, "001_toy") / "CURRENT.json"
            current = agent_flow.load_json(current_path)
            current["integration_branch"] = "main"
            agent_flow.write_json(current_path, current)
            write(target / "src" / "calc.py", "def add(a, b):\n    return a + b + 0\n")
            subprocess.check_call(["git", "add", "src/calc.py"], cwd=target, stdout=subprocess.DEVNULL)
            subprocess.check_call(["git", "commit", "-m", "executor change"], cwd=target, stdout=subprocess.DEVNULL)
            commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=target, text=True).strip()
            request = agent_flow.load_json(agent_flow.task_root(target, "001_toy") / "REQUEST.json")
            receipt = {
                "role": "Executor",
                "session_id": "exec-session",
                "runtime_adapter": "codex",
                "worktree_id": "exec-wt",
                "base_task_nonce": request["request_nonce"],
                "base_review_target_id": snapshot["review_target_id"],
                "allowed_write_scope": agent_flow.load_project_profile(target)["role_write_scopes"]["Executor"],
                "start_or_resume_status": "started",
                "produced_commit": commit,
                "produced_evidence_id": "executor-evidence",
                "commit_kind": "git",
                "touched_paths": ["src/calc.py"],
            }
            receipt_path = agent_flow.role_receipt_path(target, "001_toy", "Executor")
            agent_flow.write_json(receipt_path, receipt)

            recovered_receipt = agent_flow.load_json(receipt_path)
            first = agent_flow.integration_plan(target, "001_toy", "Executor", recovered_receipt)
            second = agent_flow.integration_plan(target, "001_toy", "Executor", agent_flow.load_json(receipt_path))

            self.assertEqual(first["role_commit"], commit)
            self.assertEqual(second, first)
            self.assertFalse(first["branch_created"])

    def test_missing_executor_receipt_and_stale_verifier_freeze_nonce_rejected(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            snapshot = self.snapshot_and_bundle(target)
            current = agent_flow.load_json(agent_flow.task_root(target, "001_toy") / "CURRENT.json")
            current["state"] = "EVIDENCE_RUNNING"
            current["current_review_target_id"] = snapshot["review_target_id"]
            agent_flow.write_json(agent_flow.task_root(target, "001_toy") / "CURRENT.json", current)
            self.write_executor_result(target)
            self.assertTrue(any("Executor role receipt" in error for error in agent_flow.validate_task_state(target, "001_toy")))

            self.write_verifier_freeze(target)
            freeze_path = agent_flow.task_root(target, "001_toy") / "VERIFIER_FREEZE.json"
            freeze = agent_flow.load_json(freeze_path)
            freeze["request_nonce"] = "old"
            agent_flow.write_json(freeze_path, freeze)
            current["state"] = "VERIFIER_FROZEN"
            agent_flow.write_json(agent_flow.task_root(target, "001_toy") / "CURRENT.json", current)
            self.write_role_receipt(target, "Verifier")
            self.assertTrue(any("request_nonce mismatch" in error for error in agent_flow.validate_task_state(target, "001_toy")))

    def test_ordinary_planner_revise_both_keeps_critic_standby(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            root = agent_flow.task_root(target, "001_toy")
            write(root / "PLANNER_DRAFT.md", "# Draft\n")
            self.apply_next(target, "PLAN_REQUESTED", "PLAN_READY_FOR_CRITIC")
            self.write_critic_freeze(target)
            self.apply_next(target, "PLAN_READY_FOR_CRITIC", "PLAN_FROZEN")
            self.write_controller_receipt(target)
            self.apply_next(target, "PLAN_FROZEN", "CONTROLLER_INITIALIZING")
            self.snapshot_and_bundle(target)
            self.apply_next(target, "CONTROLLER_INITIALIZING", "VERIFIER_RUNNING")
            self.write_verifier_freeze(target)
            self.apply_next(target, "VERIFIER_RUNNING", "VERIFIER_FROZEN")
            self.write_role_receipt(target, "Executor")
            self.apply_next(target, "VERIFIER_FROZEN", "EXECUTOR_RUNNING")
            self.write_executor_result(target)
            self.apply_next(target, "EXECUTOR_RUNNING", "EVIDENCE_RUNNING")
            self.apply_next(target, "EVIDENCE_RUNNING", "READY_FOR_PLANNER_REVIEW")
            self.apply_next(target, "READY_FOR_PLANNER_REVIEW", "WAITING_FOR_EXTERNAL_GPT")
            agent_flow.apply_transition(
                target,
                "001_toy",
                expected_state="WAITING_FOR_EXTERNAL_GPT",
                next_state="PLANNER_REVISE_BOTH",
                next_action="ORDINARY_BOTH_REPAIR",
            )
            self.assertEqual(agent_flow.load_json(root / "CURRENT.json")["critic_mode"], "STANDBY")

    def test_contract_review_requires_refreeze_and_new_snapshot_target(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            root = agent_flow.task_root(target, "001_toy")
            write(root / "PLANNER_DRAFT.md", "# Draft\n")
            self.apply_next(target, "PLAN_REQUESTED", "PLAN_READY_FOR_CRITIC")
            self.write_critic_freeze(target)
            self.apply_next(target, "PLAN_READY_FOR_CRITIC", "PLAN_FROZEN")
            self.write_controller_receipt(target)
            self.apply_next(target, "PLAN_FROZEN", "CONTROLLER_INITIALIZING")
            first = self.snapshot_and_bundle(target)
            self.apply_next(target, "CONTROLLER_INITIALIZING", "VERIFIER_RUNNING")
            self.write_verifier_freeze(target)
            self.apply_next(target, "VERIFIER_RUNNING", "VERIFIER_FROZEN")
            self.write_role_receipt(target, "Executor")
            self.apply_next(target, "VERIFIER_FROZEN", "EXECUTOR_RUNNING")
            self.write_executor_result(target)
            self.apply_next(target, "EXECUTOR_RUNNING", "EVIDENCE_RUNNING")
            self.apply_next(target, "EVIDENCE_RUNNING", "READY_FOR_PLANNER_REVIEW")
            agent_flow.write_current_findings(
                target,
                "001_toy",
                [
                    {
                        "finding_id": "F_AMBIG",
                        "classification": "CONTRACT_AMBIGUITY",
                        "blocking": True,
                        "owner_role": "Planner",
                        "requirement_ids": ["REQ_EXAMPLE_001"],
                        "summary": "contract ambiguous",
                        "observed_evidence": "Planner review",
                        "required_repair": "clarify contract",
                        "required_regression_evidence": "new target",
                        "forbidden_workaround": "runtime choice",
                        "created_against_review_target_id": first["review_target_id"],
                    }
                ],
                first["review_target_id"],
            )
            self.apply_next(target, "READY_FOR_PLANNER_REVIEW", "WAITING_FOR_EXTERNAL_GPT")
            self.apply_next(target, "WAITING_FOR_EXTERNAL_GPT", "CONTRACT_REVIEW_REQUIRED")
            current = agent_flow.load_json(root / "CURRENT.json")
            self.assertEqual(current["contract_review_base_target_id"], first["review_target_id"])

            write(root / "FROZEN_CONTRACT.md", "# Frozen Contract\n\nREQ_EXAMPLE_001: add returns numeric sum.\n")
            self.write_critic_freeze(target, critic_mode="REQUIRED_CONTRACT_REVIEW")
            plan = agent_flow.plan_transition(target, "001_toy")
            self.assertEqual(plan["next_action"], "RUN_OR_WAIT_CONTRACT_CRITIC_REVIEW")
            self.assertTrue(any("frozen_contract_sha256 is stale" in error for error in plan["waiting_on"]))
            with self.assertRaisesRegex(ValueError, "frozen_contract_sha256 is stale"):
                agent_flow.apply_transition(target, "001_toy", expected_state="CONTRACT_REVIEW_REQUIRED", next_state="PLANNER_REVISE_BOTH")

            self.snapshot_and_bundle(target)
            second = agent_flow.load_json(root / "SOURCE_SNAPSHOT.json")
            self.assertNotEqual(first["review_target_id"], second["review_target_id"])
            resumed = self.apply_next(target, "CONTRACT_REVIEW_REQUIRED", "PLANNER_REVISE_BOTH")
            self.assertNotIn("contract_review_base_target_id", resumed)
            self.assertEqual(resumed["critic_mode"], "STANDBY")

    def test_contract_review_same_snapshot_target_is_rejected(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            root = agent_flow.task_root(target, "001_toy")
            write(root / "PLANNER_DRAFT.md", "# Draft\n")
            self.apply_next(target, "PLAN_REQUESTED", "PLAN_READY_FOR_CRITIC")
            self.write_critic_freeze(target)
            self.apply_next(target, "PLAN_READY_FOR_CRITIC", "PLAN_FROZEN")
            self.write_controller_receipt(target)
            self.apply_next(target, "PLAN_FROZEN", "CONTROLLER_INITIALIZING")
            first = self.snapshot_and_bundle(target)
            current_path = root / "CURRENT.json"
            current = agent_flow.load_json(current_path)
            current["state"] = "CONTRACT_REVIEW_REQUIRED"
            current["critic_mode"] = "REQUIRED_CONTRACT_REVIEW"
            current["current_review_target_id"] = first["review_target_id"]
            current["contract_review_base_target_id"] = first["review_target_id"]
            agent_flow.write_json(current_path, current)
            self.write_critic_freeze(target, critic_mode="REQUIRED_CONTRACT_REVIEW")
            plan = agent_flow.plan_transition(target, "001_toy")
            self.assertEqual(plan["next_action"], "RUN_OR_WAIT_CONTRACT_CRITIC_REVIEW")
            self.assertTrue(any("new semantic review_target_id" in error for error in plan["waiting_on"]))
            with self.assertRaisesRegex(ValueError, "new semantic review_target_id"):
                agent_flow.apply_transition(target, "001_toy", expected_state="CONTRACT_REVIEW_REQUIRED", next_state="PLANNER_REVISE_BOTH")

    def test_production_transitions_reject_fake_test_role_receipts(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            root = agent_flow.task_root(target, "001_toy")
            write(root / "PLANNER_DRAFT.md", "# Draft\n")
            self.apply_next(target, "PLAN_REQUESTED", "PLAN_READY_FOR_CRITIC")
            self.write_critic_freeze(target)
            self.apply_next(target, "PLAN_READY_FOR_CRITIC", "PLAN_FROZEN")
            self.write_controller_receipt(target)
            controller_path = agent_flow.role_receipt_path(target, "001_toy", "Controller")
            controller = agent_flow.load_json(controller_path)
            controller["commit_kind"] = "fake-test"
            controller["produced_commit"] = "fake"
            agent_flow.write_json(controller_path, controller)
            self.assertTrue(any("fake-test" in error for error in agent_flow.validate_transition_predicates(target, "001_toy", "CONTROLLER_INITIALIZING", agent_flow.load_json(root / "CURRENT.json"), agent_flow.load_project_profile(target))))
            current_path = root / "CURRENT.json"
            current = agent_flow.load_json(current_path)
            current["state"] = "CONTROLLER_INITIALIZING"
            agent_flow.write_json(current_path, current)
            self.assertTrue(any("fake-test" in error for error in agent_flow.validate_task_state(target, "001_toy")))
            self.assertFalse(agent_flow.plan_transition(target, "001_toy")["valid"])
            current["state"] = "PLAN_FROZEN"
            agent_flow.write_json(current_path, current)
            with self.assertRaisesRegex(ValueError, "fake-test"):
                agent_flow.apply_transition(target, "001_toy", expected_state="PLAN_FROZEN", next_state="CONTROLLER_INITIALIZING")

            controller["commit_kind"] = "no_commit"
            controller["produced_commit"] = ""
            agent_flow.write_json(controller_path, controller)
            self.apply_next(target, "PLAN_FROZEN", "CONTROLLER_INITIALIZING")
            self.snapshot_and_bundle(target)
            self.apply_next(target, "CONTROLLER_INITIALIZING", "VERIFIER_RUNNING")
            self.write_verifier_freeze(target)
            verifier_path = agent_flow.role_receipt_path(target, "001_toy", "Verifier")
            verifier = agent_flow.load_json(verifier_path)
            verifier["commit_kind"] = "fake-test"
            verifier["produced_commit"] = "fake"
            agent_flow.write_json(verifier_path, verifier)
            self.assertTrue(any("fake-test" in error for error in agent_flow.validate_transition_predicates(target, "001_toy", "VERIFIER_FROZEN", agent_flow.load_json(root / "CURRENT.json"), agent_flow.load_project_profile(target))))
            with self.assertRaisesRegex(ValueError, "fake-test"):
                agent_flow.apply_transition(target, "001_toy", expected_state="VERIFIER_RUNNING", next_state="VERIFIER_FROZEN")

            verifier["commit_kind"] = "no_commit"
            verifier["produced_commit"] = ""
            agent_flow.write_json(verifier_path, verifier)
            self.apply_next(target, "VERIFIER_RUNNING", "VERIFIER_FROZEN")
            self.write_role_receipt(target, "Executor")
            self.apply_next(target, "VERIFIER_FROZEN", "EXECUTOR_RUNNING")
            self.write_executor_result(target)
            executor_path = agent_flow.role_receipt_path(target, "001_toy", "Executor")
            executor = agent_flow.load_json(executor_path)
            executor["commit_kind"] = "fake-test"
            executor["produced_commit"] = "fake"
            agent_flow.write_json(executor_path, executor)
            self.assertTrue(any("fake-test" in error for error in agent_flow.validate_transition_predicates(target, "001_toy", "EVIDENCE_RUNNING", agent_flow.load_json(root / "CURRENT.json"), agent_flow.load_project_profile(target))))
            self.assertTrue(any("fake-test" in error for error in agent_flow.validate_agent_flow(target)[0]))
            with self.assertRaisesRegex(ValueError, "fake-test"):
                agent_flow.apply_transition(target, "001_toy", expected_state="EXECUTOR_RUNNING", next_state="EVIDENCE_RUNNING")

    def test_toy_a_control_plane_path(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            snapshot = self.snapshot_and_bundle(target)
            bug_route = agent_flow.route_findings(
                [
                    {
                        "finding_id": "F_IMPL",
                        "classification": "IMPLEMENTATION_BUG",
                        "blocking": True,
                        "requirement_ids": ["REQ_EXAMPLE_001"],
                    }
                ]
            )
            self.assertEqual(bug_route["target_role"], "Executor")
            drift_errors = agent_flow.validate_finding(
                {
                    "finding_id": "F_DRIFT",
                    "classification": "VERIFIER_CONTRACT_DRIFT",
                    "blocking": True,
                    "requirement_ids": ["REQ_EXAMPLE_001"],
                    "threshold": 0.01,
                    "threshold_provenance": "verifier_preference",
                },
                {"REQ_EXAMPLE_001"},
            )
            self.assertTrue(drift_errors)
            root = agent_flow.task_root(target, "001_toy")
            self.write_planner_and_final_pass(target, snapshot)
            current = agent_flow.load_json(root / "CURRENT.json")
            current["state"] = "AWAIT_HUMAN_DECISION"
            current["terminal_policy"] = "human_gate"
            agent_flow.write_json(root / "CURRENT.json", current)
            self.assertEqual(agent_flow.validate_task_state(target, "001_toy"), [])

    def test_toy_a_e2e_controller_transition_chain(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            root = agent_flow.task_root(target, "001_toy")
            write(root / "PLANNER_DRAFT.md", "# Draft\n")
            self.apply_next(target, "PLAN_REQUESTED", "PLAN_READY_FOR_CRITIC")
            self.write_critic_freeze(target)
            self.apply_next(target, "PLAN_READY_FOR_CRITIC", "PLAN_FROZEN")
            self.write_controller_receipt(target)
            self.apply_next(target, "PLAN_FROZEN", "CONTROLLER_INITIALIZING")
            snapshot = self.snapshot_and_bundle(target)
            self.assertTrue(any("verifier-owned freeze" in item for item in agent_flow.validate_transition_predicates(target, "001_toy", "VERIFIER_FROZEN", agent_flow.load_json(root / "CURRENT.json"), agent_flow.load_project_profile(target))))
            self.apply_next(target, "CONTROLLER_INITIALIZING", "VERIFIER_RUNNING")
            self.write_verifier_freeze(target)
            self.apply_next(target, "VERIFIER_RUNNING", "VERIFIER_FROZEN")
            self.write_role_receipt(target, "Executor")
            self.apply_next(target, "VERIFIER_FROZEN", "EXECUTOR_RUNNING")
            self.assertTrue(agent_flow.validate_executor_result({"test_aware_alternate_path": True, "touched_paths": ["src/calc.py"]}))
            self.write_executor_result(target)
            self.apply_next(target, "EXECUTOR_RUNNING", "EVIDENCE_RUNNING")
            self.apply_next(target, "EVIDENCE_RUNNING", "READY_FOR_PLANNER_REVIEW")
            self.assertEqual(agent_flow.validate_task_state(target, "001_toy"), [])
            agent_flow.write_current_findings(
                target,
                "001_toy",
                [
                    {
                        "finding_id": "F_IMPL",
                        "classification": "IMPLEMENTATION_BUG",
                        "blocking": True,
                        "owner_role": "Executor",
                        "requirement_ids": ["REQ_EXAMPLE_001"],
                        "summary": "add implementation is wrong",
                        "observed_evidence": "unit-add failed before repair",
                        "required_repair": "fix src/calc.py",
                        "required_regression_evidence": "unit-add PASS",
                        "forbidden_workaround": "do not weaken test",
                        "created_against_review_target_id": snapshot["review_target_id"],
                    }
                ],
                snapshot["review_target_id"],
            )
            self.apply_next(target, "READY_FOR_PLANNER_REVIEW", "WAITING_FOR_EXTERNAL_GPT")
            self.apply_next(target, "WAITING_FOR_EXTERNAL_GPT", "PLANNER_REVISE_EXECUTOR")
            self.apply_next(target, "PLANNER_REVISE_EXECUTOR", "EXECUTOR_RUNNING")
            self.write_executor_result(target)
            agent_flow.write_current_findings(target, "001_toy", [], snapshot["review_target_id"])
            self.apply_next(target, "EXECUTOR_RUNNING", "EVIDENCE_RUNNING")
            self.apply_next(target, "EVIDENCE_RUNNING", "READY_FOR_PLANNER_REVIEW")
            self.apply_next(target, "READY_FOR_PLANNER_REVIEW", "WAITING_FOR_EXTERNAL_GPT")
            self.write_planner_and_final_pass(target, snapshot)
            self.apply_next(target, "WAITING_FOR_EXTERNAL_GPT", "PLANNER_PASS_CANDIDATE")
            self.apply_next(target, "PLANNER_PASS_CANDIDATE", "READY_FOR_CRITIC_FINAL_AUDIT")
            self.apply_next(target, "READY_FOR_CRITIC_FINAL_AUDIT", "PLANNER_PASS")
            self.apply_next(target, "PLANNER_PASS", "AWAIT_HUMAN_DECISION")
            brief = agent_flow.write_terminal_brief(target, "001_toy")
            self.assertEqual(brief["terminal_status"], "awaiting_human")

    def test_toy_b_control_plane_change_and_contract_ambiguity(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            root = agent_flow.task_root(target, "001_toy")
            write(root / "PLANNER_DRAFT.md", "# Draft\n")
            self.apply_next(target, "PLAN_REQUESTED", "PLAN_READY_FOR_CRITIC")
            self.write_critic_freeze(target)
            self.apply_next(target, "PLAN_READY_FOR_CRITIC", "PLAN_FROZEN")
            self.write_controller_receipt(target)
            self.apply_next(target, "PLAN_FROZEN", "CONTROLLER_INITIALIZING")
            first = self.snapshot_and_bundle(target)
            profile = agent_flow.load_project_profile(target)
            change_class = agent_flow.classify_paths(["automation/agent_flow/schema.json"], profile)
            plan = agent_flow.invalidation_plan(change_class, review_target_id=first["review_target_id"])
            self.assertEqual(change_class, "CONTROL_PLANE_ONLY_CHANGED")
            self.assertFalse(plan["heavy_verifier_required"])
            unchanged = agent_flow.snapshot(target, "001_toy")
            self.assertEqual(first["review_target_id"], unchanged["review_target_id"])

            self.apply_next(target, "CONTROLLER_INITIALIZING", "VERIFIER_RUNNING")
            self.write_verifier_freeze(target)
            self.apply_next(target, "VERIFIER_RUNNING", "VERIFIER_FROZEN")
            self.write_role_receipt(target, "Executor")
            self.apply_next(target, "VERIFIER_FROZEN", "EXECUTOR_RUNNING")
            self.write_executor_result(target)
            self.apply_next(target, "EXECUTOR_RUNNING", "EVIDENCE_RUNNING")
            self.apply_next(target, "EVIDENCE_RUNNING", "READY_FOR_PLANNER_REVIEW")
            agent_flow.write_current_findings(
                target,
                "001_toy",
                [
                    {
                        "finding_id": "F_AMBIG",
                        "classification": "CONTRACT_AMBIGUITY",
                        "blocking": True,
                        "owner_role": "Planner",
                        "requirement_ids": ["REQ_EXAMPLE_001"],
                        "summary": "contract ambiguous about numeric coercion",
                        "observed_evidence": "Planner detected ambiguous requirement wording",
                        "required_repair": "clarify frozen contract",
                        "required_regression_evidence": "new target Review Bundle",
                        "forbidden_workaround": "runtime roles must not choose semantics",
                        "created_against_review_target_id": first["review_target_id"],
                    }
                ],
                first["review_target_id"],
            )
            self.apply_next(target, "READY_FOR_PLANNER_REVIEW", "WAITING_FOR_EXTERNAL_GPT")
            routed = agent_flow.route_current_findings(target, "001_toy")
            self.assertEqual(routed["route"], "PLANNER_INTERPRET_CONTRACT")
            self.apply_next(target, "WAITING_FOR_EXTERNAL_GPT", "CONTRACT_REVIEW_REQUIRED")
            self.assertEqual(agent_flow.load_json(root / "CURRENT.json")["critic_mode"], "REQUIRED_CONTRACT_REVIEW")
            plan = agent_flow.plan_transition(target, "001_toy")
            self.assertEqual(plan["next_action"], "RUN_OR_WAIT_CONTRACT_CRITIC_REVIEW")
            self.assertNotIn("next_state", plan)

            write(agent_flow.task_root(target, "001_toy") / "FROZEN_CONTRACT.md", "# Frozen Contract\n\nREQ_EXAMPLE_001: add returns numeric sum only.\n")
            self.write_critic_freeze(target, critic_mode="REQUIRED_CONTRACT_REVIEW")
            second = self.snapshot_and_bundle(target)
            self.assertNotEqual(first["review_target_id"], second["review_target_id"])
            self.apply_next(target, "CONTRACT_REVIEW_REQUIRED", "PLANNER_REVISE_BOTH")
            self.apply_next(target, "PLANNER_REVISE_BOTH", "VERIFIER_RUNNING")
            self.write_verifier_freeze(target)
            self.apply_next(target, "VERIFIER_RUNNING", "VERIFIER_FROZEN")
            self.write_role_receipt(target, "Executor")
            self.apply_next(target, "VERIFIER_FROZEN", "EXECUTOR_RUNNING")
            self.write_executor_result(target)
            agent_flow.write_current_findings(target, "001_toy", [], second["review_target_id"])
            self.apply_next(target, "EXECUTOR_RUNNING", "EVIDENCE_RUNNING")
            self.apply_next(target, "EVIDENCE_RUNNING", "READY_FOR_PLANNER_REVIEW")
            self.apply_next(target, "READY_FOR_PLANNER_REVIEW", "WAITING_FOR_EXTERNAL_GPT")
            self.write_planner_and_final_pass(target, second)
            self.apply_next(target, "WAITING_FOR_EXTERNAL_GPT", "PLANNER_PASS_CANDIDATE")
            self.apply_next(target, "PLANNER_PASS_CANDIDATE", "READY_FOR_CRITIC_FINAL_AUDIT")
            self.apply_next(target, "READY_FOR_CRITIC_FINAL_AUDIT", "PLANNER_PASS")
            self.apply_next(target, "PLANNER_PASS", "AWAIT_HUMAN_DECISION")
            self.assertEqual(agent_flow.write_terminal_brief(target, "001_toy")["terminal_status"], "awaiting_human")


if __name__ == "__main__":
    unittest.main()
