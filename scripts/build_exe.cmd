@echo off
rem Build the standalone application (PAIOS.exe onedir tree, updater,
rem uninstaller) without the installer. Output: dist\product\
python "%~dp0build_installer.py" --skip-setup %*
