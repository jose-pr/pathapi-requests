"""How `pathlib_next.http` finds this transport: through the entry point this
distribution declares, with nothing imported until it is used."""

from __future__ import annotations

import importlib.metadata as metadata
import json
import os
import subprocess
import sys
import textwrap

import pytest

from pathlib_next.http import (
    TRANSPORT_ENV,
    TRANSPORT_GROUP,
    HTTPClient,
    HTTPTransport,
    default_transport,
    get_transport,
    transport_names,
)
from pathlib_next_requests import RequestsTransport
from transport_wire import Wire, response


def _entry_points():
    try:
        return metadata.entry_points(group=TRANSPORT_GROUP)
    except TypeError:  # Python 3.9
        return metadata.entry_points().get(TRANSPORT_GROUP, ())


def test_the_distribution_declares_the_requests_transport():
    declared = {entry.name: entry.value for entry in _entry_points()}
    assert TRANSPORT_GROUP == "pathlib_next.http_transports"
    assert declared["requests"] == "pathlib_next_requests:RequestsTransport"


def test_pathlib_next_lists_the_transport_and_loads_the_class_by_name():
    assert transport_names() == ("builtin", "requests")
    assert get_transport("requests") is RequestsTransport
    assert get_transport("builtin") is HTTPTransport


def test_the_variable_chooses_this_transport(monkeypatch):
    monkeypatch.setenv(TRANSPORT_ENV, "requests")
    assert TRANSPORT_ENV == "PATHLIB_NEXT_HTTP_TRANSPORT"
    with default_transport() as transport:
        assert type(transport) is RequestsTransport
    with HTTPClient() as client:
        assert type(client.transport) is RequestsTransport


def test_a_client_closes_the_session_of_the_transport_it_built(monkeypatch):
    monkeypatch.setenv(TRANSPORT_ENV, "requests")
    client = HTTPClient()
    closed = []
    client.transport.session.close = lambda: closed.append(True)
    client.close()
    client.close()
    assert closed == [True]


def test_a_client_reads_through_the_transport_the_variable_names(monkeypatch):
    monkeypatch.setenv(TRANSPORT_ENV, "requests")
    with Wire(lambda request: response(body=b"through requests")) as wire:
        with HTTPClient() as client:
            reply = client.request("GET", wire.url + "/a.txt")
            assert reply.read() == b"through requests"
            assert type(client.transport) is RequestsTransport
    assert [r.target for r in wire.requests] == ["/a.txt"]


def test_the_default_without_a_variable_is_still_the_built_in_transport(monkeypatch):
    monkeypatch.delenv(TRANSPORT_ENV, raising=False)
    with default_transport() as transport:
        assert type(transport) is HTTPTransport


def test_the_name_of_a_transport_is_case_sensitive(monkeypatch):
    monkeypatch.setenv(TRANSPORT_ENV, "Requests")
    with pytest.raises(ValueError) as raised:
        default_transport()
    assert "expected one of 'builtin', 'requests'" in str(raised.value)


def test_a_client_given_a_transport_leaves_it_open():
    with Wire() as wire, RequestsTransport() as transport:
        closed = []
        original = transport.session.close
        transport.session.close = lambda: (closed.append(True), original())
        with HTTPClient(transport) as client:
            assert client.request("GET", wire.url + "/").read() == b"ok"
        assert closed == []
        assert client.transport is transport


# --- nothing is imported before it is used -----------------------------------


def _child(code):
    env = dict(os.environ)
    env.pop(TRANSPORT_ENV, None)
    result = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(code)],
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_importing_the_package_or_listing_the_transports_imports_no_client_library():
    found = _child("""
        import json, sys
        import pathlib_next_requests
        from pathlib_next.http import transport_names
        transport_names()
        print(json.dumps(sorted(m for m in ("requests", "urllib3", "socks") if m in sys.modules)))
        """)
    assert found == []


def test_building_the_transport_imports_requests():
    found = _child("""
        import json, sys
        from pathlib_next.http import get_transport
        get_transport("requests")()
        print(json.dumps("requests" in sys.modules))
        """)
    assert found is True


def test_without_the_requests_library_building_the_transport_names_this_distribution():
    found = _child("""
        import json, sys
        sys.modules["requests"] = None
        from pathlib_next.http import get_transport
        try:
            get_transport("requests")()
        except ImportError as error:
            print(json.dumps([str(error), error.name]))
        """)
    assert "pathlib-next-requests" in found[0]
    assert found[1] == "requests"
