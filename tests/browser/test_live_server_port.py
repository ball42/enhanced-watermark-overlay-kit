"""The live server picks a free port, so two runs at once do not collide."""

import os
import socket

import pytest

from tests.browser.conftest import serve


@pytest.mark.skipif("EWOK_TEST_PORT" in os.environ, reason="a fixed port was asked for")
def test_two_live_servers_run_at_once_while_8406_is_taken(app):
    with socket.socket() as held:
        try:
            held.bind(("127.0.0.1", 8406))
        except OSError:
            pass  # someone else already holds it: the test still applies
        with serve(app) as first, serve(app) as second:
            assert first != second
            assert not first.endswith(":8406")
