import socket
import json
import threading
import time
import subprocess


DISCOVERY_PORT = 5555


class StandaloneHotspot:
    def __init__(self):
        self._active = False
        self._broadcast_thread = None
        self._ssid = "LazyBoy-Hotspot"
        self._password = "LazyBoy123"
        self._hotspot_ip = "192.168.43.1"

    def start(self, ssid="LazyBoy-Hotspot", password="LazyBoy123"):
        self._ssid = ssid
        self._password = password

        try:
            subprocess.run(
                ["svc", "wifi", "set", "hotspot", "enabled", "1"],
                capture_output=True, timeout=5
            )
            subprocess.run(
                ["settings", "put", "global", "wifi_hotspot_ssid", ssid],
                capture_output=True, timeout=3
            )
            subprocess.run(
                ["settings", "put", "global", "wifi_hotspot_password", password],
                capture_output=True, timeout=3
            )
        except Exception:
            pass

        self._active = True
        self._start_broadcasting()
        return {"success": True, "ssid": ssid, "password": password}

    def _start_broadcasting(self):
        self._broadcast_thread = threading.Thread(
            target=self._broadcast_loop, daemon=True
        )
        self._broadcast_thread.start()

    def _broadcast_loop(self):
        try:
            import android
            from jnius import autoclass
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
        except Exception:
            PythonActivity = None

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        announce = json.dumps({
            "type": "lazyboy_announce",
            "ip": self._hotspot_ip,
            "hostname": "LazyBoy Phone",
            "hotspot_ssid": self._ssid,
            "port": 8765,
        }).encode()

        while self._active:
            try:
                sock.sendto(announce, ("192.168.43.255", DISCOVERY_PORT))
                sock.sendto(announce, ("255.255.255.255", DISCOVERY_PORT))
            except Exception:
                pass
            time.sleep(2)

        sock.close()

    def get_info(self):
        return {
            "active": self._active,
            "ssid": self._ssid,
            "password": self._password,
            "ip": self._hotspot_ip,
        }

    def stop(self):
        self._active = False
        try:
            subprocess.run(
                ["svc", "wifi", "set", "hotspot", "enabled", "0"],
                capture_output=True, timeout=3
            )
        except Exception:
            pass
