"""Run local tests with a fail-closed guard against real model/SMTP effects."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


REAL_CODEX = Path("/users/a/e/aereinh/bin/codex").resolve()


def guard(event, args):
    forbidden = event == "smtplib.connect"
    if event == "subprocess.Popen":
        argv = args[1]
        if isinstance(argv, (list, tuple)) and len(argv) > 1:
            executable = shutil.which(str(argv[0])) or str(argv[0])
            # execpolicy check may quote "codex exec" as inert policy input.
            forbidden = Path(executable).resolve() == REAL_CODEX and argv[1] == "exec"
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
    # Tests must not consume real machine secrets/readiness or write Host locks.
    with tempfile.TemporaryDirectory(prefix="bridge-0111-nonlive-state-") as state:
        os.environ["AI_BRIDGE_STATE_HOME"] = state
        unittest.main(module=None, argv=[sys.argv[0], *sys.argv[1:]])
