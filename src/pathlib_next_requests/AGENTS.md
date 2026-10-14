# `pathlib_next_requests` — public API header

Header-file-style reference for the `pathlib_next_requests` package: every public
export with its signature, arguments, contract and gotchas, so the package can
be used without reading its source. It ships inside the package and is
self-contained. Development documentation lives with the source at
<https://github.com/jose-pr/pathlib-next-requests>.

Names are imported from `pathlib_next_requests`, which exports one class,
`RequestsTransport`, and `__version__`. A module or name that starts with an
underscore is private and nothing there is contract.

`pip install pathlib-next-requests`. Required dependencies: `pathlib-next>=0.10.0,<0.11`
and `requests>=2.22.0,<3`. The one extra, `socks`, adds `requests[socks]`
(PySocks) for `socks4:`, `socks5:` and `socks5h:` proxies. `requests` is imported
when a transport is built, not when this package is.

`pathlib_next_requests.__version__` is the version of the installed
distribution, read from its metadata. The rendered documentation is at
<https://jose-pr.github.io/pathlib-next-requests/> and the project overview is the
`README.md` shipped next to this file (`pathlib_next_requests/README.md`).

## The `requests` transport (`pathlib_next_requests`)

```python
class RequestsTransport:
    session: requests.Session
    def __init__(self, session=None, *, proxies=None, **requests_args): ...
    def send(
        self, method, url, *, headers, body=None, timeout, stream=False,
    ) -> HTTPResponse: ...
    def close(self) -> None: ...
```

`RequestsTransport` is an HTTP transport for `pathlib_next.http` (the contract is
"HTTP requests" in the `pathlib_next` header): `send()` makes one request with a
`requests.Session` and returns a `pathlib_next.http.HTTPResponse`.
`pathlib_next.http` finds it through the `requests` entry of its
`pathlib_next.http_transports` entry-point group, which this distribution
declares, so installing the distribution is all that is needed:

- `HTTPClient(RequestsTransport(session, **requests_args))` sends every request
  of the client through the session; `session=None` makes a new session that the
  transport closes. The client follows the redirects, and never closes a
  transport it was given.
- `PATHLIB_NEXT_HTTP_TRANSPORT=requests` makes every `HTTPClient` that was given
  no transport build `RequestsTransport()`; so do
  `pathlib_next.http.default_transport()` and
  `pathlib_next.http.get_transport("requests")()`.

Use it for what the built-in transport does not do: a session of your own with
its mounted adapters, `auth` (basic, digest, NTLM, a token) and cookies;
`~/.netrc`; `REQUESTS_CA_BUNDLE` and `CURL_CA_BUNDLE` with the certifi bundle;
and SOCKS proxies.

- **`session`** — the `requests.Session` to send with, an object with a
  `request()` method (`TypeError` otherwise). `None` makes a new one. The
  attribute `session` is the one in use. `close()` closes a session this
  transport made and leaves a caller's open, so a session passed in is still
  usable afterwards. The transport is a context manager that calls `close()`.
  A session the transport made is also closed when the transport is collected,
  and a response that is still open keeps its transport alive.
- **`proxies`** — `None` leaves `requests` to read its session and the
  environment (`HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`, `NO_PROXY`). Otherwise
  an object that is indexed with the request URL (no fragment), as the
  `proxies` of `pathlib_next.http.HTTPTransport` is. The answer is `None` (no
  proxy: direct, whatever the session and the environment say), a proxy, or an
  iterable of them; a proxy is a `str` URL or an object with a `url` attribute
  (and optionally `username` and `password`, used when the URL carries none). `requests`
  uses one proxy per request, so only the first element of an iterable is used,
  and an empty one is direct. `KeyError` means the provider has no opinion about
  the URL, and `requests` decides as it does for `proxies=None`; any other
  exception of the provider reaches the caller. An answer that is not a proxy is
  `ValueError` before anything is sent. A plain `dict` may use the keys
  `requests` does (`"http"`, `"https"`, `"all"`, `"scheme://host"`). The built-in
  transport reads `KeyError` as "direct" and an empty `dict` as "everything
  direct"; here both leave the decision to `requests`.
- **A `socks4:`, `socks5:` or `socks5h:` proxy** needs PySocks (the `socks`
  extra); without it the request raises `OSError(EPROTONOSUPPORT)` naming
  `pathlib-next-requests[socks]`, and nothing is sent. `socks5h:` leaves the
  resolution of the host name to the proxy; `socks5:` resolves it first.
- **`requests_args`** — keyword arguments passed to every `session.request()`:
  `verify`, `cert`, `auth`, `cookies`, `hooks`, ... `headers` are sent with
  every request, under the request's own. `method`, `url`, `data`, `timeout`,
  `stream` and `allow_redirects` are the transport's: a value given for one is
  ignored.
- **`send(method, url, *, headers, body=None, timeout, stream=False)`** is
  `HTTPTransport.send()`: `ValueError` before anything is sent for what
  `pathlib_next.http.prepare_request()` refuses, one request and no redirect
  followed (`allow_redirects=True` in `requests_args` changes nothing), and the
  response body read whole with `stream=False`. A reply below 200 is
  `OSError(EIO)` (`urllib3` skips only `100`).
- **Credentials belong to one server.** What the session holds for
  authentication (its `auth`, an `Authorization` among its `headers`,
  `~/.netrc`) and the `auth` and `headers` of `requests_args` are used for the
  server of the first request: its scheme, host and port. A request to any
  other server carries the `Authorization` it was given and none of those. An
  `auth` the session or `requests_args` hold wins over an `Authorization`
  header on that first server. Redirects are followed by `HTTPClient`, which
  drops `Authorization` when one leaves the server.
- **Failures** are `TimeoutError`, `ConnectionError`, `ssl.SSLError`,
  `ValueError` (the request was not valid, or `requests` refused it) or
  `OSError(EIO)` (a reply that is not valid HTTP or is cut short, or any other
  failure of the library). The text of a `requests` exception, which can quote a
  proxy URL with credentials, is never passed on, and the exception is not
  chained. `repr()` shows nothing of the session or the arguments.

`pathlib_next_requests.__version__` is a `str`.

## Checking the transport

`pathlib_next` ships the tests that hold a transport to the promises of the
built-in one. With this distribution and `pytest` installed:

```
python -m pathlib_next.http.testing --http-transports requests -q
```

## Environment variables

### `PATHLIB_NEXT_HTTP_TRANSPORT`

Read by `pathlib_next.http`. `requests` makes an `HTTPClient` that was given no
transport build `RequestsTransport()`. The name is case-sensitive, and one that
no installed distribution declares is `ValueError` naming the choices.

### `requests` variables

`RequestsTransport` leaves `requests` to read them: `HTTP_PROXY`,
`HTTPS_PROXY`, `ALL_PROXY` and `NO_PROXY` (unless `proxies=` answers),
`REQUESTS_CA_BUNDLE` and `CURL_CA_BUNDLE` (unless `verify=` is set), and
`NETRC` or `~/.netrc` (unless the first server is given an `auth`).

## Gotchas

`RequestsTransport()` builds a `requests.Session` the moment it is constructed;
a session it made is closed by `close()`, by leaving a `with` block, and when the
transport is collected, so a transport you build is yours to close. An
`HTTPClient` closes only a transport it built itself, which is why
`HTTPClient(RequestsTransport(session))` does not close one.
