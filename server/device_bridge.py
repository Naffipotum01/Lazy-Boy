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
                                "type": "usb_tether",
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
