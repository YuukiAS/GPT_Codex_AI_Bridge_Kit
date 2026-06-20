from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path


BEGIN_MARKER = "<!-- ai-bridge-kit:start -->"
END_MARKER = "<!-- ai-bridge-kit:end -->"

PROMPT_FILES = {
    "task": "chatgpt/TASK_WRITER_PROMPT.md",
    "note": "chatgpt/NOTE_WRITER_PROMPT.md",
    "review": "chatgpt/RESULT_REVIEWER_PROMPT.md",
    "next": "chatgpt/NEXT_TASK_PROMPT.md",
    "wiki": "chatgpt/WIKI_WRITER_PROMPT.md",
    "github-mcp": "chatgpt/GITHUB_MCP_REPO_INSTRUCTIONS.md",
    "codex": "codex/CODEX_START_PROMPT.md",
}

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


def kit_root() -> Path:
    return Path(__file__).resolve().parents[1]


def copy_file(src: Path, dst: Path, force: bool, actions: list[str]) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    existed = dst.exists()
    if existed and not force:
        actions.append(f"SKIP existing file: {dst}")
        return
    shutil.copy2(src, dst)
    actions.append(f"COPY {'overwrite' if existed else 'create'}: {dst}")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def install_agents_snippet(target: Path, force: bool, actions: list[str]) -> None:
    agents_path = target / "AGENTS.md"
    snippet = read_text(kit_root() / "codex" / "AGENTS_SNIPPET.md").strip()
    block = f"{BEGIN_MARKER}\n{snippet}\n{END_MARKER}\n"

    if not agents_path.exists():
        write_text(agents_path, block)
        actions.append(f"CREATE AGENTS.md with handoff protocol: {agents_path}")
        return

    current = read_text(agents_path)
    if BEGIN_MARKER in current and END_MARKER in current:
        if not force:
            actions.append(f"SKIP existing handoff block in: {agents_path}")
            return
        start = current.index(BEGIN_MARKER)
        end = current.index(END_MARKER) + len(END_MARKER)
        updated = current[:start].rstrip() + "\n\n" + block + current[end:].lstrip()
        write_text(agents_path, updated)
        actions.append(f"UPDATE handoff block in: {agents_path}")
        return

    updated = current.rstrip() + "\n\n" + block
    write_text(agents_path, updated)
    actions.append(f"APPEND handoff block to: {agents_path}")


def init_workspace(
    target: Path,
    force: bool = False,
    install_agents: bool = True,
    install_skill: bool = True,
) -> int:
    root = kit_root()
    if not (root / "templates").exists():
        print(
            "ERROR: cannot find kit templates. Use an editable local install, "
            "for example: pip install -e /path/to/GPT_Codex_AI_Bridge_Kit",
            file=sys.stderr,
        )
        return 2

    target.mkdir(parents=True, exist_ok=True)
    actions: list[str] = []

    for directory in [
        target / "prompts",
        target / "prompts" / "templates",
        target / "prompts" / "tasks",
        target / "docs",
        target / "docs" / "notes",
        target / "results",
        target / "docs" / "wiki",
        target / "docs" / "wiki" / "papers",
        target / "docs" / "wiki" / "concepts",
        target / "docs" / "wiki" / "entities",
        target / "docs" / "wiki" / "comparisons",
        target / "docs" / "wiki" / "gaps",
        target / "docs" / "wiki" / "synthesis",
    ]:
        directory.mkdir(parents=True, exist_ok=True)
        actions.append(f"DIR  {directory}")

    copy_file(
        root / "templates" / "prompts" / "AGENT_RULES.md",
        target / "prompts" / "AGENT_RULES.md",
        force,
        actions,
    )
    copy_file(
        root / "templates" / "prompts" / "CHATGPT_RULES.md",
        target / "prompts" / "CHATGPT_RULES.md",
        force,
        actions,
    )

    for name in ["TASK_TEMPLATE.md", "RESULT_TEMPLATE.md", "REVIEW_TEMPLATE.md"]:
        copy_file(
            root / "templates" / "prompts" / "templates" / name,
            target / "prompts" / "templates" / name,
            force,
            actions,
        )

    for name in ["README.md", "ARTIFACT_MANIFEST_TEMPLATE.md"]:
        copy_file(
            root / "templates" / "results" / name,
            target / "results" / name,
            force,
            actions,
        )

    copy_file(
        root / "templates" / "docs" / "notes" / "NOTE_TEMPLATE.md",
        target / "docs" / "notes" / "NOTE_TEMPLATE.md",
        force,
        actions,
    )
    for src_rel, dst_rel in [
        ("templates/docs/wiki/README.md", "docs/wiki/README.md"),
        ("templates/docs/wiki/index.md", "docs/wiki/index.md"),
        ("templates/docs/wiki/log.md", "docs/wiki/log.md"),
        ("templates/docs/wiki/papers/PAPER_TEMPLATE.md", "docs/wiki/papers/PAPER_TEMPLATE.md"),
        ("templates/docs/wiki/concepts/CONCEPT_TEMPLATE.md", "docs/wiki/concepts/CONCEPT_TEMPLATE.md"),
        ("templates/docs/wiki/synthesis/DISCUSSION_TEMPLATE.md", "docs/wiki/synthesis/DISCUSSION_TEMPLATE.md"),
        ("templates/docs/wiki/gaps/HYPOTHESES.md", "docs/wiki/gaps/HYPOTHESES.md"),
        ("templates/docs/wiki/gaps/QUESTIONS.md", "docs/wiki/gaps/QUESTIONS.md"),
    ]:
        copy_file(root / src_rel, target / dst_rel, force, actions)

    if install_agents:
        install_agents_snippet(target, force, actions)

    if install_skill:
        copy_file(
            root / "codex" / "skills" / "agent-task-executor" / "SKILL.md",
            target / ".agents" / "skills" / "agent-task-executor" / "SKILL.md",
            force,
            actions,
        )

    print(f"Initialized handoff workspace at: {target}")
    print(f"Force overwrite: {force}")
    print()
    for action in actions:
        print(action)
    print()
    print("Next:")
    print("- ChatGPT/GitHub MCP should read AGENTS.md and prompts/CHATGPT_RULES.md.")
    print("- Codex should read AGENTS.md, prompts/AGENT_RULES.md, and the selected task.")
    print("- Put executable work in prompts/tasks/<task_key>.md.")
    print("- Use <id>_<short_slug>; keep the slug to 1-3 words.")
    print("- Put execution reports and artifacts in results/<task_key>/.")
    print("- Put reusable research knowledge in docs/wiki/; reference it from tasks when needed.")
    return 0


def parse_frontmatter(path: Path) -> tuple[dict[str, str], str | None]:
    text = read_text(path)
    if not text.startswith("---\n"):
        return {}, "missing opening YAML frontmatter marker"
    end = text.find("\n---", 4)
    if end == -1:
        return {}, "missing closing YAML frontmatter marker"

    data: dict[str, str] = {}
    for line_number, line in enumerate(text[4:end].splitlines(), start=2):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in stripped:
            return data, f"invalid frontmatter line {line_number}: {line}"
        key, value = stripped.split(":", 1)
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data, None


def validate_workspace(target: Path) -> int:
    errors: list[str] = []
    warnings: list[str] = []
    oks: list[str] = []

    required_paths = [
        (target / "AGENTS.md", "AGENTS.md"),
        (target / "prompts" / "AGENT_RULES.md", "prompts/AGENT_RULES.md"),
        (target / "prompts" / "CHATGPT_RULES.md", "prompts/CHATGPT_RULES.md"),
        (target / "prompts" / "tasks", "prompts/tasks/"),
        (target / "docs" / "notes", "docs/notes/"),
        (target / "results", "results/"),
        (target / "docs" / "wiki", "docs/wiki/"),
        (target / "docs" / "wiki" / "index.md", "docs/wiki/index.md"),
    ]

    for path, label in required_paths:
        if path.exists():
            oks.append(f"OK   {label} exists")
        else:
            errors.append(f"ERROR missing {label}")

    tasks_dir = target / "prompts" / "tasks"
    results_dir = target / "results"
    if tasks_dir.exists():
        legacy_task_files = sorted(tasks_dir.glob("*_task.md"))
        task_files = sorted(
            path
            for path in tasks_dir.glob("*.md")
            if not path.name.endswith(("_task.md", "_result.md", "_review.md"))
        )
        task_keys = {path.stem for path in task_files}
        legacy_task_ids = {path.name.removesuffix("_task.md") for path in legacy_task_files}
        all_task_keys = task_keys | legacy_task_ids
        if not task_files:
            warnings.append("WARN no new-style task files found in prompts/tasks/")

        for task_file in task_files:
            data, parse_error = parse_frontmatter(task_file)
            if parse_error:
                errors.append(f"ERROR {task_file}: {parse_error}")
                continue
            if not TASK_KEY_RE.fullmatch(task_file.stem):
                errors.append(
                    f"ERROR {task_file}: filename must be <id>_<short_slug>.md with a 1-3 word slug"
                )
            missing = [field for field in REQUIRED_FIELDS if field not in data]
            if missing:
                errors.append(f"ERROR {task_file}: missing fields {', '.join(missing)}")
            elif data.get("task_key") != task_file.stem:
                errors.append(
                    f"ERROR {task_file}: task_key '{data.get('task_key')}' does not match filename"
                )
            else:
                oks.append(f"OK   {task_file.relative_to(target)} frontmatter fields present")

        for task_file in legacy_task_files:
            data, parse_error = parse_frontmatter(task_file)
            if parse_error:
                errors.append(f"ERROR {task_file}: {parse_error}")
                continue
            missing = [field for field in LEGACY_REQUIRED_FIELDS if field not in data]
            if missing:
                errors.append(f"ERROR {task_file}: missing legacy fields {', '.join(missing)}")
            elif data.get("task_id") != task_file.name.removesuffix("_task.md"):
                errors.append(
                    f"ERROR {task_file}: task_id '{data.get('task_id')}' does not match filename"
                )
            else:
                warnings.append(f"WARN legacy task naming: {task_file.relative_to(target)}")

        for result_file in sorted(tasks_dir.glob("*_result.md")):
            result_id = result_file.name.removesuffix("_result.md")
            if result_id in legacy_task_ids:
                warnings.append(f"WARN legacy result location: {result_file.relative_to(target)}")
            else:
                warnings.append(f"WARN result has no matching task: {result_file.relative_to(target)}")

        for review_file in sorted(tasks_dir.glob("*_review.md")):
            review_id = review_file.name.removesuffix("_review.md")
            if review_id in legacy_task_ids:
                warnings.append(f"WARN legacy review location: {review_file.relative_to(target)}")
            else:
                warnings.append(f"WARN review has no matching task: {review_file.relative_to(target)}")

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
                    warnings.append(
                        f"WARN missing result report: {result_report.relative_to(target)}"
                    )
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


def print_prompt(name: str) -> int:
    rel = PROMPT_FILES[name]
    print(read_text(kit_root() / rel))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ai-bridge",
        description=(
            "Deploy and validate the prompts/tasks + docs/notes + results ChatGPT/Codex handoff protocol. "
            "With no subcommand, initializes the current directory."
        ),
    )
    subparsers = parser.add_subparsers(dest="command")

    init_parser = subparsers.add_parser("init", help="Initialize a target project.")
    init_parser.add_argument("--target", type=Path, default=Path.cwd(), help="Target project directory.")
    init_parser.add_argument("--force", action="store_true", help="Overwrite managed template files.")
    init_parser.add_argument("--no-agents", action="store_true", help="Do not create or update AGENTS.md.")
    init_parser.add_argument("--no-skill", action="store_true", help="Do not install the repo-local Codex skill.")

    validate_parser = subparsers.add_parser("validate", help="Validate a target project.")
    validate_parser.add_argument("--target", type=Path, default=Path.cwd(), help="Target project directory.")

    prompt_parser = subparsers.add_parser("prompt", help="Print a reusable prompt or rule file.")
    prompt_parser.add_argument("name", choices=sorted(PROMPT_FILES), help="Prompt name to print.")

    subparsers.add_parser("where", help="Print the installed kit path.")
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        return init_workspace(Path.cwd().resolve())

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "init":
        return init_workspace(
            args.target.resolve(),
            force=args.force,
            install_agents=not args.no_agents,
            install_skill=not args.no_skill,
        )
    if args.command == "validate":
        return validate_workspace(args.target.resolve())
    if args.command == "prompt":
        return print_prompt(args.name)
    if args.command == "where":
        print(kit_root())
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
