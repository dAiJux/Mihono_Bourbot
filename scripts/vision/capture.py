import cv2
import ctypes
import json
import numpy as np
import win32gui
import win32ui
import win32con
from typing import Tuple, Optional
from pathlib import Path

CAPTUREBLT = 0x40000000

class CaptureMixin:

    def find_game_window(self):
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
        if cal_path.exists():
            try:
                with open(cal_path, encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        old = self.config.get("roi_calibration", {})
        if old:
            cal = {}
            for key in ["game_rect", "energy_bar", "support_region", "event_text", "event_choices"]:
                if key in old:
                    cal[key] = old[key]
            tp = old.get("training_positions", {})
            for name, pos in tp.items():
                cal[f"train_{name}"] = pos
            return cal
        return {}

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

    def get_game_rect(self, screenshot: np.ndarray) -> Tuple[int, int, int, int]:
        h, w = screenshot.shape[:2]
        gr = self._calibration.get("game_rect", None)
        if gr:
            gx = int(w * gr["x1"])
            gy = int(h * gr["y1"])
            gw = int(w * gr["x2"]) - gx
            gh = int(h * gr["y2"]) - gy
            return (gx, gy, max(1, gw), max(1, gh))
        game_w = h * 9 // 16
        game_x = (w - game_w) // 2
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