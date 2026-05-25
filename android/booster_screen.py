from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.clock import Clock
from kivy.metrics import dp


class BoosterScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.client = None
        self.booster = None

        layout = BoxLayout(orientation="vertical")

        header = BoxLayout(size_hint_y=0.07, padding=[5, 3], spacing=5)
        back_btn = Button(text="Back", size_hint_x=0.15,
                          background_color=(0.5, 0.5, 0.5, 1))
        back_btn.bind(on_press=self._go_back)
        header.add_widget(back_btn)
        title = Label(text="Network Booster", font_size=18, bold=True,
                      size_hint_x=0.7)
        header.add_widget(title)
        layout.add_widget(header)

        self.status_label = Label(
            text="Ready", font_size=11,
            size_hint_y=0.04, color=(0.4, 0.8, 0.4, 1)
        )
        layout.add_widget(self.status_label)

        scroll = ScrollView(size_hint_y=0.82)
        content = BoxLayout(orientation="vertical", size_hint_y=None,
                            spacing=dp(6), padding=[8, 6])
        content.bind(minimum_height=content.setter("height"))

        content.add_widget(Label(
            text="[b]Speed Test[/b]", markup=True, font_size=13,
            size_hint_y=None, height=dp(22), color=(0.2, 0.8, 0.4, 1)
        ))

        speed_btn = Button(
            text="Run Speed Test", size_hint_y=None, height=dp(40),
            background_color=(0.2, 0.5, 0.2, 1), font_size=13
        )
        speed_btn.bind(on_press=self._run_speed_test)
        content.add_widget(speed_btn)

        self.speed_label = Label(
            text="", font_size=11, size_hint_y=None, height=dp(28),
            color=(0.6, 0.8, 0.6, 1)
        )
        content.add_widget(self.speed_label)

        content.add_widget(Label(
            text="[b]DNS Accelerator[/b]", markup=True, font_size=13,
            size_hint_y=None, height=dp(22), color=(0.2, 0.8, 0.4, 1)
        ))

        dns_row = BoxLayout(size_hint_y=None, height=dp(40), spacing=5)
        dns_btn = Button(
            text="DNS: Cloudflare", size_hint_x=0.5,
            background_color=(0.5, 0.3, 0.3, 1), font_size=12
        )
        dns_btn.bind(on_press=lambda b: self._run_boost("dns_cloudflare"))
        dns_row.add_widget(dns_btn)
        dns_btn2 = Button(
            text="DNS: Google", size_hint_x=0.5,
            background_color=(0.3, 0.3, 0.5, 1), font_size=12
        )
        dns_btn2.bind(on_press=lambda b: self._run_boost("dns_google"))
        dns_row.add_widget(dns_btn2)
        content.add_widget(dns_row)

        dns_off = Button(
            text="Clear DNS Override", size_hint_y=None, height=dp(32),
            background_color=(0.3, 0.3, 0.3, 1), font_size=11
        )
        dns_off.bind(on_press=lambda b: self._run_boost("dns_clear"))
        content.add_widget(dns_off)

        content.add_widget(Label(
            text="[b]TCP Optimization[/b]", markup=True, font_size=13,
            size_hint_y=None, height=dp(22), color=(0.2, 0.8, 0.4, 1)
        ))

        tcp_btn = Button(
            text="Optimize TCP (PC)", size_hint_y=None, height=dp(40),
            background_color=(0.3, 0.5, 0.3, 1), font_size=12
        )
        tcp_btn.bind(on_press=lambda b: self._run_boost("tcp_optimize"))
        content.add_widget(tcp_btn)

        content.add_widget(Label(
            text="[b]WiFi Booster[/b]", markup=True, font_size=13,
            size_hint_y=None, height=dp(22), color=(0.2, 0.8, 0.4, 1)
        ))

        wifi_row = BoxLayout(size_hint_y=None, height=dp(40), spacing=5)
        for band, label in [("2ghz", "2.4GHz"), ("5ghz", "5GHz"), ("auto", "Auto")]:
            btn = Button(
                text=label, size_hint_x=0.33,
                background_color=(0.4, 0.3, 0.5, 1), font_size=11
            )
            btn.bind(on_press=lambda b, v=band: self._run_boost(f"wifi_{v}"))
            wifi_row.add_widget(btn)
        content.add_widget(wifi_row)

        cell_btn = Button(
            text="Optimize Mobile Data", size_hint_y=None, height=dp(36),
            background_color=(0.5, 0.3, 0.3, 1), font_size=12
        )
        cell_btn.bind(on_press=lambda b: self._run_boost("cellular"))
        content.add_widget(cell_btn)

        dual_btn = Button(
            text="Enable Dual Connection (WiFi+Cell)",
            size_hint_y=None, height=dp(36),
            background_color=(0.3, 0.3, 0.6, 1), font_size=11
        )
        dual_btn.bind(on_press=lambda b: self._run_boost("dual"))
        content.add_widget(dual_btn)

        content.add_widget(Label(
            text="[b]Hotspot Optimizer[/b]", markup=True, font_size=13,
            size_hint_y=None, height=dp(22), color=(0.2, 0.8, 0.4, 1)
        ))

        hotspot_btn = Button(
            text="Optimize PC Hotspot", size_hint_y=None, height=dp(36),
            background_color=(0.6, 0.5, 0.2, 1), font_size=12
        )
        hotspot_btn.bind(on_press=lambda b: self._run_boost("hotspot"))
        content.add_widget(hotspot_btn)

        content.add_widget(Label(
            text="[b]Connection Info[/b]", markup=True, font_size=13,
            size_hint_y=None, height=dp(22), color=(0.2, 0.8, 0.4, 1)
        ))

        info_btn = Button(
            text="Show Connection Info", size_hint_y=None, height=dp(36),
            background_color=(0.3, 0.3, 0.4, 1), font_size=12
        )
        info_btn.bind(on_press=lambda b: self._run_boost("info"))
        content.add_widget(info_btn)

        self.info_label = Label(
            text="", font_size=10, size_hint_y=None, height=dp(80),
            color=(0.5, 0.5, 0.5, 1), halign="center"
        )
        content.add_widget(self.info_label)

        scroll.add_widget(content)
        layout.add_widget(scroll)
        self.add_widget(layout)

    def _run_boost(self, action):
        if not self.client or not self.client.connected:
            return

        if action in ("dns_cloudflare", "dns_google", "dns_clear",
                      "wifi_2ghz", "wifi_5ghz", "wifi_auto",
                      "cellular", "dual"):
            if action == "dns_cloudflare":
                r = self.booster.set_dns_cloudflare() if self.booster else {}
                self.status_label.text = "DNS: Cloudflare" if r.get("success") else "DNS failed"
            elif action == "dns_google":
                r = self.booster.set_dns_google() if self.booster else {}
                self.status_label.text = "DNS: Google" if r.get("success") else "DNS failed"
            elif action == "dns_clear":
                r = self.booster.clear_dns() if self.booster else {}
                self.status_label.text = "DNS: Cleared" if r.get("success") else "DNS failed"
            elif action == "wifi_2ghz":
                r = self.booster.set_wifi_band_2ghz() if self.booster else {}
                self.status_label.text = "WiFi: 2.4GHz"
            elif action == "wifi_5ghz":
                r = self.booster.set_wifi_band_5ghz() if self.booster else {}
                self.status_label.text = "WiFi: 5GHz"
            elif action == "wifi_auto":
                r = self.booster.optimize_wifi() if self.booster else {}
                self.status_label.text = "WiFi: Auto optimized"
            elif action == "cellular":
                r = self.booster.optimize_cellular() if self.booster else {}
                self.status_label.text = "Mobile data: boosted" if r else "Failed"
            elif action == "dual":
                r = self.booster.enable_dual_connection() if self.booster else {}
                self.status_label.text = "Dual: " + ("ON" if r.get("success") else "Failed")
        else:
            self._send_server(action)

    def _send_server(self, action):
        self.client.send({"type": "booster", "action": action})

    def _run_speed_test(self, *args):
        self.status_label.text = "Running speed test..."
        self._send_server("speed_test")

    def on_booster_result(self, data):
        action = data.get("action", "")
        result = data.get("result", {})
        if action == "speed_test":
            dl = result.get("download_mbps", 0)
            ul = result.get("upload_mbps", 0)
            ms = result.get("latency_ms", 0)
            err = result.get("error")
            if err:
                self.speed_label.text = f"Error: {err}"
            else:
                self.speed_label.text = f"↓{dl} Mbps  ↑{ul} Mbps  {ms}ms ping"
                self.status_label.text = "Speed test done"
        elif action == "dns_cache":
            st = result.get("success", False)
            self.status_label.text = f"DNS cache: {'started' if st else 'failed'}"
        elif action in ("tcp_optimize", "tcp_reset"):
            self.status_label.text = f"TCP: {action.replace('_', ' ')}"
        elif action == "wifi_optimize":
            self.status_label.text = "PC WiFi: optimized"
        elif action == "hotspot":
            self.status_label.text = "Hotspot: optimized"
        elif action == "info":
            info = result.get("info", {})
            interfaces = info.get("interfaces", [])
            if interfaces:
                lines = [f"{i['name']}: {i.get('speed', 'N/A')}" for i in interfaces]
                self.info_label.text = "\n".join(lines)
            else:
                self.info_label.text = "No connection info"
        elif action == "status_update":
            rssi = data.get("wifi_rssi")
            cell = data.get("cellular_dbm")
            parts = []
            if rssi is not None:
                parts.append(f"WiFi: {rssi}dBm")
            if cell is not None:
                parts.append(f"Cell: {cell}dBm")
            if parts:
                self.status_label.text = "  |  ".join(parts)

    def on_enter(self):
        if self.booster:
            self.booster.set_client(self.client)
            self.booster.start_monitor()

    def on_leave(self):
        if self.booster:
            self.booster.stop_monitor()

    def _go_back(self, *args):
        if self.manager:
            self.manager.current = "control"
