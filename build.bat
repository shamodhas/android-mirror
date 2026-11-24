@echo off
cd /d "%~dp0"
python icon_gen.py
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
pyinstaller --noconfirm --clean android_wifi_mirror.spec
pause