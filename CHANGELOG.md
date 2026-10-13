# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

The first release of `uripath-http-requests`: `RequestsTransport`, the HTTP
transport that sends through a `requests.Session`, as a distribution of its own.
It needs Python 3.9 or newer, `uripath>=0.10.0,<0.11` and `requests>=2.22.0,<3`;
its one extra, `socks`, adds `requests[socks]` for SOCKS proxies. Under *Changed*,
the migration from `pathlib_next.uri.schemes.http.RequestsTransport` comes in
this order: the table of names, then every change of behaviour with what to do
about it.

### Added

- `uripath_http_requests.RequestsTransport` and `uripath_http_requests.__version__`.
- The distribution declares the `requests` entry of the `uripath.http_transports`
  group. Installing it is all that `uripath` needs to send through it:
  `path.with_session(session)`, `RepoBackend(session=...)` and
  `URIPATH_HTTP_TRANSPORT=requests` use it, and `uripath.transports.names()`
  lists it.
- `RequestsTransport(proxies=provider)`: an object indexed with the request URL
  that answers a proxy (a URL, or an object with a `url`), `None` for no proxy,
  or an iterable of them, of which the first is used. `KeyError` leaves the
  decision to `requests`.
- A `socks4:`, `socks5:` or `socks5h:` proxy without PySocks raises
  `OSError(EPROTONOSUPPORT)` naming `uripath-http-requests[socks]`.
- The tests `uripath` runs over its own transport run over this one
  (`python -m uripath.testing --http-transports requests`) as part of the
  test suite.

### Changed

- Migration from `pathlib-next`:

  | Was | Is |
  | --- | --- |
  | `pathlib_next.uri.schemes.http.RequestsTransport` | `uripath_http_requests.RequestsTransport` |
  | `RequestsTransport(session=None, **requests_args)` | `RequestsTransport(session=None, *, proxies=None, **requests_args)` |
  | the extra `pathlib-next[http]` | `pip install uripath-http-requests` |
  | `PATHLIB_NEXT_HTTP_TRANSPORT=requests` | `URIPATH_HTTP_TRANSPORT=requests` |

- `proxies` is a provider and no longer an argument that `requests` receives as
  it is. A `dict` keeps its `requests` meaning for the keys `"http"`, `"https"`,
  `"all"` and `"scheme://host"` (a `None` value is still no proxy); a
  `"no_proxy"` entry of the dict is not read. What to do: put `NO_PROXY` in the
  environment, or answer `None` for those URLs.
- A `requests` that cannot be imported raises an `ImportError` that names this
  distribution, where it named the `http` extra of `pathlib-next`. What to do:
  reinstall `uripath-http-requests`.
- A `session` that is not an object with a `request()` method raises
  `TypeError` where the transport is built. What to do: pass a
  `requests.Session`.

[Unreleased]: https://github.com/jose-pr/uripath-http-requests/commits/main
