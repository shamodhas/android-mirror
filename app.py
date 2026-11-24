import io
import ipaddress
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
from tkinter import messagebox, ttk
from typing import Any, Callable, List, Optional, Tuple

APP_VERSION = "3.0.0"
APP_TITLE = f"Air Screen v{APP_VERSION} — Android WiFi Mirror"
STORAGE_FOLDER = "android-wifi-mirror-scrcpy-pc"
DEFAULT_PORT = 5555
APP_DATA = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), STORAGE_FOLDER
)
TOOLS_DIR = os.path.join(APP_DATA, "tools")
STATE_FILE = os.path.join(APP_DATA, "session.json")
SCRCPY_API = "https://api.github.com/repos/Genymobile/scrcpy/releases/latest"

HOST_PORT_RE = re.compile(r"^(\d{1,3}(?:\.\d{1,3}){3}):(\d{1,5})$")
IPV4_IN_TEXT_RE = re.compile(r"\b(\d{1,3}(?:\.\d{1,3}){3})\b")


def is_valid_ipv4(value: str) -> bool:
    try:
        ip = ipaddress.IPv4Address(value.strip())
        return not ip.is_unspecified and not ip.is_loopback
    except ValueError:
        return False


def is_valid_port(value: str) -> bool:
    if not value.strip().isdigit():
        return False
    port = int(value.strip())
    return 1 <= port <= 65535


def resource_path(rel_path: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel_path)


def find_binary(exe_name: str) -> Optional[str]:
    exe_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    search_dirs: List[str] = [
        os.path.join(exe_dir, "tools"),
        TOOLS_DIR,
        exe_dir,
        *(
            p.strip()
            for p in os.environ.get("PATH", "").split(os.pathsep)
            if p.strip()
        ),
    ]
    for folder in search_dirs:
        candidate = os.path.join(folder, exe_name)
        if os.path.isfile(candidate):
            return candidate
    return None


def run_cmd(args: List[str], timeout: int = 15) -> Tuple[int, str, str]:
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=flags,
        )
        return proc.returncode, (proc.stdout or "").strip(), (proc.stderr or "").strip()
    except Exception as exc:
        return 1, "", str(exc)


def stop_adb_and_scrcpy() -> None:
    if sys.platform != "win32":
        return
    for exe in ("scrcpy.exe", "adb.exe"):
        run_cmd(["taskkill", "/F", "/IM", exe], timeout=6)
    time.sleep(0.4)


def safe_extract_zip(zip_bytes: io.BytesIO, dest_root: str) -> None:
    real_root = os.path.realpath(dest_root)
    os.makedirs(real_root, exist_ok=True)
    with zipfile.ZipFile(zip_bytes) as zf:
        for member in zf.infolist():
            if member.is_dir():
                continue
            parts = member.filename.split("/", 1)
            rel = parts[1] if len(parts) > 1 else parts[0]
            rel = rel.lstrip("/\\")
            if not rel:
                continue
            target_path = os.path.realpath(os.path.join(real_root, rel))
            if not target_path.startswith(real_root + os.sep) and target_path != real_root:
                raise RuntimeError(
                    f"Blocked unsafe archive path: {member.filename}")
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with zf.open(member) as src, open(target_path, "wb") as dst:
                dst.write(src.read())


def load_saved_state() -> dict[str, Any]:
    try:
        if os.path.isfile(STATE_FILE):
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
    except Exception:
        pass
    return {}


def save_state(data: dict[str, Any]) -> None:
    try:
        os.makedirs(APP_DATA, exist_ok=True)
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


class AirScreenApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("500x430")
        self.root.resizable(False, False)

        icon_file = resource_path(os.path.join("assets", "app.ico"))
        if os.path.isfile(icon_file):
            try:
                self.root.iconbitmap(icon_file)
            except Exception:
                pass

        self.state = load_saved_state()
        self.adb_path: Optional[str] = None
        self.scrcpy_path: Optional[str] = None
        self.scrcpy_version: Tuple[int, int, int] = (2, 0, 0)
        self._mirror_proc: Optional[subprocess.Popen[Any]] = None
        self._busy = False
        self._action_buttons: List[Tuple[ttk.Button, str]] = []
        self._spinner_idx = 0
        self._spinner_frames = ["⠋", "⠙", "⠹",
                                "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self._active_btn: Optional[ttk.Button] = None
        self._active_btn_base_text: str = ""

        self._build_ui()
        self._run_bg(
            self._auto_init_and_connect,
            on_done=self._on_auto_init_done,
            btn=self.primary_btn,
            loading_label="Preparing...",
        )

    def _register_btn(self, btn: ttk.Button) -> ttk.Button:
        self._action_buttons.append((btn, str(btn.cget("text"))))
        return btn

    def _build_ui(self) -> None:
        pad = ttk.Frame(self.root, padding=14)
        pad.pack(fill=tk.BOTH, expand=True)

        header = ttk.Frame(pad)
        header.pack(fill=tk.X)
        ttk.Label(header, text="Air Screen", font=(
            "Segoe UI", 15, "bold")).pack(side=tk.LEFT)
        ttk.Label(header, text=f"v{APP_VERSION}", foreground="#0f766e", font=("Segoe UI", 9, "bold")).pack(
            side=tk.LEFT, padx=(8, 0), anchor="s"
        )
        self.ver_badge = ttk.Label(
            header, text="scrcpy: detecting...", foreground="#555")
        self.ver_badge.pack(side=tk.RIGHT, anchor="s")

        self.tool_status = ttk.Label(
            pad, text="Auto-preparing ADB & scrcpy...", foreground="#555"
        )
        self.tool_status.pack(anchor="w", pady=(2, 8))

        notebook = ttk.Notebook(pad)
        notebook.pack(fill=tk.BOTH, expand=True)

        auto_tab = ttk.Frame(notebook, padding=12)
        notebook.add(auto_tab, text="Auto Wireless Mirror")

        dev_row = ttk.Frame(auto_tab)
        dev_row.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(dev_row, text="Active Device:").pack(side=tk.LEFT)
        self.device_var = tk.StringVar(value="Auto")
        self.device_combo = ttk.Combobox(
            dev_row, textvariable=self.device_var, values=["Auto"], width=22, state="readonly"
        )
        self.device_combo.pack(side=tk.LEFT, padx=(6, 6))
        self.scan_btn = self._register_btn(
            ttk.Button(dev_row, text="Scan", width=7,
                       command=self.refresh_devices)
        )
        self.scan_btn.pack(side=tk.LEFT)
        self.disc_btn = self._register_btn(
            ttk.Button(dev_row, text="Disconnect TCP",
                       width=13, command=self.disconnect_tcp)
        )
        self.disc_btn.pack(side=tk.LEFT, padx=(6, 0))

        ttk.Label(
            auto_tab, text="Phone Wi-Fi IP (auto-detected when empty):").pack(anchor="w")
        self.ip_entry = ttk.Entry(auto_tab)
        self.ip_entry.pack(fill=tk.X, pady=(2, 8))
        saved_ip = str(self.state.get("last_ip", "")).strip()
        if is_valid_ipv4(saved_ip):
            self.ip_entry.insert(0, saved_ip)

        opts_row = ttk.Frame(auto_tab)
        opts_row.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(opts_row, text="Port:").pack(side=tk.LEFT)
        self.port_entry = ttk.Entry(opts_row, width=7)
        saved_port = str(self.state.get("last_port", DEFAULT_PORT))
        self.port_entry.insert(0, saved_port if is_valid_port(
            saved_port) else str(DEFAULT_PORT))
        self.port_entry.pack(side=tk.LEFT, padx=(4, 10))

        self.max_size_var = tk.StringVar(
            value=str(self.state.get("max_size", "1280")))
        ttk.Label(opts_row, text="Max Res:").pack(side=tk.LEFT)
        ttk.Combobox(
            opts_row,
            textvariable=self.max_size_var,
            values=["800", "1024", "1280", "1920", "0"],
            width=6,
            state="readonly",
        ).pack(side=tk.LEFT, padx=(4, 10))

        self.screen_off_var = tk.BooleanVar(
            value=bool(self.state.get("screen_off", False)))
        ttk.Checkbutton(opts_row, text="Screen Off", variable=self.screen_off_var).pack(
            side=tk.LEFT, padx=(0, 8)
        )

        self.stay_awake_var = tk.BooleanVar(
            value=bool(self.state.get("stay_awake", True)))
        ttk.Checkbutton(opts_row, text="Stay Awake", variable=self.stay_awake_var).pack(
            side=tk.LEFT
        )

        self.close_after_mirror_var = tk.BooleanVar(
            value=bool(self.state.get("close_after_mirror", True))
        )
        ttk.Checkbutton(
            auto_tab,
            text="Close settings window after mirror opens",
            variable=self.close_after_mirror_var,
        ).pack(anchor="w", pady=(0, 8))

        btn_row = ttk.Frame(auto_tab)
        btn_row.pack(fill=tk.X, pady=(2, 6))
        self.primary_btn = self._register_btn(
            ttk.Button(btn_row, text="Auto-Connect & Mirror",
                       command=self.start_smart_mirror)
        )
        self.primary_btn.pack(side=tk.LEFT, fill=tk.X,
                              expand=True, padx=(0, 6))
        self.stop_btn = self._register_btn(
            ttk.Button(btn_row, text="Stop Mirror",
                       width=12, command=self.stop_mirror)
        )
        self.stop_btn.pack(side=tk.LEFT)

        self.update_tools_btn = self._register_btn(
            ttk.Button(
                auto_tab, text="Re-download / Update Tools", command=self.force_download_tools
            )
        )
        self.update_tools_btn.pack(fill=tk.X)

        pair_tab = ttk.Frame(notebook, padding=12)
        notebook.add(pair_tab, text="Pair (Android 11+)")

        ttk.Label(pair_tab, text="Pairing IP:Port (from Wireless Debugging):").pack(
            anchor="w")
        self.pair_addr_entry = ttk.Entry(pair_tab)
        self.pair_addr_entry.pack(fill=tk.X, pady=(2, 6))

        ttk.Label(pair_tab, text="6-Digit Pairing Code:").pack(anchor="w")
        self.pair_code_entry = ttk.Entry(pair_tab)
        self.pair_code_entry.pack(fill=tk.X, pady=(2, 6))

        ttk.Label(pair_tab, text="Connect Port (main Wireless Debugging screen):").pack(
            anchor="w")
        self.pair_conn_port = ttk.Entry(pair_tab, width=10)
        self.pair_conn_port.pack(anchor="w", pady=(2, 10))

        self.pair_btn = self._register_btn(
            ttk.Button(pair_tab, text="Pair & Mirror",
                       command=self.start_pair_and_mirror)
        )
        self.pair_btn.pack(fill=tk.X)

        self.progress = ttk.Progressbar(pad, mode="indeterminate")
        self.progress.pack(fill=tk.X, pady=(10, 4))

        self.status_var = tk.StringVar(value="Starting...")
        ttk.Label(pad, textvariable=self.status_var, wraplength=465, foreground="#222").pack(
            anchor="w"
        )

    def _tick_spinner(self) -> None:
        if not self._busy:
            return
        frame = self._spinner_frames[self._spinner_idx %
                                     len(self._spinner_frames)]
        self._spinner_idx += 1
        if self._active_btn is not None:
            try:
                self._active_btn.config(
                    text=f"{frame} {self._active_btn_base_text}")
            except Exception:
                pass
        self.root.after(90, self._tick_spinner)

    def _set_status(self, msg: str) -> None:
        self.root.after(0, lambda m=msg: self.status_var.set(m))

    def _set_tool_label(self, text: str, color: str) -> None:
        self.root.after(0, lambda t=text,
                        c=color: self.tool_status.config(text=t, foreground=c))

    def _set_version_label(self, ver: Tuple[int, int, int]) -> None:
        text = f"scrcpy v{ver[0]}.{ver[1]}.{ver[2]}"
        self.root.after(0, lambda t=text: self.ver_badge.config(
            text=t, foreground="#1d4ed8"))

    def _set_device_list(self, serials: List[str]) -> None:
        items = ["Auto", *serials]
        current = self.device_var.get()
        chosen = current if current in items else "Auto"
        self.root.after(
            0,
            lambda vals=items, sel=chosen: (
                self.device_combo.config(values=vals),
                self.device_var.set(sel),
            ),
        )

    def _set_busy(
        self,
        busy: bool,
        btn: Optional[ttk.Button] = None,
        loading_label: str = "Working...",
    ) -> None:
        self._busy = busy
        if busy:
            self._active_btn = btn
            self._active_btn_base_text = loading_label
            self._spinner_idx = 0
            for b, _ in self._action_buttons:
                b.config(state=tk.DISABLED)
            self.progress.start(12)
            self._tick_spinner()
        else:
            self.progress.stop()
            for b, orig_text in self._action_buttons:
                b.config(text=orig_text, state=tk.NORMAL)
            self._active_btn = None
            self._active_btn_base_text = ""

    def _close_settings_window(self) -> None:
        if self.close_after_mirror_var.get():
            try:
                self.root.withdraw()
            except Exception:
                pass

    def _run_bg(
        self,
        fn: Callable[[], Any],
        on_done: Optional[Callable[[Any], None]] = None,
        btn: Optional[ttk.Button] = None,
        loading_label: str = "Working...",
    ) -> None:
        if self._busy:
            return
        self._set_busy(True, btn=btn, loading_label=loading_label)

        def runner() -> None:
            result: Any = None
            err: Optional[Exception] = None
            try:
                result = fn()
            except Exception as exc:
                err = exc

            def finalize() -> None:
                self._set_busy(False)
                if err is not None:
                    self._set_status(f"Error: {err}")
                    messagebox.showerror(APP_TITLE, str(err))
                elif on_done is not None:
                    on_done(result)

            self.root.after(0, finalize)

        threading.Thread(target=runner, daemon=True).start()

    def _download_tools(self) -> Tuple[str, str]:
        self._set_tool_label("Downloading scrcpy & ADB...", "#b45309")
        self._set_status("Checking latest scrcpy release on GitHub...")

        req = urllib.request.Request(
            SCRCPY_API,
            headers={"User-Agent": STORAGE_FOLDER,
                     "Accept": "application/vnd.github+json"},
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            release = json.loads(resp.read().decode("utf-8"))

        assets = release.get("assets", [])
        asset = next(
            (
                a
                for a in assets
                if "win64" in a.get("name", "").lower()
                and a.get("name", "").endswith(".zip")
                and not release.get("prerelease", False)
            ),
            None,
        ) or next(
            (
                a
                for a in assets
                if "win64" in a.get("name", "").lower()
                and a.get("name", "").endswith(".zip")
            ),
            None,
        )
        if not asset:
            raise RuntimeError(
                "No Windows scrcpy zip asset found in GitHub release.")

        buf = io.BytesIO()
        zreq = urllib.request.Request(
            asset["browser_download_url"], headers={
                "User-Agent": STORAGE_FOLDER}
        )
        with urllib.request.urlopen(zreq, timeout=90) as zresp:
            total = int(zresp.headers.get("Content-Length") or 0)
            done = 0
            while True:
                chunk = zresp.read(65536)
                if not chunk:
                    break
                buf.write(chunk)
                done += len(chunk)
                if total > 0:
                    pct = int((done / total) * 100)
                    self._set_status(
                        f"Downloading tools... {pct}% ({done / 1048576:.1f}/{total / 1048576:.1f} MB)"
                    )

        self._set_status("Stopping running ADB/scrcpy & extracting...")
        self._stop_mirror_process()
        stop_adb_and_scrcpy()
        buf.seek(0)
        safe_extract_zip(buf, TOOLS_DIR)

        adb = find_binary("adb.exe")
        scrcpy = find_binary("scrcpy.exe")
        if not (adb and scrcpy):
            raise RuntimeError(
                "adb.exe or scrcpy.exe missing after extraction.")
        return adb, scrcpy

    def _detect_scrcpy_version(self, scrcpy_path: str) -> Tuple[int, int, int]:
        _, out, err = run_cmd([scrcpy_path, "--version"], timeout=5)
        match = re.search(
            r"\bscrcpy\s+(\d+)\.(\d+)(?:\.(\d+))?", f"{out}\n{err}")
        if match:
            return (
                int(match.group(1)),
                int(match.group(2)),
                int(match.group(3) or 0),
            )
        return (2, 0, 0)

    def _ensure_tools_ready(self, force: bool = False) -> Tuple[str, str]:
        if not force:
            adb = find_binary("adb.exe")
            scrcpy = find_binary("scrcpy.exe")
            if adb and scrcpy:
                self.adb_path, self.scrcpy_path = adb, scrcpy
            else:
                self.adb_path, self.scrcpy_path = self._download_tools()
        else:
            self.adb_path, self.scrcpy_path = self._download_tools()

        assert self.scrcpy_path is not None
        self.scrcpy_version = self._detect_scrcpy_version(self.scrcpy_path)
        self._set_version_label(self.scrcpy_version)
        self._set_tool_label("ADB & scrcpy ready", "#15803d")
        assert self.adb_path is not None
        return self.adb_path, self.scrcpy_path

    def _connected_serials(self, adb: str) -> List[str]:
        _, out, _ = run_cmd([adb, "devices"], timeout=8)
        serials: List[str] = []
        for line in out.splitlines():
            line = line.strip()
            if line.endswith("\tdevice"):
                serials.append(line.split("\t")[0].strip())
        self._set_device_list(serials)
        return serials

    def _detect_phone_ip(self, adb: str, serial: str) -> Optional[str]:
        commands = [
            ["-s", serial, "shell", "ip", "-f", "inet", "addr", "show", "wlan0"],
            ["-s", serial, "shell", "ip", "route", "get", "1.1.1.1"],
        ]
        for cmd in commands:
            _, out, _ = run_cmd([adb, *cmd], timeout=6)
            for m in IPV4_IN_TEXT_RE.finditer(out):
                candidate = m.group(1)
                if is_valid_ipv4(candidate) and candidate != "1.1.1.1":
                    return candidate
        return None

    def _build_scrcpy_cmd(self, scrcpy: str, target: str) -> List[str]:
        major, minor, _ = self.scrcpy_version
        cmd: List[str] = [scrcpy, "-s", target]

        max_size = self.max_size_var.get().strip()
        if max_size and max_size != "0":
            cmd.extend(["--max-size", max_size])

        if self.screen_off_var.get():
            cmd.append("--turn-screen-off")

        if self.stay_awake_var.get():
            cmd.append("--stay-awake")

        _ = (major, minor)
        return cmd

    def _stop_mirror_process(self) -> None:
        proc = self._mirror_proc
        self._mirror_proc = None
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=2)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

    def _launch_scrcpy(self, scrcpy: str, target: str) -> None:
        self._stop_mirror_process()
        cmd = self._build_scrcpy_cmd(scrcpy, target)
        tools_parent = os.path.dirname(scrcpy)
        env = os.environ.copy()
        env["PATH"] = f"{tools_parent}{os.pathsep}{TOOLS_DIR}{os.pathsep}{env.get('PATH', '')}"
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        self._mirror_proc = subprocess.Popen(cmd, env=env, creationflags=flags)
        self.root.after(350, self._close_settings_window)

    def stop_mirror(self) -> None:
        def task() -> str:
            self._set_status("Stopping active mirror...")
            self._stop_mirror_process()
            return "Mirroring stopped."

        self._run_bg(task, on_done=lambda m: self._set_status(
            str(m)), btn=self.stop_btn, loading_label="Stopping...")

    def refresh_devices(self) -> None:
        def task() -> str:
            self._set_status("Scanning connected ADB devices...")
            adb, _ = self._ensure_tools_ready(force=False)
            serials = self._connected_serials(adb)
            return f"Found {len(serials)} connected device(s)."

        self._run_bg(task, on_done=lambda m: self._set_status(
            str(m)), btn=self.scan_btn, loading_label="Scanning...")

    def disconnect_tcp(self) -> None:
        def task() -> str:
            self._set_status("Disconnecting wireless ADB sessions...")
            self._stop_mirror_process()
            adb, _ = self._ensure_tools_ready(force=False)
            serials = self._connected_serials(adb)
            tcp_devs = [s for s in serials if ":" in s]
            for dev in tcp_devs:
                run_cmd([adb, "disconnect", dev], timeout=6)
            self._connected_serials(adb)
            return f"Disconnected {len(tcp_devs)} wireless session(s)."

        self._run_bg(task, on_done=lambda m: self._set_status(
            str(m)), btn=self.disc_btn, loading_label="Disconnecting...")

    def _persist_session(self, ip: str, port: int) -> None:
        save_state({
            "last_ip": ip,
            "last_port": port,
            "max_size": self.max_size_var.get(),
            "screen_off": self.screen_off_var.get(),
            "stay_awake": self.stay_awake_var.get(),
            "close_after_mirror": self.close_after_mirror_var.get(),
        })

    def _auto_init_and_connect(self) -> Optional[str]:
        adb, scrcpy = self._ensure_tools_ready(force=False)
        serials = self._connected_serials(adb)
        selected = self.device_var.get()
        if selected != "Auto" and selected in serials:
            usb_devs = [selected] if ":" not in selected else []
            tcp_devs = [selected] if ":" in selected else []
        else:
            usb_devs = [s for s in serials if ":" not in s]
            tcp_devs = [s for s in serials if ":" in s]

        port_str = self.port_entry.get().strip() or str(DEFAULT_PORT)
        port = int(port_str) if is_valid_port(port_str) else DEFAULT_PORT

        if usb_devs:
            usb = usb_devs[0]
            self._set_status(
                f"USB detected ({usb}). Switching to wireless port {port}...")
            run_cmd([adb, "-s", usb, "tcpip", str(port)], timeout=8)
            time.sleep(1.2)
            ip = self._detect_phone_ip(adb, usb)
            if ip:
                self.root.after(0, lambda i=ip: (self.ip_entry.delete(
                    0, tk.END), self.ip_entry.insert(0, i)))
                target = f"{ip}:{port}"
                run_cmd([adb, "connect", target], timeout=8)
                time.sleep(0.7)
                if target in self._connected_serials(adb):
                    self._persist_session(ip, port)
                    self._launch_scrcpy(scrcpy, target)
                    return f"Auto-connected & mirroring {target}"
            return f"Enabled TCP/IP {port} via USB. Enter phone IP and click Auto-Connect & Mirror."

        for existing in tcp_devs:
            host = existing.split(":")[0]
            ip = self._detect_phone_ip(adb, existing) or host
            target = existing
            if ip != host:
                run_cmd([adb, "disconnect", existing], timeout=6)
                target = f"{ip}:{port}"
                run_cmd([adb, "connect", target], timeout=8)
            self._launch_scrcpy(scrcpy, target)
            return f"Auto-mirroring existing wireless device {target}"

        typed_ip = self.ip_entry.get().strip()
        if is_valid_ipv4(typed_ip):
            target = f"{typed_ip}:{port}"
            self._set_status(f"Connecting to saved/entered IP {target}...")
            run_cmd([adb, "connect", target], timeout=8)
            time.sleep(0.7)
            if target in self._connected_serials(adb):
                self._launch_scrcpy(scrcpy, target)
                return f"Auto-mirroring {target}"

        return "Ready. Connect USB once for auto-Wi-Fi setup, enter phone IP, or pair on Android 11+."

    def _on_auto_init_done(self, msg: Optional[str]) -> None:
        if msg:
            self._set_status(msg)

    def start_smart_mirror(self) -> None:
        typed_ip = self.ip_entry.get().strip()
        port_str = self.port_entry.get().strip() or str(DEFAULT_PORT)
        if not is_valid_port(port_str):
            messagebox.showwarning(
                APP_TITLE, "Enter a valid TCP port (1–65535).")
            return
        port = int(port_str)

        def task() -> str:
            adb, scrcpy = self._ensure_tools_ready(force=False)
            serials = self._connected_serials(adb)
            selected = self.device_var.get()
            if selected != "Auto" and selected in serials:
                usb_devs = [selected] if ":" not in selected else []
            else:
                usb_devs = [s for s in serials if ":" not in s]

            if usb_devs:
                usb = usb_devs[0]
                self._set_status(f"Enabling TCP/IP {port} on {usb}...")
                run_cmd([adb, "-s", usb, "tcpip", str(port)], timeout=8)
                time.sleep(1.2)
                ip = typed_ip if is_valid_ipv4(
                    typed_ip) else self._detect_phone_ip(adb, usb)
                if not ip:
                    raise RuntimeError(
                        "TCP/IP enabled, but phone Wi-Fi IP could not be detected automatically. Enter phone IP manually."
                    )
                self.root.after(0, lambda i=ip: (self.ip_entry.delete(
                    0, tk.END), self.ip_entry.insert(0, i)))
                target = f"{ip}:{port}"
                run_cmd([adb, "connect", target], timeout=8)
                time.sleep(0.7)
                if target not in self._connected_serials(adb):
                    raise RuntimeError(
                        f"Could not connect over Wi-Fi to {target}.")
                self._persist_session(ip, port)
                self._launch_scrcpy(scrcpy, target)
                return f"Mirroring {target} wirelessly."

            if not is_valid_ipv4(typed_ip):
                raise RuntimeError(
                    "No USB device found and no valid phone IP entered.\n\n"
                    "• Plug in via USB once for automatic Wi-Fi setup, OR\n"
                    "• Enter your phone's Wi-Fi IPv4 address (e.g. 192.168.1.42)."
                )

            target = f"{typed_ip}:{port}"
            self._set_status(f"Connecting to {target}...")
            run_cmd([adb, "connect", target], timeout=8)
            time.sleep(0.7)
            if target not in self._connected_serials(adb):
                raise RuntimeError(
                    f"Failed to connect to {target}. Ensure both devices are on the same Wi-Fi and port {port} is open."
                )
            self._persist_session(typed_ip, port)
            self._launch_scrcpy(scrcpy, target)
            return f"Mirroring {target} wirelessly."

        self._run_bg(
            task,
            on_done=lambda m: self._set_status(str(m)),
            btn=self.primary_btn,
            loading_label="Connecting...",
        )

    def force_download_tools(self) -> None:
        def task() -> str:
            self._ensure_tools_ready(force=True)
            return "Updated ADB & scrcpy tools."

        self._run_bg(
            task,
            on_done=lambda m: self._set_status(str(m)),
            btn=self.update_tools_btn,
            loading_label="Updating Tools...",
        )

    def start_pair_and_mirror(self) -> None:
        pair_addr = self.pair_addr_entry.get().strip()
        code = self.pair_code_entry.get().strip()
        conn_port_str = self.pair_conn_port.get().strip()

        m = HOST_PORT_RE.match(pair_addr)
        if not m or not is_valid_ipv4(m.group(1)) or not is_valid_port(m.group(2)):
            messagebox.showwarning(
                APP_TITLE, "Enter a valid pairing IP:Port (e.g. 192.168.1.42:37123).")
            return
        if not re.fullmatch(r"\d{4,8}", code):
            messagebox.showwarning(
                APP_TITLE, "Enter the pairing code shown on your phone.")
            return
        if not is_valid_port(conn_port_str):
            messagebox.showwarning(
                APP_TITLE, "Enter the main Wireless Debugging connect port.")
            return

        ip = m.group(1)
        conn_port = int(conn_port_str)

        def task() -> str:
            adb, scrcpy = self._ensure_tools_ready(force=False)
            self._set_status(f"Pairing with {pair_addr}...")
            rc, out, err = run_cmd([adb, "pair", pair_addr, code], timeout=12)
            combined = f"{out}\n{err}".lower()
            if rc != 0 or "successfully paired" not in combined:
                raise RuntimeError(f"Pairing failed:\n{(err or out).strip()}")

            target = f"{ip}:{conn_port}"
            self._set_status(f"Connecting to {target}...")
            run_cmd([adb, "connect", target], timeout=10)
            time.sleep(0.8)
            if target not in self._connected_serials(adb):
                raise RuntimeError(
                    f"Paired, but could not connect to {target}.")

            self.root.after(
                0,
                lambda i=ip, p=str(conn_port): (
                    self.ip_entry.delete(0, tk.END),
                    self.ip_entry.insert(0, i),
                    self.port_entry.delete(0, tk.END),
                    self.port_entry.insert(0, p),
                ),
            )
            self._persist_session(ip, conn_port)
            self._launch_scrcpy(scrcpy, target)
            return f"Paired & mirroring {target} wirelessly."

        self._run_bg(
            task,
            on_done=lambda m: self._set_status(str(m)),
            btn=self.pair_btn,
            loading_label="Pairing...",
        )


def main() -> None:
    root = tk.Tk()
    AirScreenApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
