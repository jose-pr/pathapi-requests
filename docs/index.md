# uripath-http-requests

The **`requests` HTTP transport for [`uripath`](https://jose-pr.github.io/uripath/)**.
`uripath` sends `http:`, `dav:`, `github:` and `gitlab:` requests with a
transport built on the standard library; install this distribution and the same
paths send through a `requests.Session` instead, with nothing to configure.

## Installation

```bash
pip install uripath-http-requests
```

| Extra | Adds | Needed for |
| --- | --- | --- |
| `socks` | `requests[socks]` (PySocks) | `socks4:`, `socks5:` and `socks5h:` proxies |

## 30-second tour

```python
import requests
from uripath import URIPath

with requests.Session() as session:
    session.headers["X-Team"] = "storage"
    path = URIPath("http://files.example.org/reports/today.txt").with_session(session)
    print(path.read_text())
```

`URIPATH_HTTP_TRANSPORT=requests` makes every path that was given no transport
send through a new session. A proxy per URL, `~/.netrc`, `REQUESTS_CA_BUNDLE`
and SOCKS proxies work as `requests` does them.

## Learn more

- [The transport](api/transport.md): `RequestsTransport`, its arguments and what it guarantees.
- [Benchmarks](benchmarks.md): the built-in transport and this one on loopback.
- [Changelog](changelog.md)
