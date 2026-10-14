"""The boundary of the transport with `requests`: what the server received when
a session holds credentials, which exception comes out for each failure of the
library, and that nothing a `requests` exception says reaches the caller."""

from __future__ import annotations

import errno
import ssl
import traceback

import pytest
import requests

from pathapi.http import HTTPClient
from pathapi_requests import RequestsTransport
from transport_wire import Wire, refusing_port, response

TIMEOUT = (5, 5)
QUOTED = "http://proxyuser:pr0xyS3cret@proxy.example:3128"


def send(transport, url, method="GET", headers=None, **kwargs):
    kwargs.setdefault("timeout", TIMEOUT)
    return transport.send(method, url, headers=headers or {}, **kwargs)


def formatted(error: BaseException) -> str:
    """Everything a log line or a traceback could show for `error`."""
    return "".join(
        traceback.format_exception(type(error), error, error.__traceback__)
    ) + "\n".join((str(error), repr(error)))


class Failing:
    """A session whose `request()` raises `error`, or answers `reply`."""

    auth = None
    headers = {}

    def __init__(self, error=None, reply=None):
        self.error = error
        self.reply = reply

    def request(self, method, url, **kwargs):
        if self.error is not None:
            raise self.error
        return self.reply

    def close(self):
        pass


# --- each failure of the library is the exception a transport raises -----------


@pytest.mark.parametrize(
    "name, expected",
    [
        ("ConnectionError", ConnectionError),
        ("ProxyError", ConnectionError),
        ("ConnectTimeout", TimeoutError),
        ("ReadTimeout", TimeoutError),
        ("Timeout", TimeoutError),
        ("SSLError", ssl.SSLError),
        ("InvalidURL", ValueError),
        ("InvalidSchema", ValueError),
        ("MissingSchema", ValueError),
        ("InvalidHeader", ValueError),
        ("InvalidProxyURL", ValueError),
        ("TooManyRedirects", OSError),
        ("ChunkedEncodingError", OSError),
        ("ContentDecodingError", OSError),
    ],
)
def test_a_requests_exception_is_a_builtin_one_that_quotes_nothing(name, expected):
    error = getattr(requests.exceptions, name)(f"ProxyError({QUOTED})")
    with RequestsTransport(Failing(error)) as transport:
        with pytest.raises(expected) as raised:
            send(transport, "http://127.0.0.1:9/x")
    text = formatted(raised.value)
    assert "pr0xyS3cret" not in text and "proxyuser" not in text
    assert raised.value.__cause__ is None
    assert raised.value.__suppress_context__
    assert type(raised.value).__module__ in {"builtins", "ssl"}


def test_a_request_that_failed_with_os_error_input_is_an_io_error():
    error = requests.exceptions.RequestException(f"boom {QUOTED}")
    with RequestsTransport(Failing(error)) as transport:
        with pytest.raises(OSError) as raised:
            send(transport, "http://127.0.0.1:9/x")
    assert raised.value.errno == errno.EIO
    assert "pr0xyS3cret" not in formatted(raised.value)


def test_a_malformed_location_is_an_io_error_not_a_value_error():
    with RequestsTransport(Failing(ValueError(f"Invalid URL {QUOTED}"))) as transport:
        with pytest.raises(OSError) as raised:
            send(transport, "http://127.0.0.1:9/x")
    assert raised.value.errno == errno.EIO
    assert not isinstance(raised.value, ValueError)
    assert "pr0xyS3cret" not in formatted(raised.value)


@pytest.mark.parametrize("status", [101, 102, 103])
def test_an_interim_reply_is_never_returned_as_the_final_one(status):
    closed = []

    class Interim:
        status_code = status
        reason = "Interim"
        headers = {}

        def close(self):
            closed.append(True)

    with RequestsTransport(Failing(reply=Interim())) as transport:
        with pytest.raises(OSError) as raised:
            send(transport, "http://127.0.0.1:9/x")
    assert raised.value.errno == errno.EIO
    assert str(status) in str(raised.value)
    assert closed == [True]


def test_a_connection_that_is_refused_is_a_connection_error():
    with RequestsTransport() as transport:
        with pytest.raises(ConnectionError):
            send(transport, f"http://127.0.0.1:{refusing_port()}/x")


def test_the_credentials_of_a_proxy_that_refuses_the_connection_are_not_in_the_error():
    proxy = f"http://pu:pr0xyS3cret@127.0.0.1:{refusing_port()}"
    with RequestsTransport(proxies={"http": proxy}) as transport:
        with pytest.raises(ConnectionError) as raised:
            send(transport, "http://backend.test/x")
    assert "pr0xyS3cret" not in formatted(raised.value)
    assert raised.value.__cause__ is None


# --- credentials belong to one server -----------------------------------------


@pytest.fixture
def two_servers():
    with Wire() as home, Wire() as away:
        yield home, away


def test_the_auth_of_the_session_is_not_sent_to_another_server(two_servers):
    home, away = two_servers
    with requests.Session() as session:
        session.auth = ("bob", "b")
        transport = RequestsTransport(session)
        send(transport, home.url + "/").read()
        send(transport, away.url + "/").read()
        send(transport, home.url + "/again").read()
    assert [r.header("Authorization") for r in home.requests] == ["Basic Ym9iOmI="] * 2
    assert [r.header("Authorization") for r in away.requests] == [None]


def test_an_authorization_among_the_session_headers_stays_with_its_server(two_servers):
    home, away = two_servers
    with requests.Session() as session:
        session.headers["Authorization"] = "Bearer SESSION"
        transport = RequestsTransport(session)
        send(transport, home.url + "/").read()
        send(transport, away.url + "/").read()
    assert home.requests[0].header("Authorization") == "Bearer SESSION"
    assert away.requests[0].header("Authorization") is None


def test_the_auth_argument_and_the_headers_argument_stay_with_their_server(
    two_servers,
):
    home, away = two_servers
    with RequestsTransport(
        auth=("bob", "b"), headers={"Authorization": "Bearer AMBIENT", "X-Own": "1"}
    ) as transport:
        send(transport, home.url + "/").read()
        send(transport, away.url + "/").read()
    assert home.requests[0].header("Authorization") == "Basic Ym9iOmI="
    assert away.requests[0].header("Authorization") is None
    assert away.requests[0].header("X-Own") == "1"


def test_the_first_request_decides_which_server_is_home(two_servers):
    home, away = two_servers
    with requests.Session() as session:
        session.auth = ("bob", "b")
        transport = RequestsTransport(session)
        send(transport, away.url + "/").read()
        send(transport, home.url + "/").read()
    assert away.requests[0].header("Authorization") == "Basic Ym9iOmI="
    assert home.requests[0].header("Authorization") is None


def test_an_authorization_given_for_a_request_is_sent_to_whichever_server_it_names(
    two_servers,
):
    home, away = two_servers
    with requests.Session() as session:
        session.auth = ("bob", "b")
        transport = RequestsTransport(session)
        send(transport, home.url + "/").read()
        send(
            transport, away.url + "/", headers={"Authorization": "Bearer GIVEN"}
        ).read()
    assert away.requests[0].header("Authorization") == "Bearer GIVEN"


def test_the_auth_of_the_session_wins_over_an_authorization_header_at_its_server():
    with Wire() as wire, requests.Session() as session:
        session.auth = ("bob", "b")
        send(
            RequestsTransport(session),
            wire.url + "/",
            headers={"Authorization": "Bearer GIVEN"},
        ).read()
    assert wire.requests[0].header("Authorization") == "Basic Ym9iOmI="


def test_an_authorization_header_is_sent_when_the_session_holds_no_auth():
    with Wire() as wire, requests.Session() as session:
        send(
            RequestsTransport(session),
            wire.url + "/",
            headers={"Authorization": "Bearer GIVEN"},
        ).read()
    assert wire.requests[0].header("Authorization") == "Bearer GIVEN"


def test_the_transport_does_not_follow_a_redirect_whatever_the_arguments_say(
    two_servers,
):
    home, away = two_servers
    home.script = lambda request: response(
        302, {"Location": away.url + "/landing"}, reason="Found"
    )
    with RequestsTransport(allow_redirects=True, auth=("bob", "b")) as transport:
        reply = send(transport, home.url + "/start")
    assert reply.status == 302
    assert away.requests == []


def test_a_client_redirected_to_another_server_does_not_take_the_session_there(
    two_servers,
):
    home, away = two_servers
    home.script = lambda request: response(
        302, {"Location": away.url + "/landing"}, reason="Found"
    )
    with requests.Session() as session:
        session.auth = ("bob", "b")
        client = HTTPClient(RequestsTransport(session), timeout=TIMEOUT)
        assert client.request("GET", home.url + "/start").read() == b"ok"
    assert home.requests[0].header("Authorization") == "Basic Ym9iOmI="
    assert away.requests[0].target == "/landing"
    assert away.requests[0].header("Authorization") is None
