# pathlib-next-requests

[![Version](https://img.shields.io/pypi/v/pathlib-next-requests.svg)](https://pypi.org/project/pathlib-next-requests/)
[![Python versions](https://img.shields.io/pypi/pyversions/pathlib-next-requests.svg)](https://pypi.org/project/pathlib-next-requests/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/jose-pr/pathlib-next-requests/blob/main/LICENSE)
[![Docs](https://img.shields.io/badge/docs-latest-blue.svg)](https://jose-pr.github.io/pathlib-next-requests/)
[![CI](https://img.shields.io/github/actions/workflow/status/jose-pr/pathlib-next-requests/test.yml)](https://github.com/jose-pr/pathlib-next-requests/actions/workflows/test.yml)

**The `requests` HTTP transport for [`pathlib-next`](https://github.com/jose-pr/pathlib-next).**
`pathlib_next.http` sends requests with a transport built on the standard
library; install this distribution and the same `HTTPClient` sends through a
`requests.Session` instead, with nothing to configure. It is for what the
built-in transport does not do, and it is documented at
<https://jose-pr.github.io/pathlib-next-requests/>.

## Features

| You want | Built-in transport | This transport |
| --- | --- | --- |
| Your own `requests.Session`: mounted adapters, `session.auth`, cookies, hooks | No | Yes: `HTTPClient(RequestsTransport(session))` |
| `~/.netrc` credentials | No | Yes |
| `REQUESTS_CA_BUNDLE`, `CURL_CA_BUNDLE` and the certifi bundle | The system trust store, or an `ssl_context=` | Yes |
| SOCKS proxies (`socks5h://...`) | No: only `http://` proxies | Yes, with the `socks` extra |
| Digest authentication, or any other `requests` auth class | No | Through `session.auth` |
| A proxy provider indexed with the URL | Yes | Yes: `RequestsTransport(proxies=provider)` |

- **Credentials belong to one server.** What the session holds for
  authentication is sent to the server of the first request and to no other,
  and `HTTPClient` never takes an `Authorization` header to another server on a
  redirect.
- **No third-party text in an error.** A failure of `requests` is a
  `TimeoutError`, `ConnectionError`, `ssl.SSLError`, `ValueError` or
  `OSError(EIO)`; what the library says, which can quote a proxy URL with
  credentials, is never passed on.
- **The same promises as the built-in transport.** The tests `pathlib_next` runs
  over its own transport run over this one
  (`python -m pathlib_next.http.testing --http-transports requests`).

The URI paths of `uripath` use it too: with this distribution installed,
`with_session()` and `PATHLIB_NEXT_HTTP_TRANSPORT=requests` send through it.

## Installation

```bash
pip install pathlib-next-requests
```

Requires `pathlib-next` and `requests`, which pip installs with it.

| Extra | Adds | Needed for |
| --- | --- | --- |
| `socks` | `requests[socks]` (PySocks) | `socks4:`, `socks5:` and `socks5h:` proxies |

## Quick start

**Send through your own session.** Hand the transport to an `HTTPClient`:

```python
import requests
from pathlib_next.http import HTTPClient
from pathlib_next_requests import RequestsTransport

with requests.Session() as session:
    session.headers["X-Team"] = "storage"
    client = HTTPClient(RequestsTransport(session), timeout=(3, 30))
    reply = client.request("GET", "http://files.example.org/reports/today.txt")
    print(reply.read().decode())
```

The session stays yours: neither the client nor the transport closes it.

**Choose it for the whole process.** `PATHLIB_NEXT_HTTP_TRANSPORT=requests` makes
every `HTTPClient` that was given no transport send through a new session:

```bash
PATHLIB_NEXT_HTTP_TRANSPORT=requests python -c "from pathlib_next.http import HTTPClient; print(type(HTTPClient().transport))"
```

**Pick a proxy per URL.** `proxies` is indexed with the request URL and answers
a proxy, or `None` for no proxy; `KeyError` leaves it to `requests`:

```python
from pathlib_next_requests import RequestsTransport


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
| `pathlib_next_requests.RequestsTransport` | The transport: `send()` and `close()` over a `requests.Session` |
| `pathlib_next_requests.__version__` | The installed version |

`pathlib_next.http` finds the class through the `requests` entry of its
`pathlib_next.http_transports` entry-point group, which this distribution
declares. The reference is in the
[API header](https://github.com/jose-pr/pathlib-next-requests/blob/main/src/pathlib_next_requests/AGENTS.md)
that ships with the package.

## Development

```bash
python -m venv .venv/3.14-posix-x86_64
.venv/3.14-posix-x86_64/bin/python -m pip install -e ".[dev]"
.venv/3.14-posix-x86_64/bin/python -m pytest -q -rs
```

`pathlib-next` 0.10 is a dependency; while it is not on PyPI, install it
editable from its checkout first (`pip install -e ../pathlib-next`). The test run
includes `python -m pathlib_next.http.testing --http-transports requests`, the
tests `pathlib_next` runs over its own transport.

### Releasing

This project follows [Semantic Versioning](https://semver.org/) and keeps a
[`CHANGELOG.md`](CHANGELOG.md). Pushing a tag matching `v*` triggers the release
workflow: test gate → build (checking the tag names the version built) → a strict
docs build as a gate → GitHub release → publish. The release workflow never deploys
the docs site itself: for a final release its last job dispatches the docs workflow
at the tag, which owns every Pages deploy.

## License

MIT — see [LICENSE](LICENSE).
