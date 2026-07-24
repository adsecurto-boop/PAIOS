"""The Intelligence page (M21) against a live server.

No Ollama and no cloud key in the test environment, so the page must
render the offline picture and the deterministic Test AI path — the
promise that PAIOS always works without a model.
"""

import pytest

from paios_gui.client import ApiResponseError, ApiTimeout, ApiUnreachable
from paios_gui.intelligence_page import IntelligencePage


@pytest.fixture
def page(window, monkeypatch):
    monkeypatch.delenv("PAIOS_AI_PROVIDER", raising=False)
    widget = IntelligencePage(window)
    widget.refresh(window.client)
    return widget


class TestRender:
    def test_ollama_detection_line_present(self, page):
        assert "Ollama" in page.ollama_label.text()

    def test_hardware_line_shows_ram_and_cpu(self, page):
        text = page.hardware_label.text()
        assert "RAM" in text and "CPU cores" in text

    def test_gpu_cpu_indicator_chip_is_populated(self, page):
        # Real hardware detection: either a GPU or a CPU-core indicator.
        text = page.hardware_chip.text()
        assert text.startswith("GPU:") or text.startswith("CPU:")

    def test_status_light_is_offline_without_ai(self, page):
        # Provider 'none' + no ollama -> safe offline mode, not an error.
        assert page.status_chip.text() in ("Offline mode", "Ready")

    def test_mode_selector_lists_all_modes(self, page):
        labels = [
            page.mode_combo.itemText(i)
            for i in range(page.mode_combo.count())
        ]
        assert "Local AI (Ollama)" in labels
        assert "Offline (no AI)" in labels
        assert "Anthropic" in labels


class TestTestAi:
    def test_test_ai_shows_latency_and_answer(self, page):
        page._on_test()
        assert not page.latency_label.isHidden()
        assert page.latency_label.text().endswith("ms")
        assert page.test_output.text()  # a non-empty reply

    def test_test_ai_uses_deterministic_engine_offline(self, page):
        page._on_test()
        assert "Deterministic engine" in page.test_output.text()

    def test_test_ai_reports_connected_on_success(self, page):
        page._on_test()
        assert page.test_output.text().startswith("Connected —")

    def test_test_ai_re_enables_the_button_when_done(self, page):
        page._on_test()
        assert page.test_button.isEnabled()


class TestFailureWording:
    """A slow model, a refused connection and an HTTP error are three
    different facts. Reporting all of them as "Offline" is the bug this
    wording replaces."""

    def test_timeout_is_not_reported_as_offline(self):
        text = IntelligencePage.explain_failure(ApiTimeout(300.0))
        assert "Offline" not in text
        assert "300s" in text
        assert "still loading" in text

    def test_unreachable_says_the_backend_is_not_running(self):
        text = IntelligencePage.explain_failure(
            ApiUnreachable("Connection refused")
        )
        assert "Could not reach the PAIOS backend" in text
        assert "Connection refused" in text

    def test_http_error_surfaces_status_and_type(self):
        text = IntelligencePage.explain_failure(
            ApiResponseError(500, "AdapterError", "model exploded")
        )
        assert "HTTP 500" in text
        assert "AdapterError" in text
        assert "model exploded" in text

    def test_provider_refusal_is_not_an_offline_report(self, page):
        page._show_test_result(
            {
                "source": "llm",
                "ok": False,
                "answer": "The provider did not answer: no model",
            },
            1234,
        )
        text = page.test_output.text()
        assert "Backend is reachable" in text
        assert "no model" in text
        assert "Offline" not in text


class TestApplyMode:
    def test_switch_to_offline_is_applied(self, window, page):
        # Select "Offline (no AI)" and apply.
        for index in range(page.mode_combo.count()):
            if page.mode_combo.itemText(index) == "Offline (no AI)":
                page.mode_combo.setCurrentIndex(index)
                break
        page._on_apply_mode()
        config = window.client.assistant_config()
        assert config["provider"] == "none"

    def test_cloud_key_row_toggles_with_selection(self, page):
        for index in range(page.mode_combo.count()):
            if page.mode_combo.itemText(index) == "OpenAI":
                page.mode_combo.setCurrentIndex(index)
                break
        assert not page.key_row.isHidden()
        for index in range(page.mode_combo.count()):
            if page.mode_combo.itemText(index) == "Offline (no AI)":
                page.mode_combo.setCurrentIndex(index)
                break
        assert page.key_row.isHidden()
