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
from kivy.graphics import Color, Rectangle, Line
from kivy.core.image import Image as CoreImage
from kivy.core.window import Window
from kivy.metrics import dp
from io import BytesIO
import time

from discovery import NetworkDiscovery
from client import ControlClient

SWIPE_THRESHOLD = 60
SWIPE_VELOCITY = 250
DOUBLE_TAP_TIMEOUT = 0.35
POINTER_SENSITIVITY = 2.5
TOUCH_SENSITIVITY = 1.6
SMOOTHING = 0.45
MOVE_THRESHOLD = 1


class DiscoveryScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.devices = []
        self.discovery = None
        self.app_ref = None

        layout = BoxLayout(orientation="vertical", padding=20, spacing=10)

        header = BoxLayout(size_hint_y=0.12)
        title = Label(text="Lazy Boy Remote", font_size=32, bold=True,
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
    MODE_TOUCH = "touch"
    MODE_POINTER = "pointer"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.client = None
        self.app_ref = None
        self._texture = None
        self.mode = self.MODE_TOUCH
        self._showing_screen = True

        self._t1_start = None
        self._t1_pos = None
        self._t1_time = 0
        self._t1_grabbed = False
        self._t2_start = None
        self._t2_pos = None
        self._t2_time = 0
        self._t2_grabbed = False
        self._is_dragging = False
        self._last_tap_time = 0
        self._last_tap_pos = None

        self._smooth_dx = 0
        self._smooth_dy = 0

        self.layout = FloatLayout()

        with self.layout.canvas.before:
            Color(0.08, 0.08, 0.08, 1)
            self._bg_rect = Rectangle(pos=self.layout.pos, size=self.layout.size)
        self.layout.bind(pos=self._update_bg, size=self._update_bg)

        self.screen_image = KivyImage(
            allow_stretch=True, keep_ratio=True,
            size_hint=(1, 1), pos_hint={"center_x": 0.5, "center_y": 0.5}
        )
        self.layout.add_widget(self.screen_image)

        self.trackpad_label = Label(
            text="[b]POINTER MODE[/b]\n\nFinger = trackpad\nTap = click | Double-tap = right click\nTwo-finger swipe = scroll / switch apps",
            markup=True, font_size=18, halign="center", valign="center",
            size_hint=(0.7, 0.3),
            pos_hint={"center_x": 0.5, "center_y": 0.5},
            color=(0.6, 0.6, 0.6, 1)
        )
        self.trackpad_label.bind(size=self.trackpad_label.setter("text_size"))
        self.trackpad_label.opacity = 0
        self.layout.add_widget(self.trackpad_label)

        top_bar = BoxLayout(size_hint_y=0.08, pos_hint={"top": 1},
                             padding=[6, 4], spacing=6)

        self.touch_btn = Button(
            text="Touch", size_hint_x=0.18,
            background_color=(0.2, 0.7, 0.3, 1),
            font_size=14, bold=True
        )
        self.touch_btn.bind(on_press=lambda b: self._set_mode(self.MODE_TOUCH))
        top_bar.add_widget(self.touch_btn)

        self.pointer_btn = Button(
            text="Pointer", size_hint_x=0.18,
            background_color=(0.3, 0.3, 0.3, 1),
            font_size=14
        )
        self.pointer_btn.bind(on_press=lambda b: self._set_mode(self.MODE_POINTER))
        top_bar.add_widget(self.pointer_btn)

        self.status_label = Label(text="Connecting...",
                                   font_size=12, halign="center",
                                   size_hint_x=0.24)
        self.status_label.bind(size=self.status_label.setter("text_size"))
        top_bar.add_widget(self.status_label)

        keyboard_btn = Button(text="KB", size_hint_x=0.12,
                               background_color=(0.3, 0.3, 0.8, 1),
                               font_size=14, bold=True)
        keyboard_btn.bind(on_press=self._show_keyboard)
        top_bar.add_widget(keyboard_btn)

        disconnect_btn = Button(text="X", size_hint_x=0.1,
                                 background_color=(0.7, 0.2, 0.2, 1),
                                 font_size=16, bold=True)
        disconnect_btn.bind(on_press=self._disconnect)
        top_bar.add_widget(disconnect_btn)

        self.layout.add_widget(top_bar)

        self.mode_hint = Label(
            text="[b]TOUCH MODE[/b]  |  Tap = click  |  Swipe = scroll/switch",
            markup=True, font_size=12, halign="center",
            size_hint=(0.9, 0.05),
            pos_hint={"center_x": 0.5, "y": 0.01},
            color=(1, 1, 1, 0.5)
        )
        self.mode_hint.bind(size=self.mode_hint.setter("text_size"))
        self.layout.add_widget(self.mode_hint)

        self.add_widget(self.layout)

    def _update_bg(self, *args):
        self._bg_rect.pos = self.layout.pos
        self._bg_rect.size = self.layout.size

    def _set_mode(self, mode):
        self.mode = mode
        if mode == self.MODE_TOUCH:
            self.touch_btn.background_color = (0.2, 0.7, 0.3, 1)
            self.pointer_btn.background_color = (0.3, 0.3, 0.3, 1)
            self.screen_image.opacity = 1
            self._showing_screen = True
            self.trackpad_label.opacity = 0
            self.mode_hint.text = "[b]TOUCH MODE[/b]  |  Tap = click  |  Swipe = scroll/switch"
        else:
            self.touch_btn.background_color = (0.3, 0.3, 0.3, 1)
            self.pointer_btn.background_color = (0.2, 0.5, 0.9, 1)
            self.screen_image.opacity = 0
            self._showing_screen = False
            self.trackpad_label.opacity = 1
            self.mode_hint.text = "[b]POINTER MODE[/b]  |  Finger = trackpad  |  Tap = click  |  Double-tap = right click"

    def on_enter(self):
        if self.client and self.client.connected:
            self.status_label.text = "Connected"
            Window.bind(on_keyboard=self._on_keyboard)

    def on_leave(self):
        Window.unbind(on_keyboard=self._on_keyboard)

    def update_frame(self, img_bytes):
        if not self._showing_screen:
            return
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
                self.status_label.text = "Waiting..."
                self.status_label.color = (1, 0.8, 0.2, 1)
            elif status == "denied":
                self.status_label.text = "Denied"
                self.status_label.color = (0.8, 0.2, 0.2, 1)
            elif status == "disconnected":
                self.status_label.text = "Disconnected"
                self.status_label.color = (0.6, 0.6, 0.6, 1)
            elif status.startswith("error"):
                self.status_label.text = "Error"
                self.status_label.color = (0.8, 0.2, 0.2, 1)
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

    def _is_in_control_area(self, touch):
        if touch.y < self.layout.height * 0.04:
            return False
        if touch.y > self.layout.height * 0.92:
            return False
        return True

    def on_touch_down(self, touch):
        if not self.client or not self.client.connected:
            return super().on_touch_down(touch)

        if not self._is_in_control_area(touch):
            return super().on_touch_down(touch)

        if touch.is_mouse_scrolling:
            if touch.button == "scrolldown":
                self._send_scroll(-3)
            elif touch.button == "scrollup":
                self._send_scroll(3)
            return True

        now = time.time()

        if self._t1_grabbed and not self._t2_grabbed:
            self._t2_start = (touch.x, touch.y)
            self._t2_pos = (touch.x, touch.y)
            self._t2_time = now
            self._t2_grabbed = True
            touch.grab(self)
            return True

        if not self._t1_grabbed:
            self._t1_start = (touch.x, touch.y)
            self._t1_pos = (touch.x, touch.y)
            self._t1_time = now
            self._t1_grabbed = True
            self._is_dragging = False
            self._smooth_dx = 0
            self._smooth_dy = 0
            touch.grab(self)
        return True

    def on_touch_move(self, touch):
        if touch.grab_current is not self:
            return super().on_touch_move(touch)

        if self._t2_grabbed:
            return True

        if self._t1_pos:
            dx = touch.x - self._t1_pos[0]
            dy = touch.y - self._t1_pos[1]

            if abs(dx) > MOVE_THRESHOLD or abs(dy) > MOVE_THRESHOLD:
                self._is_dragging = True

                if self.mode == self.MODE_TOUCH:
                    sens = TOUCH_SENSITIVITY
                else:
                    sens = POINTER_SENSITIVITY

                self._smooth_dx = self._smooth_dx * (1 - SMOOTHING) + dx * SMOOTHING
                self._smooth_dy = self._smooth_dy * (1 - SMOOTHING) + dy * SMOOTHING
                screen_dx = int(self._smooth_dx * sens)
                screen_dy = int(-self._smooth_dy * sens)

                if abs(screen_dx) >= 1 or abs(screen_dy) >= 1:
                    self.client.send_mouse_move_relative(screen_dx, screen_dy)

            self._t1_pos = (touch.x, touch.y)
        return True

    def on_touch_up(self, touch):
        if touch.grab_current is not self:
            return super().on_touch_up(touch)

        touch.ungrab(self)
        now = time.time()

        if self._t2_grabbed and self._t2_start:
            t2_start = self._t2_start
            t2_end = (touch.x, touch.y)
            t2_dx = t2_end[0] - t2_start[0]
            t2_dy = t2_end[1] - t2_start[1]
            t2_dist = (t2_dx**2 + t2_dy**2) ** 0.5
            t2_elapsed = max(0.01, now - self._t2_time)
            t2_velocity = t2_dist / t2_elapsed

            if t2_dist > SWIPE_THRESHOLD and t2_velocity > SWIPE_VELOCITY:
                if abs(t2_dy) > abs(t2_dx):
                    self._send_scroll(5 if t2_dy > 0 else -5)
                else:
                    if t2_dx > 0:
                        self.client.send_hotkey("alt", "shift", "tab")
                    else:
                        self.client.send_hotkey("alt", "tab")
            elif t2_dist < 20:
                if self.mode == self.MODE_TOUCH:
                    coords = self._get_screen_coords(t2_end[0], t2_end[1])
                    if coords:
                        self.client.send_mouse_click(coords[0], coords[1], "right")
                else:
                    self.client.send_mouse_click(0, 0, "right")

            self._reset_touches()
            return True

        if self._t1_start:
            t1_start = self._t1_start
            t1_end = (touch.x, touch.y)
            t1_dx = t1_end[0] - t1_start[0]
            t1_dy = t1_end[1] - t1_start[1]
            t1_dist = (t1_dx**2 + t1_dy**2) ** 0.5
            t1_elapsed = max(0.01, now - self._t1_time)
            t1_velocity = t1_dist / t1_elapsed

            is_swipe = t1_dist > SWIPE_THRESHOLD and t1_velocity > SWIPE_VELOCITY

            if self.mode == self.MODE_TOUCH:
                if is_swipe:
                    if abs(t1_dy) > abs(t1_dx):
                        self._send_scroll(5 if t1_dy > 0 else -5)
                    else:
                        if t1_dx > 0:
                            self.client.send_hotkey("alt", "shift", "tab")
                        else:
                            self.client.send_hotkey("alt", "tab")
                elif not self._is_dragging:
                    coords = self._get_screen_coords(t1_end[0], t1_end[1])
                    if coords:
                        self.client.send_mouse_click(coords[0], coords[1], "left")
            else:
                if not self._is_dragging and t1_dist < 15:
                    time_since_last = now - self._last_tap_time
                    dist_from_last = 0
                    if self._last_tap_pos:
                        dist_from_last = ((t1_end[0] - self._last_tap_pos[0])**2 +
                                          (t1_end[1] - self._last_tap_pos[1])**2) ** 0.5

                    if time_since_last < DOUBLE_TAP_TIMEOUT and dist_from_last < 40:
                        self.client.send_mouse_click(0, 0, "right")
                        self._last_tap_time = 0
                        self._last_tap_pos = None
                    else:
                        self.client.send_mouse_click(0, 0, "left")
                        self._last_tap_time = now
                        self._last_tap_pos = t1_end

        self._reset_touches()
        return True

    def _reset_touches(self):
        self._t1_start = None
        self._t1_pos = None
        self._t1_grabbed = False
        self._t2_start = None
        self._t2_pos = None
        self._t2_grabbed = False
        self._is_dragging = False
        self._smooth_dx = 0
        self._smooth_dy = 0

    def _send_scroll(self, dy):
        if self.client and self.client.connected:
            self.client.send_mouse_scroll(dy)

    def _show_keyboard(self, *args):
        content = BoxLayout(orientation="vertical", padding=10, spacing=10)
        text_input = TextInput(hint_text="Type here and press Send...",
                                multiline=False, size_hint_y=0.4,
                                font_size=18)
        content.add_widget(text_input)

        btn_layout = BoxLayout(size_hint_y=0.3, spacing=8)

        special_keys = [
            ("Enter", "enter"), ("Tab", "tab"), ("Esc", "escape"),
            ("Back", "backspace"), ("Del", "delete"),
            ("Ctrl+C", "ctrl+c"), ("Ctrl+V", "ctrl+v"),
            ("Ctrl+Z", "ctrl+z"), ("Alt+Tab", "alt+tab"),
        ]

        for label, key in special_keys:
            btn = Button(text=label, font_size=11)
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

        if key == 24 or key == 1073741952:
            self.client.send_key_press("volumeup")
            return True
        elif key == 25 or key == 1073741953:
            self.client.send_key_press("volumedown")
            return True
        elif key == 8:
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
        self.title = "Lazy Boy Remote"
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
