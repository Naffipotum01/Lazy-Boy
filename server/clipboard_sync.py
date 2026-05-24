import threading
import time
import pyperclip


class ClipboardSync:
    def __init__(self, on_change_callback=None):
        self._last = pyperclip.paste()
        self._running = False
        self._thread = None
        self._on_change = on_change_callback

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._poll, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def set(self, text):
        try:
            pyperclip.copy(text)
            self._last = text
        except Exception:
            pass

    def get(self):
        try:
            return pyperclip.paste()
        except Exception:
            return ""

    def _poll(self):
        while self._running:
            try:
                current = pyperclip.paste()
                if current != self._last:
                    self._last = current
                    if self._on_change and current.strip():
                        self._on_change(current)
            except Exception:
                pass
            time.sleep(0.5)
