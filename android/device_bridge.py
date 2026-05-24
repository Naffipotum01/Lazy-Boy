import threading
import time
import subprocess


class DeviceBridge:
    def __init__(self, client=None):
        self.client = client
        self._running = False
        self._location_thread = None
        self._last_location = None
        self._usb_detected = False

    def set_client(self, client):
        self.client = client

    # === Location Bridge ===
    def start_location_sharing(self):
        self._running = True
        self._location_thread = threading.Thread(
            target=self._location_loop, daemon=True
        )
        self._location_thread.start()

    def stop_location_sharing(self):
        self._running = False

    def _location_loop(self):
        try:
            from jnius import autoclass
            from android import activity

            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            Context = autoclass("android.content.Context")
            LocationManager = autoclass("android.location.LocationManager")
            Criteria = autoclass("android.location.Criteria")

            context = PythonActivity.mActivity
            loc_mgr = context.getSystemService(Context.LOCATION_SERVICE)
            criteria = Criteria()
            criteria.setAccuracy(Criteria.ACCURACY_FINE)
            provider = loc_mgr.getBestProvider(criteria, True)

            if not provider:
                return

            while self._running:
                try:
                    loc = loc_mgr.getLastKnownLocation(provider)
                    if loc:
                        lat = loc.getLatitude()
                        lon = loc.getLongitude()
                        acc = loc.getAccuracy()
                        self._last_location = (lat, lon, acc)
                        if self.client and self.client.connected:
                            self.client.send({
                                "type": "bridge_location",
                                "lat": lat, "lon": lon,
                                "accuracy": acc,
                            })
                except Exception:
                    pass
                time.sleep(5)
        except Exception:
            pass

    def get_last_location(self):
        return self._last_location

    # === USB Bridge ===
    def enable_usb_tethering(self):
        """Enable USB tethering — phone shares internet TO PC."""
        try:
            subprocess.run(
                ["settings", "put", "global", "usb_tethering_enabled", "1"],
                capture_output=True, timeout=5
            )
            self._usb_detected = True
            return {"success": True, "method": "phone_to_pc"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def request_pc_usb_sharing(self):
        """Request PC to share internet back TO phone over USB.
        The PC enables ICS (Internet Connection Sharing) on its USB/RNDIS
        adapter so the phone gets internet access through the cable.
        """
        if self.client and self.client.connected:
            self.client.send({
                "type": "bridge_usb_share",
                "direction": "pc_to_phone",
            })
            return {"success": True, "method": "requested"}
        return {"success": False, "error": "Not connected"}

    def enable_usb_reverse_tether(self):
        """
        Force the phone's USB network interface (rndis0/usb0) to
        request an IP via DHCP so it receives internet from the PC.
        Run this AFTER the PC has enabled ICS.
        """
        try:
            result = subprocess.run(
                ["netcfg", "usb0", "dhcp"],
                capture_output=True, timeout=10
            )
            if result.returncode == 0:
                return {"success": True, "method": "dhcp"}
        except Exception:
            pass
        try:
            result = subprocess.run(
                ["dhcptool", "usb0"],
                capture_output=True, timeout=10
            )
            if result.returncode == 0:
                return {"success": True, "method": "dhcptool"}
        except Exception:
            pass
        return {"success": False, "error": "Could not get DHCP on USB interface"}

    def check_usb_connection(self):
        """Detect if connected to PC via USB."""
        try:
            from jnius import autoclass
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            UsbManager = autoclass("android.hardware.usb.UsbManager")
            context = PythonActivity.mActivity
            usb_mgr = context.getSystemService(Context.USB_SERVICE)
            devices = usb_mgr.getDeviceList()
            self._usb_detected = devices and devices.size() > 0
            return self._usb_detected
        except Exception:
            return False

    def get_usb_ip(self):
        """Get IP address on USB network interface."""
        try:
            import socket
            import fcntl
            import struct

            def get_ip(ifname):
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                try:
                    return socket.inet_ntoa(
                        fcntl.ioctl(
                            s.fileno(), 0x8915,
                            struct.pack("256s", ifname[:15].encode())
                        )[20:24]
                    )
                except Exception:
                    return None

            for iface in ["usb0", "rndis0", "eth0"]:
                ip = get_ip(iface)
                if ip:
                    return ip
        except Exception:
            pass
        return None

    # === Network Bridge ===
    def share_phone_wifi(self):
        """Share phone's WiFi as hotspot."""
        try:
            subprocess.run(
                ["svc", "wifi", "set", "hotspot", "enabled", "1"],
                capture_output=True, timeout=5
            )
            return {"success": True, "method": "wifi_hotspot"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def connect_to_pc_hotspot(self, ssid="LazyBoy_Hotspot", password="LazyBoy123"):
        """Connect phone to PC's hotspot."""
        try:
            subprocess.run(
                ["cmd", "wifi", "connect-network", ssid, password],
                capture_output=True, timeout=10
            )
            return {"success": True, "method": "connect_hotspot"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # === Sensor Bridge ===
    def get_sensor_data(self):
        """Get available sensor info from phone."""
        try:
            from jnius import autoclass
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            Context = autoclass("android.content.Context")
            SensorManager = autoclass("android.hardware.SensorManager")
            context = PythonActivity.mActivity
            sm = context.getSystemService(Context.SENSOR_SERVICE)
            sensors = sm.getSensorList(SensorManager.TYPE_ALL)
            result = []
            for i in range(sensors.size()):
                s = sensors.get(i)
                result.append({
                    "name": str(s.getName()),
                    "type": s.getType(),
                    "vendor": str(s.getVendor()),
                    "power": s.getPower(),
                })
            return result
        except Exception:
            return []

    def stop(self):
        self._running = False
        self.stop_location_sharing()
