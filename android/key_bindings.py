import json
import os

DEFAULT_BINDINGS = {
    "A": "space",
    "B": "lctrl",
    "X": "e",
    "Y": "r",
    "LB": "q",
    "RB": "tab",
    "LT": "rightmouse",
    "RT": "leftmouse",
    "DUP": "up",
    "DDOWN": "down",
    "DLEFT": "left",
    "DRIGHT": "right",
    "STATUS": "f",
    "SELECT": "shift",
    "START": "enter",
}

CONFIG_FILE = "lazyboy_bindings.json"


def load_bindings():
    try:
        path = _get_config_path()
        if os.path.exists(path):
            with open(path, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return dict(DEFAULT_BINDINGS)


def save_bindings(bindings):
    try:
        path = _get_config_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(bindings, f, indent=2)
        return True
    except Exception:
        return False


def reset_bindings():
    save_bindings(dict(DEFAULT_BINDINGS))
    return dict(DEFAULT_BINDINGS)


def _get_config_path():
    from kivy.utils import platform
    if platform == "android":
        from android.os import Environment
        base = Environment.getExternalStorageDirectory().getAbsolutePath()
        return os.path.join(base, ".lazyboy", CONFIG_FILE)
    return os.path.join(os.path.dirname(__file__), CONFIG_FILE)
