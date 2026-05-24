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
