"""SimpleFIN egress hardening (CodeQL #3): exact-host allowlist, URL tricks, rebuild."""

from __future__ import annotations

import base64

import pytest

from app.integrations import simplefin


def _token(url: str) -> str:
    return base64.b64encode(url.encode()).decode()


def test_official_bridge_hosts_allowed():
    for host in ("bridge.simplefin.org", "beta-bridge.simplefin.org"):
        url = f"https://{host}/simplefin/claim/abc"
        assert simplefin.decode_setup_token(_token(url)) == url


@pytest.mark.parametrize(
    "url",
    [
        "http://bridge.simplefin.org/claim/abc",  # not https
        "https://evil.com/claim/abc",  # foreign host
        "https://bridge.simplefin.org.evil.com/claim/abc",  # prefix trick
        "https://api.simplefin.org/claim/abc",  # unexpected subdomain (no wildcarding)
        "https://bridge.simplefin.org@evil.com/claim/abc",  # userinfo trick
        "https://127.0.0.1:8000/api/reset-vault",  # SSRF at the app itself
        "https://169.254.169.254/latest/meta-data/",  # cloud metadata
    ],
)
def test_hostile_claim_urls_refused(url):
    with pytest.raises(simplefin.SimpleFINError):
        simplefin.decode_setup_token(_token(url))


def test_self_hosted_bridge_via_env(monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv(
        "BLACKLINE_SIMPLEFIN_ALLOWED_HOST", "bridge.simplefin.org,my-bridge.local"
    )
    get_settings.cache_clear()
    try:
        url = "https://my-bridge.local/simplefin/claim/abc"
        assert simplefin.decode_setup_token(_token(url)) == url
    finally:
        get_settings.cache_clear()


def test_request_url_rebuilt_from_validated_parts():
    # A fragment (or anything else outside scheme/host/path/query) never reaches
    # the wire; the request target is reassembled from parsed components.
    rebuilt = simplefin._rebuild_for_request(
        "https://bridge.simplefin.org:8443/claim/abc?x=1#fragment"
    )
    assert rebuilt == "https://bridge.simplefin.org:8443/claim/abc?x=1"
