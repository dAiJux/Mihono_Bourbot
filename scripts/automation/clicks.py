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

    def _is_ldplayer(self) -> bool:
        return self.config.get("platform", "google_play") == "ldplayer"

    def _find_render_child(self, parent_hwnd):
        best = None
        best_area = 0

        def callback(hwnd, _):
            nonlocal best, best_area
            try:
                cls = win32gui.GetClassName(hwnd)
                if cls in ("Shell_TrayWnd", "Progman", "WorkerW"):
                    return
                r = win32gui.GetClientRect(hwnd)
                area = r[2] * r[3]
                if area > best_area:
                    best_area = area
                    best = hwnd
            except Exception:
                pass

        win32gui.EnumChildWindows(parent_hwnd, callback, None)
        return best

    def poll_until_gone(self, button_name: str, timeout: float = 6.0,
                        interval: float = 0.07, threshold: float = 0.72) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._check_stopped():
                return False
            ss = self.vision.take_screenshot()
            if not self.vision.find_template(button_name, ss, threshold):
                return True
            time.sleep(interval)
        return False

    def poll_until_screen(self, target_screens, timeout: float = 6.0,
                          interval: float = 0.07):
        if not isinstance(target_screens, (list, tuple, set)):
            target_screens = (target_screens,)
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._check_stopped():
                return None
            ss = self.vision.take_screenshot()
            screen = self.vision.detect_screen(ss)
            if screen in target_screens:
                return screen
            time.sleep(interval)
        return None

    def poll_until_any_button_gone(self, button_names, timeout: float = 6.0,
                                   interval: float = 0.07, threshold: float = 0.72) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._check_stopped():
                return False
            ss = self.vision.take_screenshot()
            still_present = any(
                self.vision.find_template(btn, ss, threshold)
                for btn in button_names
            )
            if not still_present:
                return True
            time.sleep(interval)
        return False

    def click_at(self, x: int, y: int):
        hwnd = self.vision.game_hwnd
        if hwnd is None or not win32gui.IsWindow(hwnd):
            self.vision.find_game_window()
            hwnd = self.vision.game_hwnd
        if hwnd is None:
            self.logger.error("Game window not found")
            return

        x, y = int(x), int(y)
        client_x = x - self.vision._client_offset_x
        client_y = y - self.vision._client_offset_y

        if self._is_steam():
            self._steam_click(hwnd, client_x, client_y)
        elif self._is_ldplayer():
            self._ldplayer_click(hwnd, client_x, client_y)
        else:
            self._google_play_click(hwnd, client_x, client_y)
        self.logger.debug(f"Click at client({client_x}, {client_y}) window({x}, {y})")

    def _google_play_click(self, hwnd, client_x, client_y):
        lp = self._make_lparam(client_x, client_y)
        win32gui.PostMessage(hwnd, win32con.WM_MOUSEMOVE, 0, lp)
        win32gui.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lp)
        time.sleep(random.uniform(0.05, 0.15))
        win32gui.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, lp)

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

    def _ldplayer_click(self, parent_hwnd, client_x, client_y):
        child = self._find_render_child(parent_hwnd)
        if child is None:
            self.logger.warning("LDPlayer render child not found, falling back to parent")
            lp = self._make_lparam(client_x, client_y)
            win32gui.PostMessage(parent_hwnd, win32con.WM_MOUSEMOVE, 0, lp)
            win32gui.PostMessage(parent_hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lp)
            time.sleep(random.uniform(0.05, 0.15))
            win32gui.PostMessage(parent_hwnd, win32con.WM_LBUTTONUP, 0, lp)
            return

        try:
            p_origin = win32gui.ClientToScreen(parent_hwnd, (0, 0))
            c_origin = win32gui.ClientToScreen(child, (0, 0))
        except Exception:
            lp = self._make_lparam(client_x, client_y)
            win32gui.PostMessage(parent_hwnd, win32con.WM_MOUSEMOVE, 0, lp)
            win32gui.PostMessage(parent_hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lp)
            time.sleep(random.uniform(0.05, 0.15))
            win32gui.PostMessage(parent_hwnd, win32con.WM_LBUTTONUP, 0, lp)
            return

        child_x = client_x - (c_origin[0] - p_origin[0])
        child_y = client_y - (c_origin[1] - p_origin[1])
        lp = self._make_lparam(child_x, child_y)
        win32gui.PostMessage(child, win32con.WM_MOUSEMOVE, 0, lp)
        win32gui.PostMessage(child, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lp)
        time.sleep(random.uniform(0.05, 0.15))
        win32gui.PostMessage(child, win32con.WM_LBUTTONUP, 0, lp)

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

    def _post_action_delay(self):
        multiplier = self.config.get("automation_settings", {}).get("sleep_time_multiplier", 1.0)
        self._interruptible_sleep(0.30 * multiplier)

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

def _find_best_child(parent_hwnd):
    best = None
    best_area = 0

    def cb(hwnd, _):
        nonlocal best, best_area
        try:
            cls = win32gui.GetClassName(hwnd)
            if cls in ("Shell_TrayWnd", "Progman", "WorkerW"):
                return
            r = win32gui.GetClientRect(hwnd)
            area = r[2] * r[3]
            if area > best_area:
                best_area = area
                best = hwnd
        except Exception:
            pass

    win32gui.EnumChildWindows(parent_hwnd, cb, None)
    return best

def _child_coords(parent_hwnd, child, cx, cy):
    try:
        po = win32gui.ClientToScreen(parent_hwnd, (0, 0))
        co = win32gui.ClientToScreen(child, (0, 0))
        return cx - (co[0] - po[0]), cy - (co[1] - po[1])
    except Exception:
        return cx, cy

def click_test_dispatch(method_id, hwnd, client_x, client_y):
    cx, cy = int(client_x), int(client_y)
    lp = win32api.MAKELONG(cx, cy)

    if method_id == "gp_1_post_no_hover":
        win32gui.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lp)
        time.sleep(random.uniform(0.05, 0.15))
        win32gui.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, lp)

    elif method_id == "gp_2_post_hover":
        win32gui.PostMessage(hwnd, win32con.WM_MOUSEMOVE, 0, lp)
        win32gui.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lp)
        time.sleep(random.uniform(0.05, 0.15))
        win32gui.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, lp)

    elif method_id == "gp_3_send_hover":
        win32gui.SendMessage(hwnd, win32con.WM_MOUSEMOVE, 0, lp)
        win32gui.SendMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lp)
        time.sleep(random.uniform(0.05, 0.15))
        win32gui.SendMessage(hwnd, win32con.WM_LBUTTONUP, 0, lp)

    elif method_id == "gp_4_mixed_hover":
        win32gui.PostMessage(hwnd, win32con.WM_MOUSEMOVE, 0, lp)
        win32gui.SendMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lp)
        time.sleep(random.uniform(0.05, 0.15))
        win32gui.SendMessage(hwnd, win32con.WM_LBUTTONUP, 0, lp)

    elif method_id == "gp_5_triple_hover":
        for _ in range(3):
            win32gui.PostMessage(hwnd, win32con.WM_MOUSEMOVE, 0, lp)
        win32gui.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lp)
        time.sleep(random.uniform(0.05, 0.15))
        win32gui.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, lp)

    elif method_id == "gp_6_fg_hover":
        try:
            ctypes.windll.user32.SetForegroundWindow(hwnd)
        except Exception:
            pass
        win32gui.PostMessage(hwnd, win32con.WM_MOUSEMOVE, 0, lp)
        win32gui.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lp)
        time.sleep(random.uniform(0.05, 0.15))
        win32gui.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, lp)

    elif method_id == "ld_1_child_no_hover":
        child = _find_best_child(hwnd)
        target = child if child else hwnd
        tx, ty = _child_coords(hwnd, child, cx, cy) if child else (cx, cy)
        lp2 = win32api.MAKELONG(int(tx), int(ty))
        win32gui.PostMessage(target, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lp2)
        time.sleep(random.uniform(0.05, 0.15))
        win32gui.PostMessage(target, win32con.WM_LBUTTONUP, 0, lp2)

    elif method_id == "ld_2_child_post_hover":
        child = _find_best_child(hwnd)
        target = child if child else hwnd
        tx, ty = _child_coords(hwnd, child, cx, cy) if child else (cx, cy)
        lp2 = win32api.MAKELONG(int(tx), int(ty))
        win32gui.PostMessage(target, win32con.WM_MOUSEMOVE, 0, lp2)
        win32gui.PostMessage(target, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lp2)
        time.sleep(random.uniform(0.05, 0.15))
        win32gui.PostMessage(target, win32con.WM_LBUTTONUP, 0, lp2)

    elif method_id == "ld_3_child_send_hover":
        child = _find_best_child(hwnd)
        target = child if child else hwnd
        tx, ty = _child_coords(hwnd, child, cx, cy) if child else (cx, cy)
        lp2 = win32api.MAKELONG(int(tx), int(ty))
        win32gui.SendMessage(target, win32con.WM_MOUSEMOVE, 0, lp2)
        win32gui.SendMessage(target, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lp2)
        time.sleep(random.uniform(0.05, 0.15))
        win32gui.SendMessage(target, win32con.WM_LBUTTONUP, 0, lp2)

    elif method_id == "ld_4_parent_post_hover":
        win32gui.PostMessage(hwnd, win32con.WM_MOUSEMOVE, 0, lp)
        win32gui.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lp)
        time.sleep(random.uniform(0.05, 0.15))
        win32gui.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, lp)

    elif method_id == "ld_5_parent_send_hover":
        win32gui.SendMessage(hwnd, win32con.WM_MOUSEMOVE, 0, lp)
        win32gui.SendMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lp)
        time.sleep(random.uniform(0.05, 0.15))
        win32gui.SendMessage(hwnd, win32con.WM_LBUTTONUP, 0, lp)

    elif method_id == "ld_6_child_triple_hover":
        child = _find_best_child(hwnd)
        target = child if child else hwnd
        tx, ty = _child_coords(hwnd, child, cx, cy) if child else (cx, cy)
        lp2 = win32api.MAKELONG(int(tx), int(ty))
        for _ in range(3):
            win32gui.PostMessage(target, win32con.WM_MOUSEMOVE, 0, lp2)
        win32gui.PostMessage(target, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lp2)
        time.sleep(random.uniform(0.05, 0.15))
        win32gui.PostMessage(target, win32con.WM_LBUTTONUP, 0, lp2)

    elif method_id == "st_1_cursor_activate_send":
        origin = win32gui.ClientToScreen(hwnd, (0, 0))
        win32gui.SendMessage(hwnd, win32con.WM_ACTIVATE, win32con.WA_ACTIVE, 0)
        win32gui.SendMessage(hwnd, win32con.WM_SETFOCUS, 0, 0)
        ctypes.windll.user32.SetCursorPos(origin[0] + cx, origin[1] + cy)
        time.sleep(0.045)
        win32gui.SendMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lp)
        time.sleep(random.uniform(0.20, 0.25))
        win32gui.SendMessage(hwnd, win32con.WM_LBUTTONUP, 0, lp)

    elif method_id == "st_2_fg_cursor_send":
        origin = win32gui.ClientToScreen(hwnd, (0, 0))
        try:
            ctypes.windll.user32.SetForegroundWindow(hwnd)
        except Exception:
            pass
        ctypes.windll.user32.SetCursorPos(origin[0] + cx, origin[1] + cy)
        time.sleep(0.045)
        win32gui.SendMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lp)
        time.sleep(random.uniform(0.20, 0.25))
        win32gui.SendMessage(hwnd, win32con.WM_LBUTTONUP, 0, lp)

    elif method_id == "st_3_cursor_msg_hover":
        origin = win32gui.ClientToScreen(hwnd, (0, 0))
        win32gui.SendMessage(hwnd, win32con.WM_ACTIVATE, win32con.WA_ACTIVE, 0)
        win32gui.SendMessage(hwnd, win32con.WM_SETFOCUS, 0, 0)
        ctypes.windll.user32.SetCursorPos(origin[0] + cx, origin[1] + cy)
        time.sleep(0.03)
        win32gui.SendMessage(hwnd, win32con.WM_MOUSEMOVE, 0, lp)
        win32gui.SendMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lp)
        time.sleep(random.uniform(0.20, 0.25))
        win32gui.SendMessage(hwnd, win32con.WM_LBUTTONUP, 0, lp)

    elif method_id == "st_4_no_cursor_send":
        win32gui.SendMessage(hwnd, win32con.WM_ACTIVATE, win32con.WA_ACTIVE, 0)
        win32gui.SendMessage(hwnd, win32con.WM_SETFOCUS, 0, 0)
        win32gui.SendMessage(hwnd, win32con.WM_MOUSEMOVE, 0, lp)
        win32gui.SendMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lp)
        time.sleep(random.uniform(0.15, 0.25))
        win32gui.SendMessage(hwnd, win32con.WM_LBUTTONUP, 0, lp)

    elif method_id == "st_5_cursor_post":
        origin = win32gui.ClientToScreen(hwnd, (0, 0))
        win32gui.SendMessage(hwnd, win32con.WM_ACTIVATE, win32con.WA_ACTIVE, 0)
        win32gui.SendMessage(hwnd, win32con.WM_SETFOCUS, 0, 0)
        ctypes.windll.user32.SetCursorPos(origin[0] + cx, origin[1] + cy)
        time.sleep(0.045)
        win32gui.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lp)
        time.sleep(random.uniform(0.20, 0.25))
        win32gui.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, lp)

    elif method_id == "st_6_mouse_event":
        origin = win32gui.ClientToScreen(hwnd, (0, 0))
        try:
            ctypes.windll.user32.SetForegroundWindow(hwnd)
        except Exception:
            pass
        ctypes.windll.user32.SetCursorPos(origin[0] + cx, origin[1] + cy)
        time.sleep(0.05)
        ctypes.windll.user32.mouse_event(0x0002, 0, 0, 0, 0)
        time.sleep(random.uniform(0.15, 0.25))
        ctypes.windll.user32.mouse_event(0x0004, 0, 0, 0, 0)

def scroll_test_dispatch(method_id, hwnd, client_x, from_y, to_y, steps=25):
    cx, fy, ty = int(client_x), int(from_y), int(to_y)

    if method_id in ("gp_1_post_no_hover", "gp_2_post_hover",
                     "gp_5_triple_hover", "gp_6_fg_hover"):
        if method_id == "gp_6_fg_hover":
            try:
                ctypes.windll.user32.SetForegroundWindow(hwnd)
            except Exception:
                pass
        win32gui.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON,
                             win32api.MAKELONG(cx, fy))
        time.sleep(0.06)
        for i in range(1, steps + 1):
            iy = fy + int((ty - fy) * i / steps)
            win32gui.PostMessage(hwnd, win32con.WM_MOUSEMOVE, win32con.MK_LBUTTON,
                                 win32api.MAKELONG(cx, iy))
            time.sleep(0.04)
        win32gui.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, win32api.MAKELONG(cx, ty))

    elif method_id in ("gp_3_send_hover", "gp_4_mixed_hover"):
        win32gui.SendMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON,
                             win32api.MAKELONG(cx, fy))
        time.sleep(0.06)
        for i in range(1, steps + 1):
            iy = fy + int((ty - fy) * i / steps)
            win32gui.SendMessage(hwnd, win32con.WM_MOUSEMOVE, win32con.MK_LBUTTON,
                                 win32api.MAKELONG(cx, iy))
            time.sleep(0.04)
        win32gui.SendMessage(hwnd, win32con.WM_LBUTTONUP, 0, win32api.MAKELONG(cx, ty))

    elif method_id in ("ld_1_child_no_hover", "ld_2_child_post_hover", "ld_6_child_triple_hover"):
        child = _find_best_child(hwnd)
        target = child if child else hwnd
        scx, sfy = _child_coords(hwnd, child, cx, fy) if child else (cx, fy)
        _, sty = _child_coords(hwnd, child, cx, ty) if child else (cx, ty)
        scx, sfy, sty = int(scx), int(sfy), int(sty)
        win32gui.PostMessage(target, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON,
                             win32api.MAKELONG(scx, sfy))
        time.sleep(0.06)
        for i in range(1, steps + 1):
            iy = sfy + int((sty - sfy) * i / steps)
            win32gui.PostMessage(target, win32con.WM_MOUSEMOVE, win32con.MK_LBUTTON,
                                 win32api.MAKELONG(scx, iy))
            time.sleep(0.04)
        win32gui.PostMessage(target, win32con.WM_LBUTTONUP, 0, win32api.MAKELONG(scx, sty))

    elif method_id == "ld_3_child_send_hover":
        child = _find_best_child(hwnd)
        target = child if child else hwnd
        scx, sfy = _child_coords(hwnd, child, cx, fy) if child else (cx, fy)
        _, sty = _child_coords(hwnd, child, cx, ty) if child else (cx, ty)
        scx, sfy, sty = int(scx), int(sfy), int(sty)
        win32gui.SendMessage(target, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON,
                             win32api.MAKELONG(scx, sfy))
        time.sleep(0.06)
        for i in range(1, steps + 1):
            iy = sfy + int((sty - sfy) * i / steps)
            win32gui.SendMessage(target, win32con.WM_MOUSEMOVE, win32con.MK_LBUTTON,
                                 win32api.MAKELONG(scx, iy))
            time.sleep(0.04)
        win32gui.SendMessage(target, win32con.WM_LBUTTONUP, 0, win32api.MAKELONG(scx, sty))

    elif method_id == "ld_4_parent_post_hover":
        win32gui.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON,
                             win32api.MAKELONG(cx, fy))
        time.sleep(0.06)
        for i in range(1, steps + 1):
            iy = fy + int((ty - fy) * i / steps)
            win32gui.PostMessage(hwnd, win32con.WM_MOUSEMOVE, win32con.MK_LBUTTON,
                                 win32api.MAKELONG(cx, iy))
            time.sleep(0.04)
        win32gui.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, win32api.MAKELONG(cx, ty))

    elif method_id == "ld_5_parent_send_hover":
        win32gui.SendMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON,
                             win32api.MAKELONG(cx, fy))
        time.sleep(0.06)
        for i in range(1, steps + 1):
            iy = fy + int((ty - fy) * i / steps)
            win32gui.SendMessage(hwnd, win32con.WM_MOUSEMOVE, win32con.MK_LBUTTON,
                                 win32api.MAKELONG(cx, iy))
            time.sleep(0.04)
        win32gui.SendMessage(hwnd, win32con.WM_LBUTTONUP, 0, win32api.MAKELONG(cx, ty))

    elif method_id in ("st_1_cursor_activate_send", "st_2_fg_cursor_send",
                       "st_3_cursor_msg_hover", "st_5_cursor_post", "st_6_mouse_event"):
        origin = win32gui.ClientToScreen(hwnd, (0, 0))
        win32gui.SendMessage(hwnd, win32con.WM_ACTIVATE, win32con.WA_ACTIVE, 0)
        win32gui.SendMessage(hwnd, win32con.WM_SETFOCUS, 0, 0)
        ctypes.windll.user32.SetCursorPos(origin[0] + cx, origin[1] + fy)
        time.sleep(0.02)
        win32gui.SendMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON,
                             win32api.MAKELONG(cx, fy))
        time.sleep(0.06)
        for i in range(1, steps + 1):
            iy = fy + int((ty - fy) * i / steps)
            ctypes.windll.user32.SetCursorPos(origin[0] + cx, origin[1] + iy)
            win32gui.PostMessage(hwnd, win32con.WM_MOUSEMOVE, win32con.MK_LBUTTON,
                                 win32api.MAKELONG(cx, iy))
            time.sleep(0.04)
        win32gui.SendMessage(hwnd, win32con.WM_LBUTTONUP, 0, win32api.MAKELONG(cx, ty))

    elif method_id == "st_4_no_cursor_send":
        win32gui.SendMessage(hwnd, win32con.WM_ACTIVATE, win32con.WA_ACTIVE, 0)
        win32gui.SendMessage(hwnd, win32con.WM_SETFOCUS, 0, 0)
        win32gui.SendMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON,
                             win32api.MAKELONG(cx, fy))
        time.sleep(0.06)
        for i in range(1, steps + 1):
            iy = fy + int((ty - fy) * i / steps)
            win32gui.SendMessage(hwnd, win32con.WM_MOUSEMOVE, win32con.MK_LBUTTON,
                                 win32api.MAKELONG(cx, iy))
            time.sleep(0.04)
        win32gui.SendMessage(hwnd, win32con.WM_LBUTTONUP, 0, win32api.MAKELONG(cx, ty))

    time.sleep(0.3)