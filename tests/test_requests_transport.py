"""What a `requests.Session` gives a transport that the built-in one does not,
against loopback servers: the caller's session and what it holds, `~/.netrc`,
`REQUESTS_CA_BUNDLE`, and who closes the session. The promises every
transport keeps are run from `uripath` by `test_uripath_suite.py`."""

from __future__ import annotations

import io
import os
import ssl

import pytest
import requests

from http_wire import Wire, make_authority, response
from uripath_http_requests import RequestsTransport

TIMEOUT = (5, 5)


def send(transport, url, method="GET", headers=None, **kwargs):
    kwargs.setdefault("timeout", TIMEOUT)
    return transport.send(method, url, headers=headers or {}, **kwargs)


def seen(wire, name):
    return [r.header(name) for r in wire.requests]


# --- who closes the session ---------------------------------------------------


def test_a_session_the_transport_made_is_closed_with_it():
    transport = RequestsTransport()
    closed = []
    transport.session.close = lambda: closed.append(True)
    transport.close()
    transport.close()
    assert closed == [True, True]


def test_a_session_of_the_caller_is_left_open_and_still_works():
    closed = []
    with Wire() as wire, requests.Session() as session:
        session.close = lambda: closed.append(True)
        with RequestsTransport(session) as transport:
            assert send(transport, wire.url + "/a").read() == b"ok"
        transport.close()
        assert closed == []
        assert transport.session is session
        assert session.get(wire.url + "/b", timeout=5).content == b"ok"
        del session.close
    assert [r.target for r in wire.requests] == ["/a", "/b"]


def test_leaving_the_with_block_closes_a_session_it_made():
    with RequestsTransport() as transport:
        session = transport.session
        adapter = session.get_adapter("http://127.0.0.1/")
        closed = []
        adapter.close = lambda: closed.append(True)
    assert closed == [True]


def test_a_session_is_an_object_with_a_request_method():
    with pytest.raises(TypeError):
        RequestsTransport(object())


def test_the_repr_shows_nothing_of_the_session_or_its_arguments():
    session = requests.Session()
    session.auth = ("bob", "s3cr3t")
    with session:
        assert repr(RequestsTransport(session, auth=("a", "p4ss"))) == (
            "RequestsTransport()"
        )


# --- what the session holds is used -------------------------------------------


def test_the_headers_of_the_session_are_sent():
    with Wire() as wire, requests.Session() as session:
        session.headers["X-Session"] = "kept"
        send(RequestsTransport(session), wire.url + "/").read()
    assert seen(wire, "X-Session") == ["kept"]


def test_the_auth_of_the_session_is_sent_to_the_server_of_the_first_request():
    with Wire() as wire, requests.Session() as session:
        session.auth = ("bob", "b")
        transport = RequestsTransport(session)
        send(transport, wire.url + "/one").read()
        send(transport, wire.url + "/two").read()
    assert seen(wire, "Authorization") == ["Basic Ym9iOmI="] * 2


def test_the_auth_argument_is_sent_to_the_server_of_the_first_request():
    with Wire() as wire:
        with RequestsTransport(auth=("alice", "a")) as transport:
            send(transport, wire.url + "/").read()
    assert seen(wire, "Authorization") == ["Basic YWxpY2U6YQ=="]


def test_cookies_the_server_sets_come_back_on_the_next_request():
    def script(request):
        return response(headers={"Set-Cookie": "sid=abc123; Path=/"})

    with Wire(script) as wire, requests.Session() as session:
        transport = RequestsTransport(session)
        send(transport, wire.url + "/login").read()
        send(transport, wire.url + "/next").read()
    assert seen(wire, "Cookie") == [None, "sid=abc123"]


def test_an_adapter_mounted_on_the_session_carries_the_request():
    calls = []

    class Recording(requests.adapters.HTTPAdapter):
        def send(self, request, **kwargs):
            calls.append((request.method, request.url, kwargs["stream"]))
            return super().send(request, **kwargs)

    with Wire() as wire, requests.Session() as session:
        session.mount("http://", Recording())
        send(RequestsTransport(session), wire.url + "/x").read()
    assert calls == [("GET", wire.url + "/x", True)]


def test_digest_authentication_of_the_session_answers_the_challenge():
    def script(request):
        if (request.header("Authorization") or "").startswith("Digest "):
            return response(body=b"let in")
        return response(
            401,
            {"WWW-Authenticate": 'Digest realm="r", nonce="abc", qop="auth"'},
            reason="Unauthorized",
        )

    with Wire(script) as wire, requests.Session() as session:
        session.auth = requests.auth.HTTPDigestAuth("bob", "b")
        reply = send(RequestsTransport(session), wire.url + "/private")
        assert (reply.status, reply.read()) == (200, b"let in")
    assert [r.header("Authorization") is not None for r in wire.requests] == [
        False,
        True,
    ]


def test_a_netrc_entry_is_sent_as_basic_authorization(tmp_path):
    home = os.environ["HOME"]
    netrc = os.path.join(home, ".netrc")
    with open(netrc, "w", newline="\n") as handle:
        handle.write("machine 127.0.0.1 login carol password c4rol\n")
    os.chmod(netrc, 0o600)
    try:
        with Wire() as wire, RequestsTransport() as transport:
            send(transport, wire.url + "/").read()
        assert seen(wire, "Authorization") == ["Basic Y2Fyb2w6YzRyb2w="]
    finally:
        os.remove(netrc)


# --- the trust store ---------------------------------------------------------


@pytest.fixture
def tls_wire(tmp_path):
    authority = make_authority(tmp_path, "127.0.0.1")
    with Wire(tls=authority.server_context()) as wire:
        yield authority, wire


def test_a_certificate_the_trust_store_does_not_know_is_an_ssl_error(tls_wire):
    _authority, wire = tls_wire
    with RequestsTransport() as transport:
        with pytest.raises(ssl.SSLError):
            send(transport, wire.url + "/")
    assert wire.requests == []


def test_requests_ca_bundle_names_the_trust_store(tls_wire, monkeypatch):
    authority, wire = tls_wire
    monkeypatch.setenv("REQUESTS_CA_BUNDLE", authority.ca_file)
    with RequestsTransport() as transport:
        assert send(transport, wire.url + "/").read() == b"ok"
    assert len(wire.requests) == 1


def test_the_verify_argument_names_the_trust_store(tls_wire):
    authority, wire = tls_wire
    with RequestsTransport(verify=authority.ca_file) as transport:
        assert send(transport, wire.url + "/").read() == b"ok"


# --- the body of the request --------------------------------------------------


def test_a_file_of_known_length_is_sent_under_its_length_and_not_chunked():
    with Wire() as wire, RequestsTransport() as transport:
        send(
            transport,
            wire.url + "/f",
            method="PUT",
            body=io.BytesIO(b"from a file"),
        ).read()
    (request,) = wire.requests
    assert request.body == b"from a file"
    assert request.header("Content-Length") == "11"
    assert request.header("Transfer-Encoding") is None


def test_a_body_of_unknown_length_is_chunked():
    with Wire() as wire, RequestsTransport() as transport:
        send(
            transport,
            wire.url + "/f",
            method="PUT",
            body=(piece for piece in (b"in ", b"pieces")),
        ).read()
    (request,) = wire.requests
    assert request.body == b"in pieces"
    assert request.header("Transfer-Encoding") == "chunked"
    assert request.header("Content-Length") is None
