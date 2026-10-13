# uripath-http-requests

[![Version](https://img.shields.io/pypi/v/uripath-http-requests.svg)](https://pypi.org/project/uripath-http-requests/)
[![Python versions](https://img.shields.io/pypi/pyversions/uripath-http-requests.svg)](https://pypi.org/project/uripath-http-requests/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/jose-pr/uripath-http-requests/blob/main/LICENSE)
[![Docs](https://img.shields.io/badge/docs-latest-blue.svg)](https://jose-pr.github.io/uripath-http-requests/)
[![CI](https://img.shields.io/github/actions/workflow/status/jose-pr/uripath-http-requests/test.yml)](https://github.com/jose-pr/uripath-http-requests/actions/workflows/test.yml)

**The `requests` HTTP transport for [`uripath`](https://github.com/jose-pr/uripath).**
`uripath` sends `http:`, `dav:`, `github:` and `gitlab:` requests with a
transport built on the standard library; install this distribution and the same
paths send through a `requests.Session` instead, with nothing to configure. It
is for what the built-in transport does not do, and it is documented at
<https://jose-pr.github.io/uripath-http-requests/>.

## Features

| You want | Built-in transport | This transport |
| --- | --- | --- |
| Your own `requests.Session`: mounted adapters, `session.auth`, cookies, hooks | No | Yes: `path.with_session(session)` |
| `~/.netrc` credentials | No | Yes |
| `REQUESTS_CA_BUNDLE`, `CURL_CA_BUNDLE` and the certifi bundle | The system trust store, or an `ssl_context=` | Yes |
| SOCKS proxies (`socks5h://...`) | No: only `http://` proxies | Yes, with the `socks` extra |
| Digest authentication, or any other `requests` auth class | No | Through `session.auth` |
| A proxy provider indexed with the URL | Yes | Yes: `RequestsTransport(proxies=provider)` |

- **Credentials belong to one server.** What the session holds for
  authentication is sent to the server of the first request and to no other,
  and `uripath` never takes an `Authorization` header to another server on a
  redirect.
- **No third-party text in an error.** A failure of `requests` is a
  `TimeoutError`, `ConnectionError`, `ssl.SSLError`, `ValueError` or
  `OSError(EIO)`; what the library says, which can quote a proxy URL with
  credentials, is never passed on.
- **The same promises as the built-in transport.** The tests `uripath` runs over
  its own transport run over this one (`python -m uripath.testing`).

## Installation

```bash
pip install uripath-http-requests
```

Requires `uripath` and `requests`, which pip installs with it.

| Extra | Adds | Needed for |
| --- | --- | --- |
| `socks` | `requests[socks]` (PySocks) | `socks4:`, `socks5:` and `socks5h:` proxies |

## Quick start

**Send through your own session.** `with_session()` is on every `http:`,
`https:`, `dav:` and `davs:` path:

```python
import requests
from uripath import URIPath

session = requests.Session()
session.headers["X-Team"] = "storage"

path = URIPath("http://files.example.org/reports/today.txt").with_session(
    session, timeout=(3, 30)
)
print(path.read_text())
```

The session stays yours: the path never closes it.

**Choose it for the whole process.** `URIPATH_HTTP_TRANSPORT=requests` makes
every path that was given no transport send through a new session:

```bash
URIPATH_HTTP_TRANSPORT=requests uripath read http://files.example.org/reports/today.txt  # uripath[cli]
```

**Pick a proxy per URL.** `proxies` is indexed with the request URL and answers
a proxy, or `None` for no proxy; `KeyError` leaves it to `requests`:

```python
from uripath_http_requests import RequestsTransport


class ByHost:
    def __getitem__(self, url):
        if "internal.example.org" in url:
            return None  # direct
        if url.startswith("https://"):
            return "socks5h://gateway.example.org:1080"
        raise KeyError(url)  # what requests would have done


transport = RequestsTransport(proxies=ByHost())
```

## API overview

| Name | Purpose |
| --- | --- |
| `uripath_http_requests.RequestsTransport` | The transport: `send()` and `close()` over a `requests.Session` |
| `uripath_http_requests.__version__` | The installed version |

`uripath` finds the class through the `requests` entry of its
`uripath.http_transports` entry-point group, which this distribution declares.
The reference is in the
[API header](https://github.com/jose-pr/uripath-http-requests/blob/main/src/uripath_http_requests/AGENTS.md)
that ships with the package.

## Development

```bash
python -m venv .venv/3.14-posix-x86_64
.venv/3.14-posix-x86_64/bin/python -m pip install -e ".[dev]"
.venv/3.14-posix-x86_64/bin/python -m pytest -q -rs
```

`uripath` and `pathlib-next` 0.10 are dependencies; while they are not on PyPI,
install both editable from their checkouts first. The test run includes
`python -m uripath.testing --http-transports requests`, the tests `uripath`
runs over its own transport, and takes a couple of minutes for that.

### Releasing

This project follows [Semantic Versioning](https://semver.org/) and keeps a
[`CHANGELOG.md`](CHANGELOG.md). Pushing a tag matching `v*` triggers the release
workflow: test gate → build (checking the tag names the version built) → a strict
docs build as a gate → GitHub release → publish. The release workflow never deploys
the docs site itself: for a final release its last job dispatches the docs workflow
at the tag, which owns every Pages deploy.

## License

MIT — see [LICENSE](LICENSE).
