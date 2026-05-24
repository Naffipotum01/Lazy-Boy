import threading
import time
import subprocess
import socket
import netifaces


class DeviceBridge:
    def __init__(self):
        self._running = False
        self._location_thread = None
        self._send_callback = None

    def set_send_callback(self, cb):
        self._send_callback = cb

    # === Location Bridge ===
    def location_set(self, lat, lon, accuracy=0):
        if self._send_callback:
            self._send_callback({
                "type": "bridge_location",
                "lat": lat, "lon": lon,
                "accuracy": accuracy,
            })

    # === Network Bridge ===
    def share_wifi_to_pc(self):
        """Share phone's WiFi connection to PC via USB tethering."""
        try:
            result = subprocess.run(
                ["netsh", "wlan", "show", "interfaces"],
                capture_output=True, text=True, timeout=10
            )
            return {"success": True, "info": result.stdout}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def share_pc_wifi_to_phone(self):
        """Start Windows hotspot to share internet to phone."""
        try:
            subprocess.run(
                ["netsh", "wlan", "set", "hostednetwork",
                 "mode=allow", "ssid=LazyBoy_Hotspot",
                 "key=LazyBoy123"],
                capture_output=True, timeout=10
            )
            result = subprocess.run(
                ["netsh", "wlan", "start", "hostednetwork"],
                capture_output=True, text=True, timeout=10
            )
            return {"success": True, "info": result.stdout}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def stop_pc_hotspot(self):
        try:
            subprocess.run(
                ["netsh", "wlan", "stop", "hostednetwork"],
                capture_output=True, timeout=10
            )
        except Exception:
            pass

    # === USB Bridge ===
    def detect_usb_connections(self):
        """Detect devices connected via USB and suggest tethering."""
        interfaces = []
        try:
            import netifaces as ni
            for iface in ni.interfaces():
                addrs = ni.ifaddresses(iface)
                if ni.AF_INET in addrs:
                    for addr in addrs[ni.AF_INET]:
                        ip = addr["addr"]
                        if ip.startswith("192.168.42.") or ip.startswith("192.168.43."):
                            interfaces.append({
                                "interface": iface,
                                "ip": ip,
                                "type": "usb_tether_phone_to_pc",
                            })
                        elif ip.startswith("169.254."):
                            interfaces.append({
                                "interface": iface,
                                "ip": ip,
                                "type": "usb_direct",
                            })
        except Exception:
            pass
        return interfaces

    def _find_usb_adapters(self):
        """Find USB/RNDIS network adapters on Windows."""
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-NetAdapter | Where-Object { $_.Status -eq 'Up' } | "
                 "Select-Object Name, InterfaceDescription, InterfaceIndex, Status | ConvertTo-Json"],
                capture_output=True, text=True, timeout=15
            )
            import json
            adapters = json.loads(result.stdout)
            if isinstance(adapters, dict):
                adapters = [adapters]

            usb_adapters = []
            for a in adapters:
                desc = a.get("InterfaceDescription", "") + a.get("Name", "")
                if any(kw in desc.lower() for kw in ["rndis", "usb", "remote ndis",
                                                       "mobile", "ethernet"]):
                    if not any(kw in desc.lower() for kw in ["virtual", "vmware",
                                                              "virtualbox", "hyper-v"]):
                        usb_adapters.append(a)
            return usb_adapters
        except Exception:
            return []

    def share_pc_internet_via_usb(self):
        """
        Share PC's internet to the phone via USB connection.
        Enables Internet Connection Sharing (ICS) on Windows.
        """
        try:
            usb_adapters = self._find_usb_adapters()
            if not usb_adapters:
                return {"success": False, "error": "No USB adapter found. Is phone connected with tethering enabled?"}

            usb_iface = usb_adapters[0]["InterfaceIndex"]

            ps = f"""
            $usbIdx = {usb_iface}
            $usbAdapter = Get-NetAdapter -InterfaceIndex $usbIdx

            $internetAdapter = Get-NetAdapter | Where-Object {{
                $_.Status -eq 'Up' -and
                $_.InterfaceIndex -ne $usbIdx -and
                $_.InterfaceDescription -notmatch 'Virtual|Hyper-V|Bluetooth|Loopback'
            }} | Select-Object -First 1

            if (-not $internetAdapter) {{
                Write-Output "No internet adapter found"
                exit 1
            }}

            $netShare = New-Object -ComObject HNetCfg.HNetShare
            $connections = $netShare.EnumEveryConnection
            $internetConn = $null
            $usbConn = $null

            foreach ($conn in $connections) {{
                $props = $netShare.NetConnectionProps($conn)
                if ($props.Name -eq $internetAdapter.Name) {{
                    $internetConn = $conn
                }}
                if ($props.Name -eq $usbAdapter.Name) {{
                    $usbConn = $conn
                }}
            }}

            if ($internetConn -and $usbConn) {{
                $internetConfig = $netShare.INetSharingConfigurationForINetConnection($internetConn)
                $internetConfig.EnableSharing(0)
                $usbConfig = $netShare.INetSharingConfigurationForINetConnection($usbConn)
                $usbConfig.EnableSharing(1)
                Write-Output "ICS enabled: PC internet -> USB phone"
            }} else {{
                Write-Output "Could not find connections for ICS"
                exit 1
            }}
            """

            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                return {"success": True, "info": result.stdout.strip()}
            else:
                return {"success": False, "error": result.stderr.strip() or result.stdout.strip()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def stop_pc_usb_sharing(self):
        """Disable ICS on the USB connection."""
        try:
            ps = """
            $netShare = New-Object -ComObject HNetCfg.HNetShare
            $connections = $netShare.EnumEveryConnection
            foreach ($conn in $connections) {
                $config = $netShare.INetSharingConfigurationForINetConnection($conn)
                if ($config.SharingEnabled) {
                    $config.DisableSharing()
                }
            }
            Write-Output "ICS disabled on all connections"
            """
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps],
                capture_output=True, timeout=30
            )
        except Exception:
            pass

    def setup_adb_reverse(self):
        """Try ADB reverse port forwarding for USB WebSocket tunnel."""
        try:
            subprocess.run(
                ["adb", "reverse", "tcp:8765", "tcp:8765"],
                capture_output=True, timeout=10
            )
            return {"success": True, "method": "adb_reverse"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def setup_adb_forward(self):
        """Forward phone port to PC via ADB (for headless display)."""
        try:
            subprocess.run(
                ["adb", "forward", "tcp:8765", "tcp:8765"],
                capture_output=True, timeout=10
            )
            return {"success": True, "method": "adb_forward"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # === Radio Bridge ===
    def phone_fm_radio(self):
        """Placeholder for phone FM radio → PC audio streaming."""
        pass

    # === Status ===
    def get_bridge_status(self):
        info = {
            "usb_devices": self.detect_usb_connections(),
            "has_location": False,
            "network": {},
        }
        try:
            hostname = socket.gethostname()
            ip = socket.gethostbyname(hostname)
            info["network"]["hostname"] = hostname
            info["network"]["ip"] = ip
        except Exception:
            pass
        return info

    def stop(self):
        self._running = False
