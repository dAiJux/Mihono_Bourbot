import cv2
import ctypes.wintypes
import json
import numpy as np
import win32gui
import win32ui
import win32con
from typing import Tuple, Optional, List
from pathlib import Path

CAPTUREBLT = 0x40000000

GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
DWMWA_CLOAKED = 14

_dwmapi = ctypes.windll.dwmapi

def _is_cloaked(hwnd: int) -> bool:
    val = ctypes.wintypes.DWORD(0)
    hr = _dwmapi.DwmGetWindowAttribute(
        hwnd, DWMWA_CLOAKED, ctypes.byref(val), ctypes.sizeof(val),
    )
    return hr == 0 and val.value != 0

def _is_real_window(hwnd: int, exclude_pid: int = 0) -> bool:
    if not win32gui.IsWindowVisible(hwnd):
        return False
    title = win32gui.GetWindowText(hwnd)
    if not title or not title.strip():
        return False
    ex_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    if ex_style & WS_EX_TOOLWINDOW:
        return False
    if _is_cloaked(hwnd):
        return False
    if exclude_pid:
        pid = ctypes.wintypes.DWORD()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == exclude_pid:
            return False
    try:
        r = win32gui.GetClientRect(hwnd)
        if r[2] < 50 or r[3] < 50:
            return False
    except Exception:
        return False
    return True

class CaptureMixin:

    @staticmethod
    def enumerate_visible_windows(exclude_pid: int = 0) -> List[Tuple[int, str]]:
        results: List[Tuple[int, str]] = []
        def callback(hwnd, _):
            if _is_real_window(hwnd, exclude_pid):
                results.append((hwnd, win32gui.GetWindowText(hwnd)))
        win32gui.EnumWindows(callback, None)
        return results

    @staticmethod
    def capture_window_thumbnail(hwnd, max_size=(400, 350)):
        try:
            rect = win32gui.GetWindowRect(hwnd)
            w = rect[2] - rect[0]
            h = rect[3] - rect[1]
            if w <= 0 or h <= 0:
                return None, (0, 0)

            client_rect = win32gui.GetClientRect(hwnd)
            cw, ch = client_rect[2], client_rect[3]
            client_origin = win32gui.ClientToScreen(hwnd, (0, 0))
            off_x = client_origin[0] - rect[0]
            off_y = client_origin[1] - rect[1]

            hwnd_dc = win32gui.GetWindowDC(hwnd)
            mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
            save_dc = mfc_dc.CreateCompatibleDC()
            bitmap = win32ui.CreateBitmap()
            bitmap.CreateCompatibleBitmap(mfc_dc, w, h)
            save_dc.SelectObject(bitmap)

            ctypes.windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 0x00000002)

            bmp_info = bitmap.GetInfo()
            bmp_data = bitmap.GetBitmapBits(True)
            img = np.frombuffer(bmp_data, dtype=np.uint8)
            img = img.reshape((bmp_info['bmHeight'], bmp_info['bmWidth'], 4))

            win32gui.DeleteObject(bitmap.GetHandle())
            save_dc.DeleteDC()
            mfc_dc.DeleteDC()
            win32gui.ReleaseDC(hwnd, hwnd_dc)

            if off_x > 0 or off_y > 0:
                img = img[off_y:off_y + ch, off_x:off_x + cw]

            from PIL import Image
            pil_img = Image.frombuffer(
                "RGBA", (img.shape[1], img.shape[0]),
                img.tobytes(), "raw", "BGRA", 0, 1,
            )
            pil_img.thumbnail(max_size, Image.LANCZOS)
            return pil_img, (cw, ch)
        except Exception:
            return None, (0, 0)

    def find_game_window(self):
        saved_title = self.config.get("window_title", "")
        if saved_title:
            candidates = []
            def enum_saved(hwnd, _):
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    if title == saved_title:
                        candidates.append(hwnd)
            win32gui.EnumWindows(enum_saved, None)
            if candidates:
                self.game_hwnd = candidates[0]
                self.logger.info(f"Game window found (saved): {win32gui.GetWindowText(self.game_hwnd)}")
                return

        candidates = []
        def enum_handler(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd).lower()
                if not title:
                    return
                if any(excl in title for excl in self.EXCLUDED_WINDOW_KEYWORDS):
                    return
                if any(kw in title for kw in self.GAME_WINDOW_TITLES):
                    candidates.append(hwnd)
        win32gui.EnumWindows(enum_handler, None)
        if candidates:
            self.game_hwnd = candidates[0]
            self.logger.info(f"Game window found: {win32gui.GetWindowText(self.game_hwnd)}")
        else:
            self.game_hwnd = None

    def calibrate_screen(self) -> bool:
        self.find_game_window()
        return self.game_hwnd is not None

    def _load_calibration(self) -> dict:
        cal_path = Path("config", "calibration.json")
        cal = {}
        if cal_path.exists():
            try:
                with open(cal_path, encoding="utf-8") as f:
                    cal = json.load(f)
            except Exception:
                pass
        if not cal:
            old = self.config.get("roi_calibration", {})
            if old:
                for key in ["game_rect", "energy_bar", "support_region", "event_text", "event_choices"]:
                    if key in old:
                        cal[key] = old[key]
                tp = old.get("training_positions", {})
                for name, pos in tp.items():
                    cal[f"train_{name}"] = pos
        platform = getattr(self, 'config', {}).get("platform", "google_play")
        if platform == "steam":
            steam_overrides = {}
            steam_path = Path("config", "calibration_steam.json")
            if steam_path.exists():
                try:
                    with open(steam_path, encoding="utf-8") as f:
                        steam_overrides = json.load(f)
                except Exception:
                    pass
            gp_rect = cal.get("game_rect", {})
            steam_rect = cal.get("steam_game_rect", {})
            if gp_rect and steam_rect and "x1" in gp_rect and "x1" in steam_rect:
                gp_w = gp_rect["x2"] - gp_rect["x1"]
                steam_w = steam_rect["x2"] - steam_rect["x1"]
                if steam_w > 0 and gp_w > 0 and abs(steam_w - gp_w) / gp_w > 0.02:
                    x_ratio = gp_w / steam_w
                    x_offset = (1.0 - x_ratio) / 2.0
                    skip = {"game_rect", "steam_game_rect"}
                    for key in list(cal.keys()):
                        if key in skip or key in steam_overrides:
                            continue
                        val = cal[key]
                        if not isinstance(val, dict):
                            continue
                        if "x1" in val and "x2" in val:
                            cal[key] = {
                                "x1": round(val["x1"] * x_ratio + x_offset, 4),
                                "y1": val.get("y1", 0),
                                "x2": round(val["x2"] * x_ratio + x_offset, 4),
                                "y2": val.get("y2", 0),
                            }
                        elif "x" in val:
                            new_val = dict(val)
                            new_val["x"] = round(val["x"] * x_ratio + x_offset, 4)
                            cal[key] = new_val
            cal.update(steam_overrides)
        elif platform == "ldplayer":
            ldp_overrides = {}
            ldp_path = Path("config", "calibration_ldplayer.json")
            if ldp_path.exists():
                try:
                    with open(ldp_path, encoding="utf-8") as f:
                        ldp_overrides = json.load(f)
                except Exception:
                    pass
            gp_rect = cal.get("game_rect", {})
            ldp_rect = cal.get("ldplayer_game_rect", {})
            if gp_rect and ldp_rect and "x1" in gp_rect and "x1" in ldp_rect:
                gp_w = gp_rect["x2"] - gp_rect["x1"]
                ldp_w = ldp_rect["x2"] - ldp_rect["x1"]
                if ldp_w > 0 and gp_w > 0 and abs(ldp_w - gp_w) / gp_w > 0.02:
                    x_ratio = gp_w / ldp_w
                    x_offset = (1.0 - x_ratio) / 2.0
                    skip = {"game_rect", "ldplayer_game_rect"}
                    for key in list(cal.keys()):
                        if key in skip or key in ldp_overrides:
                            continue
                        val = cal[key]
                        if not isinstance(val, dict):
                            continue
                        if "x1" in val and "x2" in val:
                            cal[key] = {
                                "x1": round(val["x1"] * x_ratio + x_offset, 4),
                                "y1": val.get("y1", 0),
                                "x2": round(val["x2"] * x_ratio + x_offset, 4),
                                "y2": val.get("y2", 0),
                            }
                        elif "x" in val:
                            new_val = dict(val)
                            new_val["x"] = round(val["x"] * x_ratio + x_offset, 4)
                            cal[key] = new_val
            cal.update(ldp_overrides)
        return cal

    def _aspect_x_factor(self, gw: int, gh: int) -> float:
        return 1.0

    def _get_search_area(self, template_name: str, screenshot: np.ndarray):
        cal_name = self._CAL_ALIASES.get(template_name, template_name)
        region = self._calibration.get(cal_name)
        if region and "x1" in region:
            gx, gy, gw, gh = self.get_game_rect(screenshot)
            x1 = max(0, gx + int(gw * region["x1"]))
            y1 = max(0, gy + int(gh * region["y1"]))
            x2 = min(screenshot.shape[1], gx + int(gw * region["x2"]))
            y2 = min(screenshot.shape[0], gy + int(gh * region["y2"]))
            if x2 > x1 and y2 > y1:
                return screenshot[y1:y2, x1:x2], x1, y1
        return screenshot, 0, 0

    def cal_rect(self, screenshot: np.ndarray, region: dict):
        gx, gy, gw, gh = self.get_game_rect(screenshot)
        x1 = max(0, gx + int(gw * region.get("x1", 0.0)))
        y1 = max(0, gy + int(gh * region.get("y1", 0.0)))
        x2 = min(screenshot.shape[1], gx + int(gw * region.get("x2", 1.0)))
        y2 = min(screenshot.shape[0], gy + int(gh * region.get("y2", 1.0)))
        return x1, y1, x2, y2

    def get_game_rect(self, screenshot: np.ndarray) -> Tuple[int, int, int, int]:
        h, w = screenshot.shape[:2]
        cache = getattr(self, '_auto_game_rect_cache', None)
        if cache and cache[0] == h and cache[1] == w:
            return cache[2]
        result = self._resolve_game_rect(screenshot)
        self._auto_game_rect_cache = (h, w, result)
        return result

    def _resolve_game_rect(self, screenshot: np.ndarray) -> Tuple[int, int, int, int]:
        h, w = screenshot.shape[:2]
        game_w = h * 9 // 16
        platform = self.config.get("platform", "google_play")

        if platform == "steam":
            steam_rect = self._calibration.get("steam_game_rect")
            if steam_rect:
                gx = int(w * steam_rect["x1"])
                gy = int(h * steam_rect["y1"])
                gw = int(w * steam_rect["x2"]) - gx
                gh = int(h * steam_rect["y2"]) - gy
                return (gx, gy, max(1, gw), max(1, gh))
            anchor_result = self._find_anchor_game_rect(screenshot)
            if anchor_result is not None:
                return anchor_result
            return self._auto_detect_game_rect(screenshot)

        if platform == "ldplayer":
            ldp_rect = self._calibration.get("ldplayer_game_rect")
            if ldp_rect:
                gx = int(w * ldp_rect["x1"])
                gy = int(h * ldp_rect["y1"])
                gw = int(w * ldp_rect["x2"]) - gx
                gh = int(h * ldp_rect["y2"]) - gy
                return (gx, gy, max(1, gw), max(1, gh))

        if w <= int(game_w * 1.05):
            return (max(0, (w - game_w) // 2), 0, game_w, h)
        gr = self._calibration.get("game_rect")
        if gr:
            gx = int(w * gr["x1"])
            gy = int(h * gr["y1"])
            gw = int(w * gr["x2"]) - gx
            gh = int(h * gr["y2"]) - gy
            return (gx, gy, max(1, gw), max(1, gh))
        anchor_result = self._find_anchor_game_rect(screenshot)
        if anchor_result is not None:
            return anchor_result
        return self._auto_detect_game_rect(screenshot)

    def _match_anchor(self, screenshot: np.ndarray, name: str, scales: list):
        h, w = screenshot.shape[:2]
        path = self.get_template_path(name)
        if path is None:
            return None, 0.0
        tpl = cv2.imread(str(path))
        if tpl is None:
            return None, 0.0
        best_conf = 0.0
        best_loc = None
        best_size = (0, 0)
        for sf in scales:
            nw = max(1, int(tpl.shape[1] * sf))
            nh = max(1, int(tpl.shape[0] * sf))
            if nh > h or nw > w:
                continue
            interp = cv2.INTER_AREA if sf < 1.0 else cv2.INTER_LINEAR
            resized = cv2.resize(tpl, (nw, nh), interpolation=interp)
            res = cv2.matchTemplate(screenshot, resized, cv2.TM_CCOEFF_NORMED)
            _, mv, _, ml = cv2.minMaxLoc(res)
            if mv > best_conf:
                best_conf = mv
                best_loc = ml
                best_size = (nw, nh)
        if best_conf >= 0.60 and best_loc is not None:
            return (best_loc[0], best_loc[1], best_size[0], best_size[1]), best_conf
        return None, best_conf

    def _find_anchor_game_rect(self, screenshot: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
        h, w = screenshot.shape[:2]
        game_w_fallback = h * 9 // 16
        ref_w = getattr(self, '_ref_width', None)
        if ref_w:
            base = game_w_fallback / ref_w
            scales = [base * f for f in (0.80, 0.85, 0.90, 0.95, 1.0, 1.05, 1.10, 1.15, 1.20)]
        else:
            scales = [0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.4, 1.6]
        left_match, left_conf = self._match_anchor(screenshot, "anchor_left", scales)
        right_match, right_conf = self._match_anchor(screenshot, "anchor_right", scales)
        left_x = None
        right_x = None
        if left_match:
            left_x = left_match[0]
        if right_match:
            right_x = right_match[0] + right_match[2]
        if left_x is not None and right_x is not None:
            gx = left_x
            gw = max(1, right_x - left_x)
            return (max(0, gx), 0, gw, h)
        if left_x is not None:
            return (max(0, left_x), 0, game_w_fallback, h)
        if right_x is not None:
            gx = max(0, right_x - game_w_fallback)
            return (gx, 0, game_w_fallback, h)
        return None

    def _auto_detect_game_rect(self, screenshot: np.ndarray) -> Tuple[int, int, int, int]:
        h, w = screenshot.shape[:2]
        game_w = h * 9 // 16
        if w <= int(game_w * 1.05):
            return (max(0, (w - game_w) // 2), 0, game_w, h)
        btn_templates = []
        cal_names = getattr(self, '_CALIBRATION_TEMPLATES', [
            "btn_training", "btn_rest", "btn_races", "btn_recreation",
        ])
        aliases = getattr(self, '_TPL_FILE_ALIASES', {})
        for name in cal_names:
            fn = aliases.get(name, name)
            path = self.get_template_path(fn)
            if path is None:
                continue
            img = cv2.imread(str(path))
            if img is not None:
                btn_templates.append(img)
        if not btn_templates:
            return ((w - game_w) // 2, 0, game_w, h)
        ref_w = getattr(self, '_ref_width', None)
        if ref_w:
            base = game_w / ref_w
            scales = [base * f for f in (0.85, 0.92, 1.0, 1.08, 1.15)]
        else:
            scales = [0.5, 0.65, 0.8, 0.9, 1.0, 1.1, 1.2, 1.4, 1.6]
        match_xs = []
        for tpl in btn_templates:
            best_conf = 0.0
            best_cx = 0
            for sf in scales:
                if sf <= 0.1:
                    continue
                nw = max(1, int(tpl.shape[1] * sf))
                nh = max(1, int(tpl.shape[0] * sf))
                if nh > h or nw > w:
                    continue
                interp = cv2.INTER_AREA if sf < 1.0 else cv2.INTER_LINEAR
                resized = cv2.resize(tpl, (nw, nh), interpolation=interp)
                res = cv2.matchTemplate(screenshot, resized, cv2.TM_CCOEFF_NORMED)
                _, mv, _, ml = cv2.minMaxLoc(res)
                if mv > best_conf:
                    best_conf = mv
                    best_cx = ml[0] + nw // 2
            if best_conf >= 0.55:
                match_xs.append(best_cx)
        if not match_xs:
            return ((w - game_w) // 2, 0, game_w, h)
        min_x = min(match_xs)
        max_x = max(match_xs)
        padding = int(game_w * 0.05)
        low = max_x + padding - game_w
        high = min_x - padding
        game_x = (low + high) // 2
        game_x = max(0, min(w - game_w, game_x))
        return (game_x, 0, game_w, h)

    def game_pos(self, screenshot: np.ndarray, rel_x: float, rel_y: float) -> Tuple[int, int]:
        gx, gy, gw, gh = self.get_game_rect(screenshot)
        return (gx + int(gw * rel_x), gy + int(gh * rel_y))

    def take_screenshot(self) -> np.ndarray:
        if not self.game_hwnd or not win32gui.IsWindow(self.game_hwnd):
            self.find_game_window()
        if not self.game_hwnd:
            return np.zeros((1920, 1080, 3), dtype=np.uint8)
        try:
            rect = win32gui.GetWindowRect(self.game_hwnd)
            w = rect[2] - rect[0]
            h = rect[3] - rect[1]
            if w <= 0 or h <= 0:
                return np.zeros((1920, 1080, 3), dtype=np.uint8)

            try:
                client_origin = win32gui.ClientToScreen(self.game_hwnd, (0, 0))
                off_x = client_origin[0] - rect[0]
                off_y = client_origin[1] - rect[1]
                client_rect = win32gui.GetClientRect(self.game_hwnd)
                cw, ch = client_rect[2], client_rect[3]
            except Exception:
                off_x, off_y = 0, 0
                cw, ch = w, h

            hwnd_dc = win32gui.GetWindowDC(self.game_hwnd)
            mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
            save_dc = mfc_dc.CreateCompatibleDC()
            bitmap = win32ui.CreateBitmap()
            bitmap.CreateCompatibleBitmap(mfc_dc, w, h)
            save_dc.SelectObject(bitmap)

            PW_RENDERFULLCONTENT = 0x00000002
            ctypes.windll.user32.PrintWindow(
                self.game_hwnd, save_dc.GetSafeHdc(), PW_RENDERFULLCONTENT
            )

            bmp_info = bitmap.GetInfo()
            bmp_data = bitmap.GetBitmapBits(True)
            img = np.frombuffer(bmp_data, dtype=np.uint8)
            img = img.reshape((bmp_info['bmHeight'], bmp_info['bmWidth'], 4))
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

            win32gui.DeleteObject(bitmap.GetHandle())
            save_dc.DeleteDC()
            mfc_dc.DeleteDC()
            win32gui.ReleaseDC(self.game_hwnd, hwnd_dc)

            if np.mean(img) < 5:
                self.logger.warning("PrintWindow returned black, falling back to BitBlt")
                img = self._capture_bitblt(rect, w, h)
                if img is None:
                    return self.last_screenshot if self.last_screenshot is not None else np.zeros((1920, 1080, 3), dtype=np.uint8)

            if off_x > 0 or off_y > 0:
                img = img[off_y:off_y + ch, off_x:off_x + cw]

            self._client_offset_x = 0
            self._client_offset_y = 0
            self.last_screenshot = img
            return img
        except Exception as e:
            self.logger.error(f"Screenshot failed: {e}")
            return self.last_screenshot if self.last_screenshot is not None else np.zeros((1920, 1080, 3), dtype=np.uint8)

    def _capture_bitblt(self, rect, w, h) -> Optional[np.ndarray]:
        try:
            x, y = rect[0], rect[1]
            hdesktop = win32gui.GetDesktopWindow()
            desktop_dc = win32gui.GetWindowDC(hdesktop)
            img_dc = win32ui.CreateDCFromHandle(desktop_dc)
            mem_dc = img_dc.CreateCompatibleDC()
            screenshot = win32ui.CreateBitmap()
            screenshot.CreateCompatibleBitmap(img_dc, w, h)
            mem_dc.SelectObject(screenshot)
            mem_dc.BitBlt((0, 0), (w, h), img_dc, (x, y), win32con.SRCCOPY | CAPTUREBLT)
            bmpinfo = screenshot.GetInfo()
            bmpstr = screenshot.GetBitmapBits(True)
            img = np.frombuffer(bmpstr, dtype='uint8').reshape((bmpinfo['bmHeight'], bmpinfo['bmWidth'], 4))
            img = cv2.cvtColor(np.ascontiguousarray(img), cv2.COLOR_BGRA2BGR)
            win32gui.DeleteObject(screenshot.GetHandle())
            mem_dc.DeleteDC()
            img_dc.DeleteDC()
            win32gui.ReleaseDC(hdesktop, desktop_dc)
            return img
        except Exception as e:
            self.logger.error(f"BitBlt fallback also failed: {e}")
            return None

    def save_debug_screenshot(self, name: str):
        if self.last_screenshot is not None:
            Path("logs/debug").mkdir(parents=True, exist_ok=True)
            cv2.imwrite(f"logs/debug/{name}.png", self.last_screenshot)