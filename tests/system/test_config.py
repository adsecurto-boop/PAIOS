"""config.yaml: subset parsing, resolution, precedence, generation."""

import pytest

from paios.system.config import (
    SystemConfig,
    generate_default_config,
    load_system_config,
    parse_yaml_subset,
)


class TestYamlSubset:
    def test_scalars_sections_comments(self):
        parsed = parse_yaml_subset(
            "# comment\n"
            "data_dir: data\n"
            "\n"
            "server:\n"
            "  host: 0.0.0.0   # inline comment\n"
            "  port: 9000\n"
            "backup:\n"
            "  enabled: false\n"
            "  interval_hours: 12.5\n"
            "notifications:\n"
            "  quiet_hours: null\n"
            "  label: \"quoted: value\"\n"
        )
        assert parsed["data_dir"] == "data"
        assert parsed["server"] == {"host": "0.0.0.0", "port": 9000}
        assert parsed["backup"] == {"enabled": False, "interval_hours": 12.5}
        assert parsed["notifications"]["quiet_hours"] is None
        assert parsed["notifications"]["label"] == "quoted: value"

    def test_rejects_lines_outside_the_subset(self):
        with pytest.raises(ValueError, match="line 1"):
            parse_yaml_subset("- a list item\n")
        with pytest.raises(ValueError, match="outside a section"):
            parse_yaml_subset("  orphan: 1\n")
        with pytest.raises(ValueError, match="subset"):
            parse_yaml_subset("key: [1, 2]\n")


class TestLoading:
    def test_defaults_without_any_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("PAIOS_CONFIG", raising=False)
        config = load_system_config()
        assert config == SystemConfig()
        assert config.source is None

    def test_explicit_missing_file_is_an_error(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_system_config(str(tmp_path / "nope.yaml"))

    def test_relative_paths_resolve_against_the_file(self, tmp_path):
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "config.yaml").write_text(
            "data_dir: ../data\nlog_dir: ../logs\nbackup_dir: ../backups\n",
            encoding="utf-8",
        )
        config = load_system_config(str(config_dir / "config.yaml"))
        assert config.data_dir == str(config_dir / ".." / "data")
        assert config.source == str((config_dir / "config.yaml").resolve())

    def test_generated_default_round_trips(self, tmp_path):
        target = generate_default_config(tmp_path / "config" / "config.yaml")
        config = load_system_config(str(target))
        assert config.server_port == 8765
        assert config.gui_refresh_seconds == 5
        assert config.daemon_tick_seconds == 60.0
        assert config.quiet_hours is None
        assert config.backup_enabled is True
        assert config.backup_interval_hours == 24.0
        assert config.backup_keep == 14

    def test_generate_never_overwrites(self, tmp_path):
        target = tmp_path / "config.yaml"
        target.write_text("data_dir: keep-me\n", encoding="utf-8")
        generate_default_config(target)
        assert "keep-me" in target.read_text(encoding="utf-8")

    def test_env_var_search(self, tmp_path, monkeypatch):
        target = generate_default_config(tmp_path / "config.yaml")
        monkeypatch.setenv("PAIOS_CONFIG", str(target))
        assert load_system_config().source == str(target.resolve())

    def test_quiet_hours_and_overrides(self, tmp_path):
        (tmp_path / "config.yaml").write_text(
            "notifications:\n"
            "  quiet_hours: 22:00-07:00\n"
            "  cooldown_seconds: 60\n"
            "server:\n"
            "  port: 9999\n",
            encoding="utf-8",
        )
        config = load_system_config(str(tmp_path / "config.yaml"))
        assert config.quiet_hours == "22:00-07:00"
        assert config.notification_cooldown_seconds == 60
        assert config.server_port == 9999
