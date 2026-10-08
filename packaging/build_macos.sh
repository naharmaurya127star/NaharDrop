#!/usr/bin/env bash
# Builds dist/nahardrop - a single-file macOS binary with no Python install
# required on the target machine.
#
# Usage (from the project root):
#   source venv/bin/activate
#   pip install pyinstaller
#   ./packaging/build_macos.sh
set -euo pipefail
cd "$(dirname "$0")/.."

pyinstaller packaging/nahardrop.spec --distpath dist --workpath build --noconfirm

echo
echo "Built dist/nahardrop"
echo "First run will likely need: chmod +x dist/nahardrop"
echo "Unsigned binaries are blocked by Gatekeeper by default - right-click >"
echo "Open the first time, or: xattr -d com.apple.quarantine dist/nahardrop"
