#!/usr/bin/env python3
"""Run Docker Compose with optional external deployment extensions."""
import subprocess
import sys
from stack_extensions import ROOT, compose_command, settings, refresh_management_model, prepare_runtime_mounts

if __name__ == '__main__':
    if sys.argv[1:] == ['--list']:
        for stack in settings().get('stacks', {}):
            print(stack)
    elif len(sys.argv) < 3:
        sys.exit('Usage: stack-compose.py STACK COMPOSE_ARGUMENTS... | --list')
    else:
        try:
            refresh_management_model(ROOT, sys.argv[1])
            if sys.argv[2] in ('up', 'create', 'start'):
                prepare_runtime_mounts(ROOT, sys.argv[1])
            sys.exit(subprocess.call(compose_command(ROOT, sys.argv[1], sys.argv[2:])))
        except (OSError, ValueError) as error:
            sys.exit(str(error))
