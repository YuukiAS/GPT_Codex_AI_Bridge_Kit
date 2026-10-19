from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import tempfile
from pathlib import Path

from ai_bridge_kit import agent_flow, readiness, reviewed_runner


TASK_KEY = "repo--feature"


def git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.stdout.strip()


def write(path: Path, content: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")


def init_repo(root: Path, *, reviewed: bool = False, local_origin: Path | None = None) -> Path:
    root.mkdir(parents=True)
    git(root, "init", "--initial-branch=main")
    git(root, "config", "user.email", "gate@example.invalid")
    git(root, "config", "user.name", "Gate")
    origin = str(local_origin) if local_origin else "https://github.com/example/project.git"
    git(root, "remote", "add", "origin", origin)
    write(root / "AGENTS.md", "# fixture\n")
    write(root / "prompts" / "AGENT_RULES.md", "rules\n")
    write(root / "prompts" / "tasks" / f"{TASK_KEY}.md", "---\ntask_key: repo--feature\nnotify: false\nrecipient_override: ''\n---\n# Task\n")
    if reviewed:
        task_root = root / "automation" / "reviewed_handoff" / "tasks" / TASK_KEY
        write(root / "automation" / "reviewed_handoff" / "README.md", "review protocol\n")
        write(root / "automation" / "reviewed_handoff" / "prompts" / "CODEX_EXECUTOR.md", "executor\n")
        write(task_root / "REQUEST.md", "request\n")
        write(task_root / "PLAN.md", "plan exact bytes\n")
        write(task_root / "CURRENT.json", json.dumps({"task_key": TASK_KEY, "state": "PLAN_FROZEN"}) + "\n")
    git(root, "add", ".")
    git(root, "commit", "-m", "fixture")
    return root


def counter_program(root: Path, name: str) -> tuple[Path, Path]:
    count = root / f"{name}.count"
    program = root / f"{name}-codex"
    write(program, f"#!/bin/sh\nprintf 'spawn\\n' >> '{count}'\nexit 0\n")
    program.chmod(program.stat().st_mode | stat.S_IXUSR)
    return program, count


def count_lines(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines()) if path.exists() else 0


class CountingAdapter(agent_flow.RuntimeAdapter):
    name = "gate-counting-adapter"

    def __init__(self) -> None:
        self.count = 0

    def launch_role(self, request: agent_flow.RoleLaunchRequest) -> agent_flow.RoleReceipt:
        self.count += 1
        return agent_flow.RoleReceipt(
            role=request.role,
            session_id=f"gate-{self.count}",
            runtime_adapter=self.name,
            worktree_id="gate",
            base_task_nonce=request.request_nonce,
            allowed_write_scope=request.allowed_write_scope,
            start_or_resume_status="started",
            produced_commit="",
            produced_evidence_id="",
        )


def control_request() -> agent_flow.RoleLaunchRequest:
    return agent_flow.RoleLaunchRequest(
        role="Executor",
        task_key=TASK_KEY,
        request_nonce="gate-nonce",
        review_target_id=None,
        base_ref="HEAD",
        allowed_write_scope=["src/**"],
        worktree_policy="existing",
    )


def expect_zero(label: str, callback) -> dict[str, str | int]:
    adapter = CountingAdapter()
    try:
        callback(adapter)
    except readiness.ReadinessError as exc:
        assert adapter.count == 0, (label, adapter.count)
        return {"case": label, "error": exc.code, "launch_count": adapter.count}
    raise AssertionError(f"{label}: expected ReadinessError")


def main() -> None:
    base = Path(tempfile.mkdtemp(prefix="bridge-c2-a609599-", dir="/tmp"))
    results: dict[str, object] = {
        "candidate_sha": git(Path.cwd(), "rev-parse", "HEAD"),
        "fixture_root": str(base),
    }

    lite = init_repo(base / "lite")
    lite_program, lite_count = counter_program(base, "lite")
    write(lite / "unrelated.txt", "unrelated dirty bytes\n")
    lite_command = [
        os.environ["AI_BRIDGE_GATE_BIN"],
        "task",
        "run",
        "--target",
        str(lite),
        "--task-key",
        TASK_KEY,
        "--codex-bin",
        str(lite_program),
    ]
    positive = subprocess.run(lite_command, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert positive.returncode == 0, positive.stderr
    assert count_lines(lite_count) == 1
    task_path = lite / "prompts" / "tasks" / f"{TASK_KEY}.md"
    write(task_path, "worktree mismatch\n")
    negative = subprocess.run(lite_command, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert negative.returncode == 1
    assert count_lines(lite_count) == 1
    results["lite_true_launcher"] = {
        "positive_spawn_count": 1,
        "mismatch_spawn_count": count_lines(lite_count) - 1,
        "mismatch_diagnostic": negative.stderr.strip(),
        "unrelated_dirty_present": (lite / "unrelated.txt").exists(),
    }

    reviewed = init_repo(base / "reviewed", reviewed=True)
    reviewed_program, reviewed_count = counter_program(base, "reviewed")
    current_path = reviewed / "automation" / "reviewed_handoff" / "tasks" / TASK_KEY / "CURRENT.json"
    current = json.loads(current_path.read_text(encoding="utf-8"))
    reviewed_result = reviewed_runner.run_codex_event(
        reviewed,
        TASK_KEY,
        current,
        branch="main",
        codex_bin=str(reviewed_program),
        require_github_https=True,
    )
    assert reviewed_result["launched"] is True
    assert count_lines(reviewed_count) == 1
    write(reviewed / "automation" / "reviewed_handoff" / "tasks" / TASK_KEY / "PLAN.md", "mismatch\n")
    reviewed_fail = reviewed_runner.run_codex_event(
        reviewed,
        TASK_KEY,
        current,
        branch="main",
        codex_bin=str(reviewed_program),
        require_github_https=True,
    )
    assert reviewed_fail["status"] == "prelaunch_not_ready"
    assert count_lines(reviewed_count) == 1
    results["reviewed_true_launcher"] = {
        "positive_spawn_count": 1,
        "mismatch_spawn_count": count_lines(reviewed_count) - 1,
        "mismatch_error": reviewed_fail["readiness_error"],
    }

    source = init_repo(base / "control-source", local_origin=base / "control-remote.git")
    remote = base / "control-remote.git"
    git(base, "clone", "--bare", str(source), str(remote))
    git(remote, "config", "uploadpack.allowFilter", "true")
    git(source, "remote", "set-url", "origin", str(remote))
    head = git(source, "rev-parse", "HEAD")
    repo_identity = "local:" + remote.resolve().as_posix()
    mandatory = [("task", f"prompts/tasks/{TASK_KEY}.md")]
    adapter = CountingAdapter()
    receipt, preflight = agent_flow.launch_executor_with_preflight(
        source,
        adapter,
        control_request(),
        mandatory_sources=mandatory,
        expected_repo=repo_identity,
        expected_worktree=source,
        expected_branch="main",
        expected_commit=head,
    )
    assert receipt.role == "Executor" and adapter.count == 1
    assert preflight["source_bindings"][0]["read_mode"] == "local"
    results["control_true_launcher_local"] = {
        "launch_count": adapter.count,
        "read_mode": preflight["source_bindings"][0]["read_mode"],
        "sha256": preflight["source_bindings"][0]["sha256"],
    }

    negative_cases: list[dict[str, str | int]] = []
    for label, overrides in [
        ("wrong_repo", {"expected_repo": "example/other"}),
        ("wrong_worktree", {"expected_worktree": base / "not-the-worktree"}),
        ("wrong_branch", {"expected_branch": "other"}),
        ("wrong_head", {"expected_commit": "0" * 40}),
    ]:
        defaults = {
            "mandatory_sources": mandatory,
            "expected_repo": repo_identity,
            "expected_worktree": source,
            "expected_branch": "main",
            "expected_commit": head,
        }
        defaults.update(overrides)
        negative_cases.append(
            expect_zero(
                label,
                lambda current_adapter, args=defaults: agent_flow.launch_executor_with_preflight(
                    source, current_adapter, control_request(), **args
                ),
            )
        )
    negative_cases.append(
        expect_zero(
            "wrong_path",
            lambda current_adapter: agent_flow.launch_executor_with_preflight(
                source,
                current_adapter,
                control_request(),
                mandatory_sources=[("task", "../escape")],
                expected_repo=repo_identity,
                expected_worktree=source,
                expected_branch="main",
                expected_commit=head,
            ),
        )
    )
    write(source / "prompts" / "tasks" / f"{TASK_KEY}.md", "mismatch\n")
    negative_cases.append(
        expect_zero(
            "mandatory_source_mismatch",
            lambda current_adapter: agent_flow.launch_executor_with_preflight(
                source,
                current_adapter,
                control_request(),
                mandatory_sources=mandatory,
                expected_repo=repo_identity,
                expected_worktree=source,
                expected_branch="main",
                expected_commit=head,
            ),
        )
    )
    results["context_negatives"] = negative_cases

    content = (base / "control-source" / "prompts" / "tasks" / f"{TASK_KEY}.md").read_bytes()
    committed_content = subprocess.run(
        ["git", "show", f"HEAD:prompts/tasks/{TASK_KEY}.md"],
        cwd=source,
        check=True,
        stdout=subprocess.PIPE,
    ).stdout
    assert hashlib.sha256(committed_content).hexdigest() != hashlib.sha256(content).hexdigest()
    partial = base / "partial"
    git(base, "clone", "--filter=blob:none", "--no-checkout", f"file://{remote}", str(partial))
    git(partial, "read-tree", "HEAD")
    destination = partial / "prompts" / "tasks" / f"{TASK_KEY}.md"
    write(destination, committed_content)
    partial_head = git(partial, "rev-parse", "HEAD")
    partial_repo = "local:" + remote.resolve().as_posix()
    before = readiness._protected_git_snapshot(partial)
    partial_adapter = CountingAdapter()
    _, partial_preflight = agent_flow.launch_executor_with_preflight(
        partial,
        partial_adapter,
        control_request(),
        mandatory_sources=mandatory,
        expected_repo=partial_repo,
        expected_worktree=partial,
        expected_branch="main",
        expected_commit=partial_head,
        isolated_state_root=base / "isolated-state",
    )
    after = readiness._protected_git_snapshot(partial)
    assert partial_adapter.count == 1
    assert partial_preflight["source_bindings"][0]["read_mode"] == "isolated_fallback"
    assert before == after
    results["partial_clone_true_control_launcher"] = {
        "launch_count": partial_adapter.count,
        "read_mode": partial_preflight["source_bindings"][0]["read_mode"],
        "protected_git_snapshot_unchanged": before == after,
    }

    failing = base / "partial-fallback-failure"
    git(base, "clone", "--filter=blob:none", "--no-checkout", f"file://{remote}", str(failing))
    git(failing, "read-tree", "HEAD")
    write(failing / "prompts" / "tasks" / f"{TASK_KEY}.md", committed_content)
    nonexistent = base / "nonexistent-remote.git"
    git(failing, "remote", "set-url", "origin", str(nonexistent))
    failing_head = git(failing, "rev-parse", "HEAD")
    failing_repo = "local:" + nonexistent.resolve().as_posix()
    failure_before = readiness._protected_git_snapshot(failing)
    fallback_case = expect_zero(
        "isolated_fallback_failure",
        lambda current_adapter: agent_flow.launch_executor_with_preflight(
            failing,
            current_adapter,
            control_request(),
            mandatory_sources=mandatory,
            expected_repo=failing_repo,
            expected_worktree=failing,
            expected_branch="main",
            expected_commit=failing_head,
            isolated_state_root=base / "failure-state",
        ),
    )
    failure_after = readiness._protected_git_snapshot(failing)
    assert failure_before == failure_after
    fallback_case["protected_git_snapshot_unchanged"] = int(failure_before == failure_after)
    results["fallback_negative"] = fallback_case

    print(json.dumps(results, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
