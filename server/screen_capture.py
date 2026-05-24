import io
import threading
import time
from PIL import Image
import mss


class ScreenCapture:
    def __init__(self, quality=40, scale=0.5):
        self.quality = quality
        self.scale = scale
        self.running = False
        self._frame = None
        self._lock = threading.Lock()
        self._thread = None

    def _capture_loop(self):
        sct = mss.mss()
        monitor = sct.monitors[1]
        while self.running:
            try:
                screenshot = sct.grab(monitor)
                img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
                if self.scale < 1.0:
                    new_size = (int(img.width * self.scale), int(img.height * self.scale))
                    img = img.resize(new_size, Image.LANCZOS)
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=self.quality, optimize=True)
                with self._lock:
                    self._frame = buf.getvalue()
            except Exception:
                pass
            time.sleep(0.03)

    def start(self):
        self.running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self.running = False

    def get_frame(self):
        with self._lock:
            return self._frame
