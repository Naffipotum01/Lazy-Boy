from kivy.uix.floatlayout import FloatLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.boxlayout import BoxLayout
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.graphics import Color, RoundedRectangle
from kivy.properties import NumericProperty


class RecNumberButton(Button):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.font_size = dp(18)
        self.bold = True
        self.background_color = (0.15, 0.15, 0.35, 0.85)
        self.color = (1, 1, 1, 1)
        self.size_hint = (1, None)
        self.height = dp(50)


class SmartPointerOverlay(FloatLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.client = None
        self._active = False
        self._recommendations = []
        self._on_select = None

        with self.canvas:
            Color(0, 0, 0, 0.5)
            self.bg = RoundedRectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_bg, size=self._update_bg)

        card = BoxLayout(
            orientation="vertical",
            size_hint=(0.7, 0.35),
            pos_hint={"center_x": 0.5, "center_y": 0.45},
            padding=[dp(10), dp(10)],
            spacing=dp(6),
        )
        with card.canvas.before:
            Color(0.1, 0.1, 0.15, 0.95)
            self.card_bg = RoundedRectangle(pos=card.pos, size=card.size,
                                             radius=[(dp(12), dp(12))])
        card.bind(pos=self._update_card_bg, size=self._update_card_bg)

        title = Label(
            text="[b]Smart Point[/b]\nRecommendations",
            markup=True, font_size=dp(14),
            size_hint_y=0.18, color=(0.3, 1, 0.6, 1),
            halign="center",
        )
        card.add_widget(title)

        self.opt1 = RecNumberButton(text="1. ...", on_press=lambda b: self._pick(0))
        self.opt2 = RecNumberButton(text="2. ...", on_press=lambda b: self._pick(1))
        self.opt3 = RecNumberButton(text="3. ...", on_press=lambda b: self._pick(2))
        card.add_widget(self.opt1)
        card.add_widget(self.opt2)
        card.add_widget(self.opt3)

        btn_row = BoxLayout(size_hint_y=0.2, spacing=dp(8))
        no_thanks = Button(
            text="No thank you",
            font_size=dp(12),
            background_color=(0.4, 0.1, 0.1, 0.9),
            size_hint_x=0.6,
        )
        no_thanks.bind(on_press=lambda b: self.dismiss())
        btn_row.add_widget(no_thanks)

        refresh = Button(
            text="⟳ Scan",
            font_size=dp(12),
            background_color=(0.2, 0.3, 0.6, 0.9),
            size_hint_x=0.4,
        )
        refresh.bind(on_press=lambda b: self._refresh())
        btn_row.add_widget(refresh)

        card.add_widget(btn_row)
        self.add_widget(card)

        self._card = card
        self._btns = [self.opt1, self.opt2, self.opt3]

    def _update_bg(self, *args):
        self.bg.pos = self.pos
        self.bg.size = self.size

    def _update_card_bg(self, *args):
        self.card_bg.pos = self._card.pos
        self.card_bg.size = self._card.size

    def show(self, recommendations):
        self._recommendations = recommendations or []
        labels = ["(empty)"] * 3
        for i, r in enumerate(recommendations[:3]):
            text = r.get("text", "") or f"Area {i + 1}"
            labels[i] = f"{i + 1}. {text[:25]}"

        for i, btn in enumerate(self._btns):
            btn.text = labels[i]

        self._active = True
        self.opacity = 1

    def dismiss(self):
        self._active = False
        self.opacity = 0
        self._recommendations = []
        if self.client and self.client.connected:
            self.client.send({"type": "smart_point_dismiss"})

    def _pick(self, index):
        if index < len(self._recommendations) and self.client:
            pred = self._recommendations[index]
            if self._on_select:
                self._on_select(pred)
            elif self.client and self.client.connected:
                self.client.send({
                    "type": "smart_point_click",
                    "index": index,
                    "x": pred.get("cx", 0),
                    "y": pred.get("cy", 0),
                })
            self.dismiss()

    def _refresh(self):
        if self.client and self.client.connected:
            self.client.send({"type": "smart_point_scan"})
