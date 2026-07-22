"""Registry port: HKCU Run-key startup registration.

A tiny surface so the installer logic never imports winreg directly —
tests use FakeRegistry, non-Windows dev runs use NullRegistry.
"""

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


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


class NullRegistry:
    """No-op for non-Windows development runs."""

    def set_run_value(self, name: str, command: str) -> None:
        pass

    def delete_run_value(self, name: str) -> None:
        pass

    def get_run_value(self, name: str) -> str | None:
        return None
