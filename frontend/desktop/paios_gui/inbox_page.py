"""The Quick Capture page (M20): brain dump now, organize later.

Split from pages.py so the capture surface (and its assistant
suggestion plumbing) stays a small focused module. Same discipline:
every action is one REST call; the suggested kind is the server's —
this page only displays and forwards it.
"""

from PySide6.QtWidgets import QLabel, QLineEdit, QPushButton

from paios_gui import format as fmt
from paios_gui.dialogs import ConvertInboxDialog, confirm
from paios_gui.pages import TablePage


class InboxPage(TablePage):
    """Quick Capture (M20): brain dump now, organize later.

    Plain Enter captures instantly and clears the field. After every
    refresh the open items are sent to POST /assistant/plan and the
    suggested kind is shown as a chip per row — with a one-click
    "Convert as suggested" beside the manual Convert… menu. The
    suggestion is the server's; this page only displays and forwards
    it."""

    title = "Quick Capture"
    columns = ("Text", "Status", "Suggested", "Created", "Converted to", "")
    empty_hint = (
        "Nothing captured yet — type above to brain-dump (Ctrl+I from"
        " anywhere), press Enter, done."
    )

    def __init__(self, window) -> None:
        super().__init__(window)
        self._suggestions: dict[str, str] = {}
        subtitle = QLabel("Brain dump — capture now, organize later.")
        subtitle.setObjectName("subtitle")
        self.layout().insertWidget(1, subtitle)

    def _build_toolbar(self) -> None:
        self.capture_edit = QLineEdit()
        self.capture_edit.setPlaceholderText(
            "Capture a thought and press Enter…"
        )
        self.capture_edit.returnPressed.connect(self._on_add)
        self.toolbar.addWidget(self.capture_edit, stretch=1)
        self._add_button("Add", self._on_add)
        self._add_button("Convert…", self._on_convert)
        self._add_button("Archive", self._on_archive)
        self._add_button("Delete…", self._on_delete)

    def fetch(self, client):
        items = client.list_inbox()
        self._suggestions = self._fetch_suggestions(client, items)
        return items

    def _fetch_suggestions(self, client, items) -> dict[str, str]:
        """Ask the assistant to classify the open captures; text -> kind.
        Best effort: any failure means no chips, never an error."""
        open_texts = [
            item["text"] for item in items if item["status"] == "open"
        ]
        if not open_texts:
            return {}
        try:
            proposal = client.assistant_plan("\n".join(open_texts))
        except Exception:
            return {}
        return {
            item["text"]: item["kind"]
            for item in proposal.get("items") or []
            if item.get("text")
            and item.get("kind") in ("goal", "project", "event")
        }

    def refresh(self, client) -> None:
        super().refresh(client)
        for row_index, row in enumerate(self._rows):
            kind = self._suggestions.get(row["text"])
            if row["status"] == "open" and kind:
                button = QPushButton("Convert as suggested")
                button.clicked.connect(
                    lambda _checked=False, item=row, target=kind: (
                        self._convert_as(item, target)
                    )
                )
                self.table.setCellWidget(
                    row_index, len(self.columns) - 1, button
                )

    def cells(self, row):
        kind = self._suggestions.get(row["text"])
        suggested = (
            f"Suggested: {kind.title()}"
            if row["status"] == "open" and kind
            else "—"
        )
        return (
            row["text"],
            row["status"],
            suggested,
            fmt.day_time(row["created_at"]),
            fmt.text_or_dash(row.get("converted_to")),
            "",
        )

    def _convert_as(self, item: dict, kind: str) -> None:
        self._window.run_action(
            lambda: self._window.client.convert_inbox(item["id"], kind),
            f"Converted to {kind}: {item['text']}",
        )

    def focus_capture(self) -> None:
        """Public: also the window's Ctrl+I target."""
        self.capture_edit.setFocus()

    def showEvent(self, event) -> None:  # Qt naming
        """Landing on Quick Capture puts the caret in the capture box —
        typing is the page's primary action."""
        super().showEvent(event)
        self.capture_edit.setFocus()

    def _on_add(self) -> None:
        text = self.capture_edit.text().strip()
        if not text:
            self._window.notify("Type something to capture.", "warn")
            return
        self.capture_edit.clear()
        self._window.run_action(
            lambda: self._window.client.add_inbox(text),
            f"Captured: {text}",
        )

    def _on_convert(self) -> None:
        row = self._require_selection()
        if row is None:
            return
        dialog = ConvertInboxDialog(row["text"], self)
        if dialog.exec():
            values = dialog.values()
            target = values.pop("to")
            self._window.run_action(
                lambda: self._window.client.convert_inbox(
                    row["id"], target, **values
                ),
                f"Converted to {target}: {row['text']}",
            )

    def _on_archive(self) -> None:
        row = self._require_selection()
        if row is None:
            return
        self._window.run_action(
            lambda: self._window.client.archive_inbox(row["id"]),
            f"Archived: {row['text']}",
        )

    def _on_delete(self) -> None:
        row = self._require_selection()
        if row is None:
            return
        if not confirm(
            self, "Delete capture", f"Delete '{row['text']}' permanently?"
        ):
            return
        self._window.run_action(
            lambda: self._window.client.delete_inbox(row["id"]),
            f"Deleted: {row['text']}",
        )

