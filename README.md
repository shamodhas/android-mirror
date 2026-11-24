# Air Screen — Android WiFi Mirror (`android-wifi-mirror-scrcpy-pc`)

Automated Windows desktop utility for wireless Android screen mirroring over Wi-Fi, unifying automatic `adb` + `scrcpy` setup, USB-to-Wi-Fi TCP/IP switching, Android 11+ wireless pairing, session memory, and version-safe mirroring across `scrcpy` v1, v2, and newer releases.

## Features
- **Zero-manual tool setup:** Locates bundled or existing `adb.exe` and `scrcpy.exe` or downloads and safely extracts the Windows release into `%LOCALAPPDATA%\android-wifi-mirror-scrcpy-pc\tools` after stopping any locked `adb`/`scrcpy` processes.
- **Automatic startup check:** Detects connected USB or wireless ADB devices on launch, resolves the phone's IPv4 address (`wlan0` / route fallback), reconnects if the IP changed, and remembers your last session in `%LOCALAPPDATA%\android-wifi-mirror-scrcpy-pc\session.json`.
- **One-click USB -> Wi-Fi:** Enables TCP/IP (`5555` by default) on a USB-connected device, detects its Wi-Fi IP, connects over TCP/IP, and launches mirroring.
- **Android 11+ wireless pairing:** Pairs via `IP:Port` + pairing code and connects to the Wireless Debugging port from a dedicated tab.
- **Version-safe `scrcpy` execution:** Reads `scrcpy --version` at runtime and uses compatible flags across `scrcpy` v1.x, v2.x, and modern releases without freezing the UI thread.

## Project Structure
- `app.py` — Main Tkinter GUI, background worker engine, ADB/IP controller, and version-aware `scrcpy` launcher.
- `icon_gen.py` — Generates multi-resolution `assets/app.ico` using Pillow.
- `android_wifi_mirror.spec` — PyInstaller build specification building `AirScreen.exe`.
- `installer.iss` — Inno Setup script creating the **Air Screen** installer, **Air Screen** Desktop/Start Menu shortcuts, and optional `PATH` environment setup.
- `build.bat` — Generates the icon, builds `dist\AirScreen.exe`, and compiles `Output\AirScreen-Setup-v2.0.0.exe` when Inno Setup 6 is installed.
- `requirements.txt` — Build dependencies (`pillow`, `pyinstaller`).

## Clone & Setup
```bash
git clone [https://github.com/shamodhas/android-wifi-mirror-scrcpy-pc.git](https://github.com/shamodhas/android-wifi-mirror-scrcpy-pc.git)
cd android-wifi-mirror-scrcpy-pc
```

### Build & Usage
1. Install dependencies:
```bash
pip install -r requirements.txt
```
2. Build the executable by running `build.bat` (outputs `dist\AirScreen.exe`).

3. Ensure USB Debugging (or Wireless Debugging on Android 11+) is enabled on your phone and both devices are on the same Wi-Fi network, then launch `AirScreen.exe`.

---