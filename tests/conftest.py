"""Keeps the test run on this machine and independent of it, and puts the
loopback servers of `uripath`'s own transport tests within reach.

Every connection that is not to the loopback interface raises, a program other
than the interpreter cannot be started, and the proxy, CA-bundle and `.netrc`
settings of the developer's shell are not there to be read."""

from __future__ import annotations

import sys
import tempfile

import pytest

from uripath import testing

# `http_wire` (loopback servers scripted at the byte level) and `hermetic`.
sys.path.insert(0, str(testing.suite_directory()))

import hermetic  # noqa: E402


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "allow_network: lift the autouse non-loopback network guard for a test "
        "that deliberately resolves or connects to a real host",
    )
    home = tempfile.TemporaryDirectory(prefix="uripath-http-requests-home-")
    patch = pytest.MonkeyPatch()
    hermetic.isolate_environment(patch, home.name)
    config.add_cleanup(home.cleanup)
    config.add_cleanup(patch.undo)


_ENV_BEFORE = pytest.StashKey[dict]()


@pytest.hookimpl(wrapper=True)
def pytest_runtest_setup(item):
    item.stash[_ENV_BEFORE] = hermetic.environment_snapshot()
    return (yield)


@pytest.hookimpl(wrapper=True)
def pytest_runtest_teardown(item, nextitem):
    result = yield
    before = item.stash.get(_ENV_BEFORE, None)
    changed = (
        hermetic.changed_variables(before, hermetic.environment_snapshot())
        if before is not None
        else {}
    )
    if changed:
        hermetic.restore_environment(before)
        raise AssertionError(
            "the test left the process environment changed (use monkeypatch): "
            + ", ".join(f"{k}: {old!r} -> {new!r}" for k, (old, new) in changed.items())
        )
    return result


@pytest.fixture(autouse=True)
def _block_non_loopback_network(request, monkeypatch):
    blocked = []
    if not request.node.get_closest_marker("allow_network"):
        hermetic.install_network_guard(monkeypatch, blocked)
    hermetic.install_process_guard(monkeypatch, blocked, ())
    yield blocked
    if blocked:
        pytest.fail(f"non-loopback network access attempted: {blocked}")


@pytest.fixture
def transport():
    """A `RequestsTransport` on a new session, closed after the test."""
    from uripath_http_requests import RequestsTransport

    with RequestsTransport() as made:
        yield made
