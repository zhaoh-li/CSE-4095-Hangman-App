"""Browser-client integration test.

Starts a real server that always picks "apple", then runs
tests/browser_client.mjs, which loads the real static/app.js in Node with a
small fake page and plays against that server. Each check the script prints
becomes a subtest here.

Skipped automatically if Node.js is not installed.
"""

import json
import logging
import shutil
import subprocess
import threading
import unittest
from pathlib import Path

from werkzeug.serving import make_server

from server import create_app

SCRIPT = Path(__file__).resolve().parent / "browser_client.mjs"
logging.getLogger("werkzeug").setLevel(logging.ERROR)


class FixedWords:
    def random_word(self, difficulty):
        return "apple"


def run_browser_script(base_url, word=None, timeout=120):
    """Run the Node script and return (exit code, list of check results, stderr)."""
    command = ["node", str(SCRIPT), "--base", base_url]
    if word:
        command += ["--word", word]
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    checks = [json.loads(line) for line in result.stdout.splitlines() if line.startswith("{")]
    return result.returncode, checks, result.stderr


@unittest.skipUnless(shutil.which("node"), "Node.js not installed")
class BrowserClientTests(unittest.TestCase):
    def test_browser_client_against_a_real_server(self):
        app = create_app(word_manager=FixedWords())
        app.logger.disabled = True
        server = make_server("127.0.0.1", 0, app, threaded=True)
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        thread.start()
        try:
            code, checks, stderr = run_browser_script(f"http://127.0.0.1:{server.port}", word="apple")
        finally:
            server.shutdown()
            thread.join(timeout=5)

        self.assertGreaterEqual(len(checks), 55, f"too few checks ran.\n{stderr}")
        for item in checks:
            with self.subTest(check=item["name"]):
                self.assertTrue(item["ok"], item["detail"])
        self.assertEqual(code, 0, stderr)


if __name__ == "__main__":
    unittest.main()
