# The transport

`RequestsTransport` implements the HTTP transport contract of `pathlib_next.http`:
`send()` makes one request with a `requests.Session` and returns an
`HTTPResponse`, and `close()` closes a session the transport made.
`pathlib_next.http` finds it through the `requests` entry of its
`pathlib_next.http_transports` entry-point group, so
`PATHLIB_NEXT_HTTP_TRANSPORT=requests` and
`pathlib_next.http.get_transport("requests")` name it.

::: pathlib_next_requests.RequestsTransport
    options:
      show_if_no_docstring: true
      filters: ["!^_"]
