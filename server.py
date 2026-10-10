#!/usr/bin/env python3
"""HTTP front end for the unluac-rs Luau decompiler (patched for bytecode v3-v14).

Contract expected by KYNX's upstream worker (LUAU_BACKEND_URL):
  POST /decompile (or /)  body = raw Luau bytecode  ->  200 text/plain Lua source
                                                        4xx/5xx {"error": "..."}
  GET  /health            -> {"ok": true}
Optional: set BACKEND_TOKEN to require `Authorization: Bearer <token>`.
"""
import json
import os
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import luau_descramble

PORT = int(os.getenv("PORT", "8080"))
BIN = os.getenv("UNLUAC_BIN", "/usr/local/bin/unluac-cli")
TOKEN = os.getenv("BACKEND_TOKEN", "")
MAX_BYTES = 16 * 1024 * 1024
TIMEOUT = int(os.getenv("DECOMPILE_TIMEOUT", "60"))
# One decompile at a time per CPU keeps a small instance from thrashing.
SLOTS = threading.BoundedSemaphore(int(os.getenv("MAX_CONCURRENT", "2")))

CLI_ARGS = [
    BIN, "-D", "luau",
    "-i", "-",
    "-n", "heuristic",        # readable fallback names
    "-g", "permissive",       # emit pseudo-code for control flow it can't structure instead of failing
    "--comment", "false",
    # Roblox's Vector3 constants
    "--luau-vector-library", "Vector3",
    "--luau-vector-constructor", "new",
    "--luau-vector-size", "3",
]


class Failure(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


def run_cli(data):
    try:
        p = subprocess.run(CLI_ARGS, input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        raise Failure(504, "decompiler timed out")
    if p.returncode == 0:
        return p.stdout.decode("utf-8", "replace")
    err = p.stderr.decode("utf-8", "replace").strip().splitlines()
    msg = next((l for l in err if l.startswith("error")), err[0] if err else "decompiler failed")
    raise Failure(422 if p.returncode == 1 else 500, msg.replace("error: ", "", 1))


def decompile(data):
    if not data:
        raise Failure(400, "Empty request body")
    if data[0] == 0:
        raise Failure(422, "Luau compile error blob, not bytecode: " + data[1:200].decode("utf-8", "replace"))
    try:
        return run_cli(data)
    except Failure as first:
        # Roblox client/executor dumps scramble opcodes; undo that and retry once.
        if first.status in (504, 400):
            raise
        try:
            plain = luau_descramble.decode_roblox(data)
        except ValueError:
            raise first
        if plain == data:
            raise first
        try:
            return run_cli(plain)
        except Failure:
            raise first


class Handler(BaseHTTPRequestHandler):
    server_version = "unluau-backend"

    def _send(self, status, body, ctype="text/plain; charset=utf-8"):
        raw = body.encode() if isinstance(body, str) else body
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(raw)

    def _json(self, status, obj):
        self._send(status, json.dumps(obj), "application/json; charset=utf-8")

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        if self.path in ("/", "/health"):
            self._json(200, {"ok": True, "service": "unluau-backend", "engine": "unluac-rs", "luauVersions": "3-14"})
        else:
            self._json(404, {"error": "Not found"})

    def do_POST(self):
        if self.path.split("?")[0] not in ("/", "/decompile"):
            return self._json(404, {"error": "Not found"})
        if TOKEN and self.headers.get("Authorization", "") != "Bearer " + TOKEN:
            return self._json(401, {"error": "Unauthorized"})
        try:
            n = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            n = 0
        if n <= 0:
            return self._json(400, {"error": "Empty request body"})
        if n > MAX_BYTES:
            return self._json(413, {"error": "Request body too large"})
        data = self.rfile.read(n)
        try:
            with SLOTS:
                source = decompile(data)
        except Failure as f:
            return self._json(f.status, {"error": f.message})
        except Exception as e:  # never leak a stack trace
            return self._json(500, {"error": "Internal decompiler error: %s" % e})
        self._send(200, source)

    def log_message(self, fmt, *args):
        print(fmt % args, flush=True)


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
