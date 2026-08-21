from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) >= 2 and args[0] == "reviewed-handoff" and args[1] == "watcher":
        from . import reviewed_runner

        return reviewed_runner.main(args[2:])
    if args and args[0] == "reviewed-handoff":
        from . import reviewed_handoff

        return reviewed_handoff.main(args[1:])
    if args and args[0] == "visual-review":
        from . import visual_review

        return visual_review.main(args[1:])

    from .cli import main as legacy_main

    return legacy_main(args)


if __name__ == "__main__":
    raise SystemExit(main())
