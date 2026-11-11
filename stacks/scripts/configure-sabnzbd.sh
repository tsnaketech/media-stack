#!/usr/bin/env bash
# LinuxServer custom init hooks are invoked through Bash.
set -euo pipefail
/lsiopy/bin/python3 /opt/configure-sabnzbd.py
