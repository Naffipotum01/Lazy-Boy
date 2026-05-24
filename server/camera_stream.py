import threading
import time
import base64
import struct
from io import BytesIO


class PcCameraStreamer:
    def __init__(self):
        self._running = False
        self._thread = None
        self._cap = None
        self._send_callback = None

    def start(self, send_callback, camera_id=0):
        self._send_callback = send_callback
        self._running = True
        self._thread = threading.Thread(
            target=self._capture_loop, args=(camera_id,), daemon=True
        )
        self._thread.start()
        return True

    def _capture_loop(self, camera_id):
        try:
            import cv2
            self._cap = cv2.VideoCapture(camera_id)
            if not self._cap.isOpened():
                return
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self._cap.set(cv2.CAP_PROP_FPS, 15)

            while self._running:
                ret, frame = self._cap.read()
                if not ret:
                    break
                ret2, jpg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 50])
                if ret2 and self._send_callback:
                    self._send_callback(jpg.tobytes())
                time.sleep(0.05)
        except Exception:
            self._fallback_capture()

    def _fallback_capture(self):
        try:
            from PIL import ImageGrab, Image
            while self._running:
                try:
                    import cv2
                    import numpy as np
                    cap = cv2.VideoCapture(0)
                    if not cap.isOpened():
                        return
                    while self._running:
                        ret, frame = cap.read()
                        if not ret:
                            break
                        ret2, jpg = cv2.imencode(
                            ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 50]
                        )
                        if ret2 and self._send_callback:
                            self._send_callback(jpg.tobytes())
                        time.sleep(0.05)
                    cap.release()
                except Exception:
                    time.sleep(1)
        except Exception:
            pass

    def write_frame(self, jpg_bytes):
        pass  # phone→PC is handled by the tkinter viewer

    def stop(self):
        self._running = False
        if self._cap:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None
