import socket
import json
import threading
import subprocess
import os
import tempfile
import shutil
import time
import urllib.request


def get_public_ip():
    try:
        req = urllib.request.urlopen("https://api.ipify.org", timeout=5)
        return req.read().decode().strip()
    except Exception:
        try:
            req = urllib.request.urlopen("https://checkip.amazonaws.com", timeout=5)
            return req.read().decode().strip()
        except Exception:
            return None


def _download_ngrok():
    import platform
    arch = platform.machine()
    bits = platform.architecture()[0]
    if "arm64" in arch.lower() or "aarch64" in arch.lower():
        url = "https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-windows-arm64.zip"
    elif "amd64" in arch.lower() or "x86_64" in arch.lower() or bits == "64bit":
        url = "https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-windows-amd64.zip"
    else:
        url = "https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-windows-386.zip"

    dest = os.path.join(tempfile.gettempdir(), "ngrok.zip")
    out_dir = os.path.join(os.path.dirname(__file__), ".ngrok")
    ngrok_exe = os.path.join(out_dir, "ngrok.exe")
    if os.path.exists(ngrok_exe):
        return ngrok_exe

    try:
        os.makedirs(out_dir, exist_ok=True)
        urllib.request.urlretrieve(url, dest)
        import zipfile
        with zipfile.ZipFile(dest, "r") as zf:
            zf.extract("ngrok.exe", out_dir)
        os.chmod(ngrok_exe, 0o755)
        return ngrok_exe
    except Exception:
        return None


def find_ngrok():
    ngrok_candidates = [
        os.path.join(os.path.dirname(__file__), ".ngrok", "ngrok.exe"),
        os.path.join(os.path.dirname(__file__), "ngrok.exe"),
        shutil.which("ngrok"),
    ]
    for path in ngrok_candidates:
        if path and os.path.exists(path):
            return path
    return _download_ngrok()


def try_upnp(port, protocol="TCP"):
    try:
        import miniupnpc
        upnp = miniupnpc.UPnP()
        upnp.discoverdelay = 200
        upnp.discover()
        upnp.selectigd()
        added = upnp.addportmapping(port, protocol, upnp.lanaddr, port,
                                    "Lazy Boy Remote", "")
        return added
    except Exception:
        return False


def remove_upnp(port, protocol="TCP"):
    try:
        import miniupnpc
        upnp = miniupnpc.UPnP()
        upnp.discoverdelay = 200
        upnp.discover()
        upnp.selectigd()
        upnp.deleteportmapping(port, protocol)
    except Exception:
        pass


class RemoteAccess:
    def __init__(self, ws_port=8765, fs_port=8766):
        self.ws_port = ws_port
        self.fs_port = fs_port
        self.public_ip = None
        self.ngrok_url = None
        self.ngrok_process = None
        self.upnp_enabled = False
        self.ngrok_enabled = False

    def detect_public_ip(self):
        self.public_ip = get_public_ip()
        return self.public_ip

    def start_upnp(self):
        added_ws = try_upnp(self.ws_port)
        added_fs = try_upnp(self.fs_port, "TCP")
        self.upnp_enabled = added_ws or added_fs
        return self.upnp_enabled

    def stop_upnp(self):
        if self.upnp_enabled:
            remove_upnp(self.ws_port)
            remove_upnp(self.fs_port)
            self.upnp_enabled = False

    def start_ngrok(self, auth_token=None):
        ngrok_exe = find_ngrok()
        if not ngrok_exe:
            print("[!] ngrok not found. Install from https://ngrok.com/download")
            return None

        if auth_token:
            subprocess.run([ngrok_exe, "config", "add-authtoken", auth_token],
                           capture_output=True)

        self.ngrok_process = subprocess.Popen(
            [ngrok_exe, "tcp", str(self.ws_port), "--log=stdout"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        self.ngrok_enabled = True

        for _ in range(15):
            try:
                req = urllib.request.urlopen(
                    "http://127.0.0.1:4040/api/tunnels", timeout=2
                )
                data = json.loads(req.read())
                tunnels = data.get("tunnels", [])
                if tunnels:
                    self.ngrok_url = tunnels[0]["public_url"]
                    print(f"[*] ngrok tunnel: {self.ngrok_url}")
                    return self.ngrok_url
            except Exception:
                pass
            time.sleep(1)

        print("[!] ngrok tunnel may not be ready. Check http://127.0.0.1:4040")
        return None

    def stop_ngrok(self):
        self.ngrok_enabled = False
        if self.ngrok_process:
            try:
                self.ngrok_process.terminate()
                self.ngrok_process.wait(timeout=3)
            except Exception:
                try:
                    subprocess.run(["taskkill", "/f", "/im", "ngrok.exe"],
                                   capture_output=True)
                except Exception:
                    pass
            self.ngrok_process = None
        self.ngrok_url = None

    def get_connection_info(self):
        info = {
            "local_ip": None,
            "public_ip": self.public_ip,
            "ws_port": self.ws_port,
            "upnp": self.upnp_enabled,
            "ngrok_url": self.ngrok_url,
        }
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            info["local_ip"] = s.getsockname()[0]
            s.close()
        except Exception:
            pass
        return info

    def cleanup(self):
        self.stop_ngrok()
        self.stop_upnp()


if __name__ == "__main__":
    ra = RemoteAccess()
    ip = ra.detect_public_ip()
    print(f"Public IP: {ip}")
    print(f"ngrok: {find_ngrok()}")
