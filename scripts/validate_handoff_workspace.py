#!/usr/bin/env python3
"""Validate a lightweight ChatGPT + Codex handoff workspace."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


REQUIRED_FIELDS = [
    "task_key",
    "project",
    "status",
    "executor",
    "risk_level",
    "allow_code_change",
    "allow_shell_command",
    "allow_network",
    "allow_external_upload",
    "requires_human_approval",
]

LEGACY_REQUIRED_FIELDS = ["task_id", *REQUIRED_FIELDS[1:]]
TASK_KEY_RE = re.compile(r"^\d+_[A-Za-z0-9]+(?:_[A-Za-z0-9]+){0,2}$")
SKILL_REQUIRED_FIELDS = ["name", "description"]


def parse_frontmatter(path: Path) -> tuple[dict[str, str], str | None]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}, "missing opening YAML frontmatter marker"
    end = text.find("\n---", 4)
    if end == -1:
        return {}, "missing closing YAML frontmatter marker"

    raw = text[4:end].splitlines()
    data: dict[str, str] = {}
    for line_number, line in enumerate(raw, start=2):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if line[:1].isspace() or stripped.startswith("-"):
            continue
        if ":" not in stripped:
            return data, f"invalid frontmatter line {line_number}: {line}"
        key, value = stripped.split(":", 1)
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data, None


def task_id_from_name(path: Path) -> str | None:
    match = re.fullmatch(r"(.+)_task\.md", path.name)
    if not match:
        return None
    return match.group(1)


def validate(target: Path) -> int:
    errors: list[str] = []
    warnings: list[str] = []
    oks: list[str] = []

    agents = target / "AGENTS.md"
    agent_rules = target / "prompts" / "AGENT_RULES.md"
    chatgpt_rules = target / "prompts" / "CHATGPT_RULES.md"
    tasks_dir = target / "prompts" / "tasks"
    notes_dir = target / "docs" / "notes"
    results_dir = target / "results"
    wiki_dir = target / "docs" / "wiki"
    wiki_index = target / "docs" / "wiki" / "index.md"

    for path, label in [
        (agents, "AGENTS.md"),
        (agent_rules, "prompts/AGENT_RULES.md"),
        (chatgpt_rules, "prompts/CHATGPT_RULES.md"),
        (tasks_dir, "prompts/tasks/"),
        (notes_dir, "docs/notes/"),
        (results_dir, "results/"),
        (wiki_dir, "docs/wiki/"),
        (wiki_index, "docs/wiki/index.md"),
    ]:
        if path.exists():
            oks.append(f"OK   {label} exists")
        else:
            errors.append(f"ERROR missing {label}")

    executor_skill = target / ".agents" / "skills" / "agent-task-executor" / "SKILL.md"
    if executor_skill.exists():
        data, parse_error = parse_frontmatter(executor_skill)
        if parse_error:
            errors.append(f"ERROR {executor_skill}: {parse_error}")
        else:
            missing = [field for field in SKILL_REQUIRED_FIELDS if field not in data]
            if missing:
                errors.append(f"ERROR {executor_skill}: missing skill fields {', '.join(missing)}")
            else:
                oks.append("OK   .agents/skills/agent-task-executor/SKILL.md frontmatter fields present")
    elif (target / ".agents" / "skills").exists():
        warnings.append("WARN .agents/skills exists but agent-task-executor skill is not installed")

    if tasks_dir.exists():
        legacy_task_files = sorted(tasks_dir.glob("*_task.md"))
        task_files = sorted(
            path
            for path in tasks_dir.glob("*.md")
            if not path.name.endswith(("_task.md", "_result.md", "_review.md"))
        )
        result_files = sorted(tasks_dir.glob("*_result.md"))
        review_files = sorted(tasks_dir.glob("*_review.md"))

        if not task_files:
            warnings.append("WARN no new-style task files found in prompts/tasks/")

        task_keys = set()
        for task_file in task_files:
            task_key = task_file.stem
            task_keys.add(task_key)
            if not TASK_KEY_RE.fullmatch(task_key):
                errors.append(
                    f"ERROR {task_file}: filename must be <id>_<short_slug>.md with a 1-3 word slug"
                )

            data, parse_error = parse_frontmatter(task_file)
            if parse_error:
                errors.append(f"ERROR {task_file}: {parse_error}")
                continue

            missing = [field for field in REQUIRED_FIELDS if field not in data]
            if missing:
                errors.append(f"ERROR {task_file}: missing fields {', '.join(missing)}")
            elif data.get("task_key") != task_key:
                errors.append(
                    f"ERROR {task_file}: task_key '{data.get('task_key')}' does not match filename"
                )
            else:
                oks.append(f"OK   {task_file.relative_to(target)} frontmatter fields present")

        legacy_task_ids = set()
        for task_file in legacy_task_files:
            name_id = task_id_from_name(task_file)
            if name_id is None:
                errors.append(f"ERROR invalid legacy task filename: {task_file.name}")
                continue
            legacy_task_ids.add(name_id)

            data, parse_error = parse_frontmatter(task_file)
            if parse_error:
                errors.append(f"ERROR {task_file}: {parse_error}")
                continue

            missing = [field for field in LEGACY_REQUIRED_FIELDS if field not in data]
            if missing:
                errors.append(f"ERROR {task_file}: missing legacy fields {', '.join(missing)}")
            elif data.get("task_id") != name_id:
                errors.append(
                    f"ERROR {task_file}: task_id '{data.get('task_id')}' does not match filename id '{name_id}'"
                )
            else:
                warnings.append(f"WARN legacy task naming: {task_file.relative_to(target)}")

        all_task_keys = task_keys | legacy_task_ids

        for result_file in result_files:
            result_id = result_file.name.removesuffix("_result.md")
            if result_id in legacy_task_ids:
                warnings.append(f"WARN legacy result location: {result_file.relative_to(target)}")
            else:
                warnings.append(
                    f"WARN result has no matching task: {result_file.relative_to(target)}"
                )

        for review_file in review_files:
            review_id = review_file.name.removesuffix("_review.md")
            if review_id in legacy_task_ids:
                warnings.append(f"WARN legacy review location: {review_file.relative_to(target)}")
            else:
                warnings.append(
                    f"WARN review has no matching task: {review_file.relative_to(target)}"
                )

        if results_dir.exists():
            for artifact_dir in sorted(path for path in results_dir.iterdir() if path.is_dir()):
                if not TASK_KEY_RE.fullmatch(artifact_dir.name):
                    continue
                if artifact_dir.name in all_task_keys:
                    oks.append(f"OK   {artifact_dir.relative_to(target)}/ matches a task")
                else:
                    warnings.append(
                        f"WARN results directory has no matching task: {artifact_dir.relative_to(target)}/"
                    )
                    continue
                manifest = artifact_dir / "MANIFEST.md"
                if manifest.exists():
                    oks.append(f"OK   {manifest.relative_to(target)} exists")
                else:
                    warnings.append(f"WARN missing artifact manifest: {manifest.relative_to(target)}")
                result_report = artifact_dir / "result.md"
                if not result_report.exists():
                    warnings.append(f"WARN missing result report: {result_report.relative_to(target)}")
                review_report = artifact_dir / "review.md"
                if not review_report.exists():
                    warnings.append(f"WARN missing review file: {review_report.relative_to(target)}")

    print(f"Validating handoff workspace: {target}")
    print()
    for line in oks:
        print(line)
    for line in warnings:
        print(line)
    for line in errors:
        print(line)

    print()
    if errors:
        print(f"FAILED: {len(errors)} error(s), {len(warnings)} warning(s)")
        return 1
    print(f"PASSED: 0 errors, {len(warnings)} warning(s)")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate prompts/tasks, docs/notes, and results handoff workspace structure."
    )
    parser.add_argument(
        "--target",
        required=True,
        type=Path,
        help="Target project directory to validate.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    return validate(args.target.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
