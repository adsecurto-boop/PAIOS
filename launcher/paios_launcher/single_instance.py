"""Single-instance detection for the launcher.

On Windows the guard is a named kernel mutex (the "Global" namespace
is not used — one launcher per session is the product behaviour, and a
non-elevated process cannot always create Global objects). The mutex
disappears with the process, so crashes never leave a stale guard.

Everywhere else — and as the seam tests use to exercise the stale-lock
path deterministically — a lock file with the owner's PID is used; a
lock whose PID is no longer alive is stale and is taken over.
"""

import os
from pathlib import Path

MUTEX_NAME = "PAIOS.Launcher.SingleInstance"


class AlreadyRunningError(RuntimeError):
    """Another launcher instance owns the guard."""


def _pid_alive(pid: int) -> bool:
    if os.name == "nt":
        import ctypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, False, pid
        )
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return False
            return code.value == STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


class SingleInstance:
    """Acquire on entry, release on exit; second acquisition raises.

    ``lock_file`` forces the file-based guard (tests, non-Windows).
    Without it, Windows uses the named mutex.
    """

    def __init__(
        self,
        name: str = MUTEX_NAME,
        lock_file: str | Path | None = None,
    ) -> None:
        self._name = name
        self._lock_path = Path(lock_file) if lock_file else None
        self._mutex_handle = None
        self._owns_file = False

    @property
    def acquired(self) -> bool:
        return self._mutex_handle is not None or self._owns_file

    def acquire(self) -> "SingleInstance":
        if self.acquired:
            return self
        if self._lock_path is None and os.name == "nt":
            self._acquire_mutex()
        else:
            self._acquire_file()
        return self

    def release(self) -> None:
        if self._mutex_handle is not None:
            import ctypes

            kernel32 = ctypes.windll.kernel32
            kernel32.ReleaseMutex(self._mutex_handle)
            kernel32.CloseHandle(self._mutex_handle)
            self._mutex_handle = None
        if self._owns_file and self._lock_path is not None:
            self._lock_path.unlink(missing_ok=True)
            self._owns_file = False

    # --- context manager ---------------------------------------------------

    def __enter__(self) -> "SingleInstance":
        return self.acquire()

    def __exit__(self, *exc_info) -> None:
        self.release()

    # --- strategies --------------------------------------------------------

    def _acquire_mutex(self) -> None:
        import ctypes

        ERROR_ALREADY_EXISTS = 183
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.CreateMutexW(None, True, self._name)
        if not handle:
            raise OSError("CreateMutexW failed for the single-instance guard")
        if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
            kernel32.CloseHandle(handle)
            raise AlreadyRunningError(
                "PAIOS is already running (launcher mutex is held)."
            )
        self._mutex_handle = handle

    def _acquire_file(self) -> None:
        if self._lock_path is None:
            raise OSError("file guard requested without a lock file path")
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        while True:
            try:
                descriptor = os.open(
                    self._lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY
                )
            except FileExistsError:
                owner = self._read_owner()
                if owner is not None and _pid_alive(owner):
                    raise AlreadyRunningError(
                        f"PAIOS is already running (pid {owner},"
                        f" lock {self._lock_path})."
                    ) from None
                # Stale lock: its owner is gone — take it over.
                self._lock_path.unlink(missing_ok=True)
                continue
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(str(os.getpid()))
            self._owns_file = True
            return

    def _read_owner(self) -> int | None:
        try:
            return int(self._lock_path.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            return None
