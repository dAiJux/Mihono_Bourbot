import ctypes
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

    def _is_steam(self) -> bool:
        return self.config.get("platform", "google_play") == "steam"

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

        if self._is_steam():
            self._steam_click(hwnd, client_x, client_y)
        else:
            lp = self._make_lparam(client_x, client_y)
            win32gui.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lp)
            time.sleep(random.uniform(0.05, 0.15))
            win32gui.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, lp)
        self.logger.debug(f"Click at client({client_x}, {client_y}) window({x}, {y})")

    def _steam_click(self, hwnd, client_x, client_y):
        lp = self._make_lparam(client_x, client_y)
        origin = win32gui.ClientToScreen(hwnd, (0, 0))
        screen_x = origin[0] + client_x
        screen_y = origin[1] + client_y
        win32gui.SendMessage(hwnd, win32con.WM_ACTIVATE, win32con.WA_ACTIVE, 0)
        win32gui.SendMessage(hwnd, win32con.WM_SETFOCUS, 0, 0)
        ctypes.windll.user32.SetCursorPos(screen_x, screen_y)
        time.sleep(0.045)
        win32gui.SendMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lp)
        time.sleep(random.uniform(0.20, 0.25))
        win32gui.SendMessage(hwnd, win32con.WM_LBUTTONUP, 0, lp)

    def click_with_offset(self, x: int, y: int):
        lo, hi = self.click_offset_range
        ox = random.randint(-lo, hi)
        oy = random.randint(-lo, hi)
        self.click_at(x + ox, y + oy)

    def _interruptible_sleep(self, seconds: float) -> bool:
        elapsed = 0.0
        while elapsed < seconds:
            if self._check_stopped():
                return True
            step = min(0.1, seconds - elapsed)
            time.sleep(step)
            elapsed += step
        return False

    def wait(self, base_seconds: float = 2.0):
        multiplier = self.config.get("automation_settings", {}).get("sleep_time_multiplier", 1.0)
        jitter = random.uniform(1.0, 2.0)
        total = base_seconds * jitter / 2.0 * multiplier
        self._interruptible_sleep(total)

    def wait_random(self):
        time.sleep(random.uniform(*self.action_delay))

    _CLICK_Y_ADJUST = {
        "btn_training": -0.045,
        "btn_rest": -0.030,
        "btn_rest_summer": -0.020,
        "btn_recreation": -0.030,
        "btn_races": -0.030,
        "btn_skills": -0.030,
    }

    _INSTANT_DOUBLE_CLICK = {"btn_training"}

    def click_button(self, button_name: str, screenshot=None, threshold=0.75) -> bool:
        if screenshot is None:
            screenshot = self.vision.take_screenshot()
        pos = self.vision.find_template(button_name, screenshot, threshold)
        if pos:
            x, y = pos
            y_frac = self._CLICK_Y_ADJUST.get(button_name)
            if y_frac is not None:
                _, _, _, gh = self.vision.get_game_rect(screenshot)
                y += int(gh * y_frac)
            self.click_with_offset(x, y)
            if self._is_steam():
                if button_name in self._INSTANT_DOUBLE_CLICK:
                    time.sleep(0.03)
                else:
                    time.sleep(random.uniform(0.05, 0.10))
                self.click_with_offset(x, y)
            self.logger.info(f"Button '{button_name}' clicked at {(x, y)}")
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
