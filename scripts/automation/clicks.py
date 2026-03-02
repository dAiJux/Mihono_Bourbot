import win32gui
import win32con
import win32api
import random
import time
import threading

class ClickMixin:

    def set_control_flags(self, running_flag_getter, pause_event: threading.Event):
        self._running_flag = running_flag_getter
        self._pause_event = pause_event

    def _check_stopped(self) -> bool:
        if self._running_flag is not None and not self._running_flag():
            return True
        if self._pause_event is not None and not self._pause_event.is_set():
            self.logger.info("Paused — aborting current action")
            return True
        return False

    def _make_lparam(self, x: int, y: int) -> int:
        return win32api.MAKELONG(x, y)

    def click_at(self, x: int, y: int):
        hwnd = self.vision.game_hwnd
        if hwnd is None or not win32gui.IsWindow(hwnd):
            self.vision.find_game_window()
            hwnd = self.vision.game_hwnd
        if hwnd is None:
            self.logger.error("Game window not found")
            return

        client_x = x - self.vision._client_offset_x
        client_y = y - self.vision._client_offset_y

        lp = self._make_lparam(client_x, client_y)
        win32gui.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lp)
        time.sleep(random.uniform(0.05, 0.15))
        win32gui.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, lp)
        self.logger.debug(f"Click at client({client_x}, {client_y}) window({x}, {y})")

    def click_with_offset(self, x: int, y: int):
        lo, hi = self.click_offset_range
        ox = random.randint(-lo, hi)
        oy = random.randint(-lo, hi)
        self.click_at(x + ox, y + oy)

    def wait(self, base_seconds: float = 2.0):
        multiplier = self.config.get("automation_settings", {}).get("sleep_time_multiplier", 1.0)
        jitter = random.uniform(1.0, 3.0)
        total = base_seconds * jitter / 2.0 * multiplier
        elapsed = 0.0
        while elapsed < total:
            if self._check_stopped():
                return
            step = min(0.3, total - elapsed)
            time.sleep(step)
            elapsed += step

    def wait_random(self):
        time.sleep(random.uniform(*self.action_delay))

    def click_button(self, button_name: str, screenshot=None, threshold=0.75) -> bool:
        if screenshot is None:
            screenshot = self.vision.take_screenshot()
        pos = self.vision.find_template(button_name, screenshot, threshold)
        if pos:
            self.click_with_offset(*pos)
            self.logger.info(f"Button '{button_name}' clicked at {pos}")
            return True
        self.logger.warning(f"Button '{button_name}' not found")
        self.vision.save_debug_screenshot(f"notfound_{button_name}")
        return False

    def wait_and_click(self, button_name: str, timeout: float = 10.0, interval: float = 1.0) -> bool:
        elapsed = 0.0
        while elapsed < timeout:
            if self._check_stopped():
                return False
            if self.click_button(button_name):
                return True
            time.sleep(interval)
            elapsed += interval
        self.logger.warning(f"Timed out waiting for '{button_name}'")
        return False

    def click_any_next(self) -> bool:
        screenshot = self.vision.take_screenshot()
        for btn in ("btn_next", "btn_tap", "btn_race_next_finish", "btn_skip", "btn_inspiration"):
            if self.vision.find_template(btn, screenshot, threshold=0.75):
                self.click_button(btn, screenshot)
                return True
        return False
