"""The `requests` HTTP transport for `pathlib_next.http`.

Installing this distribution is enough: `pathlib_next.http` finds
`RequestsTransport` through the `requests` entry of its
`pathlib_next.http_transports` group, so `HTTPClient(RequestsTransport(session))`
and `PATHLIB_NEXT_HTTP_TRANSPORT=requests` send through it. `requests` is
imported when a transport is built, not when this package is.
"""

from __future__ import annotations

from ._transport import RequestsTransport
from ._version import __version__

__all__ = ["RequestsTransport", "__version__"]
