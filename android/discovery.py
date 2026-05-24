import socket
import json
import threading
import time

DISCOVERY_PORT = 5555
SCAN_TIMEOUT = 3


class NetworkDiscovery:
    def __init__(self, callback):
        self.callback = callback
        self.running = False
        self._thread = None
        self._found = {}

    def _get_broadcast_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            parts = local_ip.split(".")
            parts[-1] = "255"
            return ".".join(parts)
        except Exception:
            return "255.255.255.255"

    def scan_once(self):
        self._found = {}
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(SCAN_TIMEOUT)

        broadcast_ip = self._get_broadcast_ip()
        message = json.dumps({"type": "lazyboy_discover"}).encode()

        try:
            sock.sendto(message, (broadcast_ip, DISCOVERY_PORT))
        except Exception:
            pass

        deadline = time.time() + SCAN_TIMEOUT
        while time.time() < deadline:
            try:
                data, addr = sock.recvfrom(1024)
                msg = json.loads(data.decode())
                if msg.get("type") == "lazyboy_announce":
                    ip = msg.get("ip", addr[0])
                    hostname = msg.get("hostname", "Unknown")
                    if ip not in self._found:
                        self._found[ip] = {
                            "ip": ip,
                            "hostname": hostname
                        }
                        self.callback(list(self._found.values()))
            except socket.timeout:
                break
            except Exception:
                break

        sock.close()
        return list(self._found.values())

    def start_scan(self):
        self.running = True
        self._thread = threading.Thread(target=self._scan_loop, daemon=True)
        self._thread.start()

    def _scan_loop(self):
        while self.running:
            self.scan_once()
            time.sleep(3)

    def stop(self):
        self.running = False
