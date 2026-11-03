#!/bin/sh
set -eu

PYTHON="${1:-python3}"
exec "$PYTHON" -m pip install --no-deps -r requirements.txt
