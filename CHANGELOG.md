# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-10-14

The first release of `pathlib-next-requests`: `RequestsTransport`, the HTTP
transport that sends through a `requests.Session`, as a distribution of its own.
It needs Python 3.9 or newer, `pathlib-next>=0.10.0,<0.11` and
`requests>=2.22.0,<3`; its one extra, `socks`, adds `requests[socks]` for SOCKS
proxies. Under *Changed*, the migration from the `RequestsTransport` of
`pathlib-next` comes in this order: the table of names, then every change of
behaviour with what to do about it.

### Added

- `pathlib_next_requests.RequestsTransport` and `pathlib_next_requests.__version__`.
- The distribution declares the `requests` entry of the
  `pathlib_next.http_transports` group. Installing it is all that
  `pathlib_next.http` needs to send through it:
  `HTTPClient(RequestsTransport(session))` and
  `PATHLIB_NEXT_HTTP_TRANSPORT=requests` use it,
  `pathlib_next.http.get_transport("requests")` loads it, and
  `pathlib_next.http.transport_names()` lists it.
- `RequestsTransport(proxies=provider)`: an object indexed with the request URL
  that answers a proxy (a URL, or an object with a `url`), `None` for no proxy,
  or an iterable of them, of which the first is used. `KeyError` leaves the
  decision to `requests`.
- A session the transport made is closed when the transport is collected, and a
  response that is still open keeps its transport alive, so a dropped transport
  leaves no sockets to the garbage collector on any `urllib3`.
- A `socks4:`, `socks5:` or `socks5h:` proxy without PySocks raises
  `OSError(EPROTONOSUPPORT)` naming `pathlib-next-requests[socks]`.
- The tests `pathlib_next` runs over its own transport run over this one
  (`python -m pathlib_next.http.testing --http-transports requests`) as part of
  the test suite.

### Changed

- Migration from `pathlib-next`:

  | Was | Is |
  | --- | --- |
  | `pathlib_next.uri.schemes.http.RequestsTransport` | `pathlib_next_requests.RequestsTransport` |
  | `RequestsTransport(session=None, **requests_args)` | `RequestsTransport(session=None, *, proxies=None, **requests_args)` |
  | the extra `pathlib-next[http]` | `pip install pathlib-next-requests` |
  | `PATHLIB_NEXT_HTTP_TRANSPORT=requests` | the same, read by `pathlib_next.http`; this distribution must be installed |

- `proxies` is a provider and no longer an argument that `requests` receives as
  it is. A `dict` keeps its `requests` meaning for the keys `"http"`, `"https"`,
  `"all"` and `"scheme://host"` (a `None` value is still no proxy); a
  `"no_proxy"` entry of the dict is not read. What to do: put `NO_PROXY` in the
  environment, or answer `None` for those URLs.
- A `requests` that cannot be imported raises an `ImportError` that names this
  distribution, where it named the `http` extra of `pathlib-next`. What to do:
  reinstall `pathlib-next-requests`.
- A `session` that is not an object with a `request()` method raises
  `TypeError` where the transport is built. What to do: pass a
  `requests.Session`.

[Unreleased]: https://github.com/jose-pr/pathlib-next-requests/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/jose-pr/pathlib-next-requests/releases/tag/v0.1.0
