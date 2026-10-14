"""Read and write through a `requests.Session` of your own.

The script starts a small server on the loopback interface, so it needs no
network: the session carries a header and an adapter that counts requests, and
an `HTTPClient` over `RequestsTransport` sends every request through it.
"""

from __future__ import annotations

import http.server
import threading

import requests
from pathlib_next.http import HTTPClient
from pathlib_next_requests import RequestsTransport


class Handler(http.server.BaseHTTPRequestHandler):
    stored = b"hello from the server\n"

    def do_GET(self):
        body = type(self).stored
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Saw-Team", self.headers.get("X-Team", "-"))
        self.end_headers()
        self.wfile.write(body)

    def do_PUT(self):
        type(self).stored = self.rfile.read(int(self.headers["Content-Length"]))
        self.send_response(204)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *args):
        pass


class Counting(requests.adapters.HTTPAdapter):
    sent = 0

    def send(self, request, **kwargs):
        type(self).sent += 1
        return super().send(request, **kwargs)


def main() -> None:
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with requests.Session() as session:
            session.headers["X-Team"] = "storage"
            session.mount("http://", Counting())
            url = f"http://127.0.0.1:{server.server_port}/notes.txt"
            with HTTPClient(RequestsTransport(session), timeout=(3, 30)) as client:
                print(client.request("GET", url).read().decode(), end="")
                client.request("PUT", url, data=b"replaced through the session\n")
                print(client.request("GET", url).read().decode(), end="")
            print("requests sent through the session:", Counting.sent)
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
