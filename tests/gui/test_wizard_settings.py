"""First-run wizard + settings file: persistence, precedence, skipping.

The skip decision and the settings precedence are pure functions —
tested without showing the wizard. The wizard itself is only built
(offscreen) to check what it would persist.
"""

import json

from paios_gui import settings_store
from paios_gui.app import build_config
from paios_gui.first_run_wizard import FirstRunWizard, should_show_wizard


class TestSettingsStore:
    def test_save_and_load_roundtrip(self, tmp_path):
        path = tmp_path / "gui-settings.json"
        settings_store.save_settings(
            {"base_url": "http://x:1", "first_run_complete": True}, path
        )
        loaded = settings_store.load_settings(path)
        assert loaded["base_url"] == "http://x:1"
        assert settings_store.first_run_complete(loaded) is True

    def test_save_merges_over_existing(self, tmp_path):
        path = tmp_path / "gui-settings.json"
        settings_store.save_settings({"refresh_seconds": 9}, path)
        settings_store.save_settings({"theme": "dark"}, path)
        loaded = settings_store.load_settings(path)
        assert loaded == {"refresh_seconds": 9, "theme": "dark"}

    def test_missing_or_corrupt_file_loads_empty(self, tmp_path):
        assert settings_store.load_settings(tmp_path / "absent.json") == {}
        bad = tmp_path / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        assert settings_store.load_settings(bad) == {}

    def test_default_path_prefers_appdata(self, monkeypatch, tmp_path):
        monkeypatch.setenv("APPDATA", str(tmp_path))
        path = settings_store.settings_path()
        assert path == tmp_path / "PAIOS" / "gui-settings.json"
        monkeypatch.delenv("APPDATA")
        assert ".paios" in str(settings_store.settings_path())


class TestPrecedence:
    def test_settings_file_overrides_defaults(self):
        config = build_config(
            [], settings={"base_url": "http://file:1", "refresh_seconds": 9}
        )
        assert config.base_url == "http://file:1"
        assert config.refresh_seconds == 9

    def test_cli_flags_override_the_file(self):
        config = build_config(
            ["--url", "http://cli:2", "--refresh", "7"],
            settings={"base_url": "http://file:1", "refresh_seconds": 9},
        )
        assert config.base_url == "http://cli:2"
        assert config.refresh_seconds == 7

    def test_defaults_when_nothing_configures(self):
        config = build_config([], settings={})
        assert config.base_url == "http://127.0.0.1:8765"
        assert config.refresh_seconds == 5


class TestSkipRules:
    def test_marker_skips(self):
        assert should_show_wizard(
            {"first_run_complete": True}, environ={}
        ) is False

    def test_no_wizard_flag_always_skips(self):
        assert should_show_wizard({}, no_wizard=True, environ={}) is False
        assert should_show_wizard(
            {}, no_wizard=True, environ={}, force=True
        ) is False

    def test_offscreen_skips_unless_a_test_opts_in(self):
        offscreen = {"QT_QPA_PLATFORM": "offscreen"}
        assert should_show_wizard({}, environ=offscreen) is False
        assert should_show_wizard(
            {}, environ=offscreen, force=True
        ) is True

    def test_fresh_interactive_run_shows(self):
        assert should_show_wizard({}, environ={}) is True


class TestWizardPersistence:
    def test_wizard_settings_persist_and_mark_first_run(
        self, qapp, tmp_path
    ):
        wizard = FirstRunWizard(
            base_url="http://127.0.0.1:9999", refresh_seconds=15
        )
        wizard.preferences_page.interval.setValue(30)
        wizard.style_page.flexible.setChecked(True)
        stored = wizard.settings()
        assert stored["base_url"] == "http://127.0.0.1:9999"
        assert stored["refresh_seconds"] == 30
        assert stored["planning_style"] == "flexible"
        assert stored["work_hours_start"] == "09:00"
        assert stored["work_hours_end"] == "17:00"
        assert stored["intelligence_mode"] == "local"  # the default
        assert stored["first_run_complete"] is True

        path = tmp_path / "gui-settings.json"
        settings_store.save_settings(stored, path)
        on_disk = json.loads(path.read_text(encoding="utf-8"))
        assert on_disk["first_run_complete"] is True
        # And the marker now suppresses the wizard on the next start.
        assert should_show_wizard(
            settings_store.load_settings(path), environ={}
        ) is False
        wizard.deleteLater()

    def test_test_connection_against_live_server(self, qapp, live_server):
        wizard = FirstRunWizard(base_url=live_server)
        wizard.url_page.test_connection()
        assert wizard.url_page.result_label.text().startswith("✓")
        wizard.url_page.url_edit.setText("http://127.0.0.1:9")
        wizard.url_page.test_connection()
        assert wizard.url_page.result_label.text().startswith("✗")
        wizard.deleteLater()
