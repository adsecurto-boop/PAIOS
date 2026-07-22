"""Registry port: HKCU Run-key startup registration and the HKCU
Add/Remove Programs uninstall entry.

A tiny surface so the installer logic never imports winreg directly —
tests use FakeRegistry, non-Windows dev runs use NullRegistry.
"""

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
UNINSTALL_KEY = (
    r"Software\Microsoft\Windows\CurrentVersion\Uninstall\PAIOS"
)


class WindowsRegistry:
    """Real HKCU access (Windows only)."""

    def set_run_value(self, name: str, command: str) -> None:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, command)

    def delete_run_value(self, name: str) -> None:
        import winreg

        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE
            ) as key:
                winreg.DeleteValue(key, name)
        except FileNotFoundError:
            pass

    def get_run_value(self, name: str) -> str | None:
        import winreg

        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ
            ) as key:
                value, _kind = winreg.QueryValueEx(key, name)
                return value
        except FileNotFoundError:
            return None

    # --- Add/Remove Programs entry (per-user; no elevation needed) ------

    def set_uninstall_entry(self, values: dict) -> None:
        """Write the HKCU uninstall key (Settings > Apps sees it)."""
        import winreg

        with winreg.CreateKey(
            winreg.HKEY_CURRENT_USER, UNINSTALL_KEY
        ) as key:
            for name, value in values.items():
                winreg.SetValueEx(
                    key, name, 0, winreg.REG_SZ, str(value)
                )

    def delete_uninstall_entry(self) -> None:
        import winreg

        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY)
        except FileNotFoundError:
            pass

    def get_uninstall_entry(self) -> dict | None:
        import winreg

        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, UNINSTALL_KEY, 0, winreg.KEY_READ
            ) as key:
                values = {}
                index = 0
                while True:
                    try:
                        name, value, _kind = winreg.EnumValue(key, index)
                    except OSError:
                        break
                    values[name] = value
                    index += 1
                return values
        except FileNotFoundError:
            return None


class NullRegistry:
    """No-op for non-Windows development runs."""

    def set_run_value(self, name: str, command: str) -> None:
        pass

    def delete_run_value(self, name: str) -> None:
        pass

    def get_run_value(self, name: str) -> str | None:
        return None

    def set_uninstall_entry(self, values: dict) -> None:
        pass

    def delete_uninstall_entry(self) -> None:
        pass

    def get_uninstall_entry(self) -> dict | None:
        return None
