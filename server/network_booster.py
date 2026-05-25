import threading
import subprocess
import socket
import time
import struct
import select


class NetworkBooster:
    def __init__(self):
        self._dns_running = False
        self._dns_thread = None
        self._dns_cache = {}
        self._dns_server = ("1.1.1.1", 53)
        self._optimized = False

    # === Speed Test ===
    def speed_test(self):
        result = {"download_mbps": 0, "upload_mbps": 0, "latency_ms": 0, "error": None}
        try:
            result["latency_ms"] = self._ping_test()
            result["download_mbps"] = self._download_test()
            result["upload_mbps"] = self._upload_test()
        except Exception as e:
            result["error"] = str(e)
        return result

    def _ping_test(self):
        try:
            start = time.time()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            sock.connect(("1.1.1.1", 443))
            sock.close()
            return int((time.time() - start) * 1000)
        except Exception:
            return 0

    def _download_test(self):
        try:
            import urllib.request
            start = time.time()
            data = urllib.request.urlopen(
                "http://speedtest.tele2.net/1MB.zip", timeout=5
            ).read()
            elapsed = time.time() - start
            bits = len(data) * 8
            return round(bits / elapsed / 1_000_000, 1)
        except Exception:
            return 0

    def _upload_test(self):
        return 0

    # === DNS Accelerator ===
    def start_dns_cache(self):
        if self._dns_running:
            return {"success": True, "info": "DNS cache already running"}
        self._dns_running = True
        self._dns_thread = threading.Thread(target=self._dns_loop, daemon=True)
        self._dns_thread.start()
        return {"success": True, "info": "DNS cache started on port 53"}

    def stop_dns_cache(self):
        self._dns_running = False
        return {"success": True, "info": "DNS cache stopped"}

    def _dns_loop(self):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("127.0.0.1", 53))
            sock.settimeout(1)
            up_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            up_sock.settimeout(3)

            while self._dns_running:
                try:
                    data, addr = sock.recvfrom(512)
                    cache_key = data[:20]
                    if cache_key in self._dns_cache:
                        sock.sendto(self._dns_cache[cache_key], addr)
                        continue
                    up_sock.sendto(data, self._dns_server)
                    try:
                        response, _ = up_sock.recvfrom(512)
                        self._dns_cache[cache_key] = response
                        sock.sendto(response, addr)
                    except socket.timeout:
                        pass
                except socket.timeout:
                    pass
            sock.close()
            up_sock.close()
        except Exception:
            self._dns_running = False

    def set_dns_windows(self, dns_servers=["1.1.1.1", "1.0.0.1"]):
        results = []
        for i, dns in enumerate(dns_servers):
            try:
                idx = i + 1
                subprocess.run(
                    ["netsh", "interface", "ip", "set", "dns",
                     f"name=Wi-Fi", f"source=static", f"addr={dns}",
                     f"register=primary", f"validate=no"],
                    capture_output=True, timeout=10
                )
                results.append({"server": dns, "success": True})
            except Exception as e:
                results.append({"server": dns, "success": False, "error": str(e)})
        return results

    # === TCP Optimizer ===
    def optimize_tcp(self):
        results = []
        commands = [
            "netsh int tcp set global autotuninglevel=normal",
            "netsh int tcp set global chimney=disabled",
            "netsh int tcp set global rss=enabled",
            "netsh int tcp set global netdma=enabled",
            "netsh int tcp set global timestamps=disabled",
            "netsh int tcp set global initialRto=2000",
            "netsh int tcp set global nonsackrttresiliency=disabled",
        ]
        for cmd in commands:
            try:
                r = subprocess.run(
                    cmd.split(), capture_output=True, text=True, timeout=10
                )
                results.append({
                    "cmd": cmd[:50],
                    "success": r.returncode == 0,
                })
            except Exception as e:
                results.append({"cmd": cmd[:50], "success": False, "error": str(e)})
        self._optimized = True
        return results

    def reset_tcp(self):
        try:
            subprocess.run(
                ["netsh", "int", "tcp", "set", "global", "autotuninglevel=normal"],
                capture_output=True, timeout=10
            )
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # === Hotspot Optimizer ===
    def optimize_hotspot(self):
        results = []
        try:
            r = subprocess.run(
                ["netsh", "wlan", "set", "hostednetwork", "mode=allow"],
                capture_output=True, text=True, timeout=10
            )
            results.append({"cmd": "enable hostednetwork", "success": r.returncode == 0})
        except Exception as e:
            results.append({"cmd": "enable hostednetwork", "error": str(e)})
        try:
            r = subprocess.run(
                ["netsh", "wlan", "set", "autoconfig", "enabled=no", "interface=Wi-Fi"],
                capture_output=True, text=True, timeout=10
            )
            results.append({"cmd": "disable auto WiFi scan", "success": True})
        except Exception:
            pass
        try:
            r = subprocess.run(
                ["netsh", "wlan", "set", "channel", "auto", "interface=Wi-Fi"],
                capture_output=True, text=True, timeout=10
            )
            results.append({"cmd": "auto channel", "success": True})
        except Exception:
            pass
        return results

    # === Connection Stats ===
    def get_connection_info(self):
        info = {"interfaces": [], "dns_cache": len(self._dns_cache), "tcp_optimized": self._optimized}
        try:
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-NetAdapter | Where-Object {$_.Status -eq 'Up'} | "
                 "Select-Object Name, InterfaceDescription, LinkSpeed, Status | ConvertTo-Json"],
                capture_output=True, text=True, timeout=15
            )
            import json
            if r.stdout.strip():
                adapters = json.loads(r.stdout)
                if isinstance(adapters, dict):
                    adapters = [adapters]
                info["interfaces"] = [
                    {
                        "name": a.get("Name", ""),
                        "speed": a.get("LinkSpeed", ""),
                        "desc": a.get("InterfaceDescription", ""),
                    }
                    for a in adapters
                ]
        except Exception:
            pass
        return info

    def speed_history(self):
        return {"cached": False, "message": "Run speed_test to measure"}

    def stop(self):
        self.stop_dns_cache()
