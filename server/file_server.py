import os
import json
import threading
import time
import shutil
import tempfile
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, unquote


class FileRequestHandler(BaseHTTPRequestHandler):
    root = os.path.abspath(os.path.expanduser("~"))
    upload_dir = tempfile.gettempdir()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        full_path = os.path.abspath(os.path.join(self.root, path.lstrip("/")))

        if not full_path.startswith(self.root):
            self._send_json({"error": "Access denied"}, 403)
            return

        if os.path.isdir(full_path):
            self._list_dir(full_path)
        elif os.path.isfile(full_path):
            self._serve_file(full_path)
        else:
            self._send_json({"error": "Not found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        full_path = os.path.abspath(os.path.join(self.root, path.lstrip("/")))

        if not full_path.startswith(self.root):
            self._send_json({"error": "Access denied"}, 403)
            return

        cl = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(cl)
        data = json.loads(body)

        action = data.get("action")
        if action == "upload":
            name = data.get("name", "file")
            content = data.get("content", "")
            dest = os.path.join(full_path, name)
            if not dest.startswith(self.root):
                self._send_json({"error": "Access denied"}, 403)
                return
            try:
                import base64
                raw = base64.b64decode(content)
                with open(dest, "wb") as f:
                    f.write(raw)
                self._send_json({"success": True, "path": dest})
            except Exception as e:
                self._send_json({"error": str(e)}, 500)
        elif action == "mkdir":
            name = data.get("name", "New Folder")
            dest = os.path.join(full_path, name)
            if not dest.startswith(self.root):
                self._send_json({"error": "Access denied"}, 403)
                return
            try:
                os.makedirs(dest, exist_ok=True)
                self._send_json({"success": True, "path": dest})
            except Exception as e:
                self._send_json({"error": str(e)}, 500)
        else:
            self._send_json({"error": "Unknown action"}, 400)

    def _list_dir(self, path):
        try:
            entries = []
            names = sorted(os.listdir(path))
            for name in names:
                full = os.path.join(path, name)
                try:
                    st = os.stat(full)
                    entries.append({
                        "name": name,
                        "is_dir": os.path.isdir(full),
                        "size": st.st_size,
                        "mtime": st.st_mtime,
                    })
                except OSError:
                    pass
            parent = os.path.dirname(path)
            if parent and parent.startswith(self.root):
                rel_parent = os.path.relpath(parent, self.root)
            else:
                rel_parent = None
            self._send_json({
                "path": os.path.relpath(path, self.root),
                "entries": entries,
                "parent": rel_parent,
            })
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _serve_file(self, path):
        try:
            total = os.path.getsize(path)
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Disposition", f'attachment; filename="{os.path.basename(path)}"')
            self.send_header("Content-Length", str(total))
            self.send_header("X-File-Name", os.path.basename(path))
            self.end_headers()
            with open(path, "rb") as f:
                shutil.copyfileobj(f, self.wfile)
        except Exception:
            pass

    def _send_json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


class FileServer:
    def __init__(self, port=8766, root=None):
        self.port = port
        self.root = root or os.path.abspath(os.path.expanduser("~"))
        self._server = None
        self._thread = None

    def start(self):
        FileRequestHandler.root = self.root
        self._server = HTTPServer(("0.0.0.0", self.port), FileRequestHandler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        print(f"[*] File server on port {self.port} (root: {self.root})")

    def stop(self):
        if self._server:
            self._server.shutdown()
            self._server = None

    def address(self):
        return ("0.0.0.0", self.port)
