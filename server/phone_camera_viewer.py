import threading
import base64
from io import BytesIO

try:
    import tkinter as tk
    from PIL import Image, ImageTk
    TK_AVAILABLE = True
except ImportError:
    TK_AVAILABLE = False


class PhoneCameraViewer:
    def __init__(self, send_callback=None):
        self.send_callback = send_callback
        self._window = None
        self._img_label = None
        self._photo = None
        self._running = False
        self._root = None

    def start(self):
        if not TK_AVAILABLE:
            return
        self._running = True
        thread = threading.Thread(target=self._ui_thread, daemon=True)
        thread.start()

    def _ui_thread(self):
        self._root = tk.Tk()
        self._root.title("Lazy Boy - Phone Camera")
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._img_label = tk.Label(self._root, bg="#111")
        self._img_label.pack()
        instr = tk.Label(
            self._root,
            text="Phone camera feed | Close to stop",
            fg="#888", bg="#222", font=("Arial", 9)
        )
        instr.pack(fill=tk.X)
        self._root.mainloop()

    def _on_close(self):
        self._running = False
        if self.send_callback:
            self.send_callback({"type": "phone_camera_stop"})
        if self._root:
            self._root.destroy()

    def update_frame(self, jpg_bytes):
        if not self._running or not TK_AVAILABLE:
            return
        try:
            img = Image.open(BytesIO(jpg_bytes))
            w, h = img.size
            scale = min(400 / w, 600 / h)
            dw, dh = int(w * scale), int(h * scale)
            img = img.resize((dw, dh), Image.LANCZOS)
            self._photo = ImageTk.PhotoImage(img)
            if self._root:
                self._root.after(0, self._update_display)
        except Exception:
            pass

    def _update_display(self):
        if self._img_label and self._photo:
            self._img_label.config(image=self._photo)
            self._img_label.image = self._photo

    def stop(self):
        self._running = False
        if self._root:
            try:
                self._root.quit()
                self._root.destroy()
            except Exception:
                pass
