import threading
import base64
import json
from io import BytesIO

try:
    import tkinter as tk
    from PIL import Image, ImageTk
    TK_AVAILABLE = True
except ImportError:
    TK_AVAILABLE = False


class PhoneViewer:
    def __init__(self, send_callback=None):
        self.send_callback = send_callback
        self._window = None
        self._canvas = None
        self._photo = None
        self._img_label = None
        self._running = False
        self._root = None
        self._w, self._h = 480, 800
        self._scale = 0.6
        self._last_img = None

    def start(self):
        if not TK_AVAILABLE:
            print("[!] tkinter not available, can't show phone viewer")
            return
        self._running = True
        self._thread = threading.Thread(target=self._ui_thread, daemon=True)
        self._thread.start()

    def _ui_thread(self):
        self._root = tk.Tk()
        self._root.title("Lazy Boy - Phone Viewer")
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)

        w = int(self._w * self._scale)
        h = int(self._h * self._scale)
        self._canvas = tk.Canvas(self._root, width=w, height=h, bg="#111")
        self._canvas.pack()

        self._img_label = tk.Label(self._root, bg="#111")
        self._img_label.pack()

        instr = tk.Label(
            self._root,
            text="Click on phone screen to send touch | Right-click = back | Scroll = volume",
            fg="#888", bg="#222", font=("Arial", 9)
        )
        instr.pack(fill=tk.X)

        self._img_label.bind("<Button-1>", self._on_click)
        self._img_label.bind("<Button-3>", self._on_right_click)
        self._img_label.bind("<MouseWheel>", self._on_scroll)

        self._root.mainloop()

    def _on_click(self, event):
        if self.send_callback and self._last_img:
            orig_w, orig_h = self._last_img.size
            scale_x = orig_w / (int(self._w * self._scale))
            scale_y = orig_h / (int(self._h * self._scale))
            px = int(event.x * scale_x)
            py = int(event.y * scale_y)
            self.send_callback({"type": "phone_tap", "x": px, "y": py})

    def _on_right_click(self, event):
        if self.send_callback:
            self.send_callback({"type": "phone_back"})

    def _on_scroll(self, event):
        if self.send_callback:
            direction = "up" if event.delta > 0 else "down"
            self.send_callback({"type": "phone_volume", "direction": direction})

    def _on_close(self):
        self._running = False
        if self.send_callback:
            self.send_callback({"type": "phone_exit_host"})
        if self._root:
            self._root.destroy()

    def update_frame(self, jpg_bytes):
        if not self._running or not TK_AVAILABLE:
            return
        try:
            img = Image.open(BytesIO(jpg_bytes))
            self._last_img = img
            self._w, self._h = img.size
            disp_w = int(self._w * self._scale)
            disp_h = int(self._h * self._scale)
            img_small = img.resize((disp_w, disp_h), Image.LANCZOS)

            if self._root:
                self._photo = ImageTk.PhotoImage(img_small)
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
