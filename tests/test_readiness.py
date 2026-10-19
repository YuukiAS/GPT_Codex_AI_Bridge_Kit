from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from ai_bridge_kit import agent_flow, cli, readiness, reviewed_runner


def git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout.strip()


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class CountingAdapter(agent_flow.RuntimeAdapter):
    name = "counting"

    def __init__(self) -> None:
        self.count = 0

    def launch_role(self, request: agent_flow.RoleLaunchRequest) -> agent_flow.RoleReceipt:
        self.count += 1
        return agent_flow.RoleReceipt(
            role=request.role,
            session_id="session",
            runtime_adapter=self.name,
            worktree_id="worktree",
            base_task_nonce=request.request_nonce,
            allowed_write_scope=request.allowed_write_scope,
            start_or_resume_status="started",
            produced_commit="",
            produced_evidence_id="",
        )


class ReadinessTests(unittest.TestCase):
    def make_repo(self, root: Path, *, reviewed: bool = False) -> Path:
        root.mkdir(parents=True)
        git(root, "init", "-b", "main")
        git(root, "config", "user.email", "tests@example.com")
        git(root, "config", "user.name", "Tests")
        git(root, "remote", "add", "origin", "https://github.com/example/project.git")
        write(root / "AGENTS.md", "repo rules\n")
        write(root / "prompts" / "AGENT_RULES.md", "agent rules\n")
        write(
            root / "prompts" / "tasks" / "repo--feature.md",
            "---\ntask_key: repo--feature\n---\n# Task\n",
        )
        if reviewed:
            write(root / "automation" / "reviewed_handoff" / "README.md", "review rules\n")
            write(
                root / "automation" / "reviewed_handoff" / "prompts" / "CODEX_EXECUTOR.md",
                "executor rules\n",
            )
            write(
                root / "automation" / "reviewed_handoff" / "tasks" / "repo--feature" / "REQUEST.md",
                "# Request\n",
            )
            write(
                root / "automation" / "reviewed_handoff" / "tasks" / "repo--feature" / "PLAN.md",
                "# Plan\n",
            )
            write(
                root / "automation" / "reviewed_handoff" / "tasks" / "repo--feature" / "CURRENT.json",
                json.dumps({"task_key": "repo--feature", "state": "PLAN_FROZEN"}) + "\n",
            )
        git(root, "add", ".")
        git(root, "commit", "-m", "fixture")
        return root

    def test_local_exact_blob_allows_unrelated_dirty_and_binds_commit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_repo(Path(tmp) / "repo")
            write(root / "unrelated.txt", "dirty\n")
            locator = readiness.freeze_execution_locator(
                root,
                [("task", "prompts/tasks/repo--feature.md")],
            )
            result = readiness.preflight_execution_sources(locator)
            self.assertEqual(result["head"], git(root, "rev-parse", "HEAD"))
            self.assertEqual(result["source_bindings"][0]["read_mode"], "local")
            self.assertEqual(
                result["source_bindings"][0]["sha256"],
                hashlib.sha256((root / "prompts/tasks/repo--feature.md").read_bytes()).hexdigest(),
            )

    def test_context_and_mandatory_source_mismatch_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_repo(Path(tmp) / "repo")
            locator = readiness.freeze_execution_locator(
                root,
                [("task", "prompts/tasks/repo--feature.md")],
            )
            write(root / "prompts/tasks/repo--feature.md", "changed\n")
            with self.assertRaises(readiness.ReadinessError) as caught:
                readiness.preflight_execution_sources(locator)
            self.assertEqual(caught.exception.code, "MANDATORY_SOURCE_WORKTREE_MISMATCH")
            git(root, "checkout", "--", "prompts/tasks/repo--feature.md")
            write(root / "unrelated.txt", "new head\n")
            git(root, "add", "unrelated.txt")
            git(root, "commit", "-m", "advance")
            with self.assertRaises(readiness.ReadinessError) as caught:
                readiness.preflight_execution_sources(locator)
            self.assertEqual(caught.exception.code, "EXECUTION_HEAD_MISMATCH")

    def test_hidden_index_flags_and_transforms_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for flag in ("--assume-unchanged", "--skip-worktree"):
                root = self.make_repo(Path(tmp) / flag.removeprefix("--"))
                path = "prompts/tasks/repo--feature.md"
                git(root, "update-index", flag, path)
                locator = readiness.freeze_execution_locator(root, [("task", path)])
                with self.assertRaises(readiness.ReadinessError) as caught:
                    readiness.preflight_execution_sources(locator)
                self.assertEqual(caught.exception.code, "MANDATORY_SOURCE_INDEX_FLAGS_UNSAFE")
            root = self.make_repo(Path(tmp) / "attrs")
            write(root / ".gitattributes", "prompts/tasks/repo--feature.md filter=unsafe\n")
            git(root, "add", ".gitattributes")
            git(root, "commit", "-m", "attrs")
            locator = readiness.freeze_execution_locator(root, [("task", "prompts/tasks/repo--feature.md")])
            with self.assertRaises(readiness.ReadinessError) as caught:
                readiness.preflight_execution_sources(locator)
            self.assertEqual(caught.exception.code, "MANDATORY_SOURCE_GIT_ATTRIBUTE_UNSAFE")

    def test_lite_normal_entry_spawns_once_or_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_repo(Path(tmp) / "repo")
            write(root / "unrelated.txt", "dirty\n")
            real_run = subprocess.run
            calls: list[list[str]] = []

            def dispatch(command, *args, **kwargs):
                if command and command[0] == "codex":
                    calls.append(command)
                    return SimpleNamespace(returncode=0)
                return real_run(command, *args, **kwargs)

            with mock.patch.object(cli.subprocess, "run", side_effect=dispatch):
                code = cli.run_lite_task(root, "repo--feature", codex_bin="codex", dry_run=False)
            self.assertEqual(code, 0)
            self.assertEqual(len(calls), 1)
            write(root / "prompts/tasks/repo--feature.md", "mismatch\n")
            calls.clear()
            with mock.patch.object(cli.subprocess, "run", side_effect=dispatch):
                code = cli.run_lite_task(root, "repo--feature", codex_bin="codex", dry_run=False)
            self.assertEqual(code, 1)
            self.assertEqual(len(calls), 0)

    def test_reviewed_normal_entry_source_failure_keeps_codex_count_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_repo(Path(tmp) / "repo", reviewed=True)
            current_path = root / "automation/reviewed_handoff/tasks/repo--feature/CURRENT.json"
            current = json.loads(current_path.read_text(encoding="utf-8"))
            write(root / "automation/reviewed_handoff/tasks/repo--feature/PLAN.md", "mismatch\n")
            real_run = subprocess.run
            codex_count = 0

            def dispatch(command, *args, **kwargs):
                nonlocal codex_count
                if command and command[0] == "codex":
                    codex_count += 1
                    return SimpleNamespace(returncode=0)
                return real_run(command, *args, **kwargs)

            with mock.patch.object(reviewed_runner.subprocess, "run", side_effect=dispatch):
                result = reviewed_runner.run_codex_event(
                    root,
                    "repo--feature",
                    current,
                    branch="main",
                    require_github_https=True,
                )
            self.assertEqual(result["status"], "prelaunch_not_ready")
            self.assertEqual(codex_count, 0)

    def test_control_adapter_launch_is_after_exact_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_repo(Path(tmp) / "repo")
            adapter = CountingAdapter()
            request = agent_flow.RoleLaunchRequest(
                role="Executor",
                task_key="repo--feature",
                request_nonce="nonce",
                review_target_id=None,
                base_ref="HEAD",
                allowed_write_scope=["src/**"],
                worktree_policy="existing",
            )
            head = git(root, "rev-parse", "HEAD")
            receipt, preflight = agent_flow.launch_executor_with_preflight(
                root,
                adapter,
                request,
                mandatory_sources=[("task", "prompts/tasks/repo--feature.md")],
                expected_repo="example/project",
                expected_worktree=root,
                expected_branch="main",
                expected_commit=head,
            )
            self.assertEqual(receipt.role, "Executor")
            self.assertEqual(preflight["head"], head)
            self.assertEqual(adapter.count, 1)
            write(root / "prompts/tasks/repo--feature.md", "mismatch\n")
            with self.assertRaises(readiness.ReadinessError):
                agent_flow.launch_executor_with_preflight(
                    root,
                    adapter,
                    request,
                    mandatory_sources=[("task", "prompts/tasks/repo--feature.md")],
                    expected_repo="example/project",
                    expected_worktree=root,
                    expected_branch="main",
                    expected_commit=head,
                )
            self.assertEqual(adapter.count, 1)

    def test_projected_writer_budget_uses_actual_limit_and_zero_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            root.mkdir()
            original = b"user text\n"
            (root / "AGENTS.md").write_bytes(original)
            codex_home = Path(tmp) / "codex-home"
            codex_home.mkdir()
            write(codex_home / "config.toml", "project_doc_max_bytes = 16\n")
            with mock.patch.dict(os.environ, {"CODEX_HOME": str(codex_home)}, clear=False):
                with self.assertRaises(readiness.ReadinessError) as caught:
                    readiness.preflight_root_agents_mutation(
                        root,
                        b"user text\nmanaged bytes\n",
                        block_name="core",
                        block_bytes=13,
                    )
            self.assertEqual(caught.exception.code, "BRIDGE_MANAGED_INSTRUCTION_PROJECTED_OVERFLOW")
            self.assertEqual((root / "AGENTS.md").read_bytes(), original)

    def test_real_partial_clone_uses_isolated_fallback_without_repo_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source = self.make_repo(base / "source")
            bare = base / "remote.git"
            git(base, "clone", "--bare", str(source), str(bare))
            git(bare, "config", "uploadpack.allowFilter", "true")
            partial = base / "partial"
            git(base, "clone", "--filter=blob:none", "--no-checkout", f"file://{bare}", str(partial))
            git(partial, "read-tree", "HEAD")
            content = (source / "prompts/tasks/repo--feature.md").read_bytes()
            destination = partial / "prompts/tasks/repo--feature.md"
            destination.parent.mkdir(parents=True)
            destination.write_bytes(content)
            locator = readiness.freeze_execution_locator(
                partial,
                [("task", "prompts/tasks/repo--feature.md")],
            )
            state_root = base / "state"
            before = readiness._protected_git_snapshot(partial)
            result = readiness.preflight_execution_sources(locator, isolated_state_root=state_root)
            self.assertEqual(result["source_bindings"][0]["read_mode"], "isolated_fallback")
            self.assertEqual(readiness._protected_git_snapshot(partial), before)


if __name__ == "__main__":
    unittest.main()
