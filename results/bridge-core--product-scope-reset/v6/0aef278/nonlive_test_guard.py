"""Non-live verification guard inherited by Python test subprocesses."""
import os
from pathlib import Path
import sys


def guard(event, args):
    forbidden = False
    if event == 'subprocess.Popen':
        argv = args[1]
        if isinstance(argv, (list, tuple)) and argv:
            real_cli = str(Path(str(argv[0])).resolve()) == '/users/a/e/aereinh/bin/codex'
            forbidden = real_cli and len(argv) > 1 and argv[1] == 'exec'
    elif event == 'smtplib.connect':
        forbidden = True
    elif event == 'socket.getaddrinfo':
        forbidden = str(args[0]).lower() == 'smtp.gmail.com'
    if forbidden:
        with open('/tmp/bridge-v6-no-live/blocked-effects.log', 'a', encoding='utf-8') as handle:
            handle.write(f'{event} pid={os.getpid()}\n')
        raise RuntimeError('V6_IMPLEMENTATION_FORBIDS_LIVE_MODEL_AND_SMTP')


sys.addaudithook(guard)
