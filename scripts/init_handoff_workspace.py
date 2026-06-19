#!/usr/bin/env python3
"""Initialize a ChatGPT + Codex handoff workspace in a target project."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT_ROOT))

from ai_bridge_kit.cli import init_workspace  # noqa: E402


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Initialize prompts/tasks and docs/notes handoff directories in a project."
    )
    parser.add_argument(
        "--target",
        required=True,
        type=Path,
        help="Target project directory to initialize.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite managed template files and managed AGENTS.md block.",
    )
    parser.add_argument(
        "--no-agents",
        action="store_true",
        help="Do not create or update AGENTS.md.",
    )
    parser.add_argument(
        "--no-skill",
        action="store_true",
        help="Do not install the repo-local Codex skill.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    return init_workspace(
        args.target.resolve(),
        force=args.force,
        install_agents=not args.no_agents,
        install_skill=not args.no_skill,
    )


if __name__ == "__main__":
    raise SystemExit(main())
