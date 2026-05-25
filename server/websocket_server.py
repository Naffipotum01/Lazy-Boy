import asyncio
import json
import base64
import threading
import websockets
from screen_capture import ScreenCapture
from input_handler import InputHandler
from approval import ApprovalDialog
from clipboard_sync import ClipboardSync
from tablet_mode import set_tablet_mode, is_tablet_mode
from phone_viewer import PhoneViewer
from voice_commands import VoiceCommandHandler
from audio_stream import AudioStreamer
from camera_stream import PcCameraStreamer
from phone_camera_viewer import PhoneCameraViewer
from device_bridge import DeviceBridge
from radio_bridge import PcRadioTuner
from click_predictor import ClickPredictor
from network_booster import NetworkBooster
from hotspot_creator import HotspotCreator

WS_PORT = 8765
FS_PORT = 8766


class ControlServer:
    def __init__(self, screen_capture, input_handler, approval_dialog):
        self.screen = screen_capture
        self.input = input_handler
        self.approval = approval_dialog
        self.connected = set()
        self.approved_ips = set()
        self.loop = None
        self._server = None
        self._file_server = None

        self.clipboard = ClipboardSync(on_change_callback=self._on_clipboard_change)
        self._tablet_was_on = None
        self._phone_viewer = None
        self._phone_ws = None
        self.voice = VoiceCommandHandler(input_handler)
        self.audio = AudioStreamer()
        self._audio_mic_on = False
        self._audio_speaker_on = False
        self.pc_cam = PcCameraStreamer()
        self._phone_cam_viewer = None
        self.bridge = DeviceBridge()
        self.bridge.set_send_callback(self._send_to_phone)
        self.radio = PcRadioTuner()
        self.radio.set_send_callback(self._on_radio_audio)
        self._radio_playing = False
        self.predictor = ClickPredictor()
        self._smart_point_active = False
        self.network = NetworkBooster()
        self.hotspot = HotspotCreator()

    async def _handler(self, websocket):
        addr = websocket.remote_address
        ip = addr[0]
        print(f"[+] Connection from {ip}")

        if ip not in self.approved_ips:
            try:
                await websocket.send(json.dumps({"type": "approval_required"}))
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    device_name = "Android Device"
                    approved = await asyncio.get_event_loop().run_in_executor(
                        pool, self.approval.request_approval, device_name, ip
                    )
                if not approved:
                    await websocket.send(json.dumps({"type": "connection_denied"}))
                    print(f"[-] Denied: {ip}")
                    return
                self.approved_ips.add(ip)
                await websocket.send(json.dumps({"type": "connection_accepted"}))
            except Exception as e:
                print(f"[-] Approval error: {e}")
                return

        was_empty = len(self.connected) == 0
        self.connected.add(websocket)
        print(f"[+] Approved: {ip}")

        if was_empty:
            self._tablet_was_on = is_tablet_mode()
            if not self._tablet_was_on:
                print("[*] Enabling tablet mode")
                set_tablet_mode(True)

        sender_task = asyncio.ensure_future(self._send_frames(websocket))

        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    data["_ws"] = websocket
                    self._handle_command(data)
                except json.JSONDecodeError:
                    pass
        except websockets.ConnectionClosed:
            pass
        finally:
            sender_task.cancel()
            self.connected.discard(websocket)
            print(f"[-] Disconnected: {ip}")
            if websocket == self._phone_ws:
                self._stop_phone_viewer()
            if len(self.connected) == 0 and self._tablet_was_on is not None:
                if not self._tablet_was_on:
                    print("[*] Restoring desktop mode")
                    set_tablet_mode(False)
                self._tablet_was_on = None

    async def _send_frames(self, websocket):
        try:
            while True:
                frame = self.screen.get_frame()
                if frame:
                    data = base64.b64encode(frame).decode()
                    await websocket.send(json.dumps({
                        "type": "screen_frame",
                        "data": data
                    }))
                await asyncio.sleep(0.033)
        except (websockets.ConnectionClosed, asyncio.CancelledError):
            pass

    def _start_phone_viewer(self):
        if self._phone_viewer:
            return
        self._phone_viewer = PhoneViewer(send_callback=self._send_to_phone)
        self._phone_viewer.start()

    def _stop_phone_viewer(self):
        if self._phone_viewer:
            self._phone_viewer.stop()
            self._phone_viewer = None
        self._phone_ws = None

    def _start_phone_cam_viewer(self):
        if self._phone_cam_viewer:
            return
        self._phone_cam_viewer = PhoneCameraViewer(
            send_callback=self._send_to_phone
        )
        self._phone_cam_viewer.start()

    def _stop_phone_cam_viewer(self):
        if self._phone_cam_viewer:
            self._phone_cam_viewer.stop()
            self._phone_cam_viewer = None

    def _send_pc_camera_frame(self, jpg_bytes):
        import base64
        self._send_to_phone({
            "type": "pc_camera_frame",
            "data": base64.b64encode(jpg_bytes).decode(),
        })

    def _send_pc_audio(self, pcm_bytes):
        import base64
        self._send_to_phone({
            "type": "pc_audio",
            "data": base64.b64encode(pcm_bytes).decode(),
        })

    def _on_radio_audio(self, pcm_bytes):
        import base64
        self._send_to_phone({
            "type": "pc_radio_audio",
            "data": base64.b64encode(pcm_bytes).decode(),
        })

    def _send_options(self, options, prompt):
        self._send_to_phone({
            "type": "voice_options",
            "options": options,
            "prompt": prompt or "Choose an option:",
        })

    def _send_to_phone(self, msg):
        ws = self._phone_ws
        if ws:
            try:
                asyncio.run_coroutine_threadsafe(
                    ws.send(json.dumps(msg)), self.loop
                )
            except Exception:
                pass

    def _broadcast(self, msg):
        if not self.connected:
            return
        msg_str = json.dumps(msg)
        for ws in self.connected.copy():
            try:
                asyncio.run_coroutine_threadsafe(
                    ws.send(msg_str), self.loop
                )
            except Exception:
                pass

    def _on_clipboard_change(self, text):
        self._broadcast({"type": "clipboard_push", "text": text})

    def _handle_command(self, data):
        cmd = data.get("type")

        if cmd == "set_resolution":
            self.input.set_remote_resolution(
                data["width"], data["height"],
                data.get("offset_x", 0), data.get("offset_y", 0)
            )

        elif cmd == "mouse_move":
            self.input.mouse_move(data["x"], data["y"])

        elif cmd == "mouse_move_relative":
            self.input.mouse_move_relative(data["dx"], data["dy"])

        elif cmd == "mouse_down":
            self.input.mouse_down(data["x"], data["y"], data.get("button", "left"))

        elif cmd == "mouse_up":
            self.input.mouse_up(data["x"], data["y"], data.get("button", "left"))

        elif cmd == "mouse_click":
            self.input.mouse_click(data["x"], data["y"], data.get("button", "left"))

        elif cmd == "mouse_double_click":
            self.input.mouse_double_click(data["x"], data["y"])

        elif cmd == "mouse_right_click":
            self.input.mouse_right_click(data["x"], data["y"])

        elif cmd == "mouse_scroll":
            self.input.mouse_scroll(data.get("dx", 0), data["dy"])

        elif cmd == "key_down":
            key = data["key"]
            if key == "leftmouse":
                self.input.mouse_down(0, 0, "left")
            elif key == "rightmouse":
                self.input.mouse_down(0, 0, "right")
            else:
                self.input.key_down(key)

        elif cmd == "key_up":
            key = data["key"]
            if key == "leftmouse":
                self.input.mouse_up(0, 0, "left")
            elif key == "rightmouse":
                self.input.mouse_up(0, 0, "right")
            else:
                self.input.key_up(key)

        elif cmd == "key_press":
            self.input.key_press(data["key"])

        elif cmd == "type_text":
            self.input.type_text(data["text"])

        elif cmd == "hotkey":
            self.input.hotkey(*data["keys"])

        elif cmd == "clipboard_set":
            self.clipboard.set(data["text"])
            self._broadcast({"type": "clipboard_push", "text": data["text"]})

        elif cmd == "clipboard_get":
            self._broadcast({"type": "clipboard_push", "text": self.clipboard.get()})

        elif cmd == "file_list":
            self._list_files(data.get("path", "."))

        elif cmd == "file_serve":
            port = data.get("port", 0)
            self._start_file_server(port)

        elif cmd == "file_stop":
            self._stop_file_server()

        elif cmd == "file_upload":
            import base64, os
            path = data.get("path", ".")
            name = data.get("name", "file")
            content = data.get("content", "")
            root = os.path.abspath(os.path.expanduser("~"))
            dest = os.path.abspath(os.path.join(root, path, name))
            if dest.startswith(root):
                try:
                    raw = base64.b64decode(content)
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    with open(dest, "wb") as f:
                        f.write(raw)
                except Exception as e:
                    pass

        elif cmd == "file_mkdir":
            import os
            path = data.get("path", ".")
            name = data.get("name", "New Folder")
            root = os.path.abspath(os.path.expanduser("~"))
            dest = os.path.abspath(os.path.join(root, path, name))
            if dest.startswith(root):
                try:
                    os.makedirs(dest, exist_ok=True)
                except Exception:
                    pass

        elif cmd == "enter_host_mode":
            self._phone_ws = data.get("_ws", None)
            self._start_phone_viewer()

        elif cmd == "phone_frame":
            if self._phone_viewer:
                import base64
                jpg = base64.b64decode(data["data"])
                self._phone_viewer.update_frame(jpg)

        elif cmd == "phone_exit_host":
            self._stop_phone_viewer()

        elif cmd == "phone_tap":
            self._send_to_phone({"type": "phone_tap", "x": data["x"], "y": data["y"]})

        elif cmd == "phone_back":
            self._send_to_phone({"type": "phone_back"})

        elif cmd == "phone_volume":
            self._send_to_phone({"type": "phone_volume", "direction": data["direction"]})

        elif cmd == "voice_result":
            text = data.get("text", "")
            result = self.voice.execute(text, options_callback=self._send_options)
            if result.get("options"):
                self._send_to_phone({
                    "type": "voice_options",
                    "options": result["options"],
                    "prompt": result.get("prompt", "Choose:"),
                })

        elif cmd == "voice_option_picked":
            opt_id = data.get("option_id", 0)
            self.voice.click_option(opt_id)

        elif cmd == "phone_audio":
            import base64
            self.audio.write_audio(base64.b64decode(data["data"]))

        elif cmd == "audio_mic_start":
            self._audio_mic_on = True
            self.audio.start_capture(send_callback=self._send_pc_audio)

        elif cmd == "audio_mic_stop":
            self._audio_mic_on = False
            self.audio.stop()

        elif cmd == "audio_speaker_start":
            self._audio_speaker_on = True
            self.audio.start_playback()

        elif cmd == "audio_speaker_stop":
            self._audio_speaker_on = False
            self.audio.stop()

        elif cmd == "pc_camera_start":
            self.pc_cam.start(send_callback=self._send_pc_camera_frame)

        elif cmd == "pc_camera_stop":
            self.pc_cam.stop()

        elif cmd == "phone_camera_start":
            self._start_phone_cam_viewer()

        elif cmd == "phone_camera_frame":
            if self._phone_cam_viewer:
                import base64
                jpg = base64.b64decode(data["data"])
                self._phone_cam_viewer.update_frame(jpg)

        elif cmd == "phone_camera_stop":
            self._stop_phone_cam_viewer()

        elif cmd == "bt_passthrough_key":
            self.input.key_press(data["key"])

        elif cmd == "bt_passthrough_mouse":
            dx = data.get("dx", 0)
            dy = data.get("dy", 0)
            if dx or dy:
                self.input.mouse_move_relative(dx, dy)
            if data.get("click"):
                btn = data.get("button", "left")
                self.input.mouse_click(
                    data.get("x", 0), data.get("y", 0), btn
                )

        elif cmd == "bridge_location":
            self._broadcast({
                "type": "bridge_location_info",
                "lat": data["lat"],
                "lon": data["lon"],
                "accuracy": data.get("accuracy", 0),
            })

        elif cmd == "bridge_pc_hotspot_start":
            result = self.bridge.share_pc_wifi_to_phone()
            self._send_to_phone({
                "type": "bridge_hotspot_status",
                **result,
            })

        elif cmd == "bridge_pc_hotspot_stop":
            self.bridge.stop_pc_hotspot()

        elif cmd == "bridge_usb_share":
            direction = data.get("direction", "phone_to_pc")
            if direction == "pc_to_phone":
                result = self.bridge.share_pc_internet_via_usb()
                self._send_to_phone({
                    "type": "bridge_usb_share_result",
                    "direction": "pc_to_phone",
                    **result,
                })
            else:
                result = self.bridge.share_wifi_to_pc()
                self._send_to_phone({
                    "type": "bridge_network_status",
                    **result,
                })

        elif cmd == "bridge_status":
            status = self.bridge.get_bridge_status()
            self._send_to_phone({
                "type": "bridge_status_info",
                **status,
            })

        # === Radio Commands ===
        elif cmd == "radio_tune":
            station = data.get("station", "")
            direction = data.get("direction", "pc_to_phone")
            result = self.radio.tune(station)
            self._radio_playing = result.get("success", False)
            self._send_to_phone({"type": "radio_status", **result})

        elif cmd == "radio_tune_url":
            url = data.get("url", "")
            direction = data.get("direction", "pc_to_phone")
            result = self.radio.play_url_direct(url)
            self._radio_playing = result.get("success", False)
            self._send_to_phone({"type": "radio_status", **result})

        elif cmd == "radio_phone_fm":
            freq = data.get("freq", 88.0)
            self._send_to_phone({
                "type": "radio_phone_fm_start",
                "freq": freq,
            })

        elif cmd == "radio_phone_audio":
            import base64
            raw = base64.b64decode(data["data"])
            self.audio.write_audio(raw)

        elif cmd == "radio_scan":
            stations = self.radio.scan_frequencies()
            self._send_to_phone({
                "type": "radio_scan_results",
                "stations": stations,
            })

        elif cmd == "radio_stop":
            self.radio.stop()
            self._radio_playing = False
            self._send_to_phone({"type": "radio_status", "success": True, "info": "stopped"})

        elif cmd == "radio_list":
            stations = self.radio.get_stations()
            self._send_to_phone({
                "type": "radio_station_list",
                "stations": stations,
            })

        # === Smart Point ===
        elif cmd == "smart_point_activate":
            self._smart_point_active = True
            result = self._do_smart_scan()
            self._send_to_phone({"type": "smart_point_result", "predictions": result})

        elif cmd == "smart_point_scan":
            result = self._do_smart_scan()
            self._send_to_phone({"type": "smart_point_result", "predictions": result})

        elif cmd == "smart_point_click":
            x = data.get("x", 0)
            y = data.get("y", 0)
            if self._smart_point_active:
                orig_w = self.screen._orig_w if hasattr(self.screen, "_orig_w") else 1920
                orig_h = self.screen._orig_h if hasattr(self.screen, "_orig_h") else 1080
                scale = self.screen.scale
                real_x = int(x / scale) if scale > 0 else x
                real_y = int(y / scale) if scale > 0 else y
                self.input.mouse_move(real_x, real_y)
                self.input.mouse_click(real_x, real_y)
            self._smart_point_active = False
            self.screen.overlay_fn = None
            self._send_to_phone({"type": "smart_point_dismissed"})

        elif cmd == "smart_point_dismiss":
            self._smart_point_active = False
            self.screen.overlay_fn = None
            self._send_to_phone({"type": "smart_point_dismissed"})

        # === Network Booster ===
        elif cmd == "booster":
            action = data.get("action", "")
            result = None
            if action == "speed_test":
                result = self.network.speed_test()
            elif action == "tcp_optimize":
                result = self.network.optimize_tcp()
            elif action == "tcp_reset":
                result = self.network.reset_tcp()
            elif action == "dns_cache":
                result = self.network.start_dns_cache()
            elif action == "dns_stop":
                result = self.network.stop_dns_cache()
            elif action == "hotspot":
                result = self.network.optimize_hotspot()
            elif action == "wifi_optimize":
                result = self.network.optimize_hotspot()
            elif action == "info":
                info = self.network.get_connection_info()
                result = {"info": info}
            if result is not None:
                self._send_to_phone({"type": "booster_result", "action": action, "result": result})

        # === Hotspot Creator ===
        elif cmd == "hotspot_create":
            ssid = data.get("ssid", "LazyBoy-FreeNet")
            password = data.get("password", "LazyBoy123")
            result = self.hotspot.create(ssid, password)
            self._send_to_phone({"type": "hotspot_created", "info": result})

        elif cmd == "hotspot_stop":
            self.hotspot.stop()
            self._send_to_phone({"type": "hotspot_stopped"})

        elif cmd == "hotspot_status":
            status = self.hotspot.get_status()
            self._send_to_phone({"type": "hotspot_status_info", "status": status})

        elif cmd == "hotspot_bandwidth":
            bw = self.hotspot.get_bandwidth_usage()
            self._send_to_phone({"type": "hotspot_bandwidth", "bandwidth": bw})

    def _do_smart_scan(self):
        try:
            frame = self.screen.get_frame()
            if not frame:
                return []
            from PIL import Image
            import io
            pil = Image.open(io.BytesIO(frame))

            orig_w, orig_h = pil.size
            orig_w = int(orig_w / self.screen.scale) if self.screen.scale > 0 else orig_w
            orig_h = int(orig_h / self.screen.scale) if self.screen.scale > 0 else orig_h
            self.screen._orig_w = orig_w
            self.screen._orig_h = orig_h

            predictions = self.predictor.predict(pil)
            self.screen.overlay_fn = lambda img: self.predictor.render_overlay(img, predictions)
            return predictions
        except Exception as e:
            print(f"[!] Smart scan error: {e}")
            return []

    def _list_files(self, path):
        import os
        try:
            entries = []
            abs_path = os.path.abspath(os.path.expanduser(path))
            for name in os.listdir(abs_path):
                full = os.path.join(abs_path, name)
                entries.append({
                    "name": name,
                    "is_dir": os.path.isdir(full),
                    "size": os.path.getsize(full) if os.path.isfile(full) else 0,
                    "mtime": os.path.getmtime(full),
                })
            self._broadcast({
                "type": "file_list_result",
                "path": abs_path,
                "entries": entries,
                "parent": os.path.dirname(abs_path) if abs_path != os.path.abspath(os.sep) else None,
            })
        except Exception as e:
            self._broadcast({"type": "file_list_result", "error": str(e)})

    def _start_file_server(self, port):
        if self._file_server:
            self._stop_file_server()

        from file_server import FileServer
        self._file_server = FileServer(port or FS_PORT)
        self._file_server.start()
        addr = self._file_server.address()
        self._broadcast({"type": "file_server_started", "host": addr[0], "port": addr[1]})

    def _stop_file_server(self):
        if self._file_server:
            self._file_server.stop()
            self._file_server = None

    async def _run(self):
        self.clipboard.start()
        self._server = await websockets.serve(self._handler, "0.0.0.0", WS_PORT)
        print(f"[*] WebSocket server on port {WS_PORT}")
        await self._server.wait_closed()

    def start(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._run())

    def stop(self):
        self.clipboard.stop()
        self._stop_file_server()
        if self._server:
            self._server.close()
