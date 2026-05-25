import threading
import subprocess
import time


class NetworkBooster:
    def __init__(self, client=None):
        self.client = client
        self._dns_optimized = False
        self._wifi_optimized = False
        self._monitor_thread = None
        self._monitor_running = False

    def set_client(self, client):
        self.client = client

    # === DNS Optimizer ===
    def set_dns_google(self):
        try:
            subprocess.run(
                ["settings", "put", "global", "private_dns_mode", "hostname"],
                capture_output=True, timeout=5
            )
            subprocess.run(
                ["settings", "put", "global", "private_dns_specifier", "dns.google"],
                capture_output=True, timeout=5
            )
            self._dns_optimized = True
            return {"success": True, "method": "private_dns"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def set_dns_cloudflare(self):
        try:
            subprocess.run(
                ["settings", "put", "global", "private_dns_mode", "hostname"],
                capture_output=True, timeout=5
            )
            subprocess.run(
                ["settings", "put", "global", "private_dns_specifier",
                 "cloudflare-dns.com"],
                capture_output=True, timeout=5
            )
            self._dns_optimized = True
            return {"success": True, "method": "private_dns"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def clear_dns(self):
        try:
            subprocess.run(
                ["settings", "put", "global", "private_dns_mode", "off"],
                capture_output=True, timeout=5
            )
            self._dns_optimized = False
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # === WiFi Optimizer ===
    def optimize_wifi(self):
        results = []
        try:
            r = subprocess.run(
                ["svc", "wifi", "set", "powersave", "false"],
                capture_output=True, timeout=5
            )
            results.append({"cmd": "WiFi power save off", "success": r.returncode == 0})
        except Exception:
            results.append({"cmd": "WiFi power save", "error": "failed"})
        try:
            r = subprocess.run(
                ["svc", "wifi", "set", "band", "auto"],
                capture_output=True, timeout=5
            )
            results.append({"cmd": "WiFi band auto", "success": r.returncode == 0})
        except Exception:
            pass
        try:
            subprocess.run(
                ["settings", "put", "global", "wifi_scan_always_enabled", "0"],
                capture_output=True, timeout=3
            )
            results.append({"cmd": "disable always-scan", "success": True})
        except Exception:
            pass
        self._wifi_optimized = True
        return results

    def set_wifi_band_5ghz(self):
        try:
            subprocess.run(
                ["svc", "wifi", "set", "band", "1"],
                capture_output=True, timeout=5
            )
            return {"success": True, "band": "5GHz"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def set_wifi_band_2ghz(self):
        try:
            subprocess.run(
                ["svc", "wifi", "set", "band", "0"],
                capture_output=True, timeout=5
            )
            return {"success": True, "band": "2.4GHz"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # === Cellular Optimizer ===
    def optimize_cellular(self):
        results = []
        try:
            subprocess.run(
                ["settings", "put", "global", "mobile_data", "1"],
                capture_output=True, timeout=3
            )
            results.append({"cmd": "mobile data on", "success": True})
        except Exception:
            pass
        try:
            r = subprocess.run(
                ["svc", "data", "enable"],
                capture_output=True, timeout=5
            )
            results.append({"cmd": "data enable", "success": r.returncode == 0})
        except Exception:
            pass
        return results

    def set_preferred_network(self, type_str="LTE"):
        types = {
            "LTE": 5, "4G": 5, "3G": 2, "2G": 1,
            "NR": 5, "5G": 5,
        }
        val = types.get(type_str.upper(), 5)
        try:
            subprocess.run(
                ["settings", "put", "global", "preferred_network_mode", str(val)],
                capture_output=True, timeout=5
            )
            return {"success": True, "mode": type_str}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # === Dual Connection ===
    def enable_dual_connection(self):
        try:
            subprocess.run(
                ["settings", "put", "global", "mobile_data_always_on", "1"],
                capture_output=True, timeout=3
            )
            subprocess.run(
                ["svc", "data", "enable"],
                capture_output=True, timeout=5
            )
            return {"success": True, "info": "WiFi + Cellular active"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # === Connection Monitor ===
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
            try:
                r = subprocess.run(
                    ["dumpsys", "connectivity", "--brief"],
                    capture_output=True, text=True, timeout=5
                )
                rssi = self._get_wifi_rssi()
                cellular = self._get_cellular_signal()
                if self.client and self.client.connected:
                    self.client.send({
                        "type": "booster_status",
                        "wifi_rssi": rssi,
                        "cellular_dbm": cellular,
                    })
            except Exception:
                pass
            time.sleep(5)

    def _get_wifi_rssi(self):
        try:
            r = subprocess.run(
                ["dumpsys", "wifi"],
                capture_output=True, text=True, timeout=5
            )
            for line in r.stdout.split("\n"):
                if "RSSI" in line or "rssi" in line:
                    parts = line.split()
                    for p in parts:
                        try:
                            return int(p.replace(",", ""))
                        except ValueError:
                            continue
        except Exception:
            pass
        return None

    def _get_cellular_signal(self):
        try:
            r = subprocess.run(
                ["dumpsys", "telephony", "registry"],
                capture_output=True, text=True, timeout=5
            )
            for line in r.stdout.split("\n"):
                if "signalStrength" in line or "gsmSignalStrength" in line:
                    parts = line.split()
                    for p in parts:
                        try:
                            val = int(p.replace(",", ""))
                            if 0 < val < 100:
                                return -val
                        except ValueError:
                            continue
        except Exception:
            pass
        return None

    def stop_monitor(self):
        self._monitor_running = False

    def stop(self):
        self.stop_monitor()
