from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.uix.popup import Popup
from kivy.metrics import dp

from key_bindings import load_bindings, save_bindings, reset_bindings, DEFAULT_BINDINGS


class KeyBindingsScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bindings = load_bindings()
        self._rows = {}

        layout = BoxLayout(orientation="vertical")

        header = BoxLayout(size_hint_y=0.07, padding=[5, 3], spacing=5)
        back_btn = Button(text="Back", size_hint_x=0.15,
                          background_color=(0.5, 0.5, 0.5, 1))
        back_btn.bind(on_press=self._go_back)
        header.add_widget(back_btn)

        title = Label(text="Key Bindings", font_size=18, bold=True,
                      size_hint_x=0.7)
        header.add_widget(title)

        reset_btn = Button(text="Reset", size_hint_x=0.15,
                           background_color=(0.7, 0.3, 0.2, 1))
        reset_btn.bind(on_press=self._reset_all)
        header.add_widget(reset_btn)
        layout.add_widget(header)

        hint = Label(
            text="Tap a key name to change it. Changes save automatically.",
            font_size=11, size_hint_y=0.04, color=(0.6, 0.6, 0.6, 1)
        )
        layout.add_widget(hint)

        scroll = ScrollView(size_hint_y=0.82)
        self.bindings_list = BoxLayout(orientation="vertical",
                                        size_hint_y=None, spacing=2)
        self.bindings_list.bind(minimum_height=self.bindings_list.setter("height"))
        scroll.add_widget(self.bindings_list)
        layout.add_widget(scroll)

        bottom = BoxLayout(size_hint_y=0.07, padding=[5, 3], spacing=5)
        save_btn = Button(text="Save & Apply", background_color=(0.2, 0.7, 0.3, 1))
        save_btn.bind(on_press=self._apply)
        bottom.add_widget(save_btn)
        layout.add_widget(bottom)

        self.add_widget(layout)

    def on_enter(self):
        self.bindings = load_bindings()
        self._build_list()

    def _build_list(self):
        self.bindings_list.clear_widgets()
        self._rows.clear()

        for btn_name in sorted(self.bindings.keys(), key=self._sort_key):
            row = BoxLayout(size_hint_y=None, height=dp(48), spacing=2)

            label = Label(
                text=f"[b]{btn_name}[/b]",
                markup=True, font_size=14, size_hint_x=0.35,
                halign="right", valign="center", padding=[10, 0],
                color=(0.8, 0.8, 0.8, 1)
            )
            label.bind(size=label.setter("text_size"))
            row.add_widget(label)

            arrow = Label(text="→", font_size=16,
                          size_hint_x=0.08, color=(0.5, 0.5, 0.5, 1))
            row.add_widget(arrow)

            current_key = self.bindings.get(btn_name, "")
            key_label = Label(
                text=f"[b]{current_key}[/b]",
                markup=True, font_size=16, size_hint_x=0.4,
                halign="center", valign="center",
                color=(0.2, 0.8, 0.4, 1)
            )
            key_label.bind(size=key_label.setter("text_size"))
            row.add_widget(key_label)

            edit_btn = Button(text="Edit", size_hint_x=0.17,
                              font_size=11, background_color=(0.3, 0.3, 0.5, 1))
            edit_btn.bind(on_press=lambda b, n=btn_name: self._edit_binding(n))
            row.add_widget(edit_btn)

            self._rows[btn_name] = key_label
            self.bindings_list.add_widget(row)

    def _sort_key(self, name):
        order = ["A", "B", "X", "Y", "LB", "RB", "LT", "RT",
                 "DUP", "DDOWN", "DLEFT", "DRIGHT",
                 "SELECT", "START", "STATUS"]
        if name in order:
            return order.index(name)
        return 99

    def _edit_binding(self, btn_name):
        content = BoxLayout(orientation="vertical", padding=10, spacing=10)
        content.add_widget(Label(
            text=f"Key for [b]{btn_name}[/b]:", markup=True, font_size=16
        ))
        inp = TextInput(
            text=self.bindings.get(btn_name, ""),
            hint_text="Enter key name (e.g. space, ctrl, e)",
            size_hint_y=0.3, font_size=16, multiline=False
        )
        content.add_widget(inp)

        # Common keys shortcuts
        keys_layout = BoxLayout(
            orientation="vertical", size_hint_y=0.4, spacing=3
        )
        common_row1 = BoxLayout(spacing=4, size_hint_y=0.5)
        common_keys = ["space", "enter", "tab", "escape", "backspace",
                       "up", "down", "left", "right", "shift",
                       "ctrl", "alt", "e", "q", "r", "f"]
        for k in common_keys:
            kb = Button(text=k, font_size=9, size_hint_x=0.12)
            kb.bind(on_press=lambda b, val=k: self._set_key(inp, val))
            keys_layout.add_widget(kb)

        content.add_widget(keys_layout)

        btn_layout = BoxLayout(spacing=8, size_hint_y=0.2)
        cancel = Button(text="Cancel")
        confirm = Button(text="Save", background_color=(0.2, 0.7, 0.3, 1))
        btn_layout.add_widget(cancel)
        btn_layout.add_widget(confirm)
        content.add_widget(btn_layout)

        popup = Popup(title=f"Edit {btn_name}", content=content,
                      size_hint=(0.85, 0.6))
        cancel.bind(on_press=popup.dismiss)
        confirm.bind(on_press=lambda b: self._save_binding(btn_name, inp.text, popup))
        popup.open()

    def _set_key(self, inp, val):
        inp.text = val

    def _save_binding(self, btn_name, value, popup):
        popup.dismiss()
        self.bindings[btn_name] = value
        save_bindings(self.bindings)
        self._build_list()

    def _reset_all(self, *args):
        content = BoxLayout(orientation="vertical", padding=10, spacing=10)
        content.add_widget(Label(
            text="Reset all key bindings to defaults?",
            font_size=14
        ))
        btn_layout = BoxLayout(spacing=8, size_hint_y=0.3)
        cancel = Button(text="Cancel")
        confirm = Button(text="Reset", background_color=(0.7, 0.3, 0.2, 1))
        btn_layout.add_widget(cancel)
        btn_layout.add_widget(confirm)
        content.add_widget(btn_layout)

        popup = Popup(title="Reset Bindings", content=content,
                      size_hint=(0.7, 0.3))
        cancel.bind(on_press=popup.dismiss)
        confirm.bind(on_press=lambda b: self._do_reset(popup))
        popup.open()

    def _do_reset(self, popup):
        popup.dismiss()
        self.bindings = reset_bindings()
        self._build_list()

    def _apply(self, *args):
        from key_bindings import save_bindings
        save_bindings(self.bindings)
        self._show_msg("Bindings saved. Reconnect to apply.")

    def _show_msg(self, msg):
        content = BoxLayout(orientation="vertical", padding=10, spacing=10)
        content.add_widget(Label(text=msg, font_size=14))
        btn = Button(text="OK", size_hint_y=0.3)
        popup = Popup(title="Settings", content=content,
                      size_hint=(0.7, 0.3))
        btn.bind(on_press=popup.dismiss)
        content.add_widget(btn)
        popup.open()

    def _go_back(self, *args):
        if self.manager:
            self.manager.current = "control"

    def get_bindings(self):
        return dict(self.bindings)
