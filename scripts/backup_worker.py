"""Authenticated backup runner; database contents never cross its HTTP interface."""
import hmac
import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class BackupWorker:
    def __init__(self, runner=subprocess.run):
        self.runner = runner
        self.lock = threading.Lock()
        self.last = None

    def run(self, restore=False):
        if not self.lock.acquire(blocking=False):
            return 409, {"status": "running"}
        try:
            command = [sys.executable, str(Path(__file__).with_name("database_backup.py"))]
            result = self.runner(command + ["backup"], check=True, capture_output=True,
                                 text=True, timeout=300)
            summary = json.loads(result.stdout)
            if restore:
                result = self.runner(command + ["restore-check", "--snapshot", str(summary["snapshot"])],
                                     check=True, capture_output=True, text=True, timeout=300)
                checked = json.loads(result.stdout)
                if not checked.get("restored") or checked["sha256"] != summary["sha256"]:
                    raise ValueError("Restore verification failed")
                summary["restored"] = True
            self.last = summary
            print(json.dumps({"event": "independent_backup", **summary}), flush=True)
            return 200, summary
        except Exception as error:
            # Subprocess stderr and connection exceptions can contain private data.
            print(json.dumps({"event": "independent_backup", "status": "failed",
                              "type": type(error).__name__}), flush=True)
            return 503, {"status": "failed"}
        finally:
            self.lock.release()


def create_handler(worker, token):
    class Handler(BaseHTTPRequestHandler):
        def respond(self, status, payload):
            body = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)

        def authorized(self):
            value = self.headers.get("Authorization", "")
            return hmac.compare_digest(value.encode(), ("Bearer " + token).encode())

        def do_GET(self):
            if self.path in {"/", "/health"}:
                return self.respond(200 if worker.last else 503,
                                    {"status": "ok" if worker.last else "starting"})
            if self.path == "/status" and self.authorized():
                return self.respond(200, worker.last or {"status": "starting"})
            return self.respond(404, {"status": "not_found"})

        def do_POST(self):
            if self.path != "/backup":
                return self.respond(404, {"status": "not_found"})
            if not self.authorized():
                return self.respond(401, {"status": "unauthorized"})
            if self.headers.get("Transfer-Encoding") or self.headers.get("Content-Length", "0") != "0":
                return self.respond(413, {"status": "body_not_allowed"})
            status, payload = worker.run()
            self.respond(status, payload)

        def log_message(self, *_args):
            pass

    return Handler


def main():
    token = os.environ["BACKUP_OPERATOR_TOKEN"]
    if len(token) < 40:
        raise ValueError("Use a random operator token")
    worker = BackupWorker()
    server = ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("PORT", "8030"))),
                                create_handler(worker, token))
    threading.Thread(target=worker.run,
                     kwargs={"restore": os.environ.get("BACKUP_RESTORE_ON_START") == "1"},
                     daemon=True).start()
    server.serve_forever()


if __name__ == "__main__":
    main()
