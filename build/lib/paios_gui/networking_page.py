"""The Networking page (M21, Phase 3): run and reach PAIOS without ever
opening a terminal.

Shows the live picture — hostname, LAN IP, port, server + API status,
access mode, firewall and Wi-Fi — and gives every control as a button:

    * Start / Stop / Restart the API (a local process controller, since
      a dead server cannot be reached over REST);
    * Local Only  <->  Local Network (the persisted access mode; the
      server rebinds to it on the next start);
    * Copy the address a phone should use, and show it as a QR code;
    * Open the Windows firewall for the port (with a clear message when
      it needs administrator rights).

Facts come from GET /system/network; mutations POST/PUT there. The page
never raises into the poll loop.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from paios_gui.client import ApiResponseError, ApiUnreachable
from paios_gui.server_control import ServerController
from paios_gui.theme import ACCENT, BAD, GOOD, TEXT_DIM, WARN


class NetworkingPage(QWidget):
    title = "Networking"

    #: Facts shown in the status grid: (row label, state-key).
    _FACTS = (
        ("Computer name", "hostname"),
        ("Local IP address", "lan_ip"),
        ("Port", "port"),
        ("Wi-Fi network", "wifi_ssid"),
    )

    def __init__(self, window) -> None:
        super().__init__()
        self._window = window
        self._controller = ServerController(window.client.base_url)
        self._last: dict = {}

        outer = QVBoxLayout(self)
        heading = QLabel("NETWORKING")
        heading.setObjectName("sectionTitle")
        outer.addWidget(heading)

        # --- status chips row --------------------------------------------
        chips = QHBoxLayout()
        self.server_chip = self._chip("Server")
        self.mode_chip = self._chip("Mode")
        self.firewall_chip = self._chip("Firewall")
        self.discovery_chip = self._chip("Discovery")
        for chip in (
            self.server_chip,
            self.mode_chip,
            self.firewall_chip,
            self.discovery_chip,
        ):
            chips.addWidget(chip)
        chips.addStretch(1)
        outer.addLayout(chips)

        # --- facts grid --------------------------------------------------
        facts_frame = QFrame()
        facts_frame.setObjectName("card")
        self._grid = QGridLayout(facts_frame)
        self._value_labels: dict[str, QLabel] = {}
        for row, (label_text, key) in enumerate(self._FACTS):
            name = QLabel(label_text)
            name.setObjectName("subtitle")
            value = QLabel("—")
            self._grid.addWidget(name, row, 0)
            self._grid.addWidget(value, row, 1)
            self._value_labels[key] = value
        outer.addWidget(facts_frame)

        # --- server controls ---------------------------------------------
        outer.addWidget(self._section_label("Server"))
        server_row = QHBoxLayout()
        self.start_button = self._button("Start", self._on_start, server_row)
        self.stop_button = self._button("Stop", self._on_stop, server_row)
        self.restart_button = self._button(
            "Restart", self._on_restart, server_row
        )
        server_row.addStretch(1)
        outer.addLayout(server_row)

        # --- access mode -------------------------------------------------
        outer.addWidget(self._section_label("Access"))
        self.access_hint = QLabel("")
        self.access_hint.setObjectName("subtitle")
        self.access_hint.setWordWrap(True)
        outer.addWidget(self.access_hint)
        access_row = QHBoxLayout()
        self.local_button = self._button(
            "Local Only", lambda: self._on_set_mode("local"), access_row
        )
        self.lan_button = self._button(
            "Local Network", lambda: self._on_set_mode("lan"), access_row
        )
        self.firewall_button = self._button(
            "Open firewall", self._on_open_firewall, access_row
        )
        access_row.addStretch(1)
        outer.addLayout(access_row)

        # --- address + QR ------------------------------------------------
        outer.addWidget(self._section_label("Connect a phone"))
        self.address_label = QLabel("—")
        self.address_label.setObjectName("todayHeader")
        self.address_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        outer.addWidget(self.address_label)
        address_row = QHBoxLayout()
        self.copy_button = self._button(
            "Copy address", self._on_copy_address, address_row
        )
        self.qr_button = self._button(
            "Show QR code", self._on_toggle_qr, address_row
        )
        address_row.addStretch(1)
        outer.addLayout(address_row)
        self.qr_label = QLabel("")
        self.qr_label.hide()
        outer.addWidget(self.qr_label)
        self.status_line = QLabel("")
        self.status_line.setObjectName("subtitle")
        self.status_line.setWordWrap(True)
        outer.addWidget(self.status_line)

        # --- remote access (M23) -----------------------------------------
        outer.addWidget(self._build_remote_section())

        outer.addStretch(1)

    # --- remote access section -------------------------------------------

    def _build_remote_section(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("card")
        layout = QVBoxLayout(frame)
        title_row = QHBoxLayout()
        heading = QLabel("Remote access — reach PAIOS from anywhere")
        heading.setObjectName("cardTitle")
        title_row.addWidget(heading)
        self.remote_chip = QLabel("Off")
        self.remote_chip.setObjectName("statusChip")
        self.remote_chip.setStyleSheet(f"background:{TEXT_DIM}; color:#14161a;")
        title_row.addWidget(self.remote_chip)
        title_row.addStretch(1)
        layout.addLayout(title_row)

        hint = QLabel(
            "Run the PAIOS relay on any always-on server (a cheap VPS,"
            " a Raspberry Pi…) and paste its address below. Your phone"
            " then reaches PAIOS on mobile data or any Wi-Fi — your"
            " computer is never exposed to the internet."
        )
        hint.setObjectName("subtitle")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        form = QFormLayout()
        self.remote_enable = QCheckBox("Enable remote access")
        form.addRow(self.remote_enable)
        self.relay_url_edit = QLineEdit()
        self.relay_url_edit.setPlaceholderText("https://relay.example.com")
        form.addRow("Relay address", self.relay_url_edit)
        self.relay_account_edit = QLineEdit()
        self.relay_account_edit.setPlaceholderText("default")
        form.addRow("Account", self.relay_account_edit)
        self.relay_key_edit = QLineEdit()
        self.relay_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.relay_key_edit.setPlaceholderText(
            "account key — stored encrypted for your Windows account"
        )
        form.addRow("Account key", self.relay_key_edit)
        layout.addLayout(form)

        button_row = QHBoxLayout()
        self.relay_save_button = QPushButton("Save & Connect")
        self.relay_save_button.setObjectName("primaryAction")
        self.relay_save_button.clicked.connect(self._on_save_relay)
        button_row.addWidget(self.relay_save_button)
        button_row.addStretch(1)
        layout.addLayout(button_row)
        return frame

    # --- builders --------------------------------------------------------

    def _chip(self, text: str) -> QLabel:
        chip = QLabel(text)
        chip.setObjectName("statusChip")
        chip.setStyleSheet(f"background:{TEXT_DIM}; color:#14161a;")
        return chip

    def _section_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("cardTitle")
        return label

    def _button(self, text: str, handler, row) -> QPushButton:
        button = QPushButton(text)
        button.clicked.connect(handler)
        row.addWidget(button)
        return button

    def _paint_chip(self, chip: QLabel, color: str, text: str) -> None:
        chip.setText(text)
        chip.setStyleSheet(f"background:{color}; color:#14161a;")

    # --- data ------------------------------------------------------------

    def refresh(self, client) -> None:
        """Read facts + server status; repaint. Never raises."""
        try:
            facts = client.system_network()
        except ApiUnreachable:
            facts = {}
            self._paint_chip(self.server_chip, BAD, "Server: offline")
        except ApiResponseError as error:
            self.status_line.setText(f"Server error: {error}")
            return
        self._last = facts
        self._paint_facts(facts)
        self._paint_server_state()
        self._refresh_relay(client)

    def _refresh_relay(self, client) -> None:
        try:
            relay = client.system_relay()
        except (ApiUnreachable, ApiResponseError):
            return
        # Populate fields without clobbering the key (never returned).
        if not self.relay_url_edit.hasFocus():
            self.relay_url_edit.setText(relay.get("relay_url") or "")
        if not self.relay_account_edit.hasFocus():
            self.relay_account_edit.setText(relay.get("account") or "default")
        self.remote_enable.setChecked(bool(relay.get("enabled")))
        if relay.get("has_key"):
            self.relay_key_edit.setPlaceholderText("•••••••• (saved)")
        self._paint_relay(relay)

    def _paint_relay(self, relay: dict) -> None:
        if not relay.get("enabled"):
            self._paint_chip(self.remote_chip, TEXT_DIM, "Off")
        elif relay.get("connected"):
            self._paint_chip(self.remote_chip, GOOD, "Connected")
        elif relay.get("last_error"):
            self._paint_chip(self.remote_chip, BAD, "Disconnected")
        else:
            self._paint_chip(self.remote_chip, WARN, "Connecting…")

    def _paint_facts(self, facts: dict) -> None:
        for key, label in self._value_labels.items():
            value = facts.get(key)
            label.setText(str(value) if value not in (None, "") else "—")

        mode = facts.get("mode", "local")
        if mode == "lan":
            self._paint_chip(self.mode_chip, GOOD, "Local Network")
            self.access_hint.setText(
                "Local Network: phones paired with this desktop can reach"
                " PAIOS over the same Wi-Fi. Keep the firewall open for the"
                " port below."
            )
        else:
            self._paint_chip(self.mode_chip, ACCENT, "Local Only")
            self.access_hint.setText(
                "Local Only: PAIOS accepts connections from this computer"
                " alone (the safe default). Switch to Local Network to"
                " connect your phone over Wi-Fi."
            )
        self.local_button.setEnabled(mode != "local")
        self.lan_button.setEnabled(mode != "lan")

        firewall = facts.get("firewall_rule")
        if firewall is True:
            self._paint_chip(self.firewall_chip, GOOD, "Firewall: open")
            self.firewall_button.setEnabled(False)
        elif firewall is False:
            self._paint_chip(self.firewall_chip, WARN, "Firewall: closed")
            self.firewall_button.setEnabled(True)
        else:
            self._paint_chip(self.firewall_chip, TEXT_DIM, "Firewall: n/a")
            self.firewall_button.setEnabled(False)

        # Discovery: only meaningful in Local Network mode.
        if mode != "lan":
            self._paint_chip(
                self.discovery_chip, TEXT_DIM, "Discovery: off"
            )
        elif facts.get("discovering"):
            self._paint_chip(
                self.discovery_chip, GOOD, "Discoverable on Wi-Fi"
            )
        else:
            self._paint_chip(
                self.discovery_chip, WARN, "Discovery: starting…"
            )

        address = facts.get("lan_url") if mode == "lan" else facts.get(
            "loopback_url"
        )
        self.address_label.setText(address or "—")
        # Refresh a shown QR to match the current address.
        if not self.qr_label.isHidden() and address:
            self._render_qr(address)

    def _paint_server_state(self) -> None:
        state = self._controller.status()
        if state["reachable"]:
            managed = "" if state["external"] else " (managed here)"
            self._paint_chip(
                self.server_chip, GOOD, f"Server: running{managed}"
            )
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(not state["external"])
            self.restart_button.setEnabled(True)
        elif state["state"] == "starting":
            self._paint_chip(self.server_chip, WARN, "Server: starting…")
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self.restart_button.setEnabled(False)
        else:
            self._paint_chip(self.server_chip, BAD, "Server: stopped")
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self.restart_button.setEnabled(True)

    # --- server actions --------------------------------------------------

    def _on_start(self) -> None:
        self._report(self._controller.start(), "started")

    def _on_stop(self) -> None:
        self._report(self._controller.stop(), "stopped")

    def _on_restart(self) -> None:
        self._report(self._controller.restart(), "started")

    def _report(self, result: dict, ok_key: str) -> None:
        self.status_line.setText(result.get("reason", ""))
        kind = "ok" if result.get(ok_key) else "warn"
        self._window.notify(result.get("reason", ""), kind)
        self._paint_server_state()

    # --- mode + firewall -------------------------------------------------

    def _on_set_mode(self, mode: str) -> None:
        def call():
            result = self._window.client.set_network_mode(mode)
            self.status_line.setText(result.get("note", ""))

        self._window.run_action(
            call,
            "Local Network enabled — restart the server to apply"
            if mode == "lan"
            else "Local Only enabled — restart the server to apply",
        )

    def _on_open_firewall(self) -> None:
        try:
            result = self._window.client.open_firewall()
        except ApiUnreachable as error:
            self.status_line.setText(f"Offline: {error}")
            return
        except ApiResponseError as error:
            self.status_line.setText(f"Server error: {error}")
            return
        self.status_line.setText(result.get("detail", ""))
        self._window.notify(
            result.get("detail", ""),
            "ok" if result.get("ok") else "warn",
        )

    # --- address + QR ----------------------------------------------------

    def _on_copy_address(self) -> None:
        address = self.address_label.text()
        if not address or address == "—":
            return
        QApplication.clipboard().setText(address)
        self._window.notify(f"Copied {address}", "ok")

    def _on_toggle_qr(self) -> None:
        if not self.qr_label.isHidden():
            self.qr_label.hide()
            self.qr_button.setText("Show QR code")
            return
        address = self.address_label.text()
        if not address or address == "—":
            return
        self._render_qr(address)
        self.qr_label.show()
        self.qr_button.setText("Hide QR code")

    def _render_qr(self, address: str) -> None:
        from paios_gui import qr

        self.qr_label.setPixmap(qr.pixmap(address))

    # --- remote actions --------------------------------------------------

    def _on_save_relay(self) -> None:
        url = self.relay_url_edit.text().strip()
        enabled = self.remote_enable.isChecked()
        if enabled and not url:
            self._window.notify(
                "Enter the relay address before enabling remote access.",
                "warn",
            )
            return

        def call():
            result = self._window.client.set_relay_config(
                enabled=enabled,
                relay_url=url,
                account=self.relay_account_edit.text().strip() or "default",
                account_key=self.relay_key_edit.text().strip() or None,
            )
            self.relay_key_edit.clear()
            if result.get("warning"):
                self._window.notify(result["warning"], "warn")
            self._paint_relay(result)

        self._window.run_action(
            call,
            "Remote access enabled" if enabled else "Remote access disabled",
        )
