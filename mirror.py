import re
import subprocess
import sys
import time
import tkinter as tk
from tkinter import messagebox

ADB_PORT = 5555


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


def get_devices() -> list[str]:
    out = run_cmd(["adb", "devices"])
    devices = []
    for line in out.splitlines():
        line = line.strip()
        if line.endswith("\tdevice"):
            devices.append(line.split("\t")[0].strip())
    return devices


def get_wifi_ip(serial: str) -> str | None:
    out = run_cmd(["adb", "-s", serial, "shell", "ip", "-f", "inet", "addr", "show", "wlan0"])
    match = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+)/", out)
    return match.group(1) if match else None


def launch_scrcpy(target: str) -> None:
    subprocess.Popen(
        ["scrcpy", "-s", target],
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )


def show_alert(title: str, message: str) -> None:
    root = tk.Tk()
    root.withdraw()
    messagebox.showwarning(title, message)
    root.destroy()


def main() -> None:
    devices = get_devices()
    usb_devices = [d for d in devices if ":" not in d]
    tcp_devices = [d for d in devices if ":" in d]

    if usb_devices:
        usb = usb_devices[0]
        run_cmd(["adb", "-s", usb, "tcpip", str(ADB_PORT)])
        time.sleep(1.2)
        ip = get_wifi_ip(usb)
        if ip:
            target = f"{ip}:{ADB_PORT}"
            run_cmd(["adb", "connect", target])
            launch_scrcpy(target)
            return
        launch_scrcpy(usb)
        return

    for target in tcp_devices:
        old_ip = target.split(":")[0]
        current_ip = get_wifi_ip(target)
        if current_ip and current_ip != old_ip:
            run_cmd(["adb", "disconnect", target])
            new_target = f"{current_ip}:{ADB_PORT}"
            run_cmd(["adb", "connect", new_target])
            launch_scrcpy(new_target)
            return
        launch_scrcpy(target)
        return

    show_alert(
        "Android Mirror",
        "No active device found.\n\nConnect via USB once (with USB Debugging enabled), then run again.",
    )


if __name__ == "__main__":
    main()