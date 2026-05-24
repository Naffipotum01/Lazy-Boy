from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.togglebutton import ToggleButton
from kivy.clock import Clock
from kivy.metrics import dp


class RadioScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.client = None
        self.phone_radio = None
        self._playing = False
        self._direction = "phone_to_pc"
        self._current_station = None

        layout = BoxLayout(orientation="vertical")

        header = BoxLayout(size_hint_y=0.07, padding=[5, 3], spacing=5)
        back_btn = Button(text="Back", size_hint_x=0.15,
                          background_color=(0.5, 0.5, 0.5, 1))
        back_btn.bind(on_press=self._go_back)
        header.add_widget(back_btn)
        title = Label(text="Radio Tuner", font_size=18, bold=True,
                      size_hint_x=0.7)
        header.add_widget(title)
        layout.add_widget(header)

        self.status_label = Label(
            text="Ready", font_size=12,
            size_hint_y=0.05, color=(0.4, 0.8, 0.4, 1)
        )
        layout.add_widget(self.status_label)

        dir_box = BoxLayout(size_hint_y=0.07, spacing=5, padding=[10, 2])
        dir_box.add_widget(Label(text="Stream:", font_size=12,
                                 size_hint_x=0.2))
        self.dir_phone_btn = ToggleButton(
            text="Phone\xb7PC",
            size_hint_x=0.35, font_size=11,
            background_color=(0.3, 0.6, 0.3, 1),
            group="radio_dir", state="down"
        )
        self.dir_phone_btn.bind(on_press=lambda b: self._set_direction("phone_to_pc"))
        dir_box.add_widget(self.dir_phone_btn)
        self.dir_pc_btn = ToggleButton(
            text="PC\xb7Phone",
            size_hint_x=0.35, font_size=11,
            background_color=(0.3, 0.3, 0.6, 1),
            group="radio_dir"
        )
        self.dir_pc_btn.bind(on_press=lambda b: self._set_direction("pc_to_phone"))
        dir_box.add_widget(self.dir_pc_btn)
        layout.add_widget(dir_box)

        ctrl_box = BoxLayout(size_hint_y=0.08, spacing=5, padding=[10, 2])
        self.tune_input = TextInput(
            hint_text="FM freq (e.g. 98.5) or URL",
            size_hint_x=0.55, font_size=13,
            multiline=False
        )
        ctrl_box.add_widget(self.tune_input)
        self.tune_btn = Button(
            text="Tune", size_hint_x=0.2,
            background_color=(0.2, 0.6, 0.2, 1), font_size=13
        )
        self.tune_btn.bind(on_press=self._tune_station)
        ctrl_box.add_widget(self.tune_btn)
        self.stop_btn = Button(
            text="Stop", size_hint_x=0.15,
            background_color=(0.6, 0.2, 0.2, 1), font_size=13
        )
        self.stop_btn.bind(on_press=lambda b: self._stop_radio())
        ctrl_box.add_widget(self.stop_btn)
        layout.add_widget(ctrl_box)

        scroll = ScrollView(size_hint_y=0.66)
        self.station_grid = GridLayout(
            cols=2, spacing=dp(4), padding=[8, 4],
            size_hint_y=None
        )
        self.station_grid.bind(minimum_height=self.station_grid.setter("height"))
        self._build_station_list()
        scroll.add_widget(self.station_grid)
        layout.add_widget(scroll)

        self.add_widget(layout)

    def _build_station_list(self):
        self.station_grid.clear_widgets()
        stations = [
            {"name": "BBC Radio 1", "type": "internet"},
            {"name": "BBC Radio 2", "type": "internet"},
            {"name": "BBC Radio 3", "type": "internet"},
            {"name": "BBC Radio 4", "type": "internet"},
            {"name": "Classic FM", "type": "internet"},
            {"name": "Absolute Radio", "type": "internet"},
            {"name": "Capital FM", "type": "internet"},
            {"name": "Heart Radio", "type": "internet"},
            {"name": "Smooth Radio", "type": "internet"},
            {"name": "Jazz FM", "type": "internet"},
            {"name": "LBC", "type": "internet"},
            {"name": "Radio X", "type": "internet"},
            {"name": "talkSPORT", "type": "internet"},
            {"name": "Virgin Radio UK", "type": "internet"},
            {"type": "label", "name": "─── FM Presets ───"},
            {"name": "FM 88.0", "type": "fm", "freq": 88.0},
            {"name": "FM 89.1", "type": "fm", "freq": 89.1},
            {"name": "FM 90.3", "type": "fm", "freq": 90.3},
            {"name": "FM 91.1", "type": "fm", "freq": 91.1},
            {"name": "FM 92.1", "type": "fm", "freq": 92.1},
            {"name": "FM 93.1", "type": "fm", "freq": 93.1},
            {"name": "FM 94.1", "type": "fm", "freq": 94.1},
            {"name": "FM 95.1", "type": "fm", "freq": 95.1},
            {"name": "FM 96.1", "type": "fm", "freq": 96.1},
            {"name": "FM 97.1", "type": "fm", "freq": 97.1},
            {"name": "FM 98.1", "type": "fm", "freq": 98.1},
            {"name": "FM 99.1", "type": "fm", "freq": 99.1},
            {"name": "FM 100.1", "type": "fm", "freq": 100.1},
            {"name": "FM 101.1", "type": "fm", "freq": 101.1},
            {"name": "FM 102.1", "type": "fm", "freq": 102.1},
            {"name": "FM 103.1", "type": "fm", "freq": 103.1},
            {"name": "FM 104.1", "type": "fm", "freq": 104.1},
            {"name": "FM 105.1", "type": "fm", "freq": 105.1},
            {"name": "FM 106.1", "type": "fm", "freq": 106.1},
            {"name": "FM 107.1", "type": "fm", "freq": 107.1},
            {"name": "FM 107.9", "type": "fm", "freq": 107.9},
        ]
        for s in stations:
            if s.get("type") == "label":
                lbl = Label(
                    text=s["name"], font_size=12, bold=True,
                    size_hint_y=None, height=dp(24),
                    size_hint_x=1,
                    color=(0.3, 0.7, 0.3, 1)
                )
                self.station_grid.add_widget(lbl)
                self.station_grid.add_widget(Label())
                continue
            if s.get("type") == "fm":
                btn = Button(
                    text=s["name"], font_size=11,
                    size_hint_y=None, height=dp(36),
                    background_color=(0.3, 0.5, 0.7, 1)
                )
                btn.bind(on_press=lambda b, f=s["freq"]: self._tune_fm(f))
            else:
                btn = Button(
                    text=s["name"], font_size=11,
                    size_hint_y=None, height=dp(36),
                    background_color=(0.4, 0.3, 0.6, 1)
                )
                btn.bind(on_press=lambda b, n=s["name"]: self._tune_internet(n))
            self.station_grid.add_widget(btn)

    def _set_direction(self, direction):
        self._direction = direction
        dir_label = "Phone → PC" if direction == "phone_to_pc" else "PC → Phone"
        self.status_label.text = f"Direction: {dir_label}"

    def _tune_fm(self, freq):
        if self._direction == "phone_to_pc":
            self._start_phone_fm(freq)
        else:
            self._start_pc_scan()

    def _tune_internet(self, name):
        if self._direction == "phone_to_pc":
            self._start_pc_internet_radio_to_phone(name)
        else:
            self._start_pc_internet_radio(name)

    def _tune_station(self, *args):
        val = self.tune_input.text.strip()
        if not val:
            return
        if val.replace(".", "").isdigit():
            freq = float(val)
            self._tune_fm(freq)
        elif val.startswith("http"):
            self._tune_url(val)
        else:
            self._tune_internet(val)

    def _tune_url(self, url):
        if self.client and self.client.connected:
            self.client.send({
                "type": "radio_tune_url",
                "url": url,
                "direction": self._direction,
            })
            self.status_label.text = f"Tuning: {url[:40]}..."
        self._playing = True

    def _start_phone_fm(self, freq):
        self._current_station = f"FM {freq}"
        if self.phone_radio:
            result = self.phone_radio.start_fm_tuner(freq)
            if result.get("success"):
                self.status_label.text = f"Phone FM: {freq} MHz"
                self._playing = True
            else:
                self.status_label.text = f"FM failed, use Phone→PC stream"
                if self.client and self.client.connected:
                    self.client.send({
                        "type": "radio_phone_fm",
                        "freq": freq,
                    })
                    self._playing = True
        else:
            self.status_label.text = "Phone radio not available"

    def _start_pc_internet_radio(self, name):
        if self.client and self.client.connected:
            self.client.send({
                "type": "radio_tune",
                "station": name,
                "direction": self._direction,
            })
            self.status_label.text = f"Playing: {name}"
            self._current_station = name
        self._playing = True

    def _start_pc_internet_radio_to_phone(self, name):
        if self.client and self.client.connected:
            self.client.send({
                "type": "radio_tune",
                "station": name,
                "direction": "pc_to_phone",
            })
            self.status_label.text = f"PC streaming: {name}"
            self._current_station = name
        self._playing = True

    def _start_pc_scan(self):
        if self.client and self.client.connected:
            self.client.send({
                "type": "radio_scan",
                "direction": "pc_to_phone",
            })
            self.status_label.text = "PC scanning FM..."

    def _stop_radio(self):
        if self.client and self.client.connected:
            self.client.send({"type": "radio_stop"})
        if self.phone_radio:
            self.phone_radio.stop()
        self._playing = False
        self._current_station = None
        self.status_label.text = "Stopped"

    def on_pc_radio_audio(self, pcm_bytes):
        if self.phone_radio:
            self.phone_radio.write_pc_radio_audio(pcm_bytes)

    def _go_back(self, *args):
        self._stop_radio()
        if self.manager:
            self.manager.current = "control"
