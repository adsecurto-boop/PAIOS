"""The Intelligence page (M21) against a live server.

No Ollama and no cloud key in the test environment, so the page must
render the offline picture and the deterministic Test AI path — the
promise that PAIOS always works without a model.
"""

import pytest

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
