#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LUAU="$ROOT/vendor/luau/upstream"

if [ ! -d "$LUAU" ]; then
  echo "Luau source is missing. Run: node tools/fetch-luau.mjs" >&2
  exit 1
fi
if ! command -v emcmake >/dev/null 2>&1; then
  echo "Emscripten is required to build Luau.Web." >&2
  exit 1
fi

cd "$LUAU"
emcmake cmake . -DLUAU_BUILD_WEB=ON -DCMAKE_BUILD_TYPE=Release
cmake --build . --target Luau.Web -j2
mkdir -p "$ROOT/vendor/luau/build"
cp -f Luau.Web.js "$ROOT/vendor/luau/build/" 2>/dev/null || true
cp -f Luau.Web.wasm "$ROOT/vendor/luau/build/" 2>/dev/null || true

echo "Luau Web build completed."
