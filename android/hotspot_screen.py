from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.clock import Clock
from kivy.metrics import dp


class HotspotScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.client = None
        self._status_event = None

        layout = BoxLayout(orientation="vertical")

        header = BoxLayout(size_hint_y=0.07, padding=[5, 3], spacing=5)
        back_btn = Button(text="Back", size_hint_x=0.15,
                          background_color=(0.5, 0.5, 0.5, 1))
        back_btn.bind(on_press=self._go_back)
        header.add_widget(back_btn)
        title = Label(text="LazyBoy FreeNet", font_size=17, bold=True,
                      size_hint_x=0.7)
        header.add_widget(title)
        layout.add_widget(header)

        scroll = ScrollView(size_hint_y=0.86)
        content = BoxLayout(orientation="vertical", size_hint_y=None,
                            spacing=dp(8), padding=[10, 8])
        content.bind(minimum_height=content.setter("height"))

        content.add_widget(Label(
            text="[b]Create a free hotspot using both devices[/b]\n"
                 "Phone cellular + PC internet combined for max speed",
            markup=True, font_size=12, size_hint_y=None, height=dp(40),
            color=(0.5, 0.8, 0.5, 1), halign="center"
        ))

        ssid_box = BoxLayout(size_hint_y=None, height=dp(40), spacing=5)
        ssid_box.add_widget(Label(text="SSID:", font_size=12,
                                   size_hint_x=0.15, halign="right"))
        self.ssid_input = TextInput(
            text="LazyBoy-FreeNet", font_size=14,
            size_hint_x=0.85, multiline=False
        )
        ssid_box.add_widget(self.ssid_input)
        content.add_widget(ssid_box)

        pw_box = BoxLayout(size_hint_y=None, height=dp(40), spacing=5)
        pw_box.add_widget(Label(text="Pass:", font_size=12,
                                 size_hint_x=0.15, halign="right"))
        self.pw_input = TextInput(
            text="LazyBoy123", font_size=14,
            size_hint_x=0.85, multiline=False
        )
        pw_box.add_widget(self.pw_input)
        content.add_widget(pw_box)

        btn_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=8)
        self.start_btn = Button(
            text="Create Hotspot", font_size=14,
            background_color=(0.2, 0.6, 0.2, 1), size_hint_x=0.5
        )
        self.start_btn.bind(on_press=self._create_hotspot)
        btn_row.add_widget(self.start_btn)
        self.stop_btn = Button(
            text="Stop", font_size=14,
            background_color=(0.6, 0.2, 0.2, 1), size_hint_x=0.5
        )
        self.stop_btn.bind(on_press=self._stop_hotspot)
        btn_row.add_widget(self.stop_btn)
        content.add_widget(btn_row)

        content.add_widget(Label(
            text="[b]Status[/b]", markup=True, font_size=13,
            size_hint_y=None, height=dp(22), color=(0.2, 0.8, 0.4, 1)
        ))

        self.status_label = Label(
            text="Inactive", font_size=12, size_hint_y=None, height=dp(22),
            color=(0.6, 0.6, 0.6, 1)
        )
        content.add_widget(self.status_label)

        self.clients_label = Label(
            text="Connected devices: 0", font_size=12,
            size_hint_y=None, height=dp(20), color=(0.5, 0.5, 0.5, 1)
        )
        content.add_widget(self.clients_label)

        content.add_widget(Label(
            text="[b]Bandwidth[/b]", markup=True, font_size=13,
            size_hint_y=None, height=dp(22), color=(0.2, 0.8, 0.4, 1)
        ))

        self.bw_label = Label(
            text="", font_size=11, size_hint_y=None, height=dp(40),
            color=(0.5, 0.5, 0.5, 1)
        )
        content.add_widget(self.bw_label)

        content.add_widget(Label(
            text="[b]Network Sources[/b]", markup=True, font_size=13,
            size_hint_y=None, height=dp(22), color=(0.2, 0.8, 0.4, 1)
        ))

        info_box = BoxLayout(orientation="vertical", size_hint_y=None,
                             height=dp(80), spacing=4)
        self.info_labels = []
        for text in ["Phone: Share cellular via USB tether",
                     "PC: Share WiFi/Ethernet",
                     "Both combined for max throughput"]:
            lbl = Label(
                text=text, font_size=11,
                size_hint_y=None, height=dp(20),
                color=(0.5, 0.5, 0.5, 1), halign="left"
            )
            info_box.add_widget(lbl)
            self.info_labels.append(lbl)
        content.add_widget(info_box)

        usb_btn = Button(
            text="Share Phone Internet via USB",
            size_hint_y=None, height=dp(40),
            background_color=(0.3, 0.5, 0.3, 1), font_size=12
        )
        usb_btn.bind(on_press=self._share_usb)
        content.add_widget(usb_btn)

        scroll.add_widget(content)
        layout.add_widget(scroll)
        self.add_widget(layout)

    def _create_hotspot(self, *args):
        ssid = self.ssid_input.text.strip() or "LazyBoy-FreeNet"
        pw = self.pw_input.text.strip() or "LazyBoy123"
        if self.client and self.client.connected:
            self.client.send({
                "type": "hotspot_create",
                "ssid": ssid,
                "password": pw,
            })
            self.status_label.text = "Creating hotspot..."
            self.start_btn.text = "Creating..."
            self._start_polling()

    def _stop_hotspot(self, *args):
        if self.client and self.client.connected:
            self.client.send({"type": "hotspot_stop"})
        self.status_label.text = "Stopped"
        self.start_btn.text = "Create Hotspot"
        self._stop_polling()

    def _share_usb(self, *args):
        if self.client and self.client.connected:
            self.client.send({
                "type": "bridge_usb_share",
                "direction": "phone_to_pc",
            })
            self.status_label.text = "Sharing phone internet via USB..."

    def _start_polling(self):
        self._stop_polling()
        self._status_event = Clock.schedule_interval(self._poll_status, 5)

    def _stop_polling(self):
        if self._status_event:
            self._status_event.cancel()
            self._status_event = None

    def _poll_status(self, dt):
        if self.client and self.client.connected:
            self.client.send({"type": "hotspot_status"})

    def on_hotspot_result(self, data):
        msg_type = data.get("type", "")
        if msg_type == "hotspot_created":
            info = data.get("info", {})
            if info.get("success"):
                self.status_label.text = f"Active on {info.get('method', 'WiFi')}"
                self.start_btn.text = "Active"
            else:
                self.status_label.text = f"Failed: {info.get('error', 'unknown')}"
                self.start_btn.text = "Create Hotspot"
        elif msg_type == "hotspot_stopped":
            self.status_label.text = "Stopped"
            self.start_btn.text = "Create Hotspot"
        elif msg_type == "hotspot_status_info":
            status = data.get("status", {})
            if status.get("running"):
                self.status_label.text = f"Running ({status.get('method','?')})"
                self.clients_label.text = f"Connected devices: {status.get('clients', 0)}"
                dual = status.get("dual_wan", False)
                self.info_labels[2].text = (
                    "Dual-WAN active: PC + Phone combined"
                    if dual else "Single connection active"
                )
                if status.get("client_list"):
                    client_str = ", ".join(status["client_list"][:3])
                    self.clients_label.text += f"\n{client_str}"
            else:
                self.status_label.text = "Not running"
        elif msg_type == "hotspot_bandwidth":
            bw = data.get("bandwidth", [])
            if bw:
                lines = [f"{b.get('name','?')}: ↓{self._fmt_bytes(b.get('rx',0))} ↑{self._fmt_bytes(b.get('tx',0))}" for b in bw[:3]]
                self.bw_label.text = "\n".join(lines)

    def _fmt_bytes(self, b):
        if b > 1_000_000_000:
            return f"{b/1_000_000_000:.1f}GB"
        if b > 1_000_000:
            return f"{b/1_000_000:.1f}MB"
        if b > 1_000:
            return f"{b/1_000:.1f}KB"
        return f"{b}B"

    def on_enter(self):
        self._start_polling()

    def on_leave(self):
        self._stop_polling()

    def _go_back(self, *args):
        self._stop_polling()
        if self.manager:
            self.manager.current = "control"
