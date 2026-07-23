"""The desktop relay connector (M23): forwarding and reconnect, driven
through an injected fake HTTP layer — no relay and no server."""

import time

from paios.system.relay_client import RelayConnector


class FakeHttp:
    def __init__(self):
        self.calls = []
        self.responded = []
        self.poll_requests = []
        self.local_response = (200, {"ok": True})
        self.local_raises = False

    def __call__(self, method, url, body=None, headers=None, timeout=30.0):
        self.calls.append({"method": method, "url": url, "headers": headers})
        if url.endswith("/desktop/poll"):
            reqs, self.poll_requests = self.poll_requests, []
            return 200, {"requests": reqs}
        if url.endswith("/desktop/authorize"):
            return 200, {"authorized": True}
        if url.endswith("/desktop/respond"):
            self.responded.append(body)
            return 200, {"delivered": True}
        # Otherwise it's a local API call.
        if self.local_raises:
            raise OSError("connection refused")
        return self.local_response


def connector(http):
    return RelayConnector(
        "https://relay.example.com",
        "default",
        "desk-key",
        "http://127.0.0.1:8765",
        http=http,
        sleep=lambda s: None,
        poll_timeout=0.2,
    )


class TestAuthorize:
    def test_authorize_device_posts_with_desktop_key(self):
        http = FakeHttp()
        assert connector(http).authorize_device("hash-1") is True
        call = next(c for c in http.calls if c["url"].endswith("/authorize"))
        assert call["headers"]["X-Relay-Key"] == "desk-key"


class TestForwarding:
    def test_forwards_a_request_to_the_local_api_and_responds(self):
        http = FakeHttp()
        http.poll_requests = [
            {
                "id": "r1",
                "method": "GET",
                "path": "/mobile/timeline",
                "headers": {"Authorization": "Bearer device-token"},
            }
        ]
        http.local_response = (200, {"entries": []})
        served = connector(http).poll_once()
        assert served == 1
        # The local API was called at the loopback address, carrying the
        # phone's own device authorization end to end.
        local = next(
            c for c in http.calls if "127.0.0.1:8765/mobile/timeline" in c["url"]
        )
        assert local["headers"]["Authorization"] == "Bearer device-token"
        # And the response went back to the relay.
        assert http.responded == [
            {"id": "r1", "status": 200, "body": {"entries": []}}
        ]

    def test_local_failure_still_answers_the_phone(self):
        http = FakeHttp()
        http.poll_requests = [{"id": "r2", "method": "GET", "path": "/x"}]
        http.local_raises = True
        connector(http).poll_once()
        assert http.responded[0]["id"] == "r2"
        assert http.responded[0]["status"] == 502

    def test_poll_error_raises_for_the_reconnect_loop(self):
        class Down(FakeHttp):
            def __call__(self, method, url, body=None, headers=None, timeout=30.0):
                if url.endswith("/desktop/poll"):
                    return 502, {"error": "relay down"}
                return super().__call__(method, url, body, headers, timeout)

        import pytest

        with pytest.raises(OSError):
            connector(Down()).poll_once()


class TestLifecycle:
    def test_start_connects_then_stop(self):
        http = FakeHttp()
        conn = connector(http)
        conn.start()
        deadline = time.monotonic() + 2
        while not conn.connected and time.monotonic() < deadline:
            time.sleep(0.02)
        assert conn.connected is True
        conn.stop()
        assert conn.connected is False

    def test_status_shape(self):
        status = connector(FakeHttp()).status()
        assert status["relay_url"].startswith("https://")
        assert status["connected"] is False
