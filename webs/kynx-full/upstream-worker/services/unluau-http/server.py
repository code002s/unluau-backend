#!/usr/bin/env python3
"""Small HTTP adapter for the official Unluau CLI.
The worker sends raw Luau bytecode; this process executes the local Unluau binary.
"""
import base64, os, subprocess, tempfile, xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8788"))
BIN = os.getenv("UNLUAU_BIN", "unluau")
MAX_BYTES = 8 * 1024 * 1024


def run_unluau(data: bytes) -> str:
    p = subprocess.run([BIN], input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.decode("utf-8", "replace") or f"unluau exited {p.returncode}")
    return p.stdout.decode("utf-8", "replace")


def candidates_from_model(data: bytes):
    # rbmx is XML. Search BinaryString/ProtectedString values that contain base64,
    # then try each candidate; raw Luau chunks are passed through unchanged.
    try:
        root = ET.fromstring(data)
    except Exception:
        return [data]
    out = []
    for node in root.iter():
        text = (node.text or "").strip()
        if len(text) < 8:
            continue
        try:
            raw = base64.b64decode(text, validate=True)
        except Exception:
            continue
        if raw and raw[0] in range(3, 15):
            out.append(raw)
    return out


class Handler(BaseHTTPRequestHandler):
    def _send(self, status, body, content_type="text/plain; charset=utf-8"):
        b = body.encode() if isinstance(body, str) else body
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path == "/health":
            self._send(200, '{"ok":true,"backend":"Unluau"}', "application/json")
        else:
            self._send(404, "Not found")

    def do_POST(self):
        if self.path not in ("/", "/decompile"):
            self._send(404, "Not found"); return
        n = int(self.headers.get("Content-Length", "0"))
        if n <= 0 or n > MAX_BYTES:
            self._send(413, "Invalid or oversized body"); return
        data = self.rfile.read(n)
        try:
            for candidate in candidates_from_model(data):
                try:
                    self._send(200, run_unluau(candidate)); return
                except Exception:
                    pass
            raise RuntimeError("no embedded Luau bytecode could be decompiled")
        except Exception as e:
            self._send(422, f"Unluau: {e}")

    def log_message(self, fmt, *args):
        print(fmt % args)

if __name__ == "__main__":
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
