"""Stateless HTTP fixture for Dadoku's build and deployment acceptance checks."""

import json
import os
import signal
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import FrameType
from typing import NoReturn
from urllib.parse import urlsplit


def response_for(path: str) -> tuple[HTTPStatus, dict[str, str]]:
    match urlsplit(path).path:
        case "/":
            return HTTPStatus.OK, {
                "application": "dadoku-test-app",
                "message": "Hello from Dadoku.",
                "version": "1",
            }
        case "/healthz":
            return HTTPStatus.OK, {"status": "ok"}
        case _:
            return HTTPStatus.NOT_FOUND, {"error": "not_found"}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def respond(self, *, head_only: bool = False) -> None:
        status, payload = response_for(self.path)
        body = (json.dumps(payload, sort_keys=True) + "\n").encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if not head_only:
            self.wfile.write(body)

    def do_GET(self) -> None:
        self.respond()

    def do_HEAD(self) -> None:
        self.respond(head_only=True)


def stop(_signum: int, _frame: FrameType | None) -> NoReturn:
    raise SystemExit(0)


def main() -> None:
    signal.signal(signal.SIGTERM, stop)
    with ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("PORT", "8000"))), Handler) as server:
        print(f"Dadoku test app listening on port {server.server_port}", flush=True)
        server.serve_forever()


if __name__ == "__main__":
    main()
