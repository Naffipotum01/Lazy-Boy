import socket
import json
import threading
import time

DISCOVERY_PORT = 5555
BROADCAST_INTERVAL = 2


class DiscoveryService:
    def __init__(self, hostname=None, remote_info=None):
        self.hostname = hostname or socket.gethostname()
        self.ip = self._get_local_ip()
        self.remote_info = remote_info or {}
        self.running = False
        self._thread = None

    def _get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def _broadcast_loop(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(1)
        ann = {
            "type": "lazyboy_announce",
            "hostname": self.hostname,
            "ip": self.ip,
        }
        if self.remote_info.get("public_ip"):
            ann["public_ip"] = self.remote_info["public_ip"]
        if self.remote_info.get("ngrok_url"):
            ann["ngrok_url"] = self.remote_info["ngrok_url"]
        message = json.dumps(ann).encode()
        while self.running:
            try:
                sock.sendto(message, ("255.255.255.255", DISCOVERY_PORT))
            except Exception:
                pass
            time.sleep(BROADCAST_INTERVAL)
        sock.close()

    def _listen_loop(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("0.0.0.0", DISCOVERY_PORT))
        except OSError:
            return
        sock.settimeout(1)
        while self.running:
            try:
                data, addr = sock.recvfrom(1024)
                msg = json.loads(data.decode())
                if msg.get("type") == "lazyboy_discover":
                    ann = {
                        "type": "lazyboy_announce",
                        "hostname": self.hostname,
                        "ip": self.ip,
                    }
                    if self.remote_info.get("public_ip"):
                        ann["public_ip"] = self.remote_info["public_ip"]
                    if self.remote_info.get("ngrok_url"):
                        ann["ngrok_url"] = self.remote_info["ngrok_url"]
                    response = json.dumps(ann).encode()
                    sock.sendto(response, addr)
            except socket.timeout:
                continue
            except Exception:
                continue
        sock.close()

    def start(self):
        self.running = True
        self._thread = threading.Thread(target=self._broadcast_loop, daemon=True)
        self._thread.start()
        self._listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._listen_thread.start()

    def stop(self):
        self.running = False
