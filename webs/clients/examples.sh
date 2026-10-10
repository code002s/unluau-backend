#!/usr/bin/env bash
# Usage: ./examples.sh script.luauc
BASE="${KYNX_BASE:-https://kynx-site.pages.dev}"
F="$1"
curl -sS -X POST "$BASE/konstant/decompile" -H "Content-Type: text/plain" --data-binary @"$F"
curl -sS -X POST "$BASE/luau/decompile" --data-binary "$(base64 -w0 "$F")"
curl -sS -X POST "$BASE/decompile" -H "Content-Type: application/json" -d "{\"script\":\"$(base64 -w0 "$F")\"}"
curl -sS -X POST "$BASE/x2125/decompile" -H "Content-Type: application/json" -d "{\"script\":\"$(base64 -w0 "$F")\",\"options\":{}}"
curl -sS -X POST "$BASE/api/decompile" -H "Content-Type: application/json" -d "{\"bytecodeBase64\":\"$(base64 -w0 "$F")\"}"
# Direct upstream (needs the Bearer token if UPSTREAM_TOKEN is set):
# curl -sS -X POST https://kynx-upstream.kynxyy.workers.dev/decompile -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "{\"script\":\"$(base64 -w0 "$F")\"}"
