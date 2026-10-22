"""Fail-closed development tests; real API, model and Gmail effects forbidden."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
REAL_CODEX = Path("/users/a/e/aereinh/bin/codex").resolve()


def guard(event, args):
    forbidden = event == "smtplib.connect"
    if event == "subprocess.Popen":
        argv = args[1]
        if isinstance(argv, (list, tuple)) and len(argv) > 1:
            executable = shutil.which(str(argv[0])) or str(argv[0])
            forbidden = Path(executable).resolve() == REAL_CODEX and argv[1] == "exec"
    if event == "socket.getaddrinfo":
        forbidden = str(args[0]).lower() in {"smtp.gmail.com", "api.openai.com"}
    if event == "urllib.Request":
        forbidden = str(args[0]).startswith("https://api.openai.com/")
    if forbidden:
        raise RuntimeError("NORMAL_ENTRY_NONLIVE_ONLY: " + event)


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    assert head == os.environ["BRIDGE_TEST_CANDIDATE"]
    sys.addaudithook(guard)
    print("SOURCE_SHA=" + head, flush=True)
    print("MODE=DETERMINISTIC_NONLIVE; no final batch, model, API or SMTP", flush=True)
    with tempfile.TemporaryDirectory(prefix="bridge-nac-tests-") as state:
        os.environ["AI_BRIDGE_STATE_HOME"] = state
        unittest.main(module=None, argv=[sys.argv[0], *sys.argv[1:]])
