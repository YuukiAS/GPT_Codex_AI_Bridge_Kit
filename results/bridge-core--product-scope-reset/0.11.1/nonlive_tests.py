"""Run local tests with a fail-closed guard against real model/SMTP effects."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest


REAL_CODEX = Path("/users/a/e/aereinh/bin/codex").resolve()


def guard(event, args):
    forbidden = event == "smtplib.connect"
    if event == "subprocess.Popen":
        argv = args[1]
        if isinstance(argv, (list, tuple)) and len(argv) > 1:
            executable = shutil.which(str(argv[0])) or str(argv[0])
            forbidden = Path(executable).resolve() == REAL_CODEX and "exec" in argv[1:]
    if event == "socket.getaddrinfo":
        forbidden = str(args[0]).lower() == "smtp.gmail.com"
    if forbidden:
        print("FORBIDDEN_LIVE_EFFECT=" + event, file=sys.stderr, flush=True)
        raise RuntimeError("PATCH_0111_NONLIVE_TESTS_ONLY")


if __name__ == "__main__":
    # Keep the repository first on sys.path, not the evidence script directory.
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip() == os.environ["BRIDGE_TEST_CANDIDATE"]
    sys.addaudithook(guard)
    print("CANDIDATE=" + os.environ["BRIDGE_TEST_CANDIDATE"], flush=True)
    unittest.main(module=None, argv=[sys.argv[0], *sys.argv[1:]])
