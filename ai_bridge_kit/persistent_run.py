from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path, PurePosixPath


PERSISTENT_RUN_BEGIN_MARKER = "<!-- ai-bridge-kit:persistent-run:start -->"
PERSISTENT_RUN_END_MARKER = "<!-- ai-bridge-kit:persistent-run:end -->"
REQUIRED_TEMPLATE_FILES = (
    "README.md",
    "CONTRACT_TEMPLATE.md",
    "KICKOFF_TEMPLATE.md",
)


class PersistentRunError(ValueError):
    pass


def kit_root() -> Path:
    return Path(__file__).resolve().parents[1]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def git_output(cwd: Path, args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "git command failed").strip()
        raise PersistentRunError(message)
    return result.stdout.strip()


def ensure_git_repo(target: Path) -> Path:
    try:
        root = git_output(target, ["rev-parse", "--show-toplevel"])
    except Exception as exc:
        raise PersistentRunError(f"target is not inside a Git repository: {target}") from exc
    return Path(root).resolve()


def persistent_run_root(target: Path) -> Path:
    return target / "automation" / "persistent_run"


def template_root() -> Path:
    return kit_root() / "templates" / "persistent_run"


def _managed_block() -> str:
    snippet = read_text(template_root() / "AGENTS_SNIPPET.md").strip()
    return f"{PERSISTENT_RUN_BEGIN_MARKER}\n{snippet}\n{PERSISTENT_RUN_END_MARKER}\n"


def install_agents_block(target: Path) -> str:
    agents = target / "AGENTS.md"
    block = _managed_block()
    if not agents.exists():
        write_text(agents, block)
        return f"CREATE {agents}"
    current = read_text(agents)
    if PERSISTENT_RUN_BEGIN_MARKER in current and PERSISTENT_RUN_END_MARKER in current:
        start = current.index(PERSISTENT_RUN_BEGIN_MARKER)
        end = current.index(PERSISTENT_RUN_END_MARKER) + len(PERSISTENT_RUN_END_MARKER)
        prefix = current[:start].rstrip()
        suffix = current[end:].lstrip()
        parts = []
        if prefix:
            parts.append(prefix)
        parts.append(block.rstrip())
        if suffix:
            parts.append(suffix.rstrip())
        updated = "\n\n".join(parts) + "\n"
        action = "UPDATE"
    else:
        updated = current.rstrip() + "\n\n" + block
        action = "APPEND"
    if updated != current:
        write_text(agents, updated)
    return f"{action} Persistent Run managed block in {agents}"


def install_persistent_run(target: Path) -> list[str]:
    target = ensure_git_repo(target.resolve())
    actions: list[str] = []
    source_root = template_root()
    destination_root = persistent_run_root(target)
    for name in REQUIRED_TEMPLATE_FILES:
        source = source_root / name
        destination = destination_root / name
        desired = read_text(source)
        existed = destination.exists()
        current = read_text(destination) if existed else None
        if current != desired:
            write_text(destination, desired)
            actions.append(f"{'UPDATE' if existed else 'CREATE'} {destination}")
        else:
            actions.append(f"SKIP unchanged {destination}")
    actions.append(install_agents_block(target))
    return actions


def _validate_goal_path(target: Path, raw_goal: str) -> tuple[str, Path]:
    value = str(raw_goal or "").replace("\\", "/").strip()
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts or value == ".":
        raise PersistentRunError("goal must be a repo-relative path and must not contain '..'")
    candidate = target / path.as_posix()
    resolved_target = target.resolve()
    resolved_candidate = candidate.resolve()
    if not resolved_candidate.is_relative_to(resolved_target):
        raise PersistentRunError("goal resolves outside target repository")
    if not candidate.exists() or not candidate.is_file():
        raise PersistentRunError(f"goal file does not exist: {path.as_posix()}")
    return path.as_posix(), candidate


def render_kickoff_prompt(target: Path, goal: str) -> str:
    target = ensure_git_repo(target.resolve())
    rel_goal, _goal_path = _validate_goal_path(target, goal)
    template = read_text(template_root() / "KICKOFF_TEMPLATE.md")
    return template.replace("__GOAL_PATH__", rel_goal).rstrip() + "\n"


def validate_persistent_run(target: Path) -> tuple[list[str], int]:
    lines: list[str] = []
    errors: list[str] = []
    try:
        target = ensure_git_repo(target.resolve())
    except PersistentRunError as exc:
        return [f"ERROR {exc}", "FAILED: 1 error(s)"], 1

    source_root = template_root()
    destination_root = persistent_run_root(target)
    for name in REQUIRED_TEMPLATE_FILES:
        source = source_root / name
        destination = destination_root / name
        rel = destination.relative_to(target).as_posix()
        if not destination.exists():
            errors.append(f"missing {rel}")
            continue
        if not destination.is_file():
            errors.append(f"not a file: {rel}")
            continue
        if read_text(destination) != read_text(source):
            errors.append(f"template mismatch: {rel}")
            continue
        lines.append(f"OK   {rel} installed")

    agents = target / "AGENTS.md"
    if not agents.exists():
        errors.append("missing AGENTS.md")
    else:
        text = read_text(agents)
        begin_count = text.count(PERSISTENT_RUN_BEGIN_MARKER)
        end_count = text.count(PERSISTENT_RUN_END_MARKER)
        if begin_count != 1 or end_count != 1:
            errors.append("Persistent Run AGENTS managed block markers are missing or duplicated")
        elif text.index(PERSISTENT_RUN_BEGIN_MARKER) > text.index(PERSISTENT_RUN_END_MARKER):
            errors.append("Persistent Run AGENTS managed block markers are malformed")
        else:
            snippet = read_text(source_root / "AGENTS_SNIPPET.md").strip()
            block = text[
                text.index(PERSISTENT_RUN_BEGIN_MARKER) + len(PERSISTENT_RUN_BEGIN_MARKER) : text.index(PERSISTENT_RUN_END_MARKER)
            ].strip()
            if block != snippet:
                errors.append("Persistent Run AGENTS managed block content mismatch")
            else:
                lines.append("OK   AGENTS.md Persistent Run managed block installed")

    forbidden_codex_rules = target / ".codex" / "rules"
    if forbidden_codex_rules.exists():
        errors.append("Persistent Run install must not create .codex/rules")
    else:
        lines.append("OK   .codex/rules absent")

    for error in errors:
        lines.append(f"ERROR {error}")
    if errors:
        lines.append(f"FAILED: {len(errors)} error(s)")
        return lines, 1
    lines.append("Persistent Run validation passed.")
    return lines, 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ai-bridge persistent-run")
    sub = parser.add_subparsers(dest="command")
    install = sub.add_parser("install", help="Install Persistent Run in a project.")
    install.add_argument("--target", type=Path, default=Path.cwd())
    validate = sub.add_parser("validate", help="Validate a Persistent Run installation.")
    validate.add_argument("--target", type=Path, default=Path.cwd())
    prompt = sub.add_parser("prompt", help="Print Persistent Run prompts.")
    prompt_sub = prompt.add_subparsers(dest="prompt_command")
    kickoff = prompt_sub.add_parser("kickoff", help="Print explicit kickoff authorization for a Goal.")
    kickoff.add_argument("--target", type=Path, default=Path.cwd())
    kickoff.add_argument("--goal", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    try:
        if args.command == "install":
            for line in install_persistent_run(args.target):
                print(line)
            return 0
        if args.command == "validate":
            lines, code = validate_persistent_run(args.target)
            for line in lines:
                print(line)
            return code
        if args.command == "prompt" and args.prompt_command == "kickoff":
            print(render_kickoff_prompt(args.target, args.goal), end="")
            return 0
    except PersistentRunError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
