"""Writes through a `requests.Session`: what the server receives for a path
opened with `with_session()`."""

from __future__ import annotations

import io

import pytest
import requests

from http_wire import Wire, response
from uripath.schemes import HTTPURIPath

TIMEOUT = (5, 5)


def stored(request):
    return response(201, reason="Created") if request.method == "PUT" else response()


def test_a_write_is_one_put_under_its_length():
    with Wire(stored) as wire, requests.Session() as session:
        path = HTTPURIPath(wire.url + "/up/f.bin").with_session(
            session, timeout=TIMEOUT
        )
        path.write_bytes(b"payload")
    (request,) = wire.requests
    assert (request.method, request.target) == ("PUT", "/up/f.bin")
    assert request.body == b"payload"
    assert request.header("Content-Length") == "7"
    assert request.header("Transfer-Encoding") is None


def test_the_write_method_of_the_path_is_the_one_sent():
    with Wire(stored) as wire, requests.Session() as session:
        path = HTTPURIPath(wire.url + "/up/f.bin").with_session(
            session, write_method="POST", timeout=TIMEOUT
        )
        path.write_bytes(b"x")
    assert [r.method for r in wire.requests] == ["POST"]


def test_a_with_block_that_raised_uploads_nothing():
    with Wire(stored) as wire, requests.Session() as session:
        path = HTTPURIPath(wire.url + "/up/f.bin").with_session(
            session, timeout=TIMEOUT
        )
        with pytest.raises(RuntimeError):
            with path.open("wb") as handle:
                handle.write(b"half")
                raise RuntimeError("stop")
    assert wire.requests == []


def test_a_file_object_is_uploaded_whole_and_unchunked():
    with Wire(stored) as wire, requests.Session() as session:
        path = HTTPURIPath(wire.url + "/up/f.bin").with_session(
            session, timeout=TIMEOUT
        )
        response_ = path.backend.request(
            "PUT", path, data=io.BytesIO(b"from a file"), stream=False
        )
        assert response_.status == 201
    (request,) = wire.requests
    assert request.body == b"from a file"
    assert request.header("Content-Length") == "11"


def test_a_rejected_write_raises_and_the_session_is_still_usable():
    def script(request):
        return response(403, reason="Forbidden")

    with Wire(script) as wire, requests.Session() as session:
        path = HTTPURIPath(wire.url + "/up/f.bin").with_session(
            session, timeout=TIMEOUT
        )
        with pytest.raises(PermissionError):
            path.write_bytes(b"x")
        assert session.get(wire.url + "/again", timeout=5).status_code == 403
    assert [r.method for r in wire.requests] == ["PUT", "GET"]
