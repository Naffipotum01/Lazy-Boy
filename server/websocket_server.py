import asyncio
import json
import base64
import threading
import websockets
from screen_capture import ScreenCapture
from input_handler import InputHandler
from approval import ApprovalDialog

WS_PORT = 8765


class ControlServer:
    def __init__(self, screen_capture, input_handler, approval_dialog):
        self.screen = screen_capture
        self.input = input_handler
        self.approval = approval_dialog
        self.connected = set()
        self.approved_ips = set()
        self.loop = None
        self._server = None

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

        self.connected.add(websocket)
        print(f"[+] Approved: {ip}")

        sender_task = asyncio.ensure_future(self._send_frames(websocket))

        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    self._handle_command(data)
                except json.JSONDecodeError:
                    pass
        except websockets.ConnectionClosed:
            pass
        finally:
            sender_task.cancel()
            self.connected.discard(websocket)
            print(f"[-] Disconnected: {ip}")

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
            self.input.key_down(data["key"])

        elif cmd == "key_up":
            self.input.key_up(data["key"])

        elif cmd == "key_press":
            self.input.key_press(data["key"])

        elif cmd == "type_text":
            self.input.type_text(data["text"])

        elif cmd == "hotkey":
            self.input.hotkey(*data["keys"])

    async def _run(self):
        self._server = await websockets.serve(self._handler, "0.0.0.0", WS_PORT)
        print(f"[*] WebSocket server on port {WS_PORT}")
        await self._server.wait_closed()

    def start(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._run())

    def stop(self):
        if self._server:
            self._server.close()
