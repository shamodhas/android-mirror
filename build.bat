@echo off
cd /d "%~dp0"
python icon_gen.py
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
pyinstaller --noconfirm --clean android_wifi_mirror.spec
if exist "C:\Program Files\Inno Setup 6\ISCC.exe" (
    "C:\Program Files\Inno Setup 6\ISCC.exe" installer.iss
)
pause