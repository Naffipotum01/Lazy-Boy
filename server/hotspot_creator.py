import threading
import subprocess
import socket
import time
import json
import re


class HotspotCreator:
    def __init__(self):
        self._running = False
        self._ssid = "LazyBoy-FreeNet"
        self._password = "LazyBoy123"
        self._method = None
        self._monitor_thread = None
        self._clients = []
        self._dual_wan = False
        self._phone_ip = None

    def set_phone_ip(self, ip):
        self._phone_ip = ip

    def _use_windows_mobile_hotspot(self, ssid, password):
        """Use Windows 10/11 native Mobile Hotspot feature via PowerShell."""
        try:
            ps = f'''
            $connection = (Get-NetConnectionProfile | Where-Object {{
                $_.InternetConnectionConfiguration -eq "Connected"
            }} | Select-Object -First 1).Name
            if (-not $connection) {{ exit 1 }}
            $result = netsh wlan set hostednetwork mode=allow ssid="{ssid}" key="{password}"
            $result = netsh wlan start hostednetwork
            '''
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps],
                capture_output=True, text=True, timeout=30
            )
            return r.returncode == 0, r.stdout + r.stderr
        except Exception:
            return False, ""

    def _use_hostednetwork(self, ssid, password):
        """Fallback: use netsh wlan hostednetwork."""
        try:
            r1 = subprocess.run(
                ["netsh", "wlan", "set", "hostednetwork",
                 f"mode=allow", f"ssid={ssid}", f"key={password}"],
                capture_output=True, text=True, timeout=10
            )
            r2 = subprocess.run(
                ["netsh", "wlan", "start", "hostednetwork"],
                capture_output=True, text=True, timeout=10
            )
            ok = r2.returncode == 0 or "started" in r2.stdout.lower()
            return ok, r2.stdout + r2.stderr
        except Exception as e:
            return False, str(e)

    def _enable_ics(self):
        """Enable Internet Connection Sharing from active internet to hotspot."""
        try:
            ps = '''
            $netShare = New-Object -ComObject HNetCfg.HNetShare
            $connections = $netShare.EnumEveryConnection
            $internetConn = $null
            $hotspotConn = $null
            foreach ($conn in $connections) {
                $props = $netShare.NetConnectionProps($conn)
                $name = $props.Name
                $guid = $props.Guid
                try {
                    $config = $netShare.INetSharingConfigurationForINetConnection($conn)
                    $status = $config.SharingEnabled
                } catch { $status = $false }
                if ($name -like "*Wi-Fi*" -and -not $status) { $hotspotConn = $conn }
                elseif ($name -like "*Ethernet*" -and $status -eq $false) { $internetConn = $conn }
            }
            if (-not $internetConn -or -not $hotspotConn) {
                foreach ($conn in $connections) {
                    $props = $netShare.NetConnectionProps($conn)
                    $config = $netShare.INetSharingConfigurationForINetConnection($conn)
                    try { $config.EnableSharing(0); break } catch {}
                }
                foreach ($conn in $connections) {
                    $props = $netShare.NetConnectionProps($conn)
                    if ($props.Status -eq 2) {
                        $config = $netShare.INetSharingConfigurationForINetConnection($conn)
                        try { $config.EnableSharing(1) } catch {}
                        break
                    }
                }
            } else {
                $ic = $netShare.INetSharingConfigurationForINetConnection($internetConn)
                $ic.EnableSharing(0)
                $hc = $netShare.INetSharingConfigurationForINetConnection($hotspotConn)
                $hc.EnableSharing(1)
            }
            Write-Output "ICS configured"
            '''
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps],
                capture_output=True, text=True, timeout=30
            )
            return r.returncode == 0
        except Exception:
            return False

    def _enable_dual_wan_routing(self):
        """Add routes to load-balance across PC internet + phone USB tether."""
        try:
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-NetAdapter | Where-Object { $_.Status -eq 'Up' } | "
                 "Select-Object Name, ifIndex | ConvertTo-Json"],
                capture_output=True, text=True, timeout=15
            )
            adapters = json.loads(r.stdout) if r.stdout.strip() else []
            if isinstance(adapters, dict):
                adapters = [adapters]

            phone_idx = None
            pc_idx = None
            for a in adapters:
                name = a.get("Name", "").lower()
                if any(kw in name for kw in ["usb", "rndis", "ethernet", "local"]):
                    if "virtual" not in name and "bluetooth" not in name:
                        if not pc_idx:
                            pc_idx = a.get("ifIndex")
                elif "wi-fi" in name or "wifi" in name:
                    if not phone_idx:
                        phone_idx = a.get("ifIndex")

            if pc_idx and phone_idx:
                subprocess.run(
                    ["netsh", "int", "ipv4", "set", "interface", str(pc_idx),
                     "metric=25"],
                    capture_output=True, timeout=10
                )
                subprocess.run(
                    ["netsh", "int", "ipv4", "set", "interface", str(phone_idx),
                     "metric=25"],
                    capture_output=True, timeout=10
                )
                self._dual_wan = True
                return True
            return False
        except Exception:
            return False

    def create(self, ssid="LazyBoy-FreeNet", password="LazyBoy123"):
        self._ssid = ssid
        self._password = password

        ok, msg = self._use_hostednetwork(ssid, password)
        if ok:
            self._method = "hostednetwork"
        else:
            ok, msg = self._use_windows_mobile_hotspot(ssid, password)
            if ok:
                self._method = "windows_hotspot"

        if ok:
            self._enable_ics()
            self._enable_dual_wan_routing()
            self._running = True
            self._start_monitor()
            return {"success": True, "method": self._method, "ssid": ssid}
        return {"success": False, "error": msg}

    def _start_monitor(self):
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop, daemon=True
        )
        self._monitor_thread.start()

    def _monitor_loop(self):
        while self._running:
            try:
                if self._method == "hostednetwork":
                    r = subprocess.run(
                        ["netsh", "wlan", "show", "hostednetwork"],
                        capture_output=True, text=True, timeout=10
                    )
                    out = r.stdout
                    clients = []
                    in_client = False
                    for line in out.split("\n"):
                        if "BSSID" in line and "Status" in out:
                            pass
                        if "MAC" in line or "radio" in line.lower():
                            in_client = True
                            continue
                        if in_client:
                            parts = line.strip().split()
                            for p in parts:
                                if re.match(r"^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$", p):
                                    clients.append(p)
                                    break
                    self._clients = clients
            except Exception:
                pass
            time.sleep(10)

    def get_status(self):
        info = {
            "running": self._running,
            "ssid": self._ssid,
            "method": self._method,
            "clients": len(self._clients),
            "client_list": self._clients[:10],
            "dual_wan": self._dual_wan,
            "phone_ip": self._phone_ip,
        }
        try:
            r = subprocess.run(
                ["netsh", "wlan", "show", "hostednetwork"],
                capture_output=True, text=True, timeout=10
            )
            for line in r.stdout.split("\n"):
                if "Status" in line:
                    info["status"] = line.split(":")[-1].strip()
                    break
        except Exception:
            info["status"] = "unknown"
        return info

    def get_bandwidth_usage(self):
        try:
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-NetAdapterStatistics | Where-Object { $_.Status -eq 'Up' } | "
                 "Select-Object Name, ReceivedBytes, SentBytes | ConvertTo-Json"],
                capture_output=True, text=True, timeout=10
            )
            if r.stdout.strip():
                data = json.loads(r.stdout)
                if isinstance(data, dict):
                    data = [data]
                return [{
                    "name": d.get("Name", ""),
                    "rx": d.get("ReceivedBytes", 0),
                    "tx": d.get("SentBytes", 0),
                } for d in data]
        except Exception:
            pass
        return []

    def stop(self):
        self._running = False
        try:
            subprocess.run(
                ["netsh", "wlan", "stop", "hostednetwork"],
                capture_output=True, timeout=10
            )
        except Exception:
            pass
        self._dual_wan = False
        self._clients = []
