import time
import subprocess
import pyautogui
import re


VOICE_COMMANDS = {
    "start": {"action": "key", "key": "win"},
    "open start": {"action": "key", "key": "win"},
    "show desktop": {"action": "hotkey", "keys": ["win", "d"]},
    "minimize all": {"action": "hotkey", "keys": ["win", "d"]},
    "task view": {"action": "hotkey", "keys": ["win", "tab"]},
    "switch window": {"action": "hotkey", "keys": ["alt", "tab"]},
    "close window": {"action": "hotkey", "keys": ["alt", "f4"]},
    "minimize": {"action": "hotkey", "keys": ["win", "down"]},
    "maximize": {"action": "hotkey", "keys": ["win", "up"]},
    "snap left": {"action": "hotkey", "keys": ["win", "left"]},
    "snap right": {"action": "hotkey", "keys": ["win", "right"]},
    "refresh": {"action": "key", "key": "f5"},
    "enter": {"action": "key", "key": "enter"},
    "escape": {"action": "key", "key": "escape"},
    "back": {"action": "key", "key": "escape"},
    "copy": {"action": "hotkey", "keys": ["ctrl", "c"]},
    "paste": {"action": "hotkey", "keys": ["ctrl", "v"]},
    "cut": {"action": "hotkey", "keys": ["ctrl", "x"]},
    "undo": {"action": "hotkey", "keys": ["ctrl", "z"]},
    "select all": {"action": "hotkey", "keys": ["ctrl", "a"]},
    "save": {"action": "hotkey", "keys": ["ctrl", "s"]},
    "find": {"action": "hotkey", "keys": ["ctrl", "f"]},
    "lock": {"action": "hotkey", "keys": ["win", "l"]},
    "screenshot": {"action": "hotkey", "keys": ["win", "prtsc"]},
    "volume up": {"action": "key", "key": "volumeup"},
    "volume down": {"action": "key", "key": "volumedown"},
    "mute": {"action": "key", "key": "volumemute"},
    "scroll up": {"action": "scroll", "clicks": 6},
    "scroll down": {"action": "scroll", "clicks": -6},
}


class VoiceCommandHandler:
    def __init__(self, input_handler):
        self.input = input_handler

    def execute(self, text, options_callback=None):
        text = text.strip().lower()
        if not text:
            return {"action": "none"}

        cmd = VOICE_COMMANDS.get(text)
        if cmd:
            return self._run_cmd(cmd)

        match = re.match(r"^(open|launch|start|run)\s+(.+)$", text)
        if match:
            query = match.group(2)
            return self._open_app(query)

        match = re.match(r"^play\s+(.+)$", text)
        if match:
            game = match.group(1)
            return self._play_game(game)

        match = re.match(r"^click\s+(\d+)$", text)
        if match:
            return {"action": "click_option", "number": int(match.group(1))}

        match = re.match(r"^(type|say)\s+(.+)$", text)
        if match:
            self.input.type_text(match.group(2))
            return {"action": "type", "text": match.group(2)}

        match = re.match(r"^(find|search)\s+(.+)$", text)
        if match:
            return self._open_app(match.group(2))

        return {"action": "unknown", "text": text}

    def _run_cmd(self, cmd):
        action = cmd.get("action")
        if action == "key":
            self.input.key_press(cmd["key"])
            return cmd
        elif action == "hotkey":
            self.input.hotkey(*cmd["keys"])
            return cmd
        elif action == "scroll":
            self.input.mouse_scroll(0, cmd["clicks"])
            return cmd
        return cmd

    def _open_app(self, query):
        query = query.strip()
        candidates = self._find_apps(query)

        if len(candidates) == 1:
            self._launch_app(candidates[0])
            return {
                "action": "launch",
                "app": candidates[0]["name"],
                "options": None
            }
        elif len(candidates) > 1:
            options = [
                {"id": i, "label": c["name"], "path": c.get("path", "")}
                for i, c in enumerate(candidates, 1)
            ]
            return {
                "action": "show_options",
                "options": options,
                "prompt": f"Which {query}?",
            }
        else:
            self._search_and_run(query)
            return {"action": "search", "query": query, "options": None}

    def _play_game(self, game):
        game = game.strip()
        candidates = self._find_apps(game)

        if len(candidates) == 1:
            self._launch_app(candidates[0])
            return {
                "action": "play",
                "game": candidates[0]["name"],
                "options": None,
            }
        elif len(candidates) > 1:
            options = [
                {"id": i, "label": c["name"], "path": c.get("path", "")}
                for i, c in enumerate(candidates, 1)
            ]
            return {
                "action": "show_options",
                "options": options,
                "prompt": f"Which {game}?",
            }
        else:
            self._search_and_run(game)
            return {"action": "search", "query": game, "options": None}

    def _find_apps(self, query):
        q = query.lower()
        candidates = []

        known = {
            "minecraft": "Minecraft Launcher",
            "minecraft launcher": "Minecraft Launcher",
            "chrome": "Google Chrome",
            "google chrome": "Google Chrome",
            "firefox": "Firefox",
            "edge": "Microsoft Edge",
            "steam": "Steam",
            "discord": "Discord",
            "spotify": "Spotify",
            "vs code": "Visual Studio Code",
            "visual studio code": "Visual Studio Code",
            "vscode": "Visual Studio Code",
            "code": "Visual Studio Code",
            "notepad": "Notepad",
            "calculator": "Calculator",
            "file explorer": "File Explorer",
            "explorer": "File Explorer",
            "settings": "Settings",
            "control panel": "Control Panel",
            "task manager": "Task Manager",
            "terminal": "Windows Terminal",
            "command prompt": "Command Prompt",
            "cmd": "Command Prompt",
            "powershell": "Windows PowerShell",
            "word": "Word",
            "excel": "Excel",
            "powerpoint": "PowerPoint",
            "outlook": "Outlook",
            "teams": "Microsoft Teams",
            "zoom": "Zoom",
            "vlc": "VLC media player",
            "obs": "OBS Studio",
        }

        for key, name in known.items():
            if q in key or key in q:
                candidates.append({"name": name, "path": ""})

        try:
            import os
            start_menu = os.path.expanduser(
                r"~\AppData\Roaming\Microsoft\Windows\Start Menu\Programs"
            )
            for root, dirs, files in os.walk(start_menu):
                for f in files:
                    if f.endswith(".lnk"):
                        name = f[:-4]
                        if q in name.lower():
                            candidates.append({
                                "name": name,
                                "path": os.path.join(root, f)
                            })
        except Exception:
            pass

        return candidates[:10]

    def _launch_app(self, app):
        path = app.get("path", "")
        if path and path.endswith(".lnk"):
            try:
                os.startfile(path)
                return
            except Exception:
                pass
        self._search_and_run(app["name"])

    def _search_and_run(self, query):
        self.input.key_down("win")
        time.sleep(0.1)
        self.input.type_text(query)
        time.sleep(0.5)
        self.input.key_up("win")
        time.sleep(0.3)
        self.input.key_press("enter")

    def click_option(self, option_idx):
        pyautogui.scroll(-option_idx * 100)
