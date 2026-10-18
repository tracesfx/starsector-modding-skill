#!/usr/bin/env bash
# The Last Census - one-command build.
#   ./build.sh            compile Java -> jars/TheLastCensus.jar, then run the data validator
#   ./build.sh --no-validate   compile only
# Fails loudly (non-zero exit) on any compiler error or validation failure.
set -euo pipefail

MOD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$MOD_DIR"

# Locate the game: this mod lives in <game>/mods/<mod>.
GAME_DIR="$(cd "$MOD_DIR/../.." && pwd)"
CORE="$GAME_DIR/starsector-core"
MODS="$GAME_DIR/mods"

to_win() { if command -v cygpath >/dev/null 2>&1; then cygpath -m "$1"; else echo "$1"; fi; }
SEP=":"; if command -v cygpath >/dev/null 2>&1; then SEP=";"; fi

CP_ENTRIES=(
  "$CORE/starfarer.api.jar"
  "$CORE/json.jar"
  "$CORE/log4j-1.2.9.jar"
  "$CORE/lwjgl.jar"
  "$CORE/lwjgl_util.jar"
  "$CORE/xstream-1.4.10.jar"
  "$MODS/LazyLib/jars/LazyLib.jar"
  "$MODS/LazyLib/jars/internal/Kotlin-Runtime.jar"
  "$MODS/LunaLib/jars/LunaLib.jar"
  "$MODS/GraphicsLib/jars/Graphics.jar"   # optional at runtime; needed only to compile tlc.compat
)
CP=""
for e in "${CP_ENTRIES[@]}"; do
  if [[ ! -f "$e" ]]; then echo "BUILD ERROR: missing classpath entry: $e" >&2; exit 1; fi
  CP+="$(to_win "$e")$SEP"
done

command -v javac >/dev/null || { echo "BUILD ERROR: javac not found on PATH (JDK 17 required)" >&2; exit 1; }
JV="$(javac -version 2>&1 | awk '{print $2}')"
echo "[build] javac $JV, target --release 17"

OUT="build/classes"
rm -rf build && mkdir -p "$OUT"
find src -name '*.java' > build/sources.txt
NSRC=$(wc -l < build/sources.txt)
echo "[build] compiling $NSRC source files"
javac --release 17 -encoding UTF-8 -Xlint:all -Xlint:-serial -Xlint:-options -Xlint:-classfile -Xlint:-processing \
      -cp "$CP" -d "$OUT" @build/sources.txt

mkdir -p jars
rm -f jars/TheLastCensus.jar
jar cf jars/TheLastCensus.jar -C "$OUT" .
echo "[build] wrote jars/TheLastCensus.jar ($(unzip -l jars/TheLastCensus.jar | tail -1 | awk '{print $2}') entries)"

if [[ "${1:-}" != "--no-validate" ]]; then
  PY=python; command -v python >/dev/null || PY=python3
  "$PY" tools/validate.py
fi
echo "[build] OK"
