from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "reviewed-handoff":
        from . import reviewed_handoff

        return reviewed_handoff.main(args[1:])

    from .cli import main as legacy_main

    return legacy_main(args)


if __name__ == "__main__":
    raise SystemExit(main())
