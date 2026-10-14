# pathapi-requests

The **`requests` HTTP transport for [`pathapi`](https://jose-pr.github.io/pathapi/)**.
`pathapi.http` sends requests with a transport built on the standard
library; install this distribution and the same `HTTPClient` sends through a
`requests.Session` instead, with nothing to configure.

## Installation

```bash
pip install pathapi-requests
```

| Extra | Adds | Needed for |
| --- | --- | --- |
| `socks` | `requests[socks]` (PySocks) | `socks4:`, `socks5:` and `socks5h:` proxies |

## 30-second tour

```python
import requests
from pathapi.http import HTTPClient
from pathapi_requests import RequestsTransport

with requests.Session() as session:
    session.headers["X-Team"] = "storage"
    with HTTPClient(RequestsTransport(session)) as client:
        reply = client.request("GET", "http://files.example.org/reports/today.txt")
        print(reply.read().decode())
```

`PATHAPI_HTTP_TRANSPORT=requests` makes every `HTTPClient` that was given no
transport send through a new session. A proxy per URL, `~/.netrc`,
`REQUESTS_CA_BUNDLE` and SOCKS proxies work as `requests` does them.

## Learn more

- [The transport](api/transport.md): `RequestsTransport`, its arguments and what it guarantees.
- [Benchmarks](benchmarks.md): the built-in transport and this one on loopback.
- [Changelog](changelog.md)
