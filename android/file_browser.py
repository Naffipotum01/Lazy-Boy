from kivy.app import App
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.uix.popup import Popup
from kivy.clock import Clock
from kivy.metrics import dp
import time
import threading

try:
    import urllib.request
except ImportError:
    pass


class FileBrowserScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.client = None
        self.current_path = "~"
        self.entries = []
        self.file_host = None
        self.file_port = None

        layout = BoxLayout(orientation="vertical")

        top = BoxLayout(size_hint_y=0.07, padding=[5, 3], spacing=5)
        back_btn = Button(text="Back", size_hint_x=0.15,
                          background_color=(0.5, 0.5, 0.5, 1))
        back_btn.bind(on_press=self._go_back)
        top.add_widget(back_btn)

        self.path_label = Label(text="~/", font_size=12, halign="left",
                                size_hint_x=0.7)
        self.path_label.bind(size=self.path_label.setter("text_size"))
        top.add_widget(self.path_label)

        home_btn = Button(text="Home", size_hint_x=0.15,
                          background_color=(0.2, 0.5, 0.9, 1))
        home_btn.bind(on_press=self._go_home)
        top.add_widget(home_btn)
        layout.add_widget(top)

        scroll = ScrollView(size_hint_y=0.83)
        self.file_list = BoxLayout(orientation="vertical",
                                    size_hint_y=None, spacing=2)
        self.file_list.bind(minimum_height=self.file_list.setter("height"))
        scroll.add_widget(self.file_list)
        layout.add_widget(scroll)

        bottom = BoxLayout(size_hint_y=0.1, padding=[5, 3], spacing=5)
        refresh_btn = Button(text="Refresh", background_color=(0.2, 0.6, 1, 1))
        refresh_btn.bind(on_press=self._refresh)
        bottom.add_widget(refresh_btn)

        upload_btn = Button(text="Upload", background_color=(0.2, 0.7, 0.3, 1))
        upload_btn.bind(on_press=self._upload_dialog)
        bottom.add_widget(upload_btn)

        mkdir_btn = Button(text="New Folder", background_color=(0.7, 0.5, 0.2, 1))
        mkdir_btn.bind(on_press=self._mkdir_dialog)
        bottom.add_widget(mkdir_btn)
        layout.add_widget(bottom)

        self.add_widget(layout)

    def on_enter(self):
        if self.client and self.client.connected:
            self.client.set_file_list_callback(self._on_file_list)
            self.client.set_file_server_callback(self._on_file_server)
            self.client.send_file_serve(8766)
            Clock.schedule_once(lambda dt: self._refresh(), 0.5)

    def on_leave(self):
        if self.client:
            self.client.set_file_list_callback(None)
            self.client.set_file_server_callback(None)

    def _on_file_server(self, host, port):
        self.file_host = host
        self.file_port = port

    def _on_file_list(self, data):
        def update(dt):
            if "error" in data:
                self.path_label.text = f"Error: {data['error']}"
                return
            self.current_path = data.get("path", "~")
            self.entries = data.get("entries", [])
            parent = data.get("parent")
            self.path_label.text = f"/{self.current_path}"
            self._populate(parent is not None)
        Clock.schedule_once(update)

    def _populate(self, show_parent):
        self.file_list.clear_widgets()

        if show_parent:
            parent_btn = Button(
                text="[b]..[/b] (Parent Directory)",
                size_hint_y=None, height=dp(44),
                background_color=(0.25, 0.25, 0.3, 1),
                markup=True, font_size=14, halign="left", padding=[15, 0]
            )
            parent_btn.bind(on_press=lambda b: self._navigate(".."))
            self.file_list.add_widget(parent_btn)

        for entry in self.entries:
            name = entry["name"]
            is_dir = entry["is_dir"]
            size = entry.get("size", 0)

            if is_dir:
                text = f"[b]{name}[/b]/"
            else:
                sz = self._format_size(size)
                text = f"{name}  [{sz}]"

            btn = Button(
                text=text, size_hint_y=None, height=dp(44),
                background_color=(0.15, 0.15, 0.18, 1),
                markup=True, font_size=13, halign="left", padding=[15, 0]
            )
            if is_dir:
                btn.bind(on_press=lambda b, n=name: self._navigate(n))
            else:
                btn.bind(on_press=lambda b, n=name: self._download_dialog(n))
            self.file_list.add_widget(btn)

    def _navigate(self, name):
        if name == "..":
            parent = self.entries[0].get("parent") if self.entries else None
            if parent:
                self._list_dir(parent)
        else:
            self._list_dir(self.current_path + "/" + name)

    def _list_dir(self, path):
        if self.client:
            self.client.send_file_list(path)

    def _refresh(self, *args):
        if self.client:
            self.client.send_file_list(self.current_path)

    def _go_back(self, *args):
        if self.manager:
            self.manager.current = "control"

    def _go_home(self, *args):
        self._list_dir("~")

    def _download_dialog(self, name):
        if not self.file_host:
            return
        content = BoxLayout(orientation="vertical", padding=10, spacing=10)
        content.add_widget(Label(text=f"Download {name}?", font_size=16))
        btn_layout = BoxLayout(spacing=8, size_hint_y=0.3)
        cancel = Button(text="Cancel")
        confirm = Button(text="Download", background_color=(0.2, 0.6, 1, 1))
        btn_layout.add_widget(cancel)
        btn_layout.add_widget(confirm)
        content.add_widget(btn_layout)

        popup = Popup(title="Download", content=content,
                      size_hint=(0.7, 0.35))
        cancel.bind(on_press=popup.dismiss)
        confirm.bind(on_press=lambda b: self._do_download(name, popup))
        popup.open()

    def _do_download(self, name, popup):
        popup.dismiss()
        if not self.file_host:
            return
        url = f"http://{self.file_host}:{self.file_port}/{self.current_path}/{name}"
        threading.Thread(target=self._download_thread, args=(url, name), daemon=True).start()

    def _download_thread(self, url, name):
        try:
            resp = urllib.request.urlopen(url)
            data = resp.read()
            import os
            from kivy.storage.dictstore import DictStore
            save_path = f"/sdcard/Download/{name}"
            try:
                with open(save_path, "wb") as f:
                    f.write(data)
                Clock.schedule_once(lambda dt: self._show_msg(f"Saved: {save_path}"))
            except Exception:
                save_path = f"{os.environ.get('EXTERNAL_STORAGE', '/sdcard')}/Download/{name}"
                with open(save_path, "wb") as f:
                    f.write(data)
                Clock.schedule_once(lambda dt: self._show_msg(f"Saved: {save_path}"))
        except Exception as e:
            Clock.schedule_once(lambda dt: self._show_msg(f"Error: {e}"))

    def _upload_dialog(self, *args):
        content = BoxLayout(orientation="vertical", padding=10, spacing=10)
        content.add_widget(Label(text="Upload file from phone:", font_size=14))
        inp = TextInput(hint_text="Filename on PC", text="file.txt",
                        size_hint_y=0.3, font_size=16)
        content.add_widget(inp)
        btn_layout = BoxLayout(spacing=8, size_hint_y=0.3)
        cancel = Button(text="Cancel")
        confirm = Button(text="Upload", background_color=(0.2, 0.7, 0.3, 1))
        btn_layout.add_widget(cancel)
        btn_layout.add_widget(confirm)
        content.add_widget(btn_layout)

        popup = Popup(title="Upload", content=content,
                      size_hint=(0.8, 0.4))
        cancel.bind(on_press=popup.dismiss)
        confirm.bind(on_press=lambda b: self._do_upload(inp.text, popup))
        popup.open()

    def _do_upload(self, name, popup):
        popup.dismiss()
        if not name:
            return
        import base64
        import os
        try:
            path = f"/sdcard/Download/{name}"
            if not os.path.exists(path):
                self._show_msg(f"File not found: {path}")
                return
            with open(path, "rb") as f:
                raw = f.read()
            encoded = base64.b64encode(raw).decode()
            if self.client:
                self.client.send({
                    "type": "file_upload",
                    "name": name,
                    "content": encoded,
                    "path": self.current_path,
                })
                self._show_msg(f"Uploading {name}...")
                Clock.schedule_once(lambda dt: self._refresh(), 2)
        except Exception as e:
            self._show_msg(f"Error: {e}")

    def _mkdir_dialog(self, *args):
        content = BoxLayout(orientation="vertical", padding=10, spacing=10)
        content.add_widget(Label(text="New folder name:", font_size=14))
        inp = TextInput(hint_text="Folder name", text="New Folder",
                        size_hint_y=0.3, font_size=16)
        content.add_widget(inp)
        btn_layout = BoxLayout(spacing=8, size_hint_y=0.3)
        cancel = Button(text="Cancel")
        confirm = Button(text="Create", background_color=(0.7, 0.5, 0.2, 1))
        btn_layout.add_widget(cancel)
        btn_layout.add_widget(confirm)
        content.add_widget(btn_layout)

        popup = Popup(title="New Folder", content=content,
                      size_hint=(0.8, 0.4))
        cancel.bind(on_press=popup.dismiss)
        confirm.bind(on_press=lambda b: self._do_mkdir(inp.text, popup))
        popup.open()

    def _do_mkdir(self, name, popup):
        popup.dismiss()
        if self.client and name:
            self.client.send({
                "type": "file_mkdir",
                "name": name,
                "path": self.current_path,
            })
            Clock.schedule_once(lambda dt: self._refresh(), 1)

    def _show_msg(self, msg):
        content = BoxLayout(orientation="vertical", padding=10, spacing=10)
        content.add_widget(Label(text=msg, font_size=14))
        btn = Button(text="OK", size_hint_y=0.3)
        popup = Popup(title="File Transfer", content=content,
                      size_hint=(0.7, 0.3))
        btn.bind(on_press=popup.dismiss)
        content.add_widget(btn)
        popup.open()

    @staticmethod
    def _format_size(size):
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}TB"
