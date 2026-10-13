"""The tests `uripath` runs over its own HTTP transport, run over this one:
`http:`, `dav:`, `github:` and `gitlab:` against loopback servers, and the
transport contract against servers scripted at the byte level."""

from __future__ import annotations

import subprocess
import sys

from uripath import testing


def test_the_transport_suite_of_uripath_passes_over_the_requests_transport():
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "uripath.testing",
            "--http-transports",
            "requests",
            "-q",
            "-p",
            "no:cacheprovider",
        ],
        capture_output=True,
        text=True,
        timeout=1800,
    )
    summary = "\n".join(result.stdout.splitlines()[-25:])
    assert result.returncode == 0, summary + result.stderr[-2000:]
    assert " passed" in summary and " failed" not in summary


def test_the_suite_ran_the_tests_that_depend_on_the_transport_once_for_this_one():
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "uripath.testing",
            "--http-transports",
            "requests",
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
        ],
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert result.returncode == 0, result.stdout[-2000:] + result.stderr[-2000:]
    listed = [line for line in result.stdout.splitlines() if "::" in line]
    assert any("test_http_transport.py::" in line for line in listed)
    kinds = [line.partition("[")[2].rstrip("]").split("-") for line in listed]
    assert sum("requests" in ids for ids in kinds) > 500
    assert not any("builtin" in ids for ids in kinds)
    assert len(testing.MODULES) == 24
