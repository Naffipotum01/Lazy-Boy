import pyautogui

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0


class InputHandler:
    def __init__(self, screen_width, screen_height):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.remote_width = 0
        self.remote_height = 0
        self.offset_x = 0
        self.offset_y = 0

    def set_remote_resolution(self, width, height, offset_x=0, offset_y=0):
        self.remote_width = width
        self.remote_height = height
        self.offset_x = offset_x
        self.offset_y = offset_y

    def _translate_point(self, x, y):
        if self.remote_width == 0 or self.remote_height == 0:
            return x, y
        scale_x = self.screen_width / self.remote_width
        scale_y = self.screen_height / self.remote_height
        tx = int((x - self.offset_x) * scale_x)
        ty = int((y - self.offset_y) * scale_y)
        tx = max(0, min(tx, self.screen_width - 1))
        ty = max(0, min(ty, self.screen_height - 1))
        return tx, ty

    def mouse_move(self, x, y):
        tx, ty = self._translate_point(x, y)
        pyautogui.moveTo(tx, ty, _pause=False)

    def mouse_move_relative(self, dx, dy):
        pyautogui.moveRel(dx, dy, _pause=False)

    def mouse_down(self, x, y, button="left"):
        tx, ty = self._translate_point(x, y)
        pyautogui.mouseDown(tx, ty, button=button, _pause=False)

    def mouse_up(self, x, y, button="left"):
        tx, ty = self._translate_point(x, y)
        pyautogui.mouseUp(tx, ty, button=button, _pause=False)

    def mouse_click(self, x, y, button="left"):
        tx, ty = self._translate_point(x, y)
        pyautogui.click(tx, ty, button=button, _pause=False)

    def mouse_double_click(self, x, y):
        tx, ty = self._translate_point(x, y)
        pyautogui.doubleClick(tx, ty, _pause=False)

    def mouse_right_click(self, x, y):
        tx, ty = self._translate_point(x, y)
        pyautogui.rightClick(tx, ty, _pause=False)

    def mouse_scroll(self, dx, dy):
        pyautogui.scroll(int(dy * 3), _pause=False)
        if dx != 0:
            pyautogui.hscroll(int(dx * 3), _pause=False)

    def key_down(self, key):
        try:
            pyautogui.keyDown(key, _pause=False)
        except Exception:
            pass

    def key_up(self, key):
        try:
            pyautogui.keyUp(key, _pause=False)
        except Exception:
            pass

    def key_press(self, key):
        try:
            pyautogui.press(key, _pause=False)
        except Exception:
            pass

    def type_text(self, text):
        pyautogui.write(text, interval=0.02, _pause=False)

    def hotkey(self, *keys):
        try:
            pyautogui.hotkey(*keys, _pause=False)
        except Exception:
            pass
