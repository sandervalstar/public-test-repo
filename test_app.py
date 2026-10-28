import json
import signal
import unittest
from http import HTTPStatus
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from threading import Thread

from app import Handler, response_for, stop


class ResponseTests(unittest.TestCase):
    def test_home(self):
        self.assertEqual(
            response_for("/"),
            (
                HTTPStatus.OK,
                {
                    "application": "dadoku-test-app",
                    "message": "Hello from Dadoku.",
                    "version": "1",
                },
            ),
        )

    def test_health(self):
        self.assertEqual(response_for("/healthz"), (HTTPStatus.OK, {"status": "ok"}))

    def test_query_is_not_a_different_route(self):
        self.assertEqual(response_for("/healthz?probe=ci"), response_for("/healthz"))

    def test_unknown_paths_fail(self):
        for path in ("/missing", "/healthz/extra", "/.env", "/../etc/passwd"):
            with self.subTest(path=path):
                self.assertEqual(response_for(path), (HTTPStatus.NOT_FOUND, {"error": "not_found"}))

    def test_sigterm_exits_cleanly(self):
        with self.assertRaises(SystemExit) as stopped:
            stop(signal.SIGTERM, None)
        self.assertEqual(stopped.exception.code, 0)


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.addClassCleanup(cls.server.server_close)
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.addClassCleanup(cls.thread.join, 5)
        cls.addClassCleanup(cls.server.shutdown)

    def request(self, method, path):
        connection = HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        self.addCleanup(connection.close)
        connection.request(method, path)
        response = connection.getresponse()
        return response, response.read()

    def test_get_home(self):
        response, body = self.request("GET", "/")
        self.assertEqual(response.status, 200)
        self.assertEqual(json.loads(body), response_for("/")[1])
        self.assertEqual(response.getheader("Content-Type"), "application/json; charset=utf-8")
        self.assertEqual(int(response.getheader("Content-Length")), len(body))
        self.assertEqual(response.getheader("Cache-Control"), "no-store")

    def test_get_health(self):
        response, body = self.request("GET", "/healthz")
        self.assertEqual(response.status, 200)
        self.assertEqual(json.loads(body), {"status": "ok"})

    def test_head_matches_get_without_body(self):
        for path in ("/", "/healthz", "/missing"):
            with self.subTest(path=path):
                get, body = self.request("GET", path)
                head, head_body = self.request("HEAD", path)
                self.assertEqual(head.status, get.status)
                self.assertEqual(head.getheader("Content-Length"), str(len(body)))
                self.assertEqual(head_body, b"")

    def test_unknown_http_path(self):
        response, body = self.request("GET", "/missing")
        self.assertEqual(response.status, 404)
        self.assertEqual(json.loads(body), {"error": "not_found"})

    def test_post_is_not_accepted(self):
        response, _body = self.request("POST", "/")
        self.assertEqual(response.status, 501)


if __name__ == "__main__":
    unittest.main()
