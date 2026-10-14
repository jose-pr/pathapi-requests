"""The `requests` HTTP transport for `pathapi.http`.

Installing this distribution is enough: `pathapi.http` finds
`RequestsTransport` through the `requests` entry of its
`pathapi.http_transports` group, so `HTTPClient(RequestsTransport(session))`
and `PATHAPI_HTTP_TRANSPORT=requests` send through it. `requests` is
imported when a transport is built, not when this package is.
"""

from __future__ import annotations

from ._transport import RequestsTransport
from ._version import __version__

__all__ = ["RequestsTransport", "__version__"]
