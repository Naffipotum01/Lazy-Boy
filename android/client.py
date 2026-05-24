import json
import base64
import threading
import time
import ssl

try:
    import websocket
except ImportError:
    import pip
    pip.main(["install", "websocket-client"])
    import websocket


WS_PORT = 8765


class ControlClient:
    def __init__(self):
        self.ws = None
        self.connected = False
        self.approved = False
        self._frame_callback = None
        self._status_callback = None
        self._clipboard_callback = None
        self._file_list_callback = None
        self._file_server_callback = None
        self._thread = None

    def set_frame_callback(self, callback):
        self._frame_callback = callback

    def set_status_callback(self, callback):
        self._status_callback = callback

    def set_clipboard_callback(self, callback):
        self._clipboard_callback = callback

    def set_file_list_callback(self, callback):
        self._file_list_callback = callback

    def set_file_server_callback(self, callback):
        self._file_server_callback = callback

    def connect(self, ip):
        if self.connected:
            self.disconnect()

        self._status_callback and self._status_callback("connecting")
        if ip.startswith("ws://") or ip.startswith("wss://"):
            uri = ip
        else:
            uri = f"ws://{ip}:{WS_PORT}"

        self._thread = threading.Thread(target=self._connect_thread, args=(uri,), daemon=True)
        self._thread.start()

    def _connect_thread(self, uri):
        try:
            self.ws = websocket.WebSocketApp(
                uri,
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close
            )
            self.ws.run_forever()
        except Exception as e:
            self._status_callback and self._status_callback(f"error: {e}")

    def _on_open(self, ws):
        self._status_callback and self._status_callback("waiting_approval")

    def _on_message(self, ws, message):
        try:
            data = json.loads(message)
            msg_type = data.get("type")

            if msg_type == "approval_required":
                self._status_callback and self._status_callback("waiting_approval")

            elif msg_type == "connection_accepted":
                self.connected = True
                self.approved = True
                self._status_callback and self._status_callback("connected")

            elif msg_type == "connection_denied":
                self._status_callback and self._status_callback("denied")
                self.disconnect()

            elif msg_type == "screen_frame":
                if self._frame_callback and self.approved:
                    img_data = base64.b64decode(data["data"])
                    self._frame_callback(img_data)

            elif msg_type == "clipboard_push":
                if self._clipboard_callback:
                    self._clipboard_callback(data["text"])

            elif msg_type == "file_list_result":
                if self._file_list_callback:
                    self._file_list_callback(data)

            elif msg_type == "file_server_started":
                if self._file_server_callback:
                    self._file_server_callback(data.get("host"), data.get("port"))

        except Exception:
            pass

    def _on_error(self, ws, error):
        self._status_callback and self._status_callback(f"error: {error}")

    def _on_close(self, ws, close_status_code, close_msg):
        self.connected = False
        self.approved = False
        self._status_callback and self._status_callback("disconnected")

    def send(self, data):
        if self.ws and self.connected:
            try:
                self.ws.send(json.dumps(data))
            except Exception:
                pass

    def send_mouse_move(self, x, y):
        self.send({"type": "mouse_move", "x": x, "y": y})

    def send_mouse_move_relative(self, dx, dy):
        self.send({"type": "mouse_move_relative", "dx": dx, "dy": dy})

    def send_mouse_down(self, x, y, button="left"):
        self.send({"type": "mouse_down", "x": x, "y": y, "button": button})

    def send_mouse_up(self, x, y, button="left"):
        self.send({"type": "mouse_up", "x": x, "y": y, "button": button})

    def send_mouse_click(self, x, y, button="left"):
        self.send({"type": "mouse_click", "x": x, "y": y, "button": button})

    def send_mouse_double_click(self, x, y):
        self.send({"type": "mouse_double_click", "x": x, "y": y})

    def send_mouse_right_click(self, x, y):
        self.send({"type": "mouse_right_click", "x": x, "y": y})

    def send_mouse_scroll(self, dy, dx=0):
        self.send({"type": "mouse_scroll", "dx": dx, "dy": dy})

    def send_key_press(self, key):
        self.send({"type": "key_press", "key": key})

    def send_key_down(self, key):
        self.send({"type": "key_down", "key": key})

    def send_key_up(self, key):
        self.send({"type": "key_up", "key": key})

    def send_type_text(self, text):
        self.send({"type": "type_text", "text": text})

    def send_hotkey(self, *keys):
        self.send({"type": "hotkey", "keys": list(keys)})

    def send_resolution(self, width, height):
        self.send({"type": "set_resolution", "width": width, "height": height})

    def send_clipboard_set(self, text):
        self.send({"type": "clipboard_set", "text": text})

    def send_clipboard_get(self):
        self.send({"type": "clipboard_get"})

    def send_file_list(self, path="."):
        self.send({"type": "file_list", "path": path})

    def send_file_serve(self, port=8766):
        self.send({"type": "file_serve", "port": port})

    def send_file_stop(self):
        self.send({"type": "file_stop"})

    def disconnect(self):
        self.connected = False
        if self.ws and self.thread:
            try:
                self.ws.close()
            except Exception:
                pass
            self.ws = None
        self.connected = False
        self.approved = False
