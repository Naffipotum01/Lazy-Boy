import json
import os
import time

SAVED_FILE = "lazyboy_saved_devices.json"


def _get_path():
    try:
        from kivy.utils import platform
        if platform == "android":
            from android.os import Environment
            base = Environment.getExternalStorageDirectory().getAbsolutePath()
            return os.path.join(base, ".lazyboy", SAVED_FILE)
    except Exception:
        pass
    return os.path.join(os.path.dirname(__file__), SAVED_FILE)


def load_saved():
    path = _get_path()
    try:
        if os.path.exists(path):
            with open(path, "r") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
    except Exception:
        pass
    return []


def save_device(device):
    devices = load_saved()
    ip = device.get("ip", "")
    now = time.time()

    existing = None
    for d in devices:
        if d.get("ip") == ip:
            existing = d
            break

    entry = {
        "ip": ip,
        "hostname": device.get("hostname", ip),
        "public_ip": device.get("public_ip", ""),
        "ngrok_url": device.get("ngrok_url", ""),
        "last_connected": now,
        "connection_count": (existing.get("connection_count", 0) + 1) if existing else 1,
    }

    if existing:
        idx = devices.index(existing)
        devices[idx] = entry
    else:
        devices.insert(0, entry)

    devices.sort(key=lambda d: d.get("last_connected", 0), reverse=True)
    devices = devices[:20]

    try:
        path = _get_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(devices, f, indent=2)
    except Exception:
        pass
    return devices


def forget_device(ip):
    devices = load_saved()
    devices = [d for d in devices if d.get("ip") != ip]
    try:
        path = _get_path()
        with open(path, "w") as f:
            json.dump(devices, f, indent=2)
    except Exception:
        pass
    return devices


def get_last_device():
    devices = load_saved()
    if devices:
        return devices[0]
    return None


def clear_all():
    try:
        path = _get_path()
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass
