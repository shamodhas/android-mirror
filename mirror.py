import io
import json
import os
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
import urllib.request
import zipfile
from tkinter import messagebox, simpledialog, ttk

ADB_PORT = 5555
APP_DIR = os.path.join(os.environ.get(
    "LOCALAPPDATA", os.path.expanduser("~")), "AndroidMirror")
TOOLS_DIR = os.path.join(APP_DIR, "tools")
SCRCPY_RELEASES_API = "https://api.github.com/repos/Genymobile/scrcpy/releases/latest"
IP_PATTERN = re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}$")


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


def ask_phone_ip() -> str | None:
    root = create_hidden_root()
    value = simpledialog.askstring(
        "Android Mirror - Manual IP",
        "No active ADB device detected.\n\n"
        "Enter your phone's Wi-Fi IP address if TCP/IP port 5555 is already active,\n"
        "or click Cancel and connect via USB once:",
        parent=root,
    )
    root.destroy()
    if not value:
        return None
    ip = value.strip()
    if not IP_PATTERN.match(ip):
        show_warning("Invalid IP Address",
                     f"'{ip}' is not a valid IPv4 address.")
        return None
    return ip


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


def download_and_extract_with_progress() -> tuple[bool, str | None]:
    state: dict[str, object] = {
        "status": "Checking latest scrcpy release...",
        "progress": 0.0,
        "indeterminate": True,
        "done": False,
        "ok": False,
        "error": None,
    }
    lock = threading.Lock()

    def set_state(status: str, progress: float = 0.0, indeterminate: bool = False) -> None:
        with lock:
            state["status"] = status
            state["progress"] = progress
            state["indeterminate"] = indeterminate

    def worker() -> None:
        try:
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
                with lock:
                    state["error"] = "Windows scrcpy release asset not found."
                    state["done"] = True
                return

            zip_url = win64_asset["browser_download_url"]
            zip_req = urllib.request.Request(
                zip_url, headers={"User-Agent": "AndroidMirror-App"})

            buf = io.BytesIO()
            with urllib.request.urlopen(zip_req, timeout=60) as zresp:
                total_size = int(zresp.headers.get("Content-Length") or 0)
                downloaded = 0
                set_state("Downloading scrcpy & ADB...", 0.0, total_size <= 0)

                while True:
                    chunk = zresp.read(65536)
                    if not chunk:
                        break
                    buf.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        pct = min(85.0, (downloaded / total_size) * 85.0)
                        mb_done = downloaded / (1024 * 1024)
                        mb_total = total_size / (1024 * 1024)
                        set_state(
                            f"Downloading... {mb_done:.1f} / {mb_total:.1f} MB", pct, False)

            set_state("Extracting tools...", 88.0, False)
            buf.seek(0)
            with zipfile.ZipFile(buf) as zf:
                members = [m for m in zf.infolist() if not m.is_dir()]
                total_members = max(1, len(members))
                for idx, member in enumerate(members, start=1):
                    rel_parts = member.filename.split("/", 1)
                    target_rel = rel_parts[1] if len(
                        rel_parts) > 1 else rel_parts[0]
                    if not target_rel:
                        continue
                    out_path = os.path.join(TOOLS_DIR, target_rel)
                    os.makedirs(os.path.dirname(out_path), exist_ok=True)
                    with zf.open(member) as src, open(out_path, "wb") as dst:
                        dst.write(src.read())
                    pct = 88.0 + (idx / total_members) * 12.0
                    set_state(
                        f"Extracting files... ({idx}/{total_members})", pct, False)

            ok = bool(find_binary("adb.exe") and find_binary("scrcpy.exe"))
            with lock:
                state["ok"] = ok
                if not ok:
                    state["error"] = "adb.exe or scrcpy.exe missing after extraction."
                state["done"] = True
        except Exception as exc:
            with lock:
                state["error"] = str(exc)
                state["done"] = True

    dialog = tk.Tk()
    dialog.title("Android Mirror Setup")
    dialog.geometry("400x130")
    dialog.resizable(False, False)
    dialog.attributes("-topmost", True)

    container = ttk.Frame(dialog, padding=16)
    container.pack(fill=tk.BOTH, expand=True)

    status_var = tk.StringVar(value="Starting setup...")
    lbl = ttk.Label(container, textvariable=status_var, anchor="w")
    lbl.pack(fill=tk.X, pady=(0, 10))

    bar = ttk.Progressbar(container, orient="horizontal",
                          length=360, mode="indeterminate", maximum=100)
    bar.pack(fill=tk.X)
    bar.start(12)

    pct_var = tk.StringVar(value="")
    pct_lbl = ttk.Label(container, textvariable=pct_var, anchor="e")
    pct_lbl.pack(fill=tk.X, pady=(6, 0))

    threading.Thread(target=worker, daemon=True).start()

    def poll() -> None:
        with lock:
            is_done = bool(state["done"])
            status_text = str(state["status"])
            prog_val = float(state["progress"])
            is_indet = bool(state["indeterminate"])

        status_var.set(status_text)
        if is_indet:
            if str(bar["mode"]) != "indeterminate":
                bar.configure(mode="indeterminate")
                bar.start(12)
            pct_var.set("")
        else:
            if str(bar["mode"]) != "determinate":
                bar.stop()
                bar.configure(mode="determinate", maximum=100)
            bar["value"] = prog_val
            pct_var.set(f"{int(prog_val)}%")

        if is_done:
            dialog.destroy()
            return
        dialog.after(80, poll)

    dialog.after(80, poll)
    dialog.mainloop()

    with lock:
        return bool(state["ok"]), state["error"] if isinstance(state["error"], str) else None


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

    ok, err = download_and_extract_with_progress()
    if not ok:
        show_warning("Setup Failed", err or "Could not complete scrcpy setup.")
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

    manual_ip = ask_phone_ip()
    if manual_ip:
        target = f"{manual_ip}:{ADB_PORT}"
        run_cmd(["adb", "connect", target])
        active = get_devices(adb)
        if target in active:
            launch_scrcpy(scrcpy, target)
            return
        show_warning(
            "Connection Failed",
            f"Could not connect over ADB to {target}.\n\n"
            "Make sure both devices are on the same network and TCP/IP port 5555 is enabled via USB once.",
        )
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
