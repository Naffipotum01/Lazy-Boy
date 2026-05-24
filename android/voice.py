from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp
from kivy.clock import Clock
from functools import partial


class VoiceOptionOverlay(FloatLayout):
    def __init__(self, options, prompt, on_select=None, on_dismiss=None, **kwargs):
        super().__init__(**kwargs)
        self.options = options
        self.on_select = on_select
        self.on_dismiss = on_dismiss

        with self.canvas:
            Color(0, 0, 0, 0.7)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_bg, size=self._update_bg)

        main = BoxLayout(orientation="vertical", size_hint=(0.9, 0.7),
                          pos_hint={"center_x": 0.5, "center_y": 0.5})

        prompt_label = Label(
            text=f"[b]{prompt}[/b]" if prompt else "[b]Choose an option:[/b]",
            markup=True, font_size=18,
            size_hint_y=0.1, color=(1, 1, 1, 1)
        )
        main.add_widget(prompt_label)

        scroll = ScrollView(size_hint_y=0.75)
        opt_list = BoxLayout(orientation="vertical",
                              size_hint_y=None, spacing=dp(6))
        opt_list.bind(minimum_height=opt_list.setter("height"))

        for opt in options:
            row = BoxLayout(size_hint_y=None, height=dp(56), spacing=dp(8))

            num_bg = BoxLayout(size_hint_x=0.12, padding=[0, 0])
            with num_bg.canvas:
                Color(0.2, 0.6, 0.8, 1.0)
                self._make_circle(num_bg, dp(36))
            num_label = Label(
                text=f"[b]{opt['id']}[/b]",
                markup=True, font_size=18, color=(1, 1, 1, 1)
            )
            num_bg.add_widget(num_label)
            row.add_widget(num_bg)

            opt_btn = Button(
                text=opt.get("label", f"Option {opt['id']}"),
                font_size=14, halign="center",
                size_hint_x=0.88,
                background_color=(0.15, 0.15, 0.18, 1),
                color=(1, 1, 1, 0.9),
            )
            opt_btn.bind(
                on_press=lambda b, o=opt: self._select(o)
            )
            row.add_widget(opt_btn)
            opt_list.add_widget(row)

        scroll.add_widget(opt_list)
        main.add_widget(scroll)

        dismiss_btn = Button(
            text="Cancel", size_hint_y=0.1,
            background_color=(0.5, 0.15, 0.15, 1),
            font_size=14
        )
        dismiss_btn.bind(on_press=lambda b: self._dismiss())
        main.add_widget(dismiss_btn)

        self.add_widget(main)

    def _make_circle(self, widget, diameter):
        widget.bind(pos=lambda w, v: self._draw_circle(w, diameter),
                    size=lambda w, v: self._draw_circle(w, diameter))

    def _draw_circle(self, widget, diameter):
        widget.canvas.after.clear()
        with widget.canvas.after:
            Color(0.2, 0.6, 0.8, 1.0)
            cx = widget.center_x
            cy = widget.center_y
            from kivy.graphics import Ellipse
            r = diameter / 2
            Ellipse(pos=(cx - r, cy - r), size=(diameter, diameter))

    def _update_bg(self, *args):
        self._bg.pos = self.pos
        self._bg.size = self.size

    def _select(self, opt):
        if self.on_select:
            self.on_select(opt)
        self._dismiss()

    def _dismiss(self):
        if self.on_dismiss:
            self.on_dismiss()
        if self.parent:
            self.parent.remove_widget(self)

    def on_touch_down(self, touch):
        return True


class VoiceController:
    def __init__(self, app=None, client=None):
        self.app = app
        self.client = client
        self._listening = False

    def start_listening(self, callback=None):
        self._listening = True
        try:
            from kivy import platform
            if platform == "android":
                self._listen_android(callback)
            else:
                self._listen_fallback(callback)
        except Exception:
            self._listen_fallback(callback)

    def _listen_android(self, callback):
        try:
            from android import activity
            from android.runnable import run_on_ui_thread
            from jnius import autoclass
            import android.activity as activity_module

            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            Intent = autoclass("android.content.Intent")
            RecognizerIntent = autoclass("android.speech.RecognizerIntent")

            intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
            intent.putExtra(
                RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                RecognizerIntent.LANGUAGE_MODEL_FREE_FORM,
            )
            intent.putExtra(
                RecognizerIntent.EXTRA_PROMPT,
                "Speak a command for your PC...",
            )

            def on_result(requestCode, resultCode, data):
                if requestCode == 1000 and resultCode == -1:
                    results = data.getStringArrayListExtra(
                        RecognizerIntent.EXTRA_RESULTS
                    )
                    if results and results.size() > 0:
                        text = str(results.get(0))
                        if callback:
                            Clock.schedule_once(lambda dt: callback(text))
                    else:
                        if callback:
                            Clock.schedule_once(
                                lambda dt: callback(None)
                            )
                else:
                    if callback:
                        Clock.schedule_once(
                            lambda dt: callback(None)
                        )
                try:
                    activity_module.unbind(on_activity_result=on_result)
                except Exception:
                    pass

            activity_module.bind(on_activity_result=on_result)
            activity.startActivityForResult(intent, 1000)
        except Exception as e:
            if callback:
                Clock.schedule_once(lambda dt: callback(f"err:{e}"))

    def _listen_fallback(self, callback):
        try:
            from kivy.uix.popup import Popup
            from kivy.uix.textinput import TextInput

            content = BoxLayout(orientation="vertical", padding=10, spacing=10)
            inp = TextInput(
                hint_text="Type your command...",
                font_size=16, multiline=False, size_hint_y=0.4,
            )
            content.add_widget(inp)
            ok_btn = Button(
                text="Send", size_hint_y=0.3,
                background_color=(0.2, 0.6, 1, 1),
            )

            def on_ok(b):
                if callback:
                    callback(inp.text or None)
                popup.dismiss()

            ok_btn.bind(on_press=on_ok)
            content.add_widget(ok_btn)
            popup = Popup(
                title="Voice Command (type instead)",
                content=content, size_hint=(0.85, 0.4)
            )
            popup.open()
        except Exception as e:
            if callback:
                callback(f"err:{e}")

    def show_options(self, options, prompt, on_select):
        if self.app and hasattr(self.app, "control_screen"):
            cs = self.app.control_screen
            overlay = VoiceOptionOverlay(
                options, prompt,
                on_select=lambda opt: self._option_selected(opt, on_select),
                on_dismiss=lambda: setattr(self, "_listening", False),
            )
            overlay.size_hint = (1, 1)
            cs.layout.add_widget(overlay)

    def _option_selected(self, opt, on_select):
        if self.client and self.client.connected:
            self.client.send({
                "type": "voice_option_picked",
                "option_id": opt["id"],
                "label": opt.get("label", ""),
            })
        if on_select:
            on_select(opt)
