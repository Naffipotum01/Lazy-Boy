import sys
import os
import threading
import pyautogui

from discovery import DiscoveryService
from screen_capture import ScreenCapture
from input_handler import InputHandler
from websocket_server import ControlServer
from approval import ApprovalDialog
from remote import RemoteAccess


def main():
    print("=" * 40)
    print("       LAZY BOY - PC Server")
    print("=" * 40)

    screen_w, screen_h = pyautogui.size()
    print(f"[*] Screen resolution: {screen_w}x{screen_h}")

    remote = RemoteAccess()
    public_ip = remote.detect_public_ip()
    if public_ip:
        print(f"[*] Public IP: {public_ip}")
        upnp_ok = remote.start_upnp()
        if upnp_ok:
            print("[*] UPnP port forwarding enabled")
        else:
            print("[*] UPnP not available (install miniupnpc for auto port forwarding)")
    else:
        print("[*] Public IP: unknown (no internet?)")

    ngrok_token = os.environ.get("NGROK_AUTH_TOKEN")
    if ngrok_token:
        ngrok_url = remote.start_ngrok(ngrok_token)
        if ngrok_url:
            print(f"[*] Remote URL: {ngrok_url}")

    conn_info = remote.get_connection_info()
    discovery = DiscoveryService(remote_info=conn_info)
    print(f"[*] Hostname: {discovery.hostname}")
    print(f"[*] Local IP: {discovery.ip}")

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

    print("--- Connection Info ---")
    print(f"  Local:   ws://{discovery.ip}:8765")
    if public_ip:
        print(f"  Remote:  ws://{public_ip}:8765 (requires port forwarding)")
    if conn_info.get("ngrok_url"):
        print(f"  Tunnel:  {conn_info['ngrok_url']}")
    print("-----------------------\n")

    try:
        approval.start()
    except KeyboardInterrupt:
        print("\n[*] Shutting down...")
    finally:
        discovery.stop()
        screen_capture.stop()
        server.stop()
        remote.cleanup()
        print("[*] Server stopped.")


if __name__ == "__main__":
    main()
