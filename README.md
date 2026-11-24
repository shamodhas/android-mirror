# Air Screen — User Guide & Developer Manual

**Air Screen** (`android-wifi-mirror-scrcpy-pc`) is a Windows desktop app that lets you mirror your Android phone's screen onto your PC over Wi-Fi without cables, automatically handling `adb` and `scrcpy` setup along the way.

---

## How to Use (User Manual)

### 1. Install or Open Air Screen
* **Installer (`AirScreen-Setup-v3.0.0.exe`):** Run the installer to install **Air Screen** (`C:\Program Files\Air Screen\AirScreen.exe`), create Desktop and Start Menu shortcuts named **Air Screen**, and optionally add the bundled tools folder to your User `PATH`.
* **Portable (`AirScreen.exe`):** Double-click `AirScreen.exe` directly from your folder.
* On first launch, if `adb.exe` and `scrcpy.exe` are not already present, **Air Screen** automatically downloads and extracts them into `%LOCALAPPDATA%\android-wifi-mirror-scrcpy-pc\tools`.

### 2. Prepare Your Android Phone
Make sure your Android phone and Windows PC are connected to the **same Wi-Fi network**:
* Open **Settings -> About phone** and tap **Build number** **7 times** to unlock **Developer options**.
* Go to **Settings -> System -> Developer options** (or **Developer options**):
  * For **USB -> Wi-Fi setup:** Turn on **USB debugging**.
  * For **Android 11+ wireless pairing:** Turn on **Wireless debugging**.

### 3. Connect & Mirror Your Screen
* **Option A — One-Click USB to Wi-Fi (Easiest First Time):**
  * Plug your phone into the PC with a USB cable and tap **Allow** on the **Allow USB debugging?** prompt on your phone.
  * In **Air Screen**, click **Auto-Connect & Mirror**. The app enables TCP/IP (`5555` by default), detects your phone's Wi-Fi IP address, connects wirelessly, and opens the mirror window.
  * Once mirroring starts over Wi-Fi, you can unplug the USB cable.
* **Option B — Android 11+ Wireless Pairing (No Cable Needed):**
  * On your phone's **Wireless debugging** screen, tap **Pair device with pairing code** to view the **IP address & Port** and **6-digit Wi-Fi pairing code**.
  * In **Air Screen**, open the **Pair (Android 11+)** tab, enter the **Pairing IP:Port**, **6-Digit Pairing Code**, and the main **Connect Port** shown on the Wireless debugging screen, then click **Pair & Mirror**.
* **Option C — Reconnect Using Saved or Entered IP:**
  * Your last IP, port, resolution, toggles, and window preference are saved in `%LOCALAPPDATA%\android-wifi-mirror-scrcpy-pc\session.json`.
  * Enter or keep the phone's Wi-Fi IPv4 address on the **Auto Wireless Mirror** tab and click **Auto-Connect & Mirror**.

### 4. Controls & Options Explained
* **Active Device / Scan / Disconnect TCP:** Refresh connected ADB targets, pick a specific serial or leave on `Auto`, or disconnect active wireless TCP sessions.
* **Port:** TCP port used for wireless ADB (`5555` by default).
* **Max Res:** Caps the longest screen dimension (`800`, `1024`, `1280`, `1920`, or `0` for full resolution) for smoother performance over Wi-Fi.
* **Screen Off:** Turns off the phone display while mirroring to PC (`--turn-screen-off`).
* **Stay Awake:** Keeps the phone screen awake while connected (`--stay-awake`).
* **Close settings window after mirror opens:** Hides the **Air Screen** settings window automatically once the mirror window launches (uncheck if you want to keep the settings window open).
* **Stop Mirror:** Stops the active `scrcpy` mirror window.
* **Re-download / Update Tools:** Stops running `adb.exe` / `scrcpy.exe` processes to prevent file locks and downloads/extracts the latest Windows `scrcpy` release.

### Troubleshooting Tips
* **Connection failed:** Confirm both devices are on the same Wi-Fi network (guest/client-isolated Wi-Fi networks often block device-to-device traffic), check the IP and port, and verify debugging is still enabled on the phone.
* **Tools update locked:** Click **Re-download / Update Tools**—the app automatically terminates locked `adb.exe` and `scrcpy.exe` processes before extracting updates.

---

## Development & Build Guide

### Project Structure
* `app.py` — Main Tkinter GUI (`AirScreenApp`), background worker threads, multi-device ADB/IP controller, process/auto-close handling, and `scrcpy` launcher.
* `icon_gen.py` — Generates multi-resolution `assets\app.ico` using Pillow.
* `android_wifi_mirror.spec` — PyInstaller specification building `dist\AirScreen.exe`.
* `installer.iss` — Inno Setup script building `Output\AirScreen-Setup-v3.0.0.exe` with the **Air Screen** display name, Desktop/Start Menu shortcuts, and optional User `PATH` setup.
* `build.bat` — Generates the icon, builds `dist\AirScreen.exe`, and compiles `installer.iss` when Inno Setup is available.
* `requirements.txt` — Python build dependencies (`pillow`, `pyinstaller`).

### Clone & Install Dependencies
```bash
git clone [https://github.com/shamodhas/android-wifi-mirror-scrcpy-pc.git](https://github.com/shamodhas/android-wifi-mirror-scrcpy-pc.git)
cd android-wifi-mirror-scrcpy-pc
pip install -r requirements.txt
```

### Build Executable & Windows Installer
1. Run `build.bat` to generate `assets\app.ico` and build `dist\AirScreen.exe`
   ```powershell
   .\build.bat
   ```

2. Compile installer.iss using Inno Setup (ISCC.exe) to create Output\AirScreen-Setup-v3.0.0.exe
   ```powershell
   & "C:\Program Files\Inno Setup 7\ISCC.exe" .\installer.iss
   ```
---