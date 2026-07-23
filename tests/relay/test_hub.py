"""The reverse-tunnel hub: authorization, presence, and request routing."""

import threading
import time

from paios_relay.hub import RelayHub


class TestAuthorization:
    def test_authorize_and_check(self):
        hub = RelayHub()
        assert hub.is_authorized("acct", "hash1") is False
        hub.authorize_device("acct", "hash1")
        assert hub.is_authorized("acct", "hash1") is True

    def test_revoke(self):
        hub = RelayHub()
        hub.authorize_device("acct", "hash1")
        hub.revoke_device("acct", "hash1")
        assert hub.is_authorized("acct", "hash1") is False

    def test_authorization_is_per_account(self):
        hub = RelayHub()
        hub.authorize_device("acct-a", "hash1")
        assert hub.is_authorized("acct-b", "hash1") is False


class TestPresence:
    def test_online_within_window(self):
        hub = RelayHub(offline_seconds=30)
        hub.desktop_connected("acct", now=1000)
        assert hub.is_desktop_online("acct", now=1010) is True

    def test_offline_after_window(self):
        hub = RelayHub(offline_seconds=30)
        hub.desktop_connected("acct", now=1000)
        assert hub.is_desktop_online("acct", now=1040) is False

    def test_disconnect_marks_offline(self):
        hub = RelayHub()
        hub.desktop_connected("acct", now=1000)
        hub.desktop_disconnected("acct")
        assert hub.is_desktop_online("acct", now=1001) is False


class TestRouting:
    def test_request_response_roundtrip(self):
        hub = RelayHub()
        request_id = hub.submit_request(
            "acct", {"method": "GET", "path": "/status"}
        )
        # A desktop drains it and answers.
        drained = hub.poll_requests("acct", now=1000, timeout=0.1)
        assert drained[0]["id"] == request_id
        assert drained[0]["path"] == "/status"
        assert hub.submit_response(request_id, {"status": 200}) is True
        assert hub.await_response(request_id, timeout=1.0) == {"status": 200}

    def test_await_times_out_without_response(self):
        hub = RelayHub()
        request_id = hub.submit_request("acct", {"path": "/x"})
        assert hub.await_response(request_id, timeout=0.1) is None

    def test_long_poll_wakes_on_new_request(self):
        hub = RelayHub()
        drained: list = []

        def desktop():
            drained.extend(
                hub.poll_requests("acct", now=1000, timeout=2.0)
            )

        poller = threading.Thread(target=desktop)
        poller.start()
        time.sleep(0.1)  # let the desktop block in the long-poll
        hub.submit_request("acct", {"path": "/late"})
        poller.join(timeout=2.0)
        assert drained and drained[0]["path"] == "/late"

    def test_poll_marks_desktop_online(self):
        hub = RelayHub(offline_seconds=30)
        hub.poll_requests("acct", now=5000, timeout=0.01)
        assert hub.is_desktop_online("acct", now=5005) is True
