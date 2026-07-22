"""Single-instance detection: mutex (Windows) and lock-file guards."""

import os
import sys
import subprocess

import pytest

from paios_launcher.single_instance import (
    AlreadyRunningError,
    SingleInstance,
)


class TestFileGuard:
    def test_acquire_creates_lock_with_own_pid(self, tmp_path):
        lock = tmp_path / "launcher.lock"
        with SingleInstance(lock_file=lock) as guard:
            assert guard.acquired
            assert lock.read_text(encoding="utf-8") == str(os.getpid())
        assert not lock.exists()

    def test_second_acquisition_is_refused(self, tmp_path):
        lock = tmp_path / "launcher.lock"
        first = SingleInstance(lock_file=lock).acquire()
        try:
            with pytest.raises(AlreadyRunningError):
                SingleInstance(lock_file=lock).acquire()
        finally:
            first.release()

    def test_release_lets_the_next_instance_in(self, tmp_path):
        lock = tmp_path / "launcher.lock"
        SingleInstance(lock_file=lock).acquire().release()
        second = SingleInstance(lock_file=lock).acquire()
        assert second.acquired
        second.release()

    def test_stale_lock_is_taken_over(self, tmp_path):
        lock = tmp_path / "launcher.lock"
        # A pid that is certainly dead: a subprocess we already reaped.
        probe = subprocess.run(
            [sys.executable, "-c", "print('x')"], capture_output=True
        )
        dead_pid = 2 ** 22 + 1  # far outside plausible live pid space
        del probe
        lock.write_text(str(dead_pid), encoding="utf-8")
        guard = SingleInstance(lock_file=lock).acquire()
        assert guard.acquired
        assert lock.read_text(encoding="utf-8") == str(os.getpid())
        guard.release()

    def test_garbage_lock_is_taken_over(self, tmp_path):
        lock = tmp_path / "launcher.lock"
        lock.write_text("not-a-pid", encoding="utf-8")
        guard = SingleInstance(lock_file=lock).acquire()
        assert guard.acquired
        guard.release()

    def test_acquire_is_idempotent(self, tmp_path):
        lock = tmp_path / "launcher.lock"
        guard = SingleInstance(lock_file=lock)
        guard.acquire()
        guard.acquire()
        assert guard.acquired
        guard.release()
        assert not guard.acquired


@pytest.mark.skipif(os.name != "nt", reason="Windows named-mutex guard")
class TestMutexGuard:
    def test_mutex_refuses_second_holder(self):
        name = f"PAIOS.Test.SingleInstance.{os.getpid()}"
        first = SingleInstance(name=name).acquire()
        try:
            with pytest.raises(AlreadyRunningError):
                SingleInstance(name=name).acquire()
        finally:
            first.release()
        # Released: acquirable again.
        second = SingleInstance(name=name).acquire()
        assert second.acquired
        second.release()
