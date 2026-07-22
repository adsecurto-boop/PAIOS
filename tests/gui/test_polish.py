"""M20 polish: the toolbar search filter, the log viewer's states and
the backups page wiring.
"""

from paios_gui.config import GuiConfig
from paios_gui.log_page import LogPage, newest_log, tail_text
from paios_gui.pages import BackupsPage

from tests.gui.test_client_m20 import RecordingClient
from tests.gui.test_planning_page import StubWindow

GOALS_ROW = 4  # nav index of the Goals page


class TestSearchFilter:
    def test_search_hides_non_matching_rows(self, window, client):
        client.create_goal("Alpha goal", "first")
        client.create_goal("Beta goal", "second")
        window.navigation.setCurrentRow(GOALS_ROW)
        page = window.current_page()
        names = [row["name"] for row in page._rows]
        alpha, beta = names.index("Alpha goal"), names.index("Beta goal")
        window.search_edit.setText("alpha")
        assert page.table.isRowHidden(alpha) is False
        assert page.table.isRowHidden(beta) is True
        window.search_edit.setText("")
        assert page.table.isRowHidden(beta) is False

    def test_filter_survives_refresh(self, window, client):
        client.create_goal("Gamma goal", "third")
        window.navigation.setCurrentRow(GOALS_ROW)
        page = window.current_page()
        window.search_edit.setText("no-such-goal")
        page.refresh(client)
        assert all(
            page.table.isRowHidden(index)
            for index in range(len(page._rows))
        )
        window.search_edit.setText("")


class LogStubWindow(StubWindow):
    def __init__(self, log_dir) -> None:
        super().__init__(client=None)
        self.config = GuiConfig(log_dir=log_dir)


class TestLogPage:
    def test_unset_log_dir_shows_friendly_empty_state(self, qapp):
        page = LogPage(LogStubWindow(None))
        assert "No log directory configured" in page.file_label.text()
        assert "--log-dir" in page.viewer.toPlainText()

    def test_empty_directory_says_no_logs_yet(self, qapp, tmp_path):
        page = LogPage(LogStubWindow(str(tmp_path)))
        assert "No *.log files" in page.file_label.text()

    def test_tail_shows_newest_log(self, qapp, tmp_path):
        stale = tmp_path / "old.log"
        stale.write_text("ancient line\n", encoding="utf-8")
        fresh = tmp_path / "paios-gui.log"
        fresh.write_text(
            "\n".join(f"line {i}" for i in range(500)), encoding="utf-8"
        )
        import os

        os.utime(stale, (1, 1))  # force mtime ordering
        assert newest_log(str(tmp_path)) == fresh
        assert tail_text(fresh).splitlines()[0] == "line 100"  # 400 tail
        page = LogPage(LogStubWindow(str(tmp_path)))
        assert "paios-gui.log" in page.file_label.text()
        assert "line 499" in page.viewer.toPlainText()
        assert "ancient" not in page.viewer.toPlainText()


class TestBackupsPage:
    def test_backups_table_and_create(self, qapp):
        client = RecordingClient(
            {
                ("GET", "/backups"): {
                    "backups": [
                        {"name": "paios-1.zip", "size_bytes": 2048}
                    ]
                }
            }
        )
        page = BackupsPage(StubWindow(client))
        page.refresh(client)
        assert page.table.rowCount() == 1
        assert page.cells(page._rows[0]) == (
            "paios-1.zip", "2,048 bytes"
        )
        page._on_create()
        assert ("POST", "/backups", {}) in client.calls

    def test_live_backup_roundtrip(self, client):
        created = client.create_backup()
        names = [backup["name"] for backup in client.list_backups()]
        assert created["name"] in names
        restored = client.restore_backup(created["name"])
        assert "restart" in restored["note"].lower()
