"""No other site can frame EWOK's pages (clickjacking), and responses are
not content-sniffed."""

import pytest


@pytest.mark.parametrize("path", ["/", "/template", "/api/template/assets"])
def test_every_response_refuses_framing(client, path):
    resp = client.get(path)
    assert resp.status_code == 200
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["Content-Security-Policy"] == "frame-ancestors 'none'"
    assert resp.headers["X-Content-Type-Options"] == "nosniff"


def test_refused_requests_carry_the_headers_too(client):
    resp = client.get("/template", headers={"Host": "evil.example"})
    assert resp.status_code == 403
    assert resp.headers["X-Frame-Options"] == "DENY"
