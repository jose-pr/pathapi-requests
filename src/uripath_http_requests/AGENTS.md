# `uripath_http_requests` — public API header

Header-file-style reference for the `uripath_http_requests` package: every public
export with its signature, arguments, contract and gotchas, so the package can
be used without reading its source. It ships inside the package and is
self-contained. Development documentation lives with the source at
<https://github.com/jose-pr/uripath-http-requests>.

Names are imported from `uripath_http_requests`, which exports one class,
`RequestsTransport`, and `__version__`. A module or name that starts with an
underscore is private and nothing there is contract.

`pip install uripath-http-requests`. Required dependencies: `uripath>=0.10.0,<0.11`
and `requests>=2.22.0,<3`. The one extra, `socks`, adds `requests[socks]`
(PySocks) for `socks4:`, `socks5:` and `socks5h:` proxies. `requests` is imported
when a transport is built, not when this package is.

`uripath_http_requests.__version__` is the version of the installed
distribution, read from its metadata. The rendered documentation is at
<https://jose-pr.github.io/uripath-http-requests/> and the project overview is the
`README.md` shipped next to this file (`uripath_http_requests/README.md`).

## The `requests` transport (`uripath_http_requests`)

```python
class RequestsTransport:
    session: requests.Session
    def __init__(self, session=None, *, proxies=None, **requests_args): ...
    def send(
        self, method, url, *, headers, body=None, timeout, stream=False,
    ) -> HTTPResponse: ...
    def close(self) -> None: ...
```

`RequestsTransport` is an HTTP transport for `uripath` (the contract is
"The transport contract" in the `uripath` header): `send()` makes one request
with a `requests.Session` and returns an `HTTPResponse`. `uripath` finds it
through the `requests` entry of its `uripath.http_transports` group, which this
distribution declares, so installing the distribution is all that is needed:

- `path.with_session(session, write_method="PUT", append_mode="rewrite",
  **requests_args)` on an `http:`, `https:`, `dav:` or `davs:` path builds
  `RequestsTransport(session, **requests_args)` (`headers` and `timeout` in
  `requests_args` are the backend's, and `session=None` makes a new session).
- `RepoBackend(session=..., **requests_args)`, the backend of `github:` and
  `gitlab:`, builds one the same way.
- `URIPATH_HTTP_TRANSPORT=requests` makes every backend that was given no
  transport build `RequestsTransport()`.

Use it for what the built-in transport does not do: a session of your own with
its mounted adapters, `auth` (basic, digest, NTLM, a token) and cookies;
`~/.netrc`; `REQUESTS_CA_BUNDLE` and `CURL_CA_BUNDLE` with the certifi bundle;
and SOCKS proxies.

- **`session`** — the `requests.Session` to send with, an object with a
  `request()` method (`TypeError` otherwise). `None` makes a new one. The
  attribute `session` is the one in use. `close()` closes a session this
  transport made and leaves a caller's open, so a session passed in is still
  usable afterwards. The transport is a context manager that calls `close()`.
- **`proxies`** — `None` leaves `requests` to read its session and the
  environment (`HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`, `NO_PROXY`). Otherwise
  an object that is indexed with the request URL (no fragment), as the
  `proxies` of `uripath.schemes.HTTPTransport` is. The answer is `None` (no
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
  `uripath-http-requests[socks]`, and nothing is sent. `socks5h:` leaves the
  resolution of the host name to the proxy; `socks5:` resolves it first.
- **`requests_args`** — keyword arguments passed to every `session.request()`:
  `verify`, `cert`, `auth`, `cookies`, `hooks`, ... `headers` are sent with
  every request, under the request's own. `method`, `url`, `data`, `timeout`,
  `stream` and `allow_redirects` are the transport's: a value given for one is
  ignored.
- **`send(method, url, *, headers, body=None, timeout, stream=False)`** is
  `HTTPTransport.send()`: `ValueError` before anything is sent for what
  `uripath.transports.prepare_request()` refuses, one request and no redirect
  followed (`allow_redirects=True` in `requests_args` changes nothing), and the
  response body read whole with `stream=False`. A reply below 200 is
  `OSError(EIO)` (`urllib3` skips only `100`).
- **Credentials belong to one server.** What the session holds for
  authentication (its `auth`, an `Authorization` among its `headers`,
  `~/.netrc`) and the `auth` and `headers` of `requests_args` are used for the
  server of the first request: its scheme, host and port. A request to any
  other server carries the `Authorization` it was given and none of those. An
  `auth` the session or `requests_args` hold wins over an `Authorization`
  header on that first server. Redirects are followed by the `uripath` backend,
  which drops `Authorization` when one leaves the server.
- **Failures** are `TimeoutError`, `ConnectionError`, `ssl.SSLError`,
  `ValueError` (the request was not valid, or `requests` refused it) or
  `OSError(EIO)` (a reply that is not valid HTTP or is cut short, or any other
  failure of the library). The text of a `requests` exception, which can quote a
  proxy URL with credentials, is never passed on, and the exception is not
  chained. `repr()` shows nothing of the session or the arguments.

`uripath_http_requests.__version__` is a `str`.

## Environment variables

### `URIPATH_HTTP_TRANSPORT`

Read by `uripath`. `requests` makes `http(s):`, `dav(s):`, `github:`, `gitlab:`
and `git:` build `RequestsTransport()` for a backend that was given no
transport. `with_transport()` and `with_session()` do not read it.

### `requests` variables

`RequestsTransport` leaves `requests` to read them: `HTTP_PROXY`,
`HTTPS_PROXY`, `ALL_PROXY` and `NO_PROXY` (unless `proxies=` answers),
`REQUESTS_CA_BUNDLE` and `CURL_CA_BUNDLE` (unless `verify=` is set), and
`NETRC` or `~/.netrc` (unless the first server is given an `auth`).

## Gotchas

`RequestsTransport()` builds a `requests.Session` the moment it is constructed;
a session it made is closed by `close()`, by leaving a `with` block, and by
nothing else, so a transport you build is yours to close. A backend closes only
a transport it built itself, which is why `with_session()` does not close one.
