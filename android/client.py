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
        self._phone_tap_callback = None
        self._phone_back_callback = None
        self._phone_volume_callback = None
        self._voice_options_callback = None
        self._audio_callback = None
        self._pc_camera_callback = None
        self._radio_status_callback = None
        self._radio_audio_callback = None
        self._radio_phone_fm_callback = None

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

    def set_phone_tap_callback(self, callback):
        self._phone_tap_callback = callback

    def set_phone_back_callback(self, callback):
        self._phone_back_callback = callback

    def set_phone_volume_callback(self, callback):
        self._phone_volume_callback = callback

    def set_voice_options_callback(self, callback):
        self._voice_options_callback = callback

    def set_audio_callback(self, callback):
        self._audio_callback = callback

    def set_pc_camera_callback(self, callback):
        self._pc_camera_callback = callback

    def set_radio_status_callback(self, callback):
        self._radio_status_callback = callback

    def set_radio_audio_callback(self, callback):
        self._radio_audio_callback = callback

    def set_radio_phone_fm_callback(self, callback):
        self._radio_phone_fm_callback = callback
        self._voice_options_callback = callback
        self._phone_volume_callback = callback

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

            elif msg_type == "phone_tap":
                if self._phone_tap_callback:
                    self._phone_tap_callback(data["x"], data["y"])

            elif msg_type == "phone_back":
                if self._phone_back_callback:
                    self._phone_back_callback()

            elif msg_type == "phone_volume":
                if self._phone_volume_callback:
                    self._phone_volume_callback(data.get("direction", "up"))

            elif msg_type == "voice_options":
                if self._voice_options_callback:
                    self._voice_options_callback(data.get("options", []),
                                                  data.get("prompt", ""))

            elif msg_type == "pc_audio":
                if self._audio_callback:
                    import base64
                    pcm = base64.b64decode(data["data"])
                    self._audio_callback(pcm)

            elif msg_type == "pc_camera_frame":
                if self._pc_camera_callback:
                    import base64
                    jpg = base64.b64decode(data["data"])
                    self._pc_camera_callback(jpg)

            elif msg_type == "radio_status":
                if self._radio_status_callback:
                    self._radio_status_callback(data)

            elif msg_type == "radio_scan_results":
                if self._radio_status_callback:
                    self._radio_status_callback(data)

            elif msg_type == "radio_station_list":
                if self._radio_status_callback:
                    self._radio_status_callback(data)

            elif msg_type == "pc_radio_audio":
                if self._radio_audio_callback:
                    import base64
                    pcm = base64.b64decode(data["data"])
                    self._radio_audio_callback(pcm)

            elif msg_type == "radio_phone_fm_start":
                if self._radio_phone_fm_callback:
                    self._radio_phone_fm_callback(data.get("freq", 88.0))

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

    def send_enter_host_mode(self):
        self.send({"type": "enter_host_mode"})

    def send_exit_host_mode(self):
        self.send({"type": "phone_exit_host"})

    def send_voice_result(self, text):
        if text:
            self.send({"type": "voice_result", "text": text})

    def send_phone_camera(self, jpg_bytes):
        import base64
        self.send({
            "type": "phone_camera_frame",
            "data": base64.b64encode(jpg_bytes).decode(),
        })

    def send_bt_key(self, key):
        self.send({"type": "bt_passthrough_key", "key": key})

    def send_bt_mouse(self, dx=0, dy=0, click=False, x=0, y=0, button="left"):
        self.send({
            "type": "bt_passthrough_mouse",
            "dx": dx, "dy": dy,
            "click": click, "x": x, "y": y, "button": button,
        })

    def send_phone_audio(self, pcm_bytes):
        import base64
        self.send({
            "type": "phone_audio",
            "data": base64.b64encode(pcm_bytes).decode(),
        })

    def send_phone_frame(self, jpg_bytes):
        import base64
        self.send({
            "type": "phone_frame",
            "data": base64.b64encode(jpg_bytes).decode()
        })

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
