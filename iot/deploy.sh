#!/usr/bin/env bash
# One entry point on the existing Linux Docker host. No Python packages required.
set -euo pipefail
umask 077
task_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
exec python3 -B "$task_root/scripts/deploy_server.py" "$@"
