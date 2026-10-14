"""Writes through a `requests.Session`: what the server receives for a request
that `HTTPClient` sends with `RequestsTransport`."""

from __future__ import annotations

import io

import pytest
import requests

from pathapi.http import HTTPClient, raise_for_status, translate_errors
from pathapi_requests import RequestsTransport
from transport_wire import Wire, response

TIMEOUT = (5, 5)


def stored(request):
    return response(201, reason="Created") if request.method == "PUT" else response()


def client_for(session):
    return HTTPClient(RequestsTransport(session), timeout=TIMEOUT)


def test_a_write_is_one_put_under_its_length():
    with Wire(stored) as wire, requests.Session() as session:
        reply = client_for(session).request(
            "PUT", wire.url + "/up/f.bin", data=b"payload"
        )
        assert reply.status == 201
    (request,) = wire.requests
    assert (request.method, request.target) == ("PUT", "/up/f.bin")
    assert request.body == b"payload"
    assert request.header("Content-Length") == "7"
    assert request.header("Transfer-Encoding") is None


def test_the_method_of_the_request_is_the_one_sent():
    with Wire(stored) as wire, requests.Session() as session:
        client_for(session).request("POST", wire.url + "/up/f.bin", data=b"x").read()
    assert [r.method for r in wire.requests] == ["POST"]


def test_a_file_object_is_uploaded_whole_and_unchunked():
    with Wire(stored) as wire, requests.Session() as session:
        reply = client_for(session).request(
            "PUT", wire.url + "/up/f.bin", data=io.BytesIO(b"from a file")
        )
        assert reply.status == 201
    (request,) = wire.requests
    assert request.body == b"from a file"
    assert request.header("Content-Length") == "11"
    assert request.header("Transfer-Encoding") is None


def test_an_iterable_of_unknown_length_is_uploaded_chunked():
    with Wire(stored) as wire, requests.Session() as session:
        client_for(session).request(
            "PUT", wire.url + "/up/f.bin", data=(p for p in (b"in ", b"pieces"))
        ).read()
    (request,) = wire.requests
    assert request.body == b"in pieces"
    assert request.header("Transfer-Encoding") == "chunked"
    assert request.header("Content-Length") is None


def test_a_rejected_write_raises_and_the_session_is_still_usable():
    def script(request):
        return response(403, reason="Forbidden")

    with Wire(script) as wire, requests.Session() as session:
        client = client_for(session)
        with pytest.raises(PermissionError):
            with translate_errors("/up/f.bin"):
                raise_for_status(
                    client.request("PUT", wire.url + "/up/f.bin", data=b"x")
                )
        assert session.get(wire.url + "/again", timeout=5).status_code == 403
    assert [r.method for r in wire.requests] == ["PUT", "GET"]
