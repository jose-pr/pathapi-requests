"""The proxies a request goes through: a provider indexed with the URL, as the
built-in transport takes one, or what `requests` reads from its session and
the environment. Loopback servers stand in for the proxies."""

from __future__ import annotations

import errno
import select
import socket
import threading
import types

import pytest
import requests

from http_wire import Proxy, Wire, refusing_port, response
from uripath_http_requests import RequestsTransport, _transport

TIMEOUT = (5, 5)
_POLL = 0.05


def send(transport, url, method="GET", headers=None, **kwargs):
    kwargs.setdefault("timeout", TIMEOUT)
    return transport.send(method, url, headers=headers or {}, **kwargs)


class Provider:
    """A proxy provider: `provider[url]` answers `answer` (or raises it)."""

    def __init__(self, answer):
        self.answer = answer
        self.asked = []

    def __getitem__(self, url):
        self.asked.append(url)
        if isinstance(self.answer, BaseException):
            raise self.answer
        return self.answer


class Resolved:
    """A resolved proxy, as a proxy-map library hands one out: a `url` and
    optionally credentials."""

    def __init__(self, url, username=None, password=None):
        self.url = url
        self.username = username
        self.password = password


class Socks5:
    """A SOCKS5 proxy on a loopback port with no authentication. Every
    `CONNECT` is relayed to `upstream`, whatever name it asked for, and
    `asked` lists the `(host, port)` of each."""

    def __init__(self, upstream):
        self.upstream = upstream
        self.asked = []
        self._stop = threading.Event()
        self._sockets = []
        self._lock = threading.Lock()
        self._listener = socket.create_server(("127.0.0.1", 0))
        self._listener.setblocking(False)
        self.port = self._listener.getsockname()[1]
        self._threads = [threading.Thread(target=self._accept, daemon=True)]
        self._threads[0].start()

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self._stop.set()
        for thread in self._threads:
            thread.join(timeout=10)
        with self._lock:
            sockets, self._sockets = list(self._sockets), []
        for sock in sockets:
            sock.close()
        self._listener.close()

    def _track(self, sock):
        with self._lock:
            self._sockets.append(sock)
        return sock

    def _accept(self):
        while not self._stop.is_set():
            if not select.select([self._listener], [], [], _POLL)[0]:
                continue
            try:
                sock, _ = self._listener.accept()
            except OSError:
                continue
            sock.setblocking(True)
            thread = threading.Thread(
                target=self._serve, args=(self._track(sock),), daemon=True
            )
            self._threads.append(thread)
            thread.start()

    @staticmethod
    def _read(sock, count):
        data = b""
        while len(data) < count:
            chunk = sock.recv(count - len(data))
            if not chunk:
                raise OSError("closed")
            data += chunk
        return data

    def _serve(self, client):
        try:
            _version, count = self._read(client, 2)
            self._read(client, count)
            client.sendall(b"\x05\x00")
            _version, _command, _reserved, kind = self._read(client, 4)
            if kind == 3:
                (size,) = self._read(client, 1)
                host = self._read(client, size).decode("ascii")
            elif kind == 1:
                host = socket.inet_ntoa(self._read(client, 4))
            else:
                host = socket.inet_ntop(socket.AF_INET6, self._read(client, 16))
            port = int.from_bytes(self._read(client, 2), "big")
            self.asked.append((host, port))
            upstream = self._track(socket.create_connection(self.upstream, timeout=10))
            client.sendall(b"\x05\x00\x00\x01" + b"\x00" * 6)
            self._relay(client, upstream)
        except OSError:
            pass

    def _relay(self, a, b):
        pair = {a: b, b: a}
        while not self._stop.is_set():
            ready, _, _ = select.select(list(pair), [], [], _POLL)
            for sock in ready:
                data = sock.recv(65536)
                if not data:
                    return
                pair[sock].sendall(data)


# --- the provider ----------------------------------------------------------------


def test_the_provider_is_asked_with_the_url_and_its_answer_is_the_proxy():
    with Wire() as origin, Proxy(upstream=None) as proxy:
        provider = Provider(proxy.url)
        with RequestsTransport(proxies=provider) as transport:
            reply = send(transport, "http://backend.test/f?x=1")
            assert reply.read() == b"via proxy"
    assert provider.asked == ["http://backend.test/f?x=1"]
    assert [r.target for r in proxy.requests] == ["http://backend.test/f?x=1"]
    assert origin.requests == []


def test_a_proxy_is_an_object_with_a_url():
    with Proxy() as proxy:
        with RequestsTransport(proxies=Provider(Resolved(proxy.url))) as transport:
            assert send(transport, "http://backend.test/f").read() == b"via proxy"
    assert len(proxy.requests) == 1


def test_the_credentials_of_a_resolved_proxy_reach_the_proxy_and_only_the_proxy():
    with Wire() as origin, Proxy() as proxy:
        resolved = Resolved(proxy.url, "us@er", "p:w")
        with RequestsTransport(proxies=Provider(resolved)) as transport:
            send(transport, "http://backend.test/f").read()
    assert proxy.requests[0].header("Proxy-Authorization") == ("Basic dXNAZXI6cDp3")
    assert proxy.requests[0].header("Authorization") is None
    assert origin.requests == []


def test_the_credentials_in_the_url_of_a_proxy_are_sent_to_the_proxy():
    with Proxy() as proxy:
        url = proxy.url.replace("http://", "http://alice:s3cret@")
        with RequestsTransport(proxies=Provider(url)) as transport:
            send(transport, "http://backend.test/f").read()
    assert proxy.requests[0].header("Proxy-Authorization") == "Basic YWxpY2U6czNjcmV0"


def test_only_the_first_proxy_of_a_chain_is_used():
    with Proxy() as second, Proxy() as first:
        chain = Provider([first.url, second.url])
        with RequestsTransport(proxies=chain) as transport:
            send(transport, "http://backend.test/f").read()
    assert len(first.requests) == 1
    assert second.requests == []


def test_a_chain_whose_first_proxy_cannot_be_reached_is_not_walked():
    with Proxy() as second:
        chain = Provider([f"http://127.0.0.1:{refusing_port()}", second.url])
        with RequestsTransport(proxies=chain) as transport:
            with pytest.raises(ConnectionError):
                send(transport, "http://backend.test/f")
    assert second.requests == []


def test_none_in_a_chain_is_a_direct_request():
    with Wire() as origin, Proxy() as proxy:
        with RequestsTransport(proxies=Provider([None, proxy.url])) as transport:
            send(transport, origin.url + "/direct").read()
    assert [r.target for r in origin.requests] == ["/direct"]
    assert proxy.requests == []


def test_an_empty_chain_is_a_direct_request():
    with Wire() as origin:
        with RequestsTransport(proxies=Provider([])) as transport:
            send(transport, origin.url + "/direct").read()
    assert len(origin.requests) == 1


def test_none_is_direct_whatever_the_environment_and_the_session_say(monkeypatch):
    with Wire() as origin, Proxy() as from_environment, Proxy() as from_session:
        monkeypatch.setenv("HTTP_PROXY", from_environment.url)
        monkeypatch.delenv("NO_PROXY", raising=False)
        monkeypatch.delenv("no_proxy", raising=False)
        with requests.Session() as session:
            session.proxies = {"http": from_session.url, "all": from_session.url}
            transport = RequestsTransport(session, proxies=Provider(None))
            assert send(transport, origin.url + "/direct").read() == b"ok"
    assert len(origin.requests) == 1
    assert from_environment.requests == [] and from_session.requests == []


def test_no_opinion_leaves_the_environment_to_decide(monkeypatch):
    with Proxy() as from_environment:
        monkeypatch.setenv("HTTP_PROXY", from_environment.url)
        monkeypatch.delenv("NO_PROXY", raising=False)
        monkeypatch.delenv("no_proxy", raising=False)
        provider = Provider(KeyError("backend"))
        with RequestsTransport(proxies=provider) as transport:
            assert send(transport, "http://backend.test/f").read() == b"via proxy"
    assert len(provider.asked) == 1
    assert len(from_environment.requests) == 1


def test_without_a_provider_requests_reads_the_environment(monkeypatch):
    with Proxy() as from_environment:
        monkeypatch.setenv("HTTP_PROXY", from_environment.url)
        monkeypatch.delenv("NO_PROXY", raising=False)
        monkeypatch.delenv("no_proxy", raising=False)
        with RequestsTransport() as transport:
            assert send(transport, "http://backend.test/f").read() == b"via proxy"
    assert len(from_environment.requests) == 1


def test_the_answer_of_the_provider_wins_over_the_proxies_of_the_session(monkeypatch):
    with Proxy() as chosen, Proxy() as of_session:
        with requests.Session() as session:
            session.proxies = {"http": of_session.url}
            transport = RequestsTransport(session, proxies=Provider(chosen.url))
            send(transport, "http://backend.test/f").read()
    assert len(chosen.requests) == 1
    assert of_session.requests == []


def test_a_plain_dict_may_use_the_keys_requests_uses():
    with Proxy() as proxy:
        with RequestsTransport(proxies={"http": proxy.url}) as transport:
            send(transport, "http://backend.test/f").read()
    assert len(proxy.requests) == 1


def test_an_exception_of_the_provider_other_than_key_error_reaches_the_caller():
    boom = RuntimeError("the provider failed")
    with RequestsTransport(proxies=Provider(boom)) as transport:
        with pytest.raises(RuntimeError) as raised:
            send(transport, "http://127.0.0.1:9/f")
    assert raised.value is boom


@pytest.mark.parametrize(
    "answer", [3, object(), [3], [""], "   ", {"http": "http://127.0.0.1:9"}]
)
def test_an_answer_that_is_not_a_proxy_is_refused_before_anything_is_sent(answer):
    with Wire() as origin, RequestsTransport(proxies=Provider(answer)) as transport:
        with pytest.raises(ValueError):
            send(transport, origin.url + "/f")
    assert origin.requests == []


# --- SOCKS ---------------------------------------------------------------------------


def test_a_socks5_proxy_carries_the_request_and_is_given_the_name_unresolved():
    with Wire() as origin, Socks5(("127.0.0.1", origin.port)) as socks:
        provider = Provider(f"socks5h://127.0.0.1:{socks.port}")
        with RequestsTransport(proxies=provider) as transport:
            reply = send(transport, f"http://backend.test:{origin.port}/via/socks")
            assert reply.read() == b"ok"
    assert socks.asked == [("backend.test", origin.port)]
    (request,) = origin.requests
    assert request.target == "/via/socks"
    assert request.header("Host") == f"backend.test:{origin.port}"


def test_the_proxies_argument_of_the_session_can_name_a_socks_proxy():
    with Wire() as origin, Socks5(("127.0.0.1", origin.port)) as socks:
        with requests.Session() as session:
            session.proxies = {"http": f"socks5h://127.0.0.1:{socks.port}"}
            transport = RequestsTransport(session)
            send(transport, f"http://backend.test:{origin.port}/").read()
    assert socks.asked == [("backend.test", origin.port)]


def test_a_socks_proxy_without_pysocks_names_the_extra(monkeypatch):
    monkeypatch.setattr(
        _transport, "_importutil", types.SimpleNamespace(find_spec=lambda name: None)
    )
    with Wire() as origin:
        provider = Provider("socks5h://127.0.0.1:9")
        with RequestsTransport(proxies=provider) as transport:
            with pytest.raises(OSError) as raised:
                send(transport, origin.url + "/f")
    assert raised.value.errno == errno.EPROTONOSUPPORT
    assert "uripath-http-requests[socks]" in str(raised.value)
    assert "socks5h" in str(raised.value)
    assert origin.requests == []


def test_a_script_that_answers_the_proxy_is_not_needed_for_a_direct_request():
    with Wire(lambda request: response(body=b"direct")) as origin:
        with RequestsTransport(proxies=Provider(None)) as transport:
            assert send(transport, origin.url + "/").read() == b"direct"
