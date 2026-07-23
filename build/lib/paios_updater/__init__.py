"""PAIOS auto-updater (Milestone 20).

Standalone by construction: this package imports the standard library
ONLY — never paios, paios_gui or paios_launcher — so PAIOSUpdater.exe
can stop, replace and restart the application it updates without
sharing a line of runtime code with it. The launcher may import the
pure modules here (version comparison, release lookup) for its
periodic check; the reverse import never happens.

Pipeline (update.py):

    check (GitHub Releases, semver) -> download (PAIOSSetup.exe +
    SHA256SUMS.txt) -> verify (sha256) -> stop PAIOS -> backup
    (PAIOS.exe + installed paios* packages) -> install (run the new
    PAIOSSetup.exe) -> health check (installed version matches) ->
    restart; any failure after backup -> rollback from the backup.
"""
