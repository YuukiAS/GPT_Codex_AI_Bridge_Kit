from __future__ import annotations

import contextlib
import io
import subprocess
import tempfile
import unittest
from pathlib import Path

from ai_bridge_kit import agent_flow
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
            produced_commit=f"{request.role.lower()}-commit",
            produced_evidence_id=f"{request.role.lower()}-evidence",
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
                    "kind": "unit_test",
                    "path": "results/001_toy/verification/unit.json",
                    "target_sensitive": True,
                    "review_target_id": snapshot["review_target_id"],
                }
            ],
            "open_findings": [],
        }
        bundle["bundle_sha256"] = agent_flow.bundle_digest(bundle)
        agent_flow.write_json(agent_flow.result_root(target, "001_toy") / "REVIEW_BUNDLE.json", bundle)
        return snapshot

    def write_planner_and_final_pass(self, target: Path, snapshot: dict[str, str]) -> None:
        root = agent_flow.task_root(target, "001_toy")
        request = agent_flow.load_json(root / "REQUEST.json")
        bundle = agent_flow.load_json(agent_flow.result_root(target, "001_toy") / "REVIEW_BUNDLE.json")
        agent_flow.write_json(
            root / "PLANNER_PASS_CANDIDATE.json",
            {
                "schema": "AI_BRIDGE_PLANNER_PASS_CANDIDATE_V1",
                "task_key": "001_toy",
                "request_nonce": request["request_nonce"],
                "review_target_id": snapshot["review_target_id"],
                "decision": "PLANNER_PASS_CANDIDATE",
            },
        )
        agent_flow.write_json(
            root / "FINAL_CRITIC_AUDIT.json",
            {
                "schema": "AI_BRIDGE_FINAL_CRITIC_AUDIT_V1",
                "task_key": "001_toy",
                "request_nonce": request["request_nonce"],
                "review_target_id": snapshot["review_target_id"],
                "frozen_contract_sha256": snapshot["frozen_contract_sha256"],
                "requirement_ledger_sha256": snapshot["requirement_ledger_sha256"],
                "review_bundle_sha256": bundle["bundle_sha256"],
                "planner_pass_candidate_artifact": "PLANNER_PASS_CANDIDATE.json",
                "decision": "CRITIC_FINAL_PASS",
                "blocking_findings": [],
                "audit_checks": {
                    "contract_not_silently_weakened": True,
                    "ledger_not_expanded_by_runtime_roles": True,
                    "verifier_thresholds_cited": True,
                    "executor_no_test_aware_path": True,
                    "review_bundle_bound_to_target": True,
                },
                "touched_paths": [],
            },
        )

    def write_critic_freeze(self, target: Path) -> None:
        root = agent_flow.task_root(target, "001_toy")
        agent_flow.write_json(
            root / "CRITIC_FREEZE.json",
            {
                "schema": "AI_BRIDGE_CRITIC_FREEZE_V1",
                "task_key": "001_toy",
                "frozen_contract_sha256": agent_flow.file_sha256(root / "FROZEN_CONTRACT.md"),
                "requirement_ledger_sha256": agent_flow.file_sha256(root / "REQUIREMENT_LEDGER.json"),
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
        if session:
            receipt["session_id"] = session
        if worktree:
            receipt["worktree_id"] = worktree
        agent_flow.write_json(agent_flow.role_receipt_path(target, "001_toy", role), receipt)

    def write_verifier_freeze(self, target: Path) -> None:
        root = agent_flow.task_root(target, "001_toy")
        manifest = agent_flow.load_json(root / "VERIFIER_SOURCE_MANIFEST.json")
        agent_flow.write_json(
            root / "VERIFIER_FREEZE.json",
            {
                "schema": "AI_BRIDGE_VERIFIER_FREEZE_V1",
                "task_key": "001_toy",
                "verifier_semantic_digest_sha256": manifest["semantic_digest_sha256"],
                "verifier_evidence_id": "verifier-evidence",
            },
        )
        self.write_role_receipt(target, "Verifier")

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
            root = agent_flow.task_root(target, "001_toy")
            agent_flow.write_json(
                root / "planner_reviews" / "choice.json",
                {
                    "decision": "SCIENTIFIC_OR_PRODUCT_CHOICE_REQUIRED",
                    "finding_id": "F2",
                    "review_target_id": snapshot["review_target_id"],
                },
            )
            routed = agent_flow.route_findings(
                [
                    {
                        "finding_id": "F2",
                        "classification": "SCIENTIFIC_OR_PRODUCT_CHOICE_REQUIRED",
                        "blocking": True,
                        "created_against_review_target_id": snapshot["review_target_id"],
                        "planner_classification_artifact": "planner_reviews/choice.json",
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
                }
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
            agent_flow.write_json(
                agent_flow.result_root(target, "001_toy") / "open_findings.json",
                {
                    "findings": [
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
                    ]
                },
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
            agent_flow.apply_transition(
                target,
                "001_toy",
                expected_state="PLAN_REQUESTED",
                next_state="PLAN_READY_FOR_CRITIC",
                next_action="RUN_CRITIC_INITIAL",
            )
            self.write_critic_freeze(target)
            agent_flow.apply_transition(
                target,
                "001_toy",
                expected_state="PLAN_READY_FOR_CRITIC",
                next_state="PLAN_FROZEN",
                next_action="LAUNCH_VERIFIER",
            )
            snapshot = self.snapshot_and_bundle(target)
            self.assertTrue(any("verifier-owned freeze" in item for item in agent_flow.validate_transition_predicates(target, "001_toy", "VERIFIER_FROZEN", agent_flow.load_json(root / "CURRENT.json"), agent_flow.load_project_profile(target))))
            self.write_verifier_freeze(target)
            agent_flow.apply_transition(
                target,
                "001_toy",
                expected_state="PLAN_FROZEN",
                next_state="VERIFIER_FROZEN",
                next_action="LAUNCH_EXECUTOR",
            )
            self.write_role_receipt(target, "Executor")
            agent_flow.apply_transition(
                target,
                "001_toy",
                expected_state="VERIFIER_FROZEN",
                next_state="EXECUTOR_RUNNING",
                next_action="RUN_EXECUTOR",
            )
            self.assertTrue(agent_flow.validate_executor_result({"test_aware_alternate_path": True, "touched_paths": ["src/calc.py"]}))
            current = agent_flow.load_json(root / "CURRENT.json")
            current["state"] = "READY_FOR_PLANNER_REVIEW"
            current["current_review_target_id"] = snapshot["review_target_id"]
            agent_flow.write_json(root / "CURRENT.json", current)
            self.assertEqual(agent_flow.validate_task_state(target, "001_toy"), [])
            self.write_planner_and_final_pass(target, snapshot)
            agent_flow.apply_transition(
                target,
                "001_toy",
                expected_state="READY_FOR_PLANNER_REVIEW",
                next_state="PLANNER_PASS_CANDIDATE",
                next_action="RUN_FINAL_CRITIC",
            )
            agent_flow.apply_transition(
                target,
                "001_toy",
                expected_state="PLANNER_PASS_CANDIDATE",
                next_state="READY_FOR_CRITIC_FINAL_AUDIT",
                next_action="APPLY_FINAL_CRITIC_PASS",
            )
            agent_flow.apply_transition(
                target,
                "001_toy",
                expected_state="READY_FOR_CRITIC_FINAL_AUDIT",
                next_state="PLANNER_PASS",
                next_action="WRITE_TERMINAL_BRIEF",
            )
            current = agent_flow.load_json(root / "CURRENT.json")
            current["terminal_policy"] = "human_gate"
            agent_flow.write_json(root / "CURRENT.json", current)
            agent_flow.apply_transition(
                target,
                "001_toy",
                expected_state="PLANNER_PASS",
                next_state="AWAIT_HUMAN_DECISION",
                next_action="WRITE_TERMINAL_BRIEF",
            )
            brief = agent_flow.write_terminal_brief(target, "001_toy")
            self.assertEqual(brief["terminal_status"], "awaiting_human")

    def test_toy_b_control_plane_change_and_contract_ambiguity(self) -> None:
        tmp, target = self.make_project()
        with tmp:
            first = self.snapshot_and_bundle(target)
            profile = agent_flow.load_project_profile(target)
            change_class = agent_flow.classify_paths(["automation/agent_flow/schema.json"], profile)
            plan = agent_flow.invalidation_plan(change_class, review_target_id=first["review_target_id"])
            self.assertEqual(change_class, "CONTROL_PLANE_ONLY_CHANGED")
            self.assertFalse(plan["heavy_verifier_required"])
            routed = agent_flow.route_findings(
                [
                    {
                        "finding_id": "F_AMBIG",
                        "classification": "CONTRACT_AMBIGUITY",
                        "blocking": True,
                        "requirement_ids": ["REQ_EXAMPLE_001"],
                    }
                ]
            )
            self.assertEqual(routed["route"], "PLANNER_INTERPRET_CONTRACT")
            write(agent_flow.task_root(target, "001_toy") / "FROZEN_CONTRACT.md", "# Frozen Contract\n\nREQ_EXAMPLE_001: add returns numeric sum only.\n")
            second = agent_flow.snapshot(target, "001_toy")
            self.assertNotEqual(first["review_target_id"], second["review_target_id"])


if __name__ == "__main__":
    unittest.main()
