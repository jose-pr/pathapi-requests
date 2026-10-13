"""How `uripath` finds this transport: through the entry point this distribution
declares, with nothing imported until it is used."""

from __future__ import annotations

import importlib.metadata as metadata
import json
import os
import subprocess
import sys
import textwrap

import pytest

from http_wire import Wire, response
from uripath import URIPath, transports
from uripath.schemes import HTTPBackend, HTTPTransport, RepoBackend
from uripath_http_requests import RequestsTransport

VARIABLE = "URIPATH_HTTP_TRANSPORT"


def _entry_points():
    try:
        return metadata.entry_points(group="uripath.http_transports")
    except TypeError:  # Python 3.9
        return metadata.entry_points().get("uripath.http_transports", ())


def test_the_distribution_declares_the_requests_transport():
    declared = {entry.name: entry.value for entry in _entry_points()}
    assert declared["requests"] == "uripath_http_requests:RequestsTransport"


def test_uripath_lists_the_transport_and_loads_the_class_by_name():
    assert transports.names() == ("builtin", "requests")
    assert transports.get("requests") is RequestsTransport
    assert transports.get("builtin") is HTTPTransport


def test_the_variable_chooses_this_transport(monkeypatch):
    monkeypatch.setenv(VARIABLE, "requests")
    with HTTPBackend() as backend:
        assert type(backend.transport) is RequestsTransport


def test_a_backend_closes_the_session_of_the_transport_it_built(monkeypatch):
    monkeypatch.setenv(VARIABLE, "requests")
    backend = HTTPBackend()
    closed = []
    backend.transport.session.close = lambda: closed.append(True)
    backend.close()
    backend.close()
    assert closed == [True]


def test_a_path_reads_through_the_transport_the_variable_names(monkeypatch):
    monkeypatch.setenv(VARIABLE, "requests")
    with Wire(lambda request: response(body=b"through requests")) as wire:
        path = URIPath(wire.url + "/a.txt")
        try:
            assert path.read_bytes() == b"through requests"
            assert type(path.backend.transport) is RequestsTransport
        finally:
            path.backend.close()
    assert [r.target for r in wire.requests] == ["/a.txt"]


def test_the_default_without_a_variable_is_still_the_built_in_transport(monkeypatch):
    monkeypatch.delenv(VARIABLE, raising=False)
    with HTTPBackend() as backend:
        assert type(backend.transport) is HTTPTransport


def test_a_repository_backend_built_from_a_session_sends_through_this_transport():
    import requests

    with requests.Session() as session:
        backend = RepoBackend(session=session, verify=True)
        assert type(backend.transport) is RequestsTransport
        assert backend.transport.session is session


def test_a_value_that_is_not_a_transport_names_the_choices(monkeypatch):
    monkeypatch.setenv(VARIABLE, "Requests")
    with pytest.raises(ValueError) as raised:
        HTTPBackend().transport
    assert "expected one of 'builtin', 'requests'" in str(raised.value)


# --- nothing is imported before it is used -----------------------------------


def _child(code):
    env = dict(os.environ)
    env.pop(VARIABLE, None)
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
        import uripath_http_requests
        from uripath import transports
        transports.names()
        print(json.dumps(sorted(m for m in ("requests", "urllib3", "socks") if m in sys.modules)))
        """)
    assert found == []


def test_building_the_transport_imports_requests():
    found = _child("""
        import json, sys
        from uripath import transports
        transports.get("requests")()
        print(json.dumps("requests" in sys.modules))
        """)
    assert found is True


def test_without_the_requests_library_building_the_transport_names_this_distribution():
    found = _child("""
        import json, sys
        sys.modules["requests"] = None
        from uripath import transports
        try:
            transports.get("requests")()
        except ImportError as error:
            print(json.dumps([str(error), error.name]))
        """)
    assert "uripath-http-requests" in found[0]
    assert found[1] == "requests"
