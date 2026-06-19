#!/usr/bin/env python3
"""Validate a lightweight ChatGPT + Codex handoff workspace."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


REQUIRED_FIELDS = [
    "task_id",
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
    wiki_dir = target / "docs" / "wiki"
    wiki_index = target / "docs" / "wiki" / "index.md"

    for path, label in [
        (agents, "AGENTS.md"),
        (agent_rules, "prompts/AGENT_RULES.md"),
        (chatgpt_rules, "prompts/CHATGPT_RULES.md"),
        (tasks_dir, "prompts/tasks/"),
        (notes_dir, "docs/notes/"),
        (wiki_dir, "docs/wiki/"),
        (wiki_index, "docs/wiki/index.md"),
    ]:
        if path.exists():
            oks.append(f"OK   {label} exists")
        else:
            errors.append(f"ERROR missing {label}")

    if tasks_dir.exists():
        task_files = sorted(tasks_dir.glob("*_task.md"))
        result_files = sorted(tasks_dir.glob("*_result.md"))
        review_files = sorted(tasks_dir.glob("*_review.md"))

        if not task_files:
            warnings.append("WARN no task files found in prompts/tasks/")

        task_ids = set()
        for task_file in task_files:
            name_id = task_id_from_name(task_file)
            if name_id is None:
                errors.append(f"ERROR invalid task filename: {task_file.name}")
                continue
            task_ids.add(name_id)

            data, parse_error = parse_frontmatter(task_file)
            if parse_error:
                errors.append(f"ERROR {task_file}: {parse_error}")
                continue

            missing = [field for field in REQUIRED_FIELDS if field not in data]
            if missing:
                errors.append(f"ERROR {task_file}: missing fields {', '.join(missing)}")
            else:
                oks.append(f"OK   {task_file.relative_to(target)} frontmatter fields present")

            if data.get("task_id") and data["task_id"] != name_id:
                errors.append(
                    f"ERROR {task_file}: task_id '{data['task_id']}' does not match filename id '{name_id}'"
                )

        for result_file in result_files:
            result_id = result_file.name.removesuffix("_result.md")
            if result_id not in task_ids:
                warnings.append(
                    f"WARN result has no matching task: {result_file.relative_to(target)}"
                )
            else:
                oks.append(f"OK   {result_file.relative_to(target)} matches a task")

        for review_file in review_files:
            review_id = review_file.name.removesuffix("_review.md")
            if review_id not in task_ids:
                warnings.append(
                    f"WARN review has no matching task: {review_file.relative_to(target)}"
                )
            else:
                oks.append(f"OK   {review_file.relative_to(target)} matches a task")

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
        description="Validate prompts/tasks and docs/notes handoff workspace structure."
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
