from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.clock import Clock
from kivy.metrics import dp


class BridgeScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.client = None
        self.bridge = None
        self._location_active = False

        layout = BoxLayout(orientation="vertical")

        header = BoxLayout(size_hint_y=0.07, padding=[5, 3], spacing=5)
        back_btn = Button(text="Back", size_hint_x=0.15,
                          background_color=(0.5, 0.5, 0.5, 1))
        back_btn.bind(on_press=self._go_back)
        header.add_widget(back_btn)
        title = Label(text="Device Bridge", font_size=18, bold=True,
                      size_hint_x=0.7)
        header.add_widget(title)
        layout.add_widget(header)

        scroll = ScrollView(size_hint_y=0.86)
        content = BoxLayout(orientation="vertical", size_hint_y=None,
                            spacing=dp(8), padding=[10, 10])
        content.bind(minimum_height=content.setter("height"))

        content.add_widget(Label(
            text="[b]Location Bridge[/b]", markup=True, font_size=14,
            size_hint_y=None, height=dp(24), color=(0.2, 0.8, 0.4, 1)
        ))

        self.loc_btn = Button(
            text="Share GPS with PC",
            size_hint_y=None, height=dp(44),
            background_color=(0.2, 0.4, 0.7, 1), font_size=14
        )
        self.loc_btn.bind(on_press=self._toggle_location)
        content.add_widget(self.loc_btn)

        self.loc_label = Label(
            text="Location: not shared", font_size=11,
            size_hint_y=None, height=dp(20), color=(0.6, 0.6, 0.6, 1)
        )
        content.add_widget(self.loc_label)

        content.add_widget(Label(
            text="[b]USB Bridge[/b]", markup=True, font_size=14,
            size_hint_y=None, height=dp(24), color=(0.2, 0.8, 0.4, 1)
        ))

        self.usb_status = Label(
            text="USB: checking...", font_size=12,
            size_hint_y=None, height=dp(20), color=(0.6, 0.6, 0.6, 1)
        )
        content.add_widget(self.usb_status)

        usb_btn = Button(
            text="Enable USB Tethering (share internet)",
            size_hint_y=None, height=dp(44),
            background_color=(0.3, 0.5, 0.3, 1), font_size=13
        )
        usb_btn.bind(on_press=lambda b: self._run_bridge("usb_tether"))
        content.add_widget(usb_btn)

        headless_btn = Button(
            text="Headless Display Mode (USB)",
            size_hint_y=None, height=dp(44),
            background_color=(0.5, 0.3, 0.5, 1), font_size=13
        )
        headless_btn.bind(on_press=self._headless_mode)
        content.add_widget(headless_btn)

        content.add_widget(Label(
            text="[b]Network Bridge[/b]", markup=True, font_size=14,
            size_hint_y=None, height=dp(24), color=(0.2, 0.8, 0.4, 1)
        ))

        hotspot_btn = Button(
            text="Share Phone WiFi as Hotspot",
            size_hint_y=None, height=dp(44),
            background_color=(0.6, 0.5, 0.2, 1), font_size=13
        )
        hotspot_btn.bind(on_press=lambda b: self._run_bridge("phone_hotspot"))
        content.add_widget(hotspot_btn)

        pc_hotspot_btn = Button(
            text="Connect to PC Hotspot (LazyBoy_Hotspot)",
            size_hint_y=None, height=dp(44),
            background_color=(0.4, 0.4, 0.6, 1), font_size=12
        )
        pc_hotspot_btn.bind(on_press=lambda b: self._run_bridge("pc_hotspot"))
        content.add_widget(pc_hotspot_btn)

        content.add_widget(Label(
            text="[b]Sensor Bridge[/b]", markup=True, font_size=14,
            size_hint_y=None, height=dp(24), color=(0.2, 0.8, 0.4, 1)
        ))

        self.sensor_btn = Button(
            text="List Phone Sensors",
            size_hint_y=None, height=dp(44),
            background_color=(0.3, 0.3, 0.5, 1), font_size=13
        )
        self.sensor_btn.bind(on_press=self._list_sensors)
        content.add_widget(self.sensor_btn)

        self.sensor_label = Label(
            text="", font_size=10,
            size_hint_y=None, height=dp(60), color=(0.5, 0.5, 0.5, 1),
            halign="center"
        )
        content.add_widget(self.sensor_label)

        self.status_label = Label(
            text="Ready", font_size=11, size_hint_y=None, height=dp(20),
            color=(0.5, 0.5, 0.5, 1)
        )
        content.add_widget(self.status_label)

        scroll.add_widget(content)
        layout.add_widget(scroll)
        self.add_widget(layout)

    def on_enter(self):
        if self.bridge and self.client:
            self.bridge.set_client(self.client)
        self._check_usb()

    def _check_usb(self):
        if self.bridge:
            connected = self.bridge.check_usb_connection()
            self.usb_status.text = "USB: Connected" if connected else "USB: Not detected"

    def _toggle_location(self, *args):
        if not self.client or not self.client.connected:
            return
        if self._location_active:
            self._location_active = False
            self.bridge and self.bridge.stop_location_sharing()
            self.loc_btn.text = "Share GPS with PC"
            self.loc_btn.background_color = (0.2, 0.4, 0.7, 1)
            self.loc_label.text = "Location: not shared"
        else:
            self._location_active = True
            self.bridge and self.bridge.start_location_sharing()
            self.loc_btn.text = "Stop Sharing GPS"
            self.loc_btn.background_color = (0.7, 0.2, 0.2, 1)
            self.loc_label.text = "Location: sharing..."

    def _headless_mode(self, *args):
        self._show_info(
            "Headless Display Mode\n\n"
            "1. Connect phone to PC via USB\n"
            "2. Enable USB tethering on phone\n"
            "3. The PC server will detect the USB network\n"
            "4. Connect using the USB IP shown in console\n\n"
            "Alternatively:\n"
            "adb reverse tcp:8765 tcp:8765\n"
            "Then connect via the manual IP field on the main screen."
        )

    def _run_bridge(self, action):
        if not self.bridge or not self.client:
            return

        if action == "usb_tether":
            result = self.bridge.enable_usb_tethering()
            self.status_label.text = "USB tethering: " + ("OK" if result.get("success") else "Failed")
        elif action == "phone_hotspot":
            result = self.bridge.share_phone_wifi()
            self.status_label.text = "Hotspot: " + ("Started" if result.get("success") else "Failed")
        elif action == "pc_hotspot":
            self.client.send({"type": "bridge_pc_hotspot_start"})
            result = self.bridge.connect_to_pc_hotspot()
            self.status_label.text = "Connecting to PC hotspot..."
        Clock.schedule_once(lambda dt: self._check_usb(), 2)

    def _list_sensors(self, *args):
        if not self.bridge:
            return
        sensors = self.bridge.get_sensor_data()
        if sensors:
            names = [s["name"][:25] for s in sensors[:8]]
            self.sensor_label.text = "\n".join(names)
            self.status_label.text = f"{len(sensors)} sensors found"
        else:
            self.sensor_label.text = "No sensors available"
            self.status_label.text = "Sensor list failed"

    def _show_info(self, msg):
        from kivy.uix.popup import Popup
        content = BoxLayout(orientation="vertical", padding=10, spacing=10)
        content.add_widget(Label(text=msg, font_size=12, halign="center"))
        btn = Button(text="OK", size_hint_y=0.3)
        popup = Popup(title="Bridge Info", content=content, size_hint=(0.8, 0.5))
        btn.bind(on_press=popup.dismiss)
        content.add_widget(btn)
        popup.open()

    def _go_back(self, *args):
        if self.manager:
            self.manager.current = "control"

    def update_bridge_status(self, status_data):
        if "location" in status_data:
            loc = status_data["location"]
            self.loc_label.text = f"Location: {loc['lat']:.4f}, {loc['lon']:.4f}"
