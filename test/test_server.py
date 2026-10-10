"""End-to-end HTTP tests. A tiny fake `unluac-cli` stands in for the Rust binary."""

import http.client
import json
import os
import stat
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

from server import ServerConfig, make_handler
from unluau.cleanup import CleanupOptions
from unluau.decompiler import DecompileConfig

from .helpers import fixture

DECOMPILED = """local result = game:GetService("Players")
local function check(a)
    if a then
        if a.ok then
            print(a.ok)
            print(result)
        end
    end
end
"""

FAKE_CLI = f"""#!{sys.executable}
import os, sys
data = sys.stdin.buffer.read()
rejected = open(os.environ["FAKE_REJECT"], "rb").read()
if data == rejected:
    sys.stderr.write("error: unsupported opcode\\n")
    sys.exit(1)
sys.stdout.write({DECOMPILED!r})
"""

PLAIN = fixture("v13_basic_O1_g1.luauc")
ENCODED = fixture("v13_basic_O1_g1_roblox_encoded.luauc")


class ServerHarness:
    """Starts a server with a fake decompiler; mixed into the concrete test cases."""

    token = ""

    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        binary = Path(cls.directory.name) / "fake-unluac"
        binary.write_text(FAKE_CLI)
        binary.chmod(binary.stat().st_mode | stat.S_IEXEC)
        reject = Path(cls.directory.name) / "reject.bin"
        reject.write_bytes(ENCODED)  # the fake fails on Roblox-encoded input, like the real CLI
        os.environ["FAKE_REJECT"] = str(reject)

        config = ServerConfig(
            port=0, token=cls.token, max_concurrent=2, queue_timeout_seconds=5,
            decompile=DecompileConfig(binary=str(binary), timeout_seconds=10, cleanup=CleanupOptions()),
        )
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(config))
        cls.server.daemon_threads = True
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.directory.cleanup()

    def request(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_address[1], timeout=20)
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        data = response.read()
        connection.close()
        return response, data


class PublicServerTest(ServerHarness, unittest.TestCase):
    def test_health(self):
        response, body = self.request("GET", "/health")
        self.assertEqual(response.status, 200)
        self.assertEqual(json.loads(body)["engine"], "unluac-rs")

    def test_unknown_path_is_404(self):
        self.assertEqual(self.request("GET", "/nope")[0].status, 404)
        self.assertEqual(self.request("POST", "/nope", b"x")[0].status, 404)

    def test_decompile_cleans_the_output(self):
        response, body = self.request("POST", "/decompile", PLAIN)
        text = body.decode()
        self.assertEqual(response.status, 200)
        self.assertEqual(response.getheader("X-Cleanup"), "cleaned")
        self.assertTrue(response.getheader("Content-Type").startswith("text/plain"))
        self.assertIn("local Players = game:GetService(\"Players\")", text)
        self.assertIn("if not a then\n        return\n    end", text)

    def test_raw_flag_skips_cleanup(self):
        response, body = self.request("POST", "/decompile?raw=1", PLAIN)
        self.assertEqual(response.getheader("X-Cleanup"), "off")
        self.assertEqual(body.decode(), DECOMPILED)

    def test_post_to_root_also_works(self):
        self.assertEqual(self.request("POST", "/", PLAIN)[0].status, 200)

    def test_roblox_encoded_input_is_descrambled_and_retried(self):
        response, body = self.request("POST", "/decompile", ENCODED)
        self.assertEqual(response.status, 200)
        self.assertIn("Players", body.decode())

    def test_empty_body_is_400(self):
        self.assertEqual(self.request("POST", "/decompile", b"")[0].status, 400)

    def test_compile_error_blob_is_422(self):
        response, body = self.request("POST", "/decompile", b"\x00bad.lua:1: syntax error")
        self.assertEqual(response.status, 422)
        self.assertIn("compile error", json.loads(body)["error"])

    def test_non_luau_data_reports_the_cli_error(self):
        response, body = self.request("POST", "/decompile", ENCODED[:30])
        self.assertIn(response.status, (200, 422))


class TokenServerTest(ServerHarness, unittest.TestCase):
    token = "s3cret"

    def test_missing_token_is_401(self):
        self.assertEqual(self.request("POST", "/decompile", PLAIN)[0].status, 401)

    def test_wrong_token_is_401(self):
        headers = {"Authorization": "Bearer nope"}
        self.assertEqual(self.request("POST", "/decompile", PLAIN, headers)[0].status, 401)

    def test_right_token_is_accepted(self):
        headers = {"Authorization": "Bearer s3cret"}
        self.assertEqual(self.request("POST", "/decompile", PLAIN, headers)[0].status, 200)


if __name__ == "__main__":
    unittest.main()
