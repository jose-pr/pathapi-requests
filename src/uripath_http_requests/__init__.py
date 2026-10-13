"""The `requests` HTTP transport for `uripath`.

Installing this distribution is enough: `uripath` finds `RequestsTransport`
through the `requests` entry of its `uripath.http_transports` group, so
`path.with_session(session)` and `URIPATH_HTTP_TRANSPORT=requests` send through
it. `requests` is imported when a transport is built, not when this package is.
"""

from __future__ import annotations

from ._transport import RequestsTransport
from ._version import __version__

__all__ = ["RequestsTransport", "__version__"]
