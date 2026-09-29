from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
TESTS_WORKFLOW = ROOT / ".github" / "workflows" / "tests.yml"


def paths_ignore_for(event: str) -> list[str]:
    lines = TESTS_WORKFLOW.read_text(encoding="utf-8").splitlines()
    event_header = f"{event}:"
    for index, line in enumerate(lines):
        if line.strip() != event_header:
            continue
        event_indent = len(line) - len(line.lstrip())
        for inner_index in range(index + 1, len(lines)):
            inner = lines[inner_index]
            stripped = inner.strip()
            if stripped and not stripped.startswith("-") and len(inner) - len(inner.lstrip()) <= event_indent:
                break
            if stripped == "paths-ignore:":
                patterns: list[str] = []
                for pattern_line in lines[inner_index + 1 :]:
                    pattern_indent = len(pattern_line) - len(pattern_line.lstrip())
                    pattern = pattern_line.strip()
                    if pattern.startswith("- "):
                        patterns.append(pattern[2:].strip('"'))
                        continue
                    if pattern and pattern_indent <= len(inner) - len(inner.lstrip()):
                        break
                return patterns
    raise AssertionError(f"{event} paths-ignore block not found")


def github_paths_ignore_matches(pattern: str, path: str) -> bool:
    if pattern == "**/*.md":
        return path.endswith(".md")
    if pattern.endswith("/**"):
        return path.startswith(pattern[:-3] + "/")
    return path == pattern


def tests_workflow_would_trigger(changed_paths: list[str], ignore_patterns: list[str]) -> bool:
    return any(
        not any(github_paths_ignore_matches(pattern, changed_path) for pattern in ignore_patterns)
        for changed_path in changed_paths
    )


class TestsWorkflowTriggerTests(unittest.TestCase):
    def test_docs_markdown_results_only_changes_are_ignored_for_tests_workflow(self) -> None:
        changed_paths = [
            "README.md",
            "CHANGELOG.md",
            "docs/TODO_LOCAL_AUTONOMOUS_ACCEPTANCE_WORKFLOW.md",
            "docs/design/0.9.1_reviewed_handoff_first_bootstrap_normal_entry_goal_v0.1_2026-09-24.md",
            "results/repo--task/FINAL_REPORT.md",
        ]
        for event in ("push", "pull_request"):
            with self.subTest(event=event):
                ignore_patterns = paths_ignore_for(event)
                self.assertFalse(tests_workflow_would_trigger(changed_paths, ignore_patterns))

    def test_code_test_workflow_and_config_changes_still_trigger_tests_workflow(self) -> None:
        changed_paths = [
            "ai_bridge_kit/reviewed_handoff.py",
            "tests/test_reviewed_handoff.py",
            ".github/workflows/tests.yml",
            "pyproject.toml",
        ]
        for event in ("push", "pull_request"):
            ignore_patterns = paths_ignore_for(event)
            for changed_path in changed_paths:
                with self.subTest(event=event, changed_path=changed_path):
                    self.assertTrue(tests_workflow_would_trigger([changed_path], ignore_patterns))

    def test_tests_workflow_keeps_superseded_run_cancellation(self) -> None:
        text = TESTS_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("group: tests-${{ github.workflow }}-${{ github.ref }}", text)
        self.assertIn("cancel-in-progress: true", text)


if __name__ == "__main__":
    unittest.main()
