# The transport

`RequestsTransport` implements the HTTP transport contract of `pathapi.http`:
`send()` makes one request with a `requests.Session` and returns an
`HTTPResponse`, and `close()` closes a session the transport made.
`pathapi.http` finds it through the `requests` entry of its
`pathapi.http_transports` entry-point group, so
`PATHAPI_HTTP_TRANSPORT=requests` and
`pathapi.http.get_transport("requests")` name it.

::: pathapi_requests.RequestsTransport
    options:
      show_if_no_docstring: true
      filters: ["!^_"]
