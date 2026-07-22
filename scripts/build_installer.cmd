@echo off
rem Build the complete release: PAIOS.exe + PAIOSUpdater.exe +
rem PAIOSUninstall.exe + PAIOSSetup.exe + SHA256SUMS.txt +
rem RELEASE_NOTES.md. Output: dist\product\PAIOSSetup.exe
python "%~dp0build_installer.py" %*
