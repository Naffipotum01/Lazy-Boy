import threading
import subprocess
import time


class HotspotHelper:
    def __init__(self, client=None):
        self.client = client
        self._sharing = False
        self._monitor_running = False
        self._monitor_thread = None

    def set_client(self, client):
        self.client = client

    def share_cellular_to_pc(self):
        """Share phone's cellular internet to PC via USB tethering."""
        results = []
        try:
            r = subprocess.run(
                ["settings", "put", "global", "usb_tethering_enabled", "1"],
                capture_output=True, timeout=5
            )
            results.append({"cmd": "USB tether", "success": r.returncode == 0})
        except Exception as e:
            results.append({"cmd": "USB tether", "error": str(e)})

        try:
            r = subprocess.run(
                ["svc", "data", "enable"],
                capture_output=True, timeout=5
            )
            results.append({"cmd": "mobile data", "success": True})
        except Exception:
            pass

        self._sharing = True
        return results

    def share_cellular_via_wifi(self, ssid="LazyBoy_Fallback", password="LazyBoy123"):
        """Share phone's cellular via WiFi hotspot (fallback if USB unavailable)."""
        try:
            subprocess.run(
                ["svc", "wifi", "set", "hotspot", "enabled", "1"],
                capture_output=True, timeout=5
            )
            self._sharing = True
            return {"success": True, "method": "wifi_hotspot", "ssid": ssid}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def stop_sharing(self):
        try:
            subprocess.run(
                ["settings", "put", "global", "usb_tethering_enabled", "0"],
                capture_output=True, timeout=3
            )
        except Exception:
            pass
        try:
            subprocess.run(
                ["svc", "wifi", "set", "hotspot", "enabled", "0"],
                capture_output=True, timeout=3
            )
        except Exception:
            pass
        self._sharing = False

    def start_monitor(self):
        if self._monitor_running:
            return
        self._monitor_running = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop, daemon=True
        )
        self._monitor_thread.start()

    def _monitor_loop(self):
        while self._monitor_running:
            if self.client and self.client.connected and self._sharing:
                try:
                    r = subprocess.run(
                        ["dumpsys", "connectivity"],
                        capture_output=True, text=True, timeout=5
                    )
                    active_network = "cellular"
                    for line in r.stdout.split("\n"):
                        if "ActiveNetwork:" in line:
                            if "WIFI" in line.upper():
                                active_network = "wifi"
                            break

                    if self.client:
                        self.client.send({
                            "type": "hotspot_phone_status",
                            "sharing": self._sharing,
                            "active_network": active_network,
                        })
                except Exception:
                    pass
            time.sleep(10)

    def stop_monitor(self):
        self._monitor_running = False

    def stop(self):
        self.stop_monitor()
        self.stop_sharing()
