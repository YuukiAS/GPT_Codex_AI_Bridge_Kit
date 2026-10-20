"""Disallow live Codex/SMTP during locator-only candidate regression."""
import os
from pathlib import Path
import sys


def guard(event, args):
    forbidden = False
    if event == 'subprocess.Popen':
        argv = args[1]
        if isinstance(argv, (list, tuple)) and len(argv) > 1:
            forbidden = str(Path(str(argv[0])).resolve()) == '/users/a/e/aereinh/bin/codex' and argv[1] == 'exec'
    elif event == 'smtplib.connect':
        forbidden = True
    elif event == 'socket.getaddrinfo':
        forbidden = str(args[0]).lower() == 'smtp.gmail.com'
    if forbidden:
        with open('/tmp/bridge-v6-locator-nonlive/blocked-effects.log', 'a', encoding='utf-8') as handle:
            handle.write(f'{event} pid={os.getpid()}\n')
        raise RuntimeError('V6_LOCATOR_NONLIVE_ONLY')


sys.addaudithook(guard)
