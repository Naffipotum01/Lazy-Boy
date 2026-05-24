import sys
import os
import threading
import pyautogui

from discovery import DiscoveryService
from screen_capture import ScreenCapture
from input_handler import InputHandler
from websocket_server import ControlServer
from approval import ApprovalDialog


def main():
    print("=" * 40)
    print("       LAZY BOY - PC Server")
    print("=" * 40)

    screen_w, screen_h = pyautogui.size()
    print(f"[*] Screen resolution: {screen_w}x{screen_h}")

    discovery = DiscoveryService()
    print(f"[*] Hostname: {discovery.hostname}")
    print(f"[*] IP: {discovery.ip}")

    screen_capture = ScreenCapture(quality=40, scale=0.5)
    input_handler = InputHandler(screen_w, screen_h)
    approval = ApprovalDialog()
    server = ControlServer(screen_capture, input_handler, approval)

    discovery.start()
    screen_capture.start()
    print("[*] Discovery service started")
    print("[*] Screen capture started")

    ws_thread = threading.Thread(target=server.start, daemon=True)
    ws_thread.start()

    print(f"[*] Listening on port 8765")
    print("[*] Waiting for connections...")
    print("[*] Press Ctrl+C to stop\n")

    try:
        approval.start()
    except KeyboardInterrupt:
        print("\n[*] Shutting down...")
    finally:
        discovery.stop()
        screen_capture.stop()
        server.stop()
        print("[*] Server stopped.")


if __name__ == "__main__":
    main()
