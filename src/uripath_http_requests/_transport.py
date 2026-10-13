"""`requests` as an HTTP transport for `uripath`, for what the built-in one does
not do: a caller's session with its adapters, authentication and cookies,
`~/.netrc`, `REQUESTS_CA_BUNDLE` and SOCKS proxies."""

from __future__ import annotations

import errno as _errno
import http.client as _client
import importlib.util as _importutil
import ssl as _ssl
import threading as _threading
import typing as _ty
import urllib.parse as _urlparse

from uripath.schemes import HTTPResponse
from uripath.transports import prepare_request

_OWN_KEYS = frozenset(
    {"method", "url", "headers", "data", "timeout", "stream", "allow_redirects"}
)

_DEFAULT_PORTS = {"http": 80, "https": 443}


def _import_requests():
    try:
        import requests
    except ImportError as error:
        raise ImportError(
            "requests could not be imported; reinstall uripath-http-requests",
            name="requests",
        ) from error
    return requests


def _origin(url: str) -> "tuple[str, str, int | None]":
    """The scheme, host and port a URL names."""
    parts = _urlparse.urlsplit(url)
    scheme = parts.scheme.lower()
    try:
        port = parts.port
    except ValueError:
        port = -1
    return scheme, (parts.hostname or "").lower(), port or _DEFAULT_PORTS.get(scheme)


def _drop_header(headers: "_ty.Mapping[str, str]", name: str) -> "dict[str, str]":
    key = name.lower()
    return {field: value for field, value in headers.items() if field.lower() != key}


def _merge_headers(*layers: "_ty.Mapping[str, str]") -> "dict[str, str]":
    """The layers laid over one another, a later one winning on a name whatever
    its case."""
    merged: "dict[str, tuple[str, str]]" = {}
    for layer in layers:
        for name, value in layer.items():
            merged[name.lower()] = (name, value)
    return dict(merged.values())


class _OnlyThis:
    """Authentication that adds nothing of its own. `requests` would otherwise
    apply the session's `auth`, an `Authorization` among its default headers or
    `~/.netrc` to a request; those belong to one server, so a request to any
    other carries the `Authorization` it was given or none."""

    def __init__(self, authorization: "str | None"):
        self._authorization = authorization

    def __call__(self, request):
        request.headers.pop("Authorization", None)
        if self._authorization is not None:
            request.headers["Authorization"] = self._authorization
        return request


def _find(error: BaseException, kind: type) -> "BaseException | None":
    """An exception of `kind` among the causes of `error`, however deep the
    client libraries buried it."""
    pending, seen = [error], set()
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        if isinstance(current, kind):
            return current
        pending.extend(
            nxt
            for nxt in (
                getattr(current, "reason", None),
                current.__cause__,
                current.__context__,
                *current.args,
            )
            if isinstance(nxt, BaseException)
        )
    return None


class _Body:
    """The raw (still encoded) body of a `requests` response."""

    def __init__(self, response, expected: "int | None"):
        self._response = response
        self._expected = expected
        self._received = 0

    def read(self, amount: int) -> bytes:
        raw = self._response.raw
        try:
            # urllib3 2 can return what has arrived; 1.x fills the amount.
            chunk = getattr(raw, "read1", raw.read)(amount)
        except Exception as error:
            raise _read_failure(error) from None
        if chunk:
            self._received += len(chunk)
            return chunk
        if self._expected is not None and self._received < self._expected:
            raise OSError(
                _errno.EIO,
                f"the response ended after {self._received} of {self._expected} bytes",
            )
        return b""

    def close(self) -> None:
        self._response.close()


def _read_failure(error: Exception) -> BaseException:
    """A failure while reading a body as the exception a transport raises."""
    name = type(error).__name__
    if name in ("ReadTimeoutError", "TimeoutError") or isinstance(error, TimeoutError):
        return TimeoutError(_errno.ETIMEDOUT, "the request timed out")
    if _find(error, ConnectionError) is not None:
        return ConnectionError("the connection failed while reading the response")
    if isinstance(error, OSError) and type(error).__module__ == "builtins":
        return error
    return OSError(_errno.EIO, f"the response could not be read ({name})")


def _header_pairs(response) -> "list[tuple[str, str]]":
    """The headers of `response`, a name sent twice as two pairs (`requests`
    joins them in its own mapping)."""
    raw = getattr(getattr(response, "raw", None), "headers", None)
    if hasattr(raw, "getlist"):
        return [(name, value) for name in raw for value in raw.getlist(name)]
    return list(response.headers.items())


def _proxy_url(proxy: object) -> str:
    """The URL `requests` is given for a proxy: a URL, or an object with a
    `url` (and optionally a `username` and `password` for a URL that has none)."""
    url = proxy if isinstance(proxy, str) else getattr(proxy, "url", None)
    if not isinstance(url, str) or not url.strip():
        raise ValueError("a proxy is a URL or an object with a url")
    url = url.strip()
    if "://" not in url:
        url = "http://" + url
    user = getattr(proxy, "username", None) if not isinstance(proxy, str) else None
    if user:
        parts = _urlparse.urlsplit(url)
        if "@" not in parts.netloc:
            password = getattr(proxy, "password", None) or ""
            userinfo = (
                _urlparse.quote(str(user), safe="")
                + ":"
                + _urlparse.quote(str(password), safe="")
            )
            url = _urlparse.urlunsplit(
                parts._replace(netloc=f"{userinfo}@{parts.netloc}")
            )
    return url


def _lookup(provider: _ty.Any, url: str, keys: "tuple[str, ...]") -> object:
    """`provider[url]`; for a plain `dict`, the keys `requests` uses for its
    `proxies` too, so a mapping written for it is not silently ignored.
    `KeyError` means the provider has no opinion about this URL."""
    try:
        return provider[url]
    except KeyError:
        if not isinstance(provider, dict):
            raise
    for key in keys:
        if key in provider:
            return provider[key]
    raise KeyError(url)


def _first_answer(found: _ty.Any) -> "str | None":
    """The proxy URL of the first answer of a provider, `None` for direct. An
    iterable of proxies is a chain that `requests` cannot walk: only its first
    element is used, and an empty one is direct."""
    if found is None:
        return None
    if isinstance(found, str) or hasattr(found, "url"):
        return _proxy_url(found)
    try:
        items = iter(found)
    except TypeError:
        raise ValueError("a proxy is a URL or an object with a url") from None
    first = next(items, None)
    return None if first is None else _proxy_url(first)


class RequestsTransport:
    """Sends requests with a `requests.Session`.

    `session` is the session to use (the caller's: `close()` leaves it open),
    or `None` for a new one that `close()` closes. `proxies` is a provider
    indexed with the request URL, as the built-in transport takes one: the
    answer is a proxy (a URL, or an object with a `url`), an iterable of them
    of which only the first is used, or `None` for no proxy; `KeyError` means
    no opinion, and then `requests` decides from the session and the
    environment, as it does when `proxies` is `None`. A plain `dict` may use
    the keys `requests` does. `requests_args` (`verify`, `cert`, `auth`, ...)
    are passed to every `session.request()`.

    The transport sends one request and follows no redirect. What the session
    holds for authentication (`auth`, an `Authorization` among its headers,
    `~/.netrc`) is used for the server of the first request only; a request to
    any other server carries just the `Authorization` it was given.

    Failures are `TimeoutError`, `ConnectionError`, `ssl.SSLError`, or
    `OSError(EIO)`; the text of a `requests` exception, which can quote a proxy
    URL with credentials, is never passed on."""

    def __init__(
        self, session: "_ty.Any" = None, *, proxies: "_ty.Any" = None, **requests_args
    ):
        self._requests = _import_requests()
        if session is not None and not callable(getattr(session, "request", None)):
            raise TypeError("a session is an object with a request() method")
        self._owns_session = session is None
        self.session = session if session is not None else self._requests.Session()
        self._provider = proxies
        self._args = requests_args
        self._pinned: "tuple | None" = None
        self._lock = _threading.Lock()

    def __repr__(self) -> str:
        return "RequestsTransport()"

    def __enter__(self) -> "RequestsTransport":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def close(self) -> None:
        """Closes the session if this transport made it. Harmless when called
        again."""
        if self._owns_session:
            self.session.close()

    def _failure(self, error) -> BaseException:
        exceptions = self._requests.exceptions
        if isinstance(error, exceptions.Timeout):
            return TimeoutError(_errno.ETIMEDOUT, "the request timed out")
        if isinstance(error, exceptions.SSLError):
            found = _find(error, _ssl.SSLError)
            return found if found is not None else _ssl.SSLError("TLS error")
        if isinstance(error, exceptions.ConnectionError):
            malformed = _find(error, _client.HTTPException)
            if malformed is not None and not isinstance(
                malformed, _client.RemoteDisconnected
            ):
                return OSError(
                    _errno.EIO,
                    f"the response is not valid HTTP ({type(malformed).__name__})",
                )
            return ConnectionError(f"connection failed ({type(error).__name__})")
        if isinstance(
            error,
            (
                exceptions.InvalidURL,
                exceptions.InvalidSchema,
                exceptions.MissingSchema,
                exceptions.InvalidHeader,
                exceptions.InvalidProxyURL,
            ),
        ):
            return ValueError(f"the request is not valid ({type(error).__name__})")
        return OSError(_errno.EIO, f"request failed ({type(error).__name__})")

    def _proxies_for(self, url: str) -> "dict[str, str | None] | None":
        """The `proxies=` of one request: `None` when `requests` is left to
        decide, else every key it reads for this URL, so that the answer wins
        over the session's own and the environment's."""
        if self._provider is None:
            return None
        parts = _urlparse.urlsplit(url)
        scheme, host = parts.scheme.lower(), parts.hostname or ""
        keys = (f"{scheme}://{host}", scheme, f"all://{host}", "all")
        try:
            found = _lookup(self._provider, url, keys)
        except KeyError:
            return None
        proxy = _first_answer(found)
        if proxy is None:
            return dict.fromkeys(keys)
        proxy_scheme = _urlparse.urlsplit(proxy).scheme.lower()
        if proxy_scheme.startswith("socks") and _importutil.find_spec("socks") is None:
            raise OSError(
                _errno.EPROTONOSUPPORT,
                f"a {proxy_scheme!r} proxy needs PySocks: "
                'pip install "uripath-http-requests[socks]"',
            )
        return {keys[0]: proxy}

    def send(
        self,
        method: str,
        url: str,
        *,
        headers: "_ty.Mapping[str, str]",
        body: "bytes | _ty.BinaryIO | _ty.Iterable[bytes] | None" = None,
        timeout: "float | tuple | None",
        stream: bool = False,
    ) -> HTTPResponse:
        """One request, one response, as `HTTPTransport.send()`; `requests`'
        own trust store and authentication apply."""
        request = prepare_request(
            method, url, headers=headers, body=body, timeout=timeout
        )
        sent = request.headers
        args = {k: v for k, v in self._args.items() if k not in _OWN_KEYS}
        ambient = self._args.get("headers")
        with self._lock:
            if self._pinned is None:
                self._pinned = _origin(request.url)
            home = self._pinned == _origin(request.url)
        if ambient:
            sent = _merge_headers(
                ambient if home else _drop_header(ambient, "Authorization"), sent
            )
        explicit = next(
            (v for k, v in sent.items() if k.lower() == "authorization"), None
        )
        if not home:
            args["auth"] = _OnlyThis(explicit)
        elif (
            explicit is not None
            and args.get("auth") is None
            and not getattr(self.session, "auth", None)
        ):
            args["auth"] = _OnlyThis(explicit)
        proxies = self._proxies_for(request.url)
        if proxies is not None:
            args["proxies"] = proxies
        try:
            response = self.session.request(
                method=request.method,
                url=request.url,
                headers=sent,
                data=request.body,
                timeout=request.timeout,
                stream=True,
                allow_redirects=False,
                **args,
            )
        except self._requests.exceptions.RequestException as error:
            raise self._failure(error) from None
        except ValueError as error:
            # The URL and the headers were checked before this call, so this
            # is `requests` reading what the server said: a `Location` it
            # cannot parse, when it looks ahead to the redirect.
            raise OSError(
                _errno.EIO, f"the reply could not be read ({type(error).__name__})"
            ) from None
        status = response.status_code
        if status < 200:
            # An interim reply taken as the final one (urllib3 skips only
            # `100`); the real reply is still to come on that connection.
            response.close()
            raise OSError(
                _errno.EIO,
                f"the server's reply was an interim one (HTTP {status}), "
                "not a final one",
            )
        length = response.headers.get("Content-Length", "")
        if request.method == "HEAD" or status in (204, 304):
            expected = 0
        elif "chunked" in response.headers.get("Transfer-Encoding", "").lower():
            expected = None
        else:
            expected = int(length) if length.isascii() and length.isdigit() else None
        result = HTTPResponse(
            response.status_code,
            response.reason,
            _header_pairs(response),
            getattr(response, "url", None) or request.url,
            _Body(response, expected),
            decode=request.decode,
        )
        return result if stream else result.buffered()
