#!/usr/bin/env bash
# One-command build for {{MOD_NAME}}: compile src/ -> jars/{{JAR_NAME}}.jar -> validate. Non-zero exit on any error.
#   ./build.sh                 build + validate
#   ./build.sh --no-validate   compile only
#   ./build.sh --strict        warnings fail too (run before a release)
set -euo pipefail
cd "$(dirname "$0")"
# Prefer `python`: on Windows `python3` can be the Microsoft Store stub.
PY=python; command -v python >/dev/null 2>&1 || PY=python3
exec "$PY" tools/build_mod.py "$@"
