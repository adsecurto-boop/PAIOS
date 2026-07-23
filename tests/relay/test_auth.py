"""Relay JWTs, refresh and replay protection (deterministic clocks)."""

import pytest

from paios_relay import auth


class TestJwt:
    def test_encode_decode_roundtrip(self):
        token = auth.encode({"account": "a", "sub": "d"}, "secret", now=100, ttl=60)
        claims = auth.decode(token, "secret", now=120)
        assert claims["account"] == "a" and claims["sub"] == "d"
        assert claims["iat"] == 100 and claims["exp"] == 160

    def test_expired_token_is_rejected(self):
        token = auth.encode({"x": 1}, "secret", now=100, ttl=60)
        assert auth.decode(token, "secret", now=161) is None

    def test_wrong_secret_is_rejected(self):
        token = auth.encode({"x": 1}, "secret", now=100, ttl=60)
        assert auth.decode(token, "other", now=120) is None

    def test_tampered_token_is_rejected(self):
        token = auth.encode({"role": "user"}, "secret", now=100, ttl=60)
        head, body, sig = token.split(".")
        forged = f"{head}.{body}x.{sig}"
        assert auth.decode(forged, "secret", now=120) is None

    def test_garbage_is_rejected(self):
        assert auth.decode("not-a-token", "secret", now=1) is None
        assert auth.decode("", "secret", now=1) is None


class TestTokenIssuer:
    def test_issue_and_verify_access(self):
        issuer = auth.TokenIssuer("secret")
        pair = issuer.issue_pair("acct", "pixel", now=1000)
        assert pair["token_type"] == "Bearer"
        claims = issuer.verify_access(pair["access_token"], now=1100)
        assert claims["account"] == "acct" and claims["sub"] == "pixel"

    def test_refresh_token_is_not_an_access_token(self):
        issuer = auth.TokenIssuer("secret")
        pair = issuer.issue_pair("acct", "pixel", now=1000)
        assert issuer.verify_access(pair["refresh_token"], now=1000) is None

    def test_refresh_mints_a_new_pair(self):
        issuer = auth.TokenIssuer("secret")
        pair = issuer.issue_pair("acct", "pixel", now=1000)
        refreshed = issuer.refresh(pair["refresh_token"], now=2000)
        assert refreshed is not None
        assert issuer.verify_access(refreshed["access_token"], now=2000)

    def test_refresh_rejects_access_token(self):
        issuer = auth.TokenIssuer("secret")
        pair = issuer.issue_pair("acct", "pixel", now=1000)
        assert issuer.refresh(pair["access_token"], now=1000) is None

    def test_empty_secret_is_refused(self):
        with pytest.raises(ValueError):
            auth.TokenIssuer("")


class TestReplayGuard:
    def test_fresh_nonce_is_accepted_once(self):
        guard = auth.ReplayGuard(window_seconds=300)
        assert guard.check("n1", timestamp=1000, now=1000) is True
        assert guard.check("n1", timestamp=1000, now=1000) is False  # replay

    def test_stale_timestamp_is_rejected(self):
        guard = auth.ReplayGuard(window_seconds=300)
        assert guard.check("n1", timestamp=1000, now=2000) is False

    def test_future_timestamp_is_rejected(self):
        guard = auth.ReplayGuard(window_seconds=300)
        assert guard.check("n1", timestamp=2000, now=1000) is False

    def test_expired_nonces_are_forgotten(self):
        guard = auth.ReplayGuard(window_seconds=100)
        assert guard.check("n1", timestamp=1000, now=1000) is True
        # Long after the window, a fresh request with a new nonce clears
        # the old one; the same nonce is now reusable (its record aged out).
        assert guard.check("n2", timestamp=2000, now=2000) is True
        assert guard.check("n1", timestamp=2000, now=2000) is True
