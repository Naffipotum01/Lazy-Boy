import os
import sys
os.environ["KIVY_NO_CONSOLELOG"] = "0"

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.image import Image as KivyImage
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle
from kivy.core.image import Image as CoreImage
from kivy.core.window import Window
from io import BytesIO

from discovery import NetworkDiscovery
from client import ControlClient


class DiscoveryScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.devices = []
        self.discovery = None
        self.app_ref = None

        layout = BoxLayout(orientation="vertical", padding=20, spacing=10)

        header = BoxLayout(size_hint_y=0.12)
        title = Label(text="Lazy Boy", font_size=32, bold=True,
                       color=(0.2, 0.8, 0.4, 1))
        header.add_widget(title)
        layout.add_widget(header)

        self.status_label = Label(text="Scanning for PCs...",
                                   font_size=16, size_hint_y=0.08,
                                   color=(0.6, 0.6, 0.6, 1))
        layout.add_widget(self.status_label)

        scroll = ScrollView(size_hint_y=0.65)
        self.device_list = BoxLayout(orientation="vertical",
                                      size_hint_y=None, spacing=8, padding=[0, 10])
        self.device_list.bind(minimum_height=self.device_list.setter("height"))
        scroll.add_widget(self.device_list)
        layout.add_widget(scroll)

        btn_layout = BoxLayout(size_hint_y=0.1, spacing=10)
        refresh_btn = Button(text="Refresh", background_color=(0.2, 0.6, 1, 1))
        refresh_btn.bind(on_press=self.refresh_devices)
        btn_layout.add_widget(refresh_btn)
        layout.add_widget(btn_layout)

        self.add_widget(layout)

    def on_enter(self):
        self.refresh_devices()

    def refresh_devices(self, *args):
        self.device_list.clear_widgets()
        self.status_label.text = "Scanning for PCs..."

        if self.discovery:
            self.discovery.stop()

        def on_found(devices):
            Clock.schedule_once(lambda dt: self._update_device_list(devices))

        self.discovery = NetworkDiscovery(on_found)
        self.discovery.start_scan()

    def _update_device_list(self, devices):
        self.devices = devices
        self.device_list.clear_widgets()

        if not devices:
            self.status_label.text = "No PCs found. Make sure server is running."
            return

        self.status_label.text = f"Found {len(devices)} PC(s)"

        for device in devices:
            btn = Button(
                text=f"{device['hostname']}\n{device['ip']}",
                size_hint_y=None, height=80,
                background_color=(0.15, 0.15, 0.15, 1),
                font_size=18
            )
            btn.bind(on_press=lambda b, d=device: self._connect_to(d))
            self.device_list.add_widget(btn)

    def _connect_to(self, device):
        if self.discovery:
            self.discovery.stop()
        self.app_ref.connect_to(device)


class ControlScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.client = None
        self.app_ref = None
        self._texture = None
        self._last_touch_pos = None
        self._touch_start = None
        self._is_dragging = False

        self.layout = FloatLayout()

        self.screen_image = KivyImage(
            allow_stretch=True, keep_ratio=True,
            size_hint=(1, 1), pos_hint={"center_x": 0.5, "center_y": 0.5}
        )
        self.layout.add_widget(self.screen_image)

        top_bar = BoxLayout(size_hint_y=0.08, pos_hint={"top": 1},
                             padding=[10, 5], spacing=10)

        self.status_label = Label(text="Connecting...",
                                   font_size=14, halign="left",
                                   size_hint_x=0.6)
        self.status_label.bind(size=self.status_label.setter("text_size"))
        top_bar.add_widget(self.status_label)

        disconnect_btn = Button(text="Disconnect", size_hint_x=0.2,
                                 background_color=(0.8, 0.2, 0.2, 1))
        disconnect_btn.bind(on_press=self._disconnect)
        top_bar.add_widget(disconnect_btn)

        self.layout.add_widget(top_bar)

        bottom_bar = BoxLayout(size_hint_y=0.1, pos_hint={"y": 0},
                                padding=[10, 5], spacing=10)

        keyboard_btn = Button(text="Keyboard", size_hint_x=0.3,
                               background_color=(0.3, 0.3, 0.8, 1))
        keyboard_btn.bind(on_press=self._show_keyboard)
        bottom_bar.add_widget(keyboard_btn)

        left_click = Button(text="Left Click", size_hint_x=0.25,
                             background_color=(0.2, 0.6, 0.2, 1))
        left_click.bind(on_press=lambda b: self._send_click("left"))
        bottom_bar.add_widget(left_click)

        right_click = Button(text="Right Click", size_hint_x=0.25,
                              background_color=(0.6, 0.4, 0.2, 1))
        right_click.bind(on_press=lambda b: self._send_click("right"))
        bottom_bar.add_widget(right_click)

        scroll_up = Button(text="^", size_hint_x=0.1,
                            background_color=(0.4, 0.4, 0.4, 1))
        scroll_up.bind(on_press=lambda b: self._send_scroll(3))
        bottom_bar.add_widget(scroll_up)

        scroll_down = Button(text="v", size_hint_x=0.1,
                              background_color=(0.4, 0.4, 0.4, 1))
        scroll_down.bind(on_press=lambda b: self._send_scroll(-3))
        bottom_bar.add_widget(scroll_down)

        self.layout.add_widget(bottom_bar)

        self.add_widget(self.layout)

    def on_enter(self):
        if self.client and self.client.connected:
            self.status_label.text = "Connected"
            Window.bind(on_keyboard=self._on_keyboard)

    def on_leave(self):
        Window.unbind(on_keyboard=self._on_keyboard)

    def update_frame(self, img_bytes):
        try:
            buf = BytesIO(img_bytes)
            ci = CoreImage(buf, ext="jpg")
            self._texture = ci
            self.screen_image.texture = ci.texture
        except Exception:
            pass

    def update_status(self, status):
        def _update(dt):
            if status == "connected":
                self.status_label.text = "Connected"
                self.status_label.color = (0.2, 0.8, 0.4, 1)
            elif status == "waiting_approval":
                self.status_label.text = "Waiting for PC approval..."
                self.status_label.color = (1, 0.8, 0.2, 1)
            elif status == "denied":
                self.status_label.text = "Connection denied"
                self.status_label.color = (0.8, 0.2, 0.2, 1)
            elif status == "disconnected":
                self.status_label.text = "Disconnected"
                self.status_label.color = (0.6, 0.6, 0.6, 1)
            elif status.startswith("error"):
                self.status_label.text = status
                self.status_label.color = (0.8, 0.2, 0.2, 1)
            else:
                self.status_label.text = status
        Clock.schedule_once(_update)

    def _get_screen_coords(self, touch_x, touch_y):
        img = self.screen_image
        if not img.texture:
            return None

        tex_w, tex_h = img.texture.size
        img_w = img.size[0]
        img_h = img.size[1]

        if img_w == 0 or img_h == 0:
            return None

        if img.keep_ratio:
            ratio = min(img_w / tex_w, img_h / tex_h)
            display_w = tex_w * ratio
            display_h = tex_h * ratio
        else:
            display_w = img_w
            display_h = img_h

        offset_x = img.pos[0] + (img_w - display_w) / 2
        offset_y = img.pos[1] + (img_h - display_h) / 2

        rel_x = (touch_x - offset_x) / display_w
        rel_y = (touch_y - offset_y) / display_h

        if 0 <= rel_x <= 1 and 0 <= rel_y <= 1:
            return (int(rel_x * tex_w), int(rel_y * tex_h))
        return None

    def on_touch_down(self, touch):
        if not self.client or not self.client.connected:
            return super().on_touch_down(touch)

        if touch.y < self.layout.height * 0.1 or touch.y > self.layout.height * 0.92:
            return super().on_touch_down(touch)

        coords = self._get_screen_coords(touch.x, touch.y)
        if coords:
            self._last_touch_pos = (touch.x, touch.y)
            self._touch_start = (touch.x, touch.y)
            self._is_dragging = False
            touch.grab(self)
        return True

    def on_touch_move(self, touch):
        if touch.grab_current is self:
            if self._last_touch_pos:
                dx = touch.x - self._last_touch_pos[0]
                dy = touch.y - self._last_touch_pos[1]

                if abs(dx) > 2 or abs(dy) > 2:
                    self._is_dragging = True
                    screen_dx = int(dx * 2)
                    screen_dy = int(dy * 2)
                    self.client.send_mouse_move_relative(screen_dx, screen_dy)

            self._last_touch_pos = (touch.x, touch.y)
            return True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)

            if not self._is_dragging and self._touch_start:
                coords = self._get_screen_coords(touch.x, touch.y)
                if coords:
                    self.client.send_mouse_click(coords[0], coords[1], "left")

            self._last_touch_pos = None
            self._touch_start = None
            self._is_dragging = False
            return True
        return super().on_touch_up(touch)

    def _send_click(self, button):
        if self.client and self.client.connected:
            self.client.send_mouse_click(0, 0, button)

    def _send_scroll(self, dy):
        if self.client and self.client.connected:
            self.client.send_mouse_scroll(dy)

    def _show_keyboard(self, *args):
        content = BoxLayout(orientation="vertical", padding=10, spacing=10)
        text_input = TextInput(hint_text="Type here and press Send...",
                                multiline=False, size_hint_y=0.4,
                                font_size=18)
        content.add_widget(text_input)

        btn_layout = BoxLayout(size_hint_y=0.3, spacing=10)

        special_keys = [
            ("Enter", "enter"), ("Tab", "tab"), ("Esc", "escape"),
            ("Back", "backspace"), ("Del", "delete"),
            ("Ctrl+C", "ctrl+c"), ("Ctrl+V", "ctrl+v"),
            ("Ctrl+Z", "ctrl+z"), ("Alt+Tab", "alt+tab"),
        ]

        for label, key in special_keys:
            btn = Button(text=label, font_size=12)
            btn.bind(on_press=lambda b, k=key: self._send_special_key(k))
            btn_layout.add_widget(btn)

        content.add_widget(btn_layout)

        send_btn = Button(text="Send Text", size_hint_y=0.3,
                           background_color=(0.2, 0.6, 1, 1))
        send_btn.bind(on_press=lambda b: self._send_text(text_input.text))
        content.add_widget(send_btn)

        popup = Popup(title="Keyboard", content=content,
                      size_hint=(0.9, 0.6))
        send_btn.bind(on_press=lambda b: popup.dismiss())
        popup.open()

    def _send_text(self, text):
        if text and self.client and self.client.connected:
            self.client.send_type_text(text)

    def _send_special_key(self, key):
        if self.client and self.client.connected:
            if "+" in key:
                keys = key.split("+")
                self.client.send_hotkey(*keys)
            else:
                self.client.send_key_press(key)

    def _on_keyboard(self, window, key, scancode, codepoint, modifiers):
        if not self.client or not self.client.connected:
            return False

        if key == 8:
            self.client.send_key_press("backspace")
            return True
        elif key == 13:
            self.client.send_key_press("enter")
            return True
        elif key == 9:
            self.client.send_key_press("tab")
            return True
        elif key == 27:
            self.client.send_key_press("escape")
            return True
        elif key == 32:
            self.client.send_key_press("space")
            return True
        elif codepoint:
            if "ctrl" in modifiers:
                if codepoint == "c":
                    self.client.send_hotkey("ctrl", "c")
                elif codepoint == "v":
                    self.client.send_hotkey("ctrl", "v")
                elif codepoint == "z":
                    self.client.send_hotkey("ctrl", "z")
                elif codepoint == "a":
                    self.client.send_hotkey("ctrl", "a")
            else:
                self.client.send_type_text(codepoint)
            return True
        return False

    def _disconnect(self, *args):
        if self.client:
            self.client.disconnect()
        if self.app_ref:
            self.app_ref.show_discovery()


class LazyBoyApp(App):
    def build(self):
        self.title = "Lazy Boy"
        self.sm = ScreenManager()

        self.discovery_screen = DiscoveryScreen(name="discovery")
        self.discovery_screen.app_ref = self

        self.control_screen = ControlScreen(name="control")
        self.control_screen.app_ref = self

        self.sm.add_widget(self.discovery_screen)
        self.sm.add_widget(self.control_screen)

        self.client = ControlClient()
        self.client.set_frame_callback(self._on_frame)
        self.client.set_status_callback(self._on_status)

        return self.sm

    def connect_to(self, device):
        self.control_screen.client = self.client
        self.client.set_frame_callback(self._on_frame)
        self.client.set_status_callback(self._on_status)
        self.sm.current = "control"
        self.client.connect(device["ip"])

    def show_discovery(self):
        self.sm.current = "discovery"

    def _on_frame(self, img_bytes):
        self.control_screen.update_frame(img_bytes)

    def _on_status(self, status):
        self.control_screen.update_status(status)
        if status in ("denied", "disconnected"):
            Clock.schedule_once(lambda dt: self.show_discovery(), 2)

    def on_stop(self):
        self.client.disconnect()


if __name__ == "__main__":
    LazyBoyApp().run()
