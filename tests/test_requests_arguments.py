"""`with_session()` and `RepoBackend(session=...)` hand the arguments of
`requests` to this transport and keep the backend's own apart."""

from __future__ import annotations

import pytest
import requests

from http_wire import Wire, response
from uripath import URIPath
from uripath.schemes import HTTPURIPath, RepoBackend
from uripath_http_requests import RequestsTransport

TIMEOUT = (5, 5)


def test_with_session_sends_through_the_session_it_was_given():
    calls = []

    class Recording(requests.adapters.HTTPAdapter):
        def send(self, request, **kwargs):
            calls.append((request.method, request.url))
            return super().send(request, **kwargs)

    with Wire() as wire, requests.Session() as session:
        session.mount("http://", Recording())
        path = HTTPURIPath(wire.url + "/f.txt").with_session(session, timeout=TIMEOUT)
        assert path.read_bytes() == b"ok"
        assert type(path.backend.transport) is RequestsTransport
        assert path.backend.transport.session is session
    assert calls == [("GET", wire.url + "/f.txt")]


def test_the_session_is_still_open_after_the_path_is_done_with_it():
    with Wire() as wire, requests.Session() as session:
        path = HTTPURIPath(wire.url + "/f.txt").with_session(session, timeout=TIMEOUT)
        path.read_bytes()
        path.backend.close()
        assert session.get(wire.url + "/after", timeout=5).content == b"ok"


def test_with_session_without_a_session_makes_one_that_the_transport_closes():
    with Wire() as wire:
        path = HTTPURIPath(wire.url + "/f.txt").with_session(None, timeout=TIMEOUT)
        transport = path.backend.transport
        try:
            assert path.read_bytes() == b"ok"
        finally:
            transport.close()
    assert len(wire.requests) == 1


def test_the_arguments_of_requests_and_the_arguments_of_the_backend_do_not_collide():
    with Wire() as wire, requests.Session() as session:
        path = HTTPURIPath(wire.url + "/redirect.txt").with_session(
            session,
            allow_redirects=True,
            stream=False,
            headers={"X-Token": "t"},
            timeout=TIMEOUT,
            write_method="POST",
            append_mode="patch",
        )
        assert path.read_bytes() == b"ok"
        assert path.backend.write_method == "POST"
        assert path.backend.append_mode == "patch"
        assert path.backend.timeout == TIMEOUT
    assert [r.header("X-Token") for r in wire.requests] == ["t"]


def test_headers_of_with_session_go_with_every_request():
    with Wire() as wire, requests.Session() as session:
        session.headers["X-Session"] = "s"
        path = HTTPURIPath(wire.url + "/f").with_session(
            session, headers={"X-Backend": "b"}, timeout=TIMEOUT
        )
        path.read_bytes()
    assert wire.requests[0].header("X-Session") == "s"
    assert wire.requests[0].header("X-Backend") == "b"


@pytest.mark.parametrize("scheme", ["http", "dav"])
def test_allow_redirects_among_the_arguments_does_not_make_a_write_follow(scheme):
    def script(request):
        if request.method == "PUT":
            return response(302, {"Location": "/elsewhere"}, reason="Found")
        return response(404, reason="Not Found")

    with Wire(script) as wire, requests.Session() as session:
        url = f"{scheme}{wire.url[len('http'):]}/f.bin"
        path = URIPath(url).with_session(session, timeout=TIMEOUT, allow_redirects=True)
        with pytest.raises(OSError):
            path.write_bytes(b"NEW")
    assert [r.method for r in wire.requests] == ["PUT"]


def test_explicit_session_auth_wins_over_the_userinfo_of_the_url():
    with Wire() as wire, requests.Session() as session:
        host = wire.url[len("http://") :]
        path = HTTPURIPath(f"http://alice:s3cr3t@{host}/ok").with_session(
            session, auth=("bob", "b"), timeout=TIMEOUT
        )
        path.read_bytes()
    assert wire.requests[0].header("Authorization") == "Basic Ym9iOmI="
    assert "alice" not in wire.requests[0].target


def test_the_userinfo_of_the_url_is_sent_as_authorization_when_the_session_has_none():
    with Wire() as wire, requests.Session() as session:
        host = wire.url[len("http://") :]
        path = HTTPURIPath(f"http://alice:s3cr3t@{host}/ok").with_session(
            session, timeout=TIMEOUT
        )
        path.read_bytes()
    assert wire.requests[0].header("Authorization") == "Basic YWxpY2U6czNjcjN0"


def test_a_repository_backend_given_a_session_and_arguments_builds_this_transport():
    with requests.Session() as session:
        backend = RepoBackend(session=session, verify=False, cert=None)
        transport = backend.transport
        assert type(transport) is RequestsTransport
        assert transport.session is session


def test_a_repository_backend_given_arguments_only_makes_its_own_session():
    backend = RepoBackend(verify=False)
    transport = backend.transport
    try:
        assert type(transport) is RequestsTransport
        assert transport._owns_session
    finally:
        transport.close()


def test_a_session_and_a_transport_together_are_refused():
    with RequestsTransport() as transport, requests.Session() as session:
        with pytest.raises(TypeError):
            RepoBackend(transport=transport, session=session)
