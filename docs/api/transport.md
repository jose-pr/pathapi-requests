# The transport

`RequestsTransport` implements the transport contract of `uripath`: `send()` makes
one request with a `requests.Session` and returns an `HTTPResponse`, and `close()`
closes a session the transport made. `uripath` finds it through the `requests`
entry of its `uripath.http_transports` group.

::: uripath_http_requests.RequestsTransport
    options:
      show_if_no_docstring: true
      filters: ["!^_"]
