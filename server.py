#!/usr/bin/env python3
"""HTTP front end for the unluac-rs Luau decompiler (bytecode v3-v14).

Contract expected by KYNX's upstream Worker (`LUAU_BACKEND_URL`):

    POST /decompile (or /)   body = raw Luau bytecode  ->  200 text/plain Luau source
                                                           4xx/5xx {"error": "..."}
    GET  /health             -> {"ok": true, ...}

Optional: `BACKEND_TOKEN` requires `Authorization: Bearer <token>`.
Add `?raw=1` to `POST /decompile` to skip the readability cleanup.
"""

from __future__ import annotations

import hmac
import json
import os
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from unluau.cleanup import CleanupOptions
from unluau.decompiler import DecompileConfig, Failure, decompile

MAX_BODY_BYTES = 16 * 1024 * 1024
DECOMPILE_PATHS = ("/", "/decompile")
HEALTH_PATHS = ("/", "/health")
ENGINE_INFO = {"ok": True, "service": "unluau-backend", "engine": "unluac-rs", "luauVersions": "3-14"}


@dataclass(frozen=True)
class ServerConfig:
    port: int
    token: str
    max_concurrent: int
    queue_timeout_seconds: float
    decompile: DecompileConfig

    @classmethod
    def from_env(cls) -> "ServerConfig":
        env = os.environ.get
        cleanup = CleanupOptions(strict_header=env("LUAU_STRICT_HEADER", "") == "1")
        return cls(
            port=int(env("PORT", "8080")),
            token=env("BACKEND_TOKEN", ""),
            max_concurrent=int(env("MAX_CONCURRENT", "2")),
            queue_timeout_seconds=float(env("QUEUE_TIMEOUT", "20")),
            decompile=DecompileConfig(
                binary=env("UNLUAC_BIN", "/usr/local/bin/unluac-cli"),
                # The KYNX Worker gives up after 30 s, so answer before that.
                timeout_seconds=int(env("DECOMPILE_TIMEOUT", "25")),
                cleanup=cleanup,
            ),
        )


def make_handler(config: ServerConfig) -> type[BaseHTTPRequestHandler]:
    slots = threading.BoundedSemaphore(config.max_concurrent)

    class Handler(BaseHTTPRequestHandler):
        server_version = "unluau-backend"

        # -- responses -------------------------------------------------------- #

        def _send(self, status: int, body: str | bytes, content_type: str = "text/plain; charset=utf-8",
                  headers: dict[str, str] | None = None) -> None:
            payload = body.encode() if isinstance(body, str) else body
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            for name, value in (headers or {}).items():
                self.send_header(name, value)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(payload)

        def _json(self, status: int, payload: dict) -> None:
            self._send(status, json.dumps(payload), "application/json; charset=utf-8")

        def _is_authorized(self) -> bool:
            if not config.token:
                return True
            supplied = self.headers.get("Authorization", "")
            return hmac.compare_digest(supplied, f"Bearer {config.token}")

        # -- routes ----------------------------------------------------------- #

        def do_HEAD(self) -> None:  # noqa: N802
            self.do_GET()

        def do_GET(self) -> None:  # noqa: N802
            if urlsplit(self.path).path not in HEALTH_PATHS:
                return self._json(404, {"error": "Not found"})
            self._json(200, ENGINE_INFO)

        def do_POST(self) -> None:  # noqa: N802
            url = urlsplit(self.path)
            if url.path not in DECOMPILE_PATHS:
                return self._json(404, {"error": "Not found"})
            if not self._is_authorized():
                return self._json(401, {"error": "Unauthorized"})

            data = self._read_body()
            if data is None:
                return
            clean = parse_qs(url.query).get("raw", ["0"])[0] != "1"
            self._respond_with_decompile(data, clean)

        def _read_body(self) -> bytes | None:
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            if length <= 0:
                self._json(400, {"error": "Empty request body"})
                return None
            if length > MAX_BODY_BYTES:
                self._json(413, {"error": "Request body too large"})
                return None
            return self.rfile.read(length)

        def _respond_with_decompile(self, data: bytes, clean: bool) -> None:
            if not slots.acquire(timeout=config.queue_timeout_seconds):
                return self._json(503, {"error": "Decompiler is busy, retry shortly"})
            try:
                result = decompile(data, config.decompile, clean)
            except Failure as failure:
                return self._json(failure.status, {"error": failure.message})
            except Exception as error:  # noqa: BLE001 - never leak a stack trace
                return self._json(500, {"error": f"Internal decompiler error: {type(error).__name__}"})
            finally:
                slots.release()

            cleanup = result.cleanup
            status = "off" if cleanup is None else ("cleaned" if cleanup.cleaned else "skipped")
            headers = {"X-Cleanup": status}
            if cleanup is not None and cleanup.note:
                headers["X-Cleanup-Note"] = cleanup.note.encode("ascii", "replace").decode()[:200]
            self._send(200, result.source, headers=headers)

        def log_message(self, format: str, *args) -> None:  # noqa: A002
            print(format % args, flush=True)

    return Handler


def main() -> None:
    config = ServerConfig.from_env()
    server = ThreadingHTTPServer(("0.0.0.0", config.port), make_handler(config))
    server.daemon_threads = True
    server.serve_forever()


if __name__ == "__main__":
    main()
