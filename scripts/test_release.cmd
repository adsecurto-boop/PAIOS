@echo off
rem Verify the built release: artifacts, checksums, version, payload,
rem and a sandboxed install/uninstall cycle.
python "%~dp0test_release.py" --full %*
