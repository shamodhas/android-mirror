import io
import os
import re
import subprocess
import sys
import time
import tkinter as tk
import urllib.request
import zipfile
from tkinter import messagebox, simpledialog

ADB_PORT = 5555
APP_DIR = os.path.join(os.environ.get(
    "LOCALAPPDATA", os.path.expanduser("~")), "AndroidMirror")
TOOLS_DIR = os.path.join(APP_DIR, "tools")
SCRCPY_RELEASES_API = "https://api.github.com/repos/Genymobile/scrcpy/releases/latest"


def create_hidden_root() -> tk.Tk:
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    return root


def show_info(title: str, message: str) -> None:
    root = create_hidden_root()
    messagebox.showinfo(title, message, parent=root)
    root.destroy()


def show_warning(title: str, message: str) -> None:
    root = create_hidden_root()
    messagebox.showwarning(title, message, parent=root)
    root.destroy()


def ask_yes_no(title: str, message: str) -> bool:
    root = create_hidden_root()
    result = messagebox.askyesno(title, message, parent=root)
    root.destroy()
    return result


def find_binary(name: str) -> str | None:
    for folder in (TOOLS_DIR, os.path.dirname(os.path.abspath(sys.argv[0]))):
        candidate = os.path.join(folder, name)
        if os.path.isfile(candidate):
            return candidate
    for path_dir in os.environ.get("PATH", "").split(os.pathsep):
        if not path_dir:
            continue
        candidate = os.path.join(path_dir.strip(), name)
        if os.path.isfile(candidate):
            return candidate
    return None


def download_scrcpy_bundle() -> bool:
    import json

    os.makedirs(TOOLS_DIR, exist_ok=True)
    req = urllib.request.Request(
        SCRCPY_RELEASES_API,
        headers={"User-Agent": "AndroidMirror-App",
                 "Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    assets = data.get("assets", [])
    win64_asset = next(
        (a for a in assets if "win64" in a.get("name", "").lower()
         and a.get("name", "").endswith(".zip")),
        None,
    )
    if not win64_asset:
        return False

    zip_url = win64_asset["browser_download_url"]
    zip_req = urllib.request.Request(
        zip_url, headers={"User-Agent": "AndroidMirror-App"})
    with urllib.request.urlopen(zip_req, timeout=60) as zresp:
        archive_bytes = zresp.read()

    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as zf:
        for member in zf.infolist():
            if member.is_dir():
                continue
            rel_parts = member.filename.split("/", 1)
            target_rel = rel_parts[1] if len(rel_parts) > 1 else rel_parts[0]
            if not target_rel:
                continue
            out_path = os.path.join(TOOLS_DIR, target_rel)
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            with zf.open(member) as src, open(out_path, "wb") as dst:
                dst.write(src.read())

    return bool(find_binary("adb.exe") and find_binary("scrcpy.exe"))


def ensure_tools() -> tuple[str, str] | None:
    adb = find_binary("adb.exe")
    scrcpy = find_binary("scrcpy.exe")
    if adb and scrcpy:
        return adb, scrcpy

    proceed = ask_yes_no(
        "Android Mirror Setup",
        "ADB and scrcpy were not found on this PC.\n\nDownload and set them up automatically now?",
    )
    if not proceed:
        return None

    try:
        ok = download_scrcpy_bundle()
    except Exception as exc:
        show_warning("Setup Failed",
                     f"Could not download scrcpy automatically:\n{exc}")
        return None

    if not ok:
        show_warning(
            "Setup Failed", "Windows scrcpy package could not be installed automatically.")
        return None

    adb = find_binary("adb.exe")
    scrcpy = find_binary("scrcpy.exe")
    if adb and scrcpy:
        show_info("Android Mirror Setup",
                  "Setup complete. Connect your phone via USB to start mirroring.")
        return adb, scrcpy
    return None


def run_cmd(args: list[str], timeout: int = 8) -> str:
    try:
        res = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        return res.stdout or ""
    except Exception:
        return ""


def get_devices(adb: str) -> list[str]:
    out = run_cmd([adb, "devices"])
    devices = []
    for line in out.splitlines():
        line = line.strip()
        if line.endswith("\tdevice"):
            devices.append(line.split("\t")[0].strip())
    return devices


def get_wifi_ip(adb: str, serial: str) -> str | None:
    out = run_cmd([adb, "-s", serial, "shell", "ip",
                  "-f", "inet", "addr", "show", "wlan0"])
    match = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+)/", out)
    return match.group(1) if match else None


def launch_scrcpy(scrcpy: str, target: str) -> None:
    env = os.environ.copy()
    env["PATH"] = f"{TOOLS_DIR}{os.pathsep}{env.get('PATH', '')}"
    subprocess.Popen(
        [scrcpy, "-s", target],
        env=env,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )


def main() -> None:
    tools = ensure_tools()
    if not tools:
        return
    adb, scrcpy = tools

    devices = get_devices(adb)
    usb_devices = [d for d in devices if ":" not in d]
    tcp_devices = [d for d in devices if ":" in d]

    if usb_devices:
        usb = usb_devices[0]
        run_cmd([adb, "-s", usb, "tcpip", str(ADB_PORT)])
        time.sleep(1.2)
        ip = get_wifi_ip(adb, usb)
        if ip:
            target = f"{ip}:{ADB_PORT}"
            run_cmd([adb, "connect", target])
            launch_scrcpy(scrcpy, target)
            return
        launch_scrcpy(scrcpy, usb)
        return

    for target in tcp_devices:
        old_ip = target.split(":")[0]
        current_ip = get_wifi_ip(adb, target)
        if current_ip and current_ip != old_ip:
            run_cmd([adb, "disconnect", target])
            new_target = f"{current_ip}:{ADB_PORT}"
            run_cmd([adb, "connect", new_target])
            launch_scrcpy(scrcpy, new_target)
            return
        launch_scrcpy(scrcpy, target)
        return

    show_warning(
        "Android Mirror",
        "No active Android device detected.\n\n"
        "1. Enable Developer Options & USB Debugging on your phone.\n"
        "2. Connect via USB once and tap Allow on the prompt.\n"
        "3. Run Android Mirror again.",
    )


if __name__ == "__main__":
    main()
