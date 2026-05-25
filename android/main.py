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
from kivy.uix.widget import Widget
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle, Ellipse, Line
from kivy.core.image import Image as CoreImage
from kivy.core.window import Window
from kivy.metrics import dp
from io import BytesIO
import time
import math

from discovery import NetworkDiscovery
from client import ControlClient
from key_bindings import load_bindings
from settings_screen import KeyBindingsScreen
from file_browser import FileBrowserScreen
from saved_devices import load_saved, save_device, forget_device
from voice import VoiceController
from bridge_screen import BridgeScreen
from device_bridge import DeviceBridge
from radio_screen import RadioScreen
from phone_radio import PhoneRadio
from smart_pointer import SmartPointerOverlay
from booster_screen import BoosterScreen
from network_booster import NetworkBooster as AndroidNetworkBooster

SWIPE_THRESHOLD = 60
SWIPE_VELOCITY = 250
DOUBLE_TAP_TIMEOUT = 0.35
POINTER_SENSITIVITY = 2.5
TOUCH_SENSITIVITY = 1.6
SMOOTHING = 0.45
MOVE_THRESHOLD = 1


class VirtualJoystick(Widget):
    def __init__(self, size_val=dp(140), deadzone=0.15, **kwargs):
        super().__init__(**kwargs)
        self.size_hint = (None, None)
        self.size = (size_val, size_val)
        self.base_radius = size_val / 2
        self.thumb_radius = size_val / 4
        self.deadzone = deadzone
        self.norm_x = 0.0
        self.norm_y = 0.0
        self._touch_id = None
        self._touch_pos = None
        self._update_event = None
        self._draw_base()

    def _draw_base(self):
        self.canvas.clear()
        with self.canvas:
            Color(1, 1, 1, 0.12)
            Ellipse(pos=self.pos, size=self.size)
            Color(1, 1, 1, 0.06)
            Line(circle=(self.center_x, self.center_y, self.base_radius), width=dp(2))
            Color(1, 1, 1, 0.4)
            self._thumb = Ellipse(
                pos=(self.center_x - self.thumb_radius, self.center_y - self.thumb_radius),
                size=(self.thumb_radius * 2, self.thumb_radius * 2)
            )

    def _update_thumb(self, tx, ty):
        dx = tx - self.center_x
        dy = ty - self.center_y
        dist = math.sqrt(dx * dx + dy * dy)
        max_dist = self.base_radius - self.thumb_radius

        if dist > max_dist:
            dx = dx / dist * max_dist
            dy = dy / dist * max_dist
            dist = max_dist

        normalized = dist / max_dist if max_dist > 0 else 0
        if normalized < self.deadzone:
            self.norm_x = 0.0
            self.norm_y = 0.0
            thumb_x = self.center_x - self.thumb_radius
            thumb_y = self.center_y - self.thumb_radius
        else:
            self.norm_x = dx / max_dist
            self.norm_y = dy / max_dist
            thumb_x = self.center_x + dx - self.thumb_radius
            thumb_y = self.center_y + dy - self.thumb_radius

        self._thumb.pos = (thumb_x, thumb_y)

    def _reset_thumb(self):
        self.norm_x = 0.0
        self.norm_y = 0.0
        self._thumb.pos = (
            self.center_x - self.thumb_radius,
            self.center_y - self.thumb_radius
        )

    def on_touch_down(self, touch):
        if self._touch_id is not None:
            return False
        if not self.collide_point(touch.x, touch.y):
            return False
        self._touch_id = touch.uid
        self._touch_pos = (touch.x, touch.y)
        self._update_thumb(touch.x, touch.y)
        touch.grab(self)
        return True

    def on_touch_move(self, touch):
        if touch.uid != self._touch_id:
            return False
        self._touch_pos = (touch.x, touch.y)
        self._update_thumb(touch.x, touch.y)
        return True

    def on_touch_up(self, touch):
        if touch.uid != self._touch_id:
            return False
        touch.ungrab(self)
        self._touch_id = None
        self._touch_pos = None
        self._reset_thumb()
        return True

    def on_pos(self, *args):
        self._draw_base()

    def on_size(self, *args):
        self._draw_base()


class GamepadButton(Widget):
    def __init__(self, label="", key="", color=(1, 1, 1, 0.25),
                 text_color=(1, 1, 1, 0.9), size_val=dp(52), **kwargs):
        super().__init__(**kwargs)
        self.size_hint = (None, None)
        self.size = (size_val, size_val)
        self.label = label
        self.key = key
        self.btn_color = color
        self.text_color = text_color
        self._touch_id = None
        self._pressed = False
        self.client = None
        self._draw_btn(pressed=False)

    def _draw_btn(self, pressed=False):
        self.canvas.clear()
        with self.canvas:
            if pressed:
                Color(*self.btn_color[:3], min(1, self.btn_color[3] + 0.3))
            else:
                Color(*self.btn_color)
            Ellipse(pos=self.pos, size=self.size)

        if self.label:
            lbl = Label(
                text=f"[b]{self.label}[/b]",
                markup=True, font_size=self.size[0] * 0.35,
                halign="center", valign="center",
                size=self.size, pos=self.pos,
                color=self.text_color
            )
            lbl.bind(size=lbl.setter("text_size"))

    def on_touch_down(self, touch):
        if self._touch_id is not None:
            return False
        if not self.collide_point(touch.x, touch.y):
            return False
        self._touch_id = touch.uid
        self._pressed = True
        self._draw_btn(pressed=True)
        if self.key and self.client:
            self.client.send_key_down(self.key)
        touch.grab(self)
        return True

    def on_touch_move(self, touch):
        if touch.uid != self._touch_id:
            return False
        return True

    def on_touch_up(self, touch):
        if touch.uid != self._touch_id:
            return False
        touch.ungrab(self)
        self._touch_id = None
        self._pressed = False
        self._draw_btn(pressed=False)
        if self.key and self.client:
            self.client.send_key_up(self.key)
        return True

    def on_pos(self, *args):
        self._draw_btn(self._pressed)

    def on_size(self, *args):
        self._draw_btn(self._pressed)


class GamepadOverlay(FloatLayout):
    def __init__(self, client=None, **kwargs):
        super().__init__(**kwargs)
        self.client = client
        self._input_event = None

        self.left_stick = VirtualJoystick(size_val=dp(130))
        self.add_widget(self.left_stick)

        self.right_stick = VirtualJoystick(size_val=dp(130))
        self.add_widget(self.right_stick)

        self.btn_a = GamepadButton("A", "space", (0.2, 0.7, 0.2, 0.35), size_val=dp(54))
        self.btn_b = GamepadButton("B", "lctrl", (0.8, 0.2, 0.2, 0.35), size_val=dp(54))
        self.btn_x = GamepadButton("X", "e", (0.2, 0.4, 0.9, 0.35), size_val=dp(54))
        self.btn_y = GamepadButton("Y", "r", (0.9, 0.8, 0.1, 0.35), size_val=dp(54))

        for btn in (self.btn_a, self.btn_b, self.btn_x, self.btn_y):
            self.add_widget(btn)

        self.btn_lb = GamepadButton("LB", "q", (0.5, 0.5, 0.5, 0.3), size_val=dp(50))
        self.btn_rb = GamepadButton("RB", "tab", (0.5, 0.5, 0.5, 0.3), size_val=dp(50))
        self.btn_lt = GamepadButton("LT", "rightmouse", (0.4, 0.4, 0.4, 0.3), size_val=dp(50))
        self.btn_rt = GamepadButton("RT", "leftmouse", (0.6, 0.3, 0.3, 0.35), size_val=dp(50))

        for btn in (self.btn_lb, self.btn_rb, self.btn_lt, self.btn_rt):
            self.add_widget(btn)

        self.btn_dup = GamepadButton("^", "up", (0.4, 0.4, 0.4, 0.3), dp(44))
        self.btn_ddown = GamepadButton("v", "down", (0.4, 0.4, 0.4, 0.3), dp(44))
        self.btn_dleft = GamepadButton("<", "left", (0.4, 0.4, 0.4, 0.3), dp(44))
        self.btn_dright = GamepadButton(">", "right", (0.4, 0.4, 0.4, 0.3), dp(44))

        for btn in (self.btn_dup, self.btn_ddown, self.btn_dleft, self.btn_dright):
            self.add_widget(btn)

        self.bind(pos=self._layout, size=self._layout)
        self._layout()

    def set_client(self, client):
        self.client = client
        self.left_stick.client = client
        self.right_stick.client = client
        for child in self.children:
            if isinstance(child, GamepadButton):
                child.client = client

    def apply_bindings(self, bindings):
        mapping = {
            self.btn_a: "A", self.btn_b: "B", self.btn_x: "X", self.btn_y: "Y",
            self.btn_lb: "LB", self.btn_rb: "RB", self.btn_lt: "LT", self.btn_rt: "RT",
            self.btn_dup: "DUP", self.btn_ddown: "DDOWN",
            self.btn_dleft: "DLEFT", self.btn_dright: "DRIGHT",
        }
        for btn, name in mapping.items():
            if name in bindings and bindings[name]:
                btn.key = bindings[name]

    def _layout(self, *args):
        w, h = self.size
        ox, oy = self.pos

        ls_size = self.left_stick.size[0]
        rs_size = self.right_stick.size[0]

        ls_cx = ox + w * 0.18
        ls_cy = oy + h * 0.30
        self.left_stick.center = (ls_cx, ls_cy)

        rs_cx = ox + w * 0.82
        rs_cy = oy + h * 0.30
        self.right_stick.center = (rs_cx, rs_cy)

        abxy_cx = rs_cx
        abxy_cy = oy + h * 0.62
        abxy_spread = dp(36)
        self.btn_a.center = (abxy_cx, abxy_cy - abxy_spread)
        self.btn_b.center = (abxy_cx + abxy_spread, abxy_cy)
        self.btn_x.center = (abxy_cx - abxy_spread, abxy_cy)
        self.btn_y.center = (abxy_cx, abxy_cy + abxy_spread)

        dpad_cx = ls_cx
        dpad_cy = oy + h * 0.62
        dpad_spread = dp(28)
        self.btn_dup.center = (dpad_cx, dpad_cy + dpad_spread)
        self.btn_ddown.center = (dpad_cx, dpad_cy - dpad_spread)
        self.btn_dleft.center = (dpad_cx - dpad_spread, dpad_cy)
        self.btn_dright.center = (dpad_cx + dpad_spread, dpad_cy)

        trigger_y = oy + h * 0.85
        bumper_y = oy + h * 0.75
        self.btn_lt.center = (ox + w * 0.12, trigger_y)
        self.btn_rt.center = (ox + w * 0.88, trigger_y)
        self.btn_lb.center = (ox + w * 0.12, bumper_y)
        self.btn_rb.center = (ox + w * 0.88, bumper_y)

    def start_input_loop(self):
        if self._input_event:
            return
        self._input_event = Clock.schedule_interval(self._send_stick_input, 0.02)

    def stop_input_loop(self):
        if self._input_event:
            self._input_event.cancel()
            self._input_event = None

    def _send_stick_input(self, dt):
        if not self.client:
            return

        lsx = self.left_stick.norm_x
        lsy = self.left_stick.norm_y
        ls_deadzone = 0.2

        if abs(lsx) > ls_deadzone or abs(lsy) > ls_deadzone:
            self._send_wasd(lsx, lsy)
        else:
            self._release_wasd()

        rsx = self.right_stick.norm_x
        rsy = self.right_stick.norm_y
        rs_deadzone = 0.2
        rs_sensitivity = 12

        if abs(rsx) > rs_deadzone or abs(rsy) > rs_deadzone:
            mdx = int(rsx * rs_sensitivity)
            mdy = int(-rsy * rs_sensitivity)
            if abs(mdx) >= 1 or abs(mdy) >= 1:
                self.client.send_mouse_move_relative(mdx, mdy)

    def _send_wasd(self, x, y):
        if not self.client:
            return
        keys = []
        threshold = 0.3
        if y > threshold:
            keys.append("w")
        elif y < -threshold:
            keys.append("s")
        if x < -threshold:
            keys.append("a")
        elif x > threshold:
            keys.append("d")

        if hasattr(self, '_held_wasd'):
            for k in self._held_wasd:
                if k not in keys:
                    self.client.send_key_up(k)
        for k in keys:
            if not hasattr(self, '_held_wasd') or k not in self._held_wasd:
                self.client.send_key_down(k)
        self._held_wasd = keys

    def _release_wasd(self):
        if hasattr(self, '_held_wasd') and self._held_wasd:
            for k in self._held_wasd:
                if self.client:
                    self.client.send_key_up(k)
            self._held_wasd = []

    def cleanup(self):
        self.stop_input_loop()
        self._release_wasd()


class DiscoveryScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.devices = []
        self.discovery = None
        self.app_ref = None

        layout = BoxLayout(orientation="vertical", padding=20, spacing=6)

        header = BoxLayout(size_hint_y=0.10)
        title = Label(text="Lazy Boy Remote", font_size=28, bold=True,
                       color=(0.2, 0.8, 0.4, 1))
        header.add_widget(title)
        layout.add_widget(header)

        self.status_label = Label(text="Scanning for PCs...",
                                   font_size=14, size_hint_y=0.04,
                                   color=(0.6, 0.6, 0.6, 1))
        layout.add_widget(self.status_label)

        scroll = ScrollView(size_hint_y=0.45)
        self.device_list = BoxLayout(orientation="vertical",
                                       size_hint_y=None, spacing=4, padding=[0, 6])
        self.device_list.bind(minimum_height=self.device_list.setter("height"))
        scroll.add_widget(self.device_list)
        layout.add_widget(scroll)

        self.saved_label = Label(
            text="", font_size=11, size_hint_y=0.03,
            color=(0.4, 0.6, 0.4, 1), halign="center"
        )
        layout.add_widget(self.saved_label)

        self.saved_list = BoxLayout(orientation="vertical",
                                     size_hint_y=None, spacing=2)
        self.saved_list.bind(minimum_height=self.saved_list.setter("height"))
        layout.add_widget(self.saved_list)

        manual_box = BoxLayout(orientation="vertical", size_hint_y=0.18, spacing=4,
                                padding=[0, 4])
        manual_box.add_widget(Label(text="Manual Connect (remote IP or tunnel URL):",
                                     font_size=12, size_hint_y=0.2,
                                     color=(0.5, 0.5, 0.5, 1)))
        ip_row = BoxLayout(size_hint_y=0.35, spacing=5)
        self.manual_input = TextInput(
            hint_text="IP, hostname, or ws:// url", font_size=14,
            size_hint_x=0.7, multiline=False
        )
        ip_row.add_widget(self.manual_input)
        connect_btn = Button(text="Connect", size_hint_x=0.3,
                              background_color=(0.2, 0.7, 0.3, 1),
                              font_size=14, bold=True)
        connect_btn.bind(on_press=self._manual_connect)
        ip_row.add_widget(connect_btn)
        manual_box.add_widget(ip_row)
        layout.add_widget(manual_box)

        btn_layout = BoxLayout(size_hint_y=0.1, spacing=10)
        refresh_btn = Button(text="Refresh", background_color=(0.2, 0.6, 1, 1))
        refresh_btn.bind(on_press=self.refresh_devices)
        btn_layout.add_widget(refresh_btn)
        layout.add_widget(btn_layout)

        self.add_widget(layout)

    def on_enter(self):
        self._show_saved()
        self.refresh_devices()

    def _show_saved(self):
        self.saved_list.clear_widgets()
        saved = load_saved()
        if not saved:
            self.saved_label.text = ""
            return

        self.saved_label.text = f"Saved devices ({len(saved)})  |  Long-press to forget"
        for i, dev in enumerate(saved[:5]):
            name = dev.get("hostname", dev["ip"])
            ip = dev.get("ip", "")
            label = f"  {name}  ({ip})"
            row = BoxLayout(size_hint_y=None, height=32, spacing=2)
            btn = Button(
                text=label,
                font_size=12, halign="left", padding=[10, 0],
                size_hint_x=0.8,
                background_color=(0.12, 0.2, 0.12, 1)
            )
            btn.bind(on_press=lambda b, d=dev: self._connect_saved(d))
            row.add_widget(btn)
            forget_btn = Button(
                text="X", font_size=10,
                size_hint_x=0.2,
                background_color=(0.4, 0.15, 0.15, 1)
            )
            forget_btn.bind(on_press=lambda b, d=dev: self._forget_device(d))
            row.add_widget(forget_btn)
            self.saved_list.add_widget(row)

    def _connect_saved(self, dev):
        if self.discovery:
            self.discovery.stop()
        self.app_ref.connect_to(dev)

    def _forget_device(self, dev):
        forget_device(dev.get("ip", ""))
        self._show_saved()

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
            lines = f"{device['hostname']}\n{device['ip']}"
            has_remote = "public_ip" in device or "ngrok_url" in device
            if has_remote:
                lines += "\n[Remote available]"

            btn = Button(
                text=lines,
                size_hint_y=None, height=70,
                background_color=(0.15, 0.15, 0.18, 1),
                font_size=15, markup=True, halign="center"
            )
            btn.bind(on_press=lambda b, d=device: self._connect_to(d))

            wrapper = BoxLayout(orientation="vertical", size_hint_y=None, height=95)
            wrapper.add_widget(btn)

            if has_remote:
                remote_row = BoxLayout(size_hint_y=None, height=25, spacing=2)
                if device.get("public_ip"):
                    rbtn = Button(
                        text=f"Remote: {device['public_ip']}",
                        font_size=10,
                        background_color=(0.6, 0.4, 0.2, 1),
                        size_hint_x=0.5
                    )
                    rbtn.bind(on_press=lambda b, d=device: self._connect_remote(d, d["public_ip"]))
                    remote_row.add_widget(rbtn)
                if device.get("ngrok_url"):
                    tbtn = Button(
                        text="Tunnel",
                        font_size=10,
                        background_color=(0.4, 0.2, 0.6, 1),
                        size_hint_x=0.5
                    )
                    tbtn.bind(on_press=lambda b, d=device: self._connect_remote(d, d["ngrok_url"]))
                    remote_row.add_widget(tbtn)
                wrapper.add_widget(remote_row)

            self.device_list.add_widget(wrapper)

    def _connect_to(self, device):
        if self.discovery:
            self.discovery.stop()
        self.app_ref.connect_to(device)

    def _connect_remote(self, device, remote_addr):
        if self.discovery:
            self.discovery.stop()
        addr = remote_addr.replace("tcp://", "ws://")
        if not addr.startswith("ws://"):
            addr = f"ws://{addr}"
        device_copy = dict(device)
        device_copy["ip"] = addr
        self.app_ref.connect_to(device_copy)

    def _manual_connect(self, *args):
        text = self.manual_input.text.strip()
        if not text:
            return
        text = text.replace("tcp://", "ws://")
        if not text.startswith("ws://") and not text.startswith("wss://"):
            if ":" in text:
                text = f"ws://{text}"
            else:
                text = f"ws://{text}:8765"
        if self.discovery:
            self.discovery.stop()
        self.app_ref.connect_to({"ip": text, "hostname": text})


class ControlScreen(Screen):
    MODE_TOUCH = "touch"
    MODE_POINTER = "pointer"
    MODE_GAMEPAD = "gamepad"
    MODE_BT_PASS = "bt_pass"

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

        self.gamepad = GamepadOverlay(size_hint=(1, 1))
        self.gamepad.opacity = 0
        self.gamepad.disabled = True
        self.layout.add_widget(self.gamepad)

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
                             padding=[6, 4], spacing=3)

        self.touch_btn = Button(
            text="Touch", size_hint_x=0.12,
            background_color=(0.2, 0.7, 0.3, 1),
            font_size=11, bold=True
        )
        self.touch_btn.bind(on_press=lambda b: self._set_mode(self.MODE_TOUCH))
        top_bar.add_widget(self.touch_btn)

        self.pointer_btn = Button(
            text="Pointer", size_hint_x=0.12,
            background_color=(0.3, 0.3, 0.3, 1),
            font_size=11
        )
        self.pointer_btn.bind(on_press=lambda b: self._set_mode(self.MODE_POINTER))
        top_bar.add_widget(self.pointer_btn)

        self.game_btn = Button(
            text="Game", size_hint_x=0.09,
            background_color=(0.3, 0.3, 0.3, 1),
            font_size=11
        )
        self.game_btn.bind(on_press=lambda b: self._set_mode(self.MODE_GAMEPAD))
        top_bar.add_widget(self.game_btn)

        self.bt_btn = Button(
            text="BT", size_hint_x=0.08,
            background_color=(0.3, 0.3, 0.3, 1),
            font_size=11
        )
        self.bt_btn.bind(on_press=lambda b: self._set_mode(self.MODE_BT_PASS))
        top_bar.add_widget(self.bt_btn)

        self.status_label = Label(text="Connecting...",
                                   font_size=11, halign="center",
                                   size_hint_x=0.25)
        self.status_label.bind(size=self.status_label.setter("text_size"))
        top_bar.add_widget(self.status_label)

        clipboard_btn = Button(text="Clip", size_hint_x=0.1,
                                background_color=(0.3, 0.7, 0.3, 1),
                                font_size=11)
        clipboard_btn.bind(on_press=self._sync_clipboard)
        top_bar.add_widget(clipboard_btn)

        files_btn = Button(text="Files", size_hint_x=0.1,
                            background_color=(0.2, 0.5, 0.9, 1),
                            font_size=11)
        files_btn.bind(on_press=self._open_files)
        top_bar.add_widget(files_btn)

        keyboard_btn = Button(text="KB", size_hint_x=0.1,
                               background_color=(0.3, 0.3, 0.8, 1),
                               font_size=13, bold=True)
        keyboard_btn.bind(on_press=self._show_keyboard)
        top_bar.add_widget(keyboard_btn)

        self.voice_btn = Button(text="🎤", size_hint_x=0.1,
                                background_color=(0.4, 0.2, 0.6, 1),
                                font_size=16)
        self.voice_btn.bind(on_press=self._voice_press)
        top_bar.add_widget(self.voice_btn)

        self.audio_mic_btn = Button(text="Mic➡", size_hint_x=0.08,
                                    background_color=(0.3, 0.3, 0.3, 1),
                                    font_size=8)
        self.audio_mic_btn.bind(on_press=self._toggle_phone_mic)
        top_bar.add_widget(self.audio_mic_btn)

        self.audio_speaker_btn = Button(text="⬅Spk", size_hint_x=0.08,
                                        background_color=(0.3, 0.3, 0.3, 1),
                                        font_size=8)
        self.audio_speaker_btn.bind(on_press=self._toggle_pc_mic)
        top_bar.add_widget(self.audio_speaker_btn)

        self.cam_btn = Button(text="📷", size_hint_x=0.08,
                              background_color=(0.3, 0.3, 0.3, 1),
                              font_size=12)
        self.cam_btn.bind(on_press=self._toggle_phone_camera)
        top_bar.add_widget(self.cam_btn)

        self.pc_cam_btn = Button(text="PC📷", size_hint_x=0.08,
                                 background_color=(0.3, 0.3, 0.3, 1),
                                 font_size=8)
        self.pc_cam_btn.bind(on_press=self._toggle_pc_camera)
        top_bar.add_widget(self.pc_cam_btn)

        bridge_btn = Button(text="Bridge", size_hint_x=0.1,
                            background_color=(0.2, 0.6, 0.6, 1),
                            font_size=9)
        bridge_btn.bind(on_press=self._open_bridge)
        top_bar.add_widget(bridge_btn)

        radio_btn = Button(text="Radio", size_hint_x=0.1,
                           background_color=(0.6, 0.5, 0.2, 1),
                           font_size=9)
        radio_btn.bind(on_press=self._open_radio)
        top_bar.add_widget(radio_btn)

        boost_btn = Button(text="Boost", size_hint_x=0.1,
                           background_color=(0.2, 0.5, 0.7, 1),
                           font_size=9)
        boost_btn.bind(on_press=self._open_booster)
        top_bar.add_widget(boost_btn)

        settings_btn = Button(text="Bind", size_hint_x=0.1,
                              background_color=(0.5, 0.3, 0.7, 1),
                              font_size=11, bold=True)
        settings_btn.bind(on_press=self._open_settings)
        top_bar.add_widget(settings_btn)

        self.smart_btn = Button(text="Smart", size_hint_x=0.1,
                                background_color=(0.3, 0.3, 0.3, 1),
                                font_size=9)
        self.smart_btn.bind(on_press=self._toggle_smart_point)
        top_bar.add_widget(self.smart_btn)

        self.host_btn = Button(text="Host", size_hint_x=0.1,
                               background_color=(0.3, 0.3, 0.3, 1),
                               font_size=11)
        self.host_btn.bind(on_press=self._toggle_host_mode)
        top_bar.add_widget(self.host_btn)

        disconnect_btn = Button(text="X", size_hint_x=0.08,
                                 background_color=(0.7, 0.2, 0.2, 1),
                                 font_size=15, bold=True)
        disconnect_btn.bind(on_press=self._disconnect)
        top_bar.add_widget(disconnect_btn)

        self.layout.add_widget(top_bar)

        self._host_mode = False
        self._host_capture_event = None
        self.voice = VoiceController(app=None, client=None)
        self.device_bridge = DeviceBridge()
        self.smart_point = SmartPointerOverlay()
        self.smart_point.opacity = 0
        self.smart_point.client = None
        self.layout.add_widget(self.smart_point)

        self.mode_hint = Label(
            text="[b]TOUCH MODE[/b]  |  Tap = click  |  Swipe = scroll/switch",
            markup=True, font_size=11, halign="center",
            size_hint=(0.9, 0.04),
            pos_hint={"center_x": 0.5, "y": 0.005},
            color=(1, 1, 1, 0.4)
        )
        self.mode_hint.bind(size=self.mode_hint.setter("text_size"))
        self.layout.add_widget(self.mode_hint)

        self.add_widget(self.layout)

    def _update_bg(self, *args):
        self._bg_rect.pos = self.layout.pos
        self._bg_rect.size = self.layout.size

    def _set_mode(self, mode):
        self.mode = mode
        self.touch_btn.background_color = (0.3, 0.3, 0.3, 1)
        self.pointer_btn.background_color = (0.3, 0.3, 0.3, 1)
        self.game_btn.background_color = (0.3, 0.3, 0.3, 1)

        self.screen_image.opacity = 1
        self._showing_screen = True
        self.trackpad_label.opacity = 0
        self.gamepad.opacity = 0
        self.gamepad.disabled = True
        self.gamepad.stop_input_loop()

        self.touch_btn.background_color = (0.3, 0.3, 0.3, 1)
        self.pointer_btn.background_color = (0.3, 0.3, 0.3, 1)
        self.game_btn.background_color = (0.3, 0.3, 0.3, 1)
        self.bt_btn.background_color = (0.3, 0.3, 0.3, 1)

        if mode == self.MODE_TOUCH:
            self.touch_btn.background_color = (0.2, 0.7, 0.3, 1)
            self.mode_hint.text = "[b]TOUCH MODE[/b]  |  Tap = click  |  Swipe = scroll/switch"
        elif mode == self.MODE_POINTER:
            self.pointer_btn.background_color = (0.2, 0.5, 0.9, 1)
            self.screen_image.opacity = 0
            self._showing_screen = False
            self.trackpad_label.opacity = 1
            self.mode_hint.text = "[b]POINTER MODE[/b]  |  Finger = trackpad  |  Tap = click  |  Double-tap = right click"
        elif mode == self.MODE_GAMEPAD:
            self.game_btn.background_color = (0.8, 0.3, 0.1, 1)
            self.gamepad.opacity = 1
            self.gamepad.disabled = False
            self.gamepad.set_client(self.client)
            self.gamepad.apply_bindings(load_bindings())
            self.gamepad.start_input_loop()
            self.mode_hint.text = "[b]GAMEPAD MODE[/b]  |  L-stick = move  |  R-stick = aim  |  Buttons = actions"
        elif mode == self.MODE_BT_PASS:
            self.bt_btn.background_color = (0.2, 0.4, 0.8, 1)
            self.screen_image.opacity = 0
            self._showing_screen = False
            self.mode_hint.text = "[b]BT PASSTHROUGH[/b]  |  All input forwards to PC"

    def on_enter(self):
        if self.client and self.client.connected:
            self.status_label.text = "Connected"
            Window.bind(on_keyboard=self._on_keyboard)
            self.client.set_clipboard_callback(self._on_clipboard_push)
            self.client.set_voice_options_callback(self._on_voice_options)
            self.device_bridge.set_client(self.client)
            self.phone_radio.set_client(self.client)
            self.android_booster.set_client(self.client)

    def on_leave(self):
        Window.unbind(on_keyboard=self._on_keyboard)
        self.gamepad.cleanup()
        if self._host_mode:
            self._stop_host_mode()
        if getattr(self, '_phone_mic_on', False):
            self._phone_mic_on = False
            self.client and self.client.send({"type": "audio_speaker_stop"})
        if getattr(self, '_pc_mic_on', False):
            self._pc_mic_on = False
            self.client and self.client.send({"type": "audio_mic_stop"})
        if getattr(self, '_phone_cam_on', False):
            self._phone_cam_on = False
            if hasattr(self, '_phone_cam'):
                self._phone_cam.stop()
            self.client and self.client.send({"type": "phone_camera_stop"})
        if getattr(self, '_pc_cam_on', False):
            self._pc_cam_on = False
            self.client and self.client.send({"type": "pc_camera_stop"})

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

        if self.mode == self.MODE_GAMEPAD:
            if self.gamepad.on_touch_down(touch):
                return True
            return super().on_touch_down(touch)

        if self.mode == self.MODE_BT_PASS:
            if self._is_in_control_area(touch):
                self._t1_start = (touch.x, touch.y)
                self._t1_pos = (touch.x, touch.y)
                self._t1_time = time.time()
                self._t1_grabbed = True
                self._is_dragging = False
                touch.grab(self)
                return True
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
        if self.mode == self.MODE_GAMEPAD:
            if self.gamepad.on_touch_move(touch):
                return True
            return super().on_touch_move(touch)

        if self.mode == self.MODE_BT_PASS:
            if touch.grab_current is not self:
                return super().on_touch_move(touch)
            if self._t1_pos:
                dx = touch.x - self._t1_pos[0]
                dy = touch.y - self._t1_pos[1]
                if abs(dx) > 1 or abs(dy) > 1:
                    sens = 3.0
                    sdx = int(dx * sens)
                    sdy = int(-dy * sens)
                    if abs(sdx) >= 1 or abs(sdy) >= 1:
                        self.client.send_bt_mouse(dx=sdx, dy=sdy)
                        self._t1_pos = (touch.x, touch.y)
            return True

        if touch.grab_current is not self:
            return super().on_touch_move(touch)

        if self._t2_grabbed:
            return True

        if self._t1_pos:
            dx = touch.x - self._t1_pos[0]
            dy = touch.y - self._t1_pos[1]

            if abs(dx) > MOVE_THRESHOLD or abs(dy) > MOVE_THRESHOLD:
                self._is_dragging = True

                sens = TOUCH_SENSITIVITY if self.mode == self.MODE_TOUCH else POINTER_SENSITIVITY

                self._smooth_dx = self._smooth_dx * (1 - SMOOTHING) + dx * SMOOTHING
                self._smooth_dy = self._smooth_dy * (1 - SMOOTHING) + dy * SMOOTHING
                screen_dx = int(self._smooth_dx * sens)
                screen_dy = int(-self._smooth_dy * sens)

                if abs(screen_dx) >= 1 or abs(screen_dy) >= 1:
                    self.client.send_mouse_move_relative(screen_dx, screen_dy)

            self._t1_pos = (touch.x, touch.y)
        return True

    def on_touch_up(self, touch):
        if self.mode == self.MODE_GAMEPAD:
            if self.gamepad.on_touch_up(touch):
                return True
            return super().on_touch_up(touch)

        if self.mode == self.MODE_BT_PASS:
            if touch.grab_current is not self:
                return super().on_touch_up(touch)
            touch.ungrab(self)
            if self._t1_start:
                dx = touch.x - self._t1_start[0]
                dy = touch.y - self._t1_start[1]
                dist = (dx**2 + dy**2) ** 0.5
                if dist < 15:
                    self.client.send_bt_mouse(click=True, button="left")
            self._reset_touches()
            return True

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

    def _sync_clipboard(self, *args):
        if not self.client or not self.client.connected:
            return
        try:
            from kivy.core.clipboard import Clipboard
            text = Clipboard.paste()
            if text:
                self.client.send_clipboard_set(text)
                self.mode_hint.text = "[b]CLIPBOARD SYNCED[/b]  |  Sent to PC"
                Clock.schedule_once(lambda dt: self._restore_hint(), 2)
            else:
                self.client.send_clipboard_get()
                self.mode_hint.text = "[b]CLIPBOARD REQUESTED[/b]  |  Fetching from PC..."
                Clock.schedule_once(lambda dt: self._restore_hint(), 2)
        except Exception:
            pass

    def _on_clipboard_push(self, text):
        if text:
            try:
                from kivy.core.clipboard import Clipboard
                Clipboard.copy(text)
                self.mode_hint.text = "[b]CLIPBOARD RECEIVED[/b]  |  Pasted from PC"
                Clock.schedule_once(lambda dt: self._restore_hint(), 3)
            except Exception:
                pass

    def _restore_hint(self):
        if self.mode == self.MODE_TOUCH:
            self.mode_hint.text = "[b]TOUCH MODE[/b]  |  Tap = click  |  Swipe = scroll/switch"
        elif self.mode == self.MODE_POINTER:
            self.mode_hint.text = "[b]POINTER MODE[/b]  |  Finger = trackpad  |  Tap = click  |  Double-tap = right click"
        elif self.mode == self.MODE_GAMEPAD:
            self.mode_hint.text = "[b]GAMEPAD MODE[/b]  |  L-stick = move  |  R-stick = aim  |  Buttons = actions"

    def _open_files(self, *args):
        if self.manager and hasattr(self.manager, "get_screen"):
            fs = self.manager.get_screen("file_browser")
            fs.client = self.client
            self.manager.current = "file_browser"

    def _toggle_host_mode(self, *args):
        if self._host_mode:
            self._stop_host_mode()
        else:
            self._start_host_mode()

    def _start_host_mode(self):
        if not self.client or not self.client.connected:
            return
        self._host_mode = True
        self.host_btn.background_color = (0.8, 0.3, 0.1, 1)
        self.host_btn.text = "Host ON"

        self.client.set_phone_tap_callback(self._on_phone_tap)
        self.client.set_phone_back_callback(self._on_phone_back)
        self.client.set_phone_volume_callback(self._on_phone_volume)
        self.client.send_enter_host_mode()
        self._host_capture_event = Clock.schedule_interval(self._capture_phone_frame, 0.15)

        self.mode_hint.text = "[b]HOST MODE[/b]  |  PC can see and touch this phone"

    def _stop_host_mode(self):
        self._host_mode = False
        self.host_btn.background_color = (0.3, 0.3, 0.3, 1)
        self.host_btn.text = "Host"

        if self._host_capture_event:
            self._host_capture_event.cancel()
            self._host_capture_event = None

        self.client.set_phone_tap_callback(None)
        self.client.set_phone_back_callback(None)
        self.client.set_phone_volume_callback(None)
        self.client.send_exit_host_mode()
        self._restore_hint()

    def _capture_phone_frame(self, dt):
        if not self._host_mode or not self.client or not self.client.connected:
            return
        try:
            import subprocess
            result = subprocess.run(
                ["screencap", "-p"],
                capture_output=True, timeout=2
            )
            if result.returncode == 0 and len(result.stdout) > 100:
                self.client.send_phone_frame(result.stdout)
        except Exception:
            pass

    def _on_phone_tap(self, x, y):
        try:
            import subprocess
            subprocess.run(
                ["input", "tap", str(x), str(y)],
                capture_output=True, timeout=2
            )
        except Exception:
            pass

    def _on_phone_back(self):
        try:
            import subprocess
            subprocess.run(
                ["input", "keyevent", "KEYCODE_BACK"],
                capture_output=True, timeout=2
            )
        except Exception:
            pass

    def _on_phone_volume(self, direction):
        try:
            import subprocess
            key = "KEYCODE_VOLUME_UP" if direction == "up" else "KEYCODE_VOLUME_DOWN"
            subprocess.run(
                ["input", "keyevent", key],
                capture_output=True, timeout=2
            )
        except Exception:
            pass

    def _voice_press(self, *args):
        if not self.client or not self.client.connected:
            return
        self.voice.client = self.client
        self.voice.app = self.app_ref
        self.voice_btn.background_color = (0.8, 0.5, 0.1, 1)
        Clock.schedule_once(lambda dt: self.voice.start_listening(
            callback=self._on_voice_result
        ), 0.1)

    def _on_voice_result(self, text):
        self.voice_btn.background_color = (0.4, 0.2, 0.6, 1)
        if text and self.client and self.client.connected:
            if text.startswith("err:"):
                self.mode_hint.text = f"[b]Voice Error[/b]  |  {text[4:]}"
                Clock.schedule_once(lambda dt: self._restore_hint(), 3)
                return
            self.mode_hint.text = f"[b]{text}[/b]  |  Sending to PC..."
            self.client.send_voice_result(text)
        elif not text:
            self.mode_hint.text = "[b]Voice cancelled[/b]"

    def _toggle_phone_camera(self, *args):
        if not self.client or not self.client.connected:
            return
        if getattr(self, '_phone_cam_on', False):
            self._phone_cam_on = False
            self.cam_btn.background_color = (0.3, 0.3, 0.3, 1)
            if hasattr(self, '_phone_cam'):
                self._phone_cam.stop()
            self.client.send({"type": "phone_camera_stop"})
            self.mode_hint.text = "[b]PHONE CAM OFF[/b]"
        else:
            self._phone_cam_on = True
            self.cam_btn.background_color = (0.2, 0.7, 0.2, 1)
            self.client.send({"type": "phone_camera_start"})
            from phone_camera import PhoneCameraStreamer
            self._phone_cam = PhoneCameraStreamer(client=self.client)
            self._phone_cam.start()
            self.mode_hint.text = "[b]PHONE CAM ON[/b]  |  Streaming to PC"
        Clock.schedule_once(lambda dt: self._restore_hint(), 3)

    def _toggle_pc_camera(self, *args):
        if not self.client or not self.client.connected:
            return
        if getattr(self, '_pc_cam_on', False):
            self._pc_cam_on = False
            self.pc_cam_btn.background_color = (0.3, 0.3, 0.3, 1)
            self.client.send({"type": "pc_camera_stop"})
            self.mode_hint.text = "[b]PC CAM OFF[/b]"
        else:
            self._pc_cam_on = True
            self.pc_cam_btn.background_color = (0.7, 0.2, 0.2, 1)
            self.client.set_pc_camera_callback(self._on_pc_camera)
            self.client.send({"type": "pc_camera_start"})
            self.mode_hint.text = "[b]PC CAM ON[/b]  |  Viewing on phone"
        Clock.schedule_once(lambda dt: self._restore_hint(), 3)

    def _on_pc_camera(self, jpg_bytes):
        if not getattr(self, '_pc_cam_on', False):
            return
        try:
            from io import BytesIO
            from kivy.core.image import Image as CoreImage
            buf = BytesIO(jpg_bytes)
            ci = CoreImage(buf, ext="jpg")
            self.screen_image.texture = ci.texture
            self.screen_image.opacity = 1
        except Exception:
            pass

    def _toggle_phone_mic(self, *args):
        if not self.client or not self.client.connected:
            return
        if hasattr(self, '_phone_mic_on') and self._phone_mic_on:
            self._phone_mic_on = False
            self.audio_mic_btn.background_color = (0.3, 0.3, 0.3, 1)
            self.client.send({"type": "audio_speaker_stop"})
            self.mode_hint.text = "[b]MIC OFF[/b]  |  Phone mic → PC stopped"
        else:
            self._phone_mic_on = True
            self.audio_mic_btn.background_color = (0.2, 0.7, 0.2, 1)
            self.client.send({"type": "audio_speaker_start"})
            self.mode_hint.text = "[b]MIC ON[/b]  |  Speaking through PC speakers"
        Clock.schedule_once(lambda dt: self._restore_hint(), 3)

    def _toggle_pc_mic(self, *args):
        if not self.client or not self.client.connected:
            return
        if hasattr(self, '_pc_mic_on') and self._pc_mic_on:
            self._pc_mic_on = False
            self.audio_speaker_btn.background_color = (0.3, 0.3, 0.3, 1)
            self.client.send({"type": "audio_mic_stop"})
            self.mode_hint.text = "[b]PC MIC OFF[/b]  |  PC mic → Phone stopped"
        else:
            self._pc_mic_on = True
            self.audio_speaker_btn.background_color = (0.7, 0.2, 0.2, 1)
            self.client.send({"type": "audio_mic_start"})
            self.client.set_audio_callback(self._on_pc_audio)
            self.mode_hint.text = "[b]PC MIC ON[/b]  |  Listening to PC mic on phone"
        Clock.schedule_once(lambda dt: self._restore_hint(), 3)

    def _on_pc_audio(self, pcm_bytes):
        try:
            if not hasattr(self, '_phone_audio'):
                from phone_audio import PhoneAudio
                self._phone_audio = PhoneAudio()
            self._phone_audio.write_audio(pcm_bytes)
        except Exception:
            pass

    def _open_bridge(self, *args):
        if self.manager and hasattr(self.manager, "get_screen"):
            bs = self.manager.get_screen("bridge")
            bs.client = self.client
            bs.bridge = self.device_bridge
            self.manager.current = "bridge"

    def _on_voice_options(self, options, prompt):
        self.voice.app = self.app_ref
        self.voice.client = self.client
        self.voice.show_options(
            options, prompt,
            on_select=lambda opt: self._on_option_picked(opt)
        )

    def _on_option_picked(self, opt):
        self.mode_hint.text = f"[b]Selected:[/b] {opt.get('label', opt['id'])}"
        Clock.schedule_once(lambda dt: self._restore_hint(), 3)

    def _open_settings(self, *args):
        if self.manager and hasattr(self.manager, "get_screen"):
            self.manager.current = "settings"

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

        if self.mode == self.MODE_BT_PASS:
            if codepoint and codepoint.isprintable():
                self.client.send_type_text(codepoint)
                return True
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
        if self._host_mode:
            self._stop_host_mode()
        if getattr(self, '_phone_cam_on', False):
            self._phone_cam_on = False
            if hasattr(self, '_phone_cam'):
                self._phone_cam.stop()
        if getattr(self, '_pc_cam_on', False):
            self._pc_cam_on = False
        self.gamepad.cleanup()
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

        self.file_browser_screen = FileBrowserScreen(name="file_browser")
        self.settings_screen = KeyBindingsScreen(name="settings")
        self.bridge_screen = BridgeScreen(name="bridge")
        self.radio_screen = RadioScreen(name="radio")
        self.phone_radio = PhoneRadio()
        self.booster_screen = BoosterScreen(name="booster")
        self.android_booster = AndroidNetworkBooster()

        self.sm.add_widget(self.discovery_screen)
        self.sm.add_widget(self.control_screen)
        self.sm.add_widget(self.file_browser_screen)
        self.sm.add_widget(self.settings_screen)
        self.sm.add_widget(self.bridge_screen)
        self.sm.add_widget(self.radio_screen)
        self.sm.add_widget(self.booster_screen)

        self.client = ControlClient()
        self.client.set_frame_callback(self._on_frame)
        self.client.set_status_callback(self._on_status)
        self.client.set_radio_status_callback(self._on_radio_status)
        self.client.set_radio_audio_callback(self._on_radio_audio)
        self.client.set_radio_phone_fm_callback(self._on_radio_phone_fm)
        self.client.set_smart_point_callback(self._on_smart_point)
        self.client.set_booster_callback(self._on_booster)

        self.radio_screen.client = self.client
        self.radio_screen.phone_radio = self.phone_radio

        self.booster_screen.client = self.client
        self.booster_screen.booster = self.android_booster

        self._smart_point_on = True
        self._smart_scan_event = None

        return self.sm

    def connect_to(self, device):
        self.control_screen.client = self.client
        self.client.set_frame_callback(self._on_frame)
        self.client.set_status_callback(self._on_status)
        self.sm.current = "control"
        self._pending_device = device
        self.client.connect(device["ip"])

    def show_discovery(self):
        self.sm.current = "discovery"

    def _on_frame(self, img_bytes):
        self.control_screen.update_frame(img_bytes)

    def _on_status(self, status):
        self.control_screen.update_status(status)
        if status == "connected":
            if hasattr(self, "_pending_device") and self._pending_device:
                save_device(self._pending_device)
                self._pending_device = None
            self._smart_point_on = True
            self.smart_btn.background_color = (0.6, 0.2, 0.6, 1)
            Clock.schedule_once(lambda dt: self._do_smart_activate(), 1)
        if status in ("denied", "disconnected"):
            self._smart_point_on = False
            if self._smart_scan_event:
                self._smart_scan_event.cancel()
                self._smart_scan_event = None
            self.smart_btn.background_color = (0.3, 0.3, 0.3, 1)
            Clock.schedule_once(lambda dt: self.show_discovery(), 2)

    def _open_radio(self, *args):
        if self.manager and hasattr(self.manager, "get_screen"):
            rs = self.manager.get_screen("radio")
            rs.client = self.client
            rs.phone_radio = self.phone_radio
            self.manager.current = "radio"

    def _open_booster(self, *args):
        if self.manager and hasattr(self.manager, "get_screen"):
            bs = self.manager.get_screen("booster")
            bs.client = self.client
            bs.booster = self.android_booster
            self.manager.current = "booster"

    def _on_booster(self, data):
        if self.manager and hasattr(self.manager, "get_screen"):
            bs = self.manager.get_screen("booster")
            bs.on_booster_result(data)

    def _on_radio_status(self, data):
        if self.manager and hasattr(self.manager, "get_screen"):
            rs = self.manager.get_screen("radio")
            msg_type = data.get("type", "")
            if msg_type == "radio_station_list":
                rs.status_label.text = "Stations loaded"
            elif msg_type == "radio_scan_results":
                stations = data.get("stations", [])
                rs.status_label.text = f"{len(stations)} frequencies scanned"
            else:
                rs.status_label.text = data.get("info", data.get("station", str(data)))

    def _on_radio_audio(self, pcm_bytes):
        if self.manager and hasattr(self.manager, "get_screen"):
            rs = self.manager.get_screen("radio")
            rs.on_pc_radio_audio(pcm_bytes)

    def _on_radio_phone_fm(self, freq):
        if self.manager and hasattr(self.manager, "get_screen"):
            rs = self.manager.get_screen("radio")
            rs.status_label.text = f"Phone FM tuning: {freq} MHz"

    def _do_smart_activate(self):
        if not self.client or not self.client.connected:
            return
        if not self._smart_point_on:
            return
        self.smart_point.client = self.client
        self.client.send({"type": "smart_point_activate"})

    def _do_smart_scan_poll(self, dt=None):
        if not self._smart_point_on or not self.client or not self.client.connected:
            return
        self.client.send({"type": "smart_point_scan"})
        self._smart_scan_event = Clock.schedule_once(self._do_smart_scan_poll, 3)

    def _toggle_smart_point(self, *args):
        if not self.client or not self.client.connected:
            return
        self._smart_point_on = not self._smart_point_on
        if self._smart_point_on:
            self.smart_btn.background_color = (0.6, 0.2, 0.6, 1)
            self._do_smart_activate()
        else:
            if self._smart_scan_event:
                self._smart_scan_event.cancel()
                self._smart_scan_event = None
            self.smart_point.dismiss()
            self.smart_btn.background_color = (0.3, 0.3, 0.3, 1)
            self.client.send({"type": "smart_point_dismiss"})

    def _on_smart_point(self, predictions):
        if predictions and self._smart_point_on:
            self.smart_point.show(predictions)
            if self._smart_scan_event:
                self._smart_scan_event.cancel()
            self._smart_scan_event = Clock.schedule_once(self._do_smart_scan_poll, 3)
        elif not self._smart_point_on:
            self.smart_point.dismiss()

    def on_stop(self):
        self.client.disconnect()


if __name__ == "__main__":
    LazyBoyApp().run()
