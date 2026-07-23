"""Desktop UX polish (M24): dual themes, runtime switching, keyboard
shortcut discoverability, and accessibility metadata."""

from PySide6.QtWidgets import QApplication

from paios_gui import theme
from paios_gui.dialogs import ShortcutsDialog


class TestThemeSystem:
    def test_both_palettes_differ(self):
        dark = theme.build_stylesheet(theme.DARK)
        light = theme.build_stylesheet(theme.LIGHT)
        assert theme.DARK["bg"] in dark
        assert theme.LIGHT["bg"] in light
        assert dark != light

    def test_normalize_theme_falls_back_to_default(self):
        assert theme.normalize_theme("light") == "light"
        assert theme.normalize_theme("dark") == "dark"
        assert theme.normalize_theme("neon") == "dark"
        assert theme.normalize_theme(None) == "dark"

    def test_apply_theme_sets_stylesheet(self, qapp):
        theme.apply_theme(qapp, "light")
        assert theme.LIGHT["bg"] in qapp.styleSheet()
        theme.apply_theme(qapp, "dark")
        assert theme.DARK["bg"] in qapp.styleSheet()

    def test_legacy_symbols_preserved(self):
        # Existing pages import these — they must keep resolving.
        assert theme.BACKGROUND and theme.ACCENT and theme.GOOD
        assert theme.WARN and theme.BAD and theme.TEXT_DIM
        assert theme.status_color("Completed") == theme.GOOD
        assert theme.status_color("unknown") == theme.TEXT_DIM


class TestRuntimeToggle:
    def test_set_theme_applies_and_returns_mode(self, window, monkeypatch):
        # Do not touch the real settings file during the test.
        import paios_gui.settings_store as store

        monkeypatch.setattr(store, "save_settings", lambda *a, **k: None)
        applied = window.set_theme("light")
        assert applied == "light"
        assert theme.LIGHT["bg"] in QApplication.instance().styleSheet()
        assert window.config.theme == "light"
        # Restore for other tests sharing the session QApplication.
        window.set_theme("dark")

    def test_set_theme_rejects_unknown(self, window, monkeypatch):
        import paios_gui.settings_store as store

        monkeypatch.setattr(store, "save_settings", lambda *a, **k: None)
        assert window.set_theme("hologram") == "dark"


class TestShortcuts:
    def test_shortcuts_dialog_lists_every_binding(self, qapp):
        dialog = ShortcutsDialog()
        keys = [row[0] for row in dialog.SHORTCUTS]
        assert any("F5" in k for k in keys)
        assert any("Ctrl+N" in k for k in keys)
        assert any("F1" in k for k in keys)
        assert any("Ctrl+," in k for k in keys)
        dialog.deleteLater()

    def test_help_and_settings_shortcuts_registered(self, window):
        from PySide6.QtGui import QShortcut

        sequences = {
            shortcut.key().toString()
            for shortcut in window.findChildren(QShortcut)
        }
        assert "F1" in sequences
        assert "Ctrl+," in sequences


class TestAccessibility:
    def test_core_controls_have_accessible_names(self, window):
        assert window.navigation.accessibleName() == "Main navigation"
        assert window.search_edit.accessibleName()
        assert window.search_edit.toolTip()
