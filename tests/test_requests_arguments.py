"""The arguments of `requests` that `RequestsTransport` takes and the arguments
of `HTTPClient` that it keeps apart, seen from what the server received."""

from __future__ import annotations

import errno

import pytest
import requests

import pathlib_next.http as http
from pathlib_next.http import HTTPClient
from pathlib_next_requests import RequestsTransport
from transport_wire import Wire, response

TIMEOUT = (5, 5)


def client_for(session, **requests_args):
    return HTTPClient(RequestsTransport(session, **requests_args), timeout=TIMEOUT)


def test_a_client_sends_through_the_session_it_was_given():
    calls = []

    class Recording(requests.adapters.HTTPAdapter):
        def send(self, request, **kwargs):
            calls.append((request.method, request.url))
            return super().send(request, **kwargs)

    with Wire() as wire, requests.Session() as session:
        session.mount("http://", Recording())
        client = client_for(session)
        assert client.request("GET", wire.url + "/f.txt").read() == b"ok"
        assert client.transport.session is session
    assert calls == [("GET", wire.url + "/f.txt")]


def test_the_session_is_still_open_after_the_client_is_closed():
    with Wire() as wire, requests.Session() as session:
        client = client_for(session)
        client.request("GET", wire.url + "/f.txt").read()
        client.close()
        client.transport.close()
        assert session.get(wire.url + "/after", timeout=5).content == b"ok"


def test_the_arguments_of_requests_and_the_arguments_of_the_client_do_not_collide():
    with Wire() as wire, requests.Session() as session:
        client = client_for(
            session,
            allow_redirects=True,
            stream=False,
            headers={"X-Token": "t", "X-Both": "transport"},
        )
        reply = client.request("GET", wire.url + "/f", headers={"X-Both": "request"})
        assert reply.read() == b"ok"
    (request,) = wire.requests
    assert request.header("X-Token") == "t"
    assert request.header("X-Both") == "request"


def test_headers_of_the_session_and_of_the_transport_go_with_every_request():
    with Wire() as wire, requests.Session() as session:
        session.headers["X-Session"] = "s"
        client = client_for(session, headers={"X-Transport": "b"})
        client.request("GET", wire.url + "/f").read()
        client.request("GET", wire.url + "/g").read()
    for request in wire.requests:
        assert request.header("X-Session") == "s"
        assert request.header("X-Transport") == "b"
    assert len(wire.requests) == 2


@pytest.mark.parametrize("method", ["PUT", "POST", "DELETE"])
def test_allow_redirects_among_the_arguments_does_not_make_a_write_follow(method):
    def script(request):
        if request.method == method:
            return response(302, {"Location": "/elsewhere"}, reason="Found")
        return response(404, reason="Not Found")

    with Wire(script) as wire, requests.Session() as session:
        client = client_for(session, allow_redirects=True)
        with pytest.raises(OSError) as raised:
            client.request(method, wire.url + "/f.bin", data=b"NEW")
        assert raised.value.errno == errno.EIO
    assert [r.method for r in wire.requests] == [method]


def test_the_auth_of_the_session_wins_over_the_auth_of_the_request():
    with Wire() as wire, requests.Session() as session:
        session.auth = ("bob", "b")
        client = client_for(session)
        client.request("GET", wire.url + "/ok", auth=("alice", "s3cr3t")).read()
    assert wire.requests[0].header("Authorization") == "Basic Ym9iOmI="
    assert "alice" not in wire.requests[0].target


def test_the_auth_of_the_request_is_sent_as_authorization_when_the_session_has_none():
    with Wire() as wire, requests.Session() as session:
        client = client_for(session)
        client.request("GET", wire.url + "/ok", auth=("alice", "s3cr3t")).read()
    assert wire.requests[0].header("Authorization") == "Basic YWxpY2U6czNjcjN0"


def test_a_reply_read_whole_is_capped_whatever_the_transport(monkeypatch):
    monkeypatch.setattr(http, "MAX_REPLY_BYTES", 100)
    with Wire(lambda request: response(body=b"x" * 500)) as wire:
        with requests.Session() as session:
            client = client_for(session)
            with pytest.raises(OSError) as raised:
                client.request("GET", wire.url + "/big")
            assert raised.value.errno == errno.EFBIG
            streamed = client.request("GET", wire.url + "/big", stream=True)
            assert streamed.read() == b"x" * 500
