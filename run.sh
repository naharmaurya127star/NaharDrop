#!/usr/bin/env bash
# Convenience launcher for macOS/Linux: creates the venv on first run,
# installs/updates dependencies, then starts the server. Any arguments are
# passed straight through to run.py (e.g. ./run.sh --https --dest ~/Downloads).
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d venv ]; then
  echo "Creating virtual environment..."
  python3 -m venv venv
fi

source venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt
python run.py "$@"
