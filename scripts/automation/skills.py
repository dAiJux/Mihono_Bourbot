import time
import json
import numpy as np
import cv2
import ctypes
import win32api
import win32con
import win32gui
from difflib import SequenceMatcher
from pathlib import Path
from typing import List
from ..vision.ocr import _ocr_text_raw
from ..models import GameScreen

try:
    from rapidfuzz.distance import Levenshtein as _lev
    def _similarity(a: str, b: str) -> float:
        return _lev.normalized_similarity(a, b)
except ImportError:
    def _similarity(a: str, b: str) -> float:
        a, b = a.lower(), b.lower()
        if not a or not b:
            return 0.0
        la, lb = len(a), len(b)
        dp = list(range(lb + 1))
        for i in range(1, la + 1):
            prev = dp[0]
            dp[0] = i
            for j in range(1, lb + 1):
                temp = dp[j]
                dp[j] = prev if a[i-1] == b[j-1] else 1 + min(prev, dp[j], dp[j-1])
                prev = temp
        return 1.0 - dp[lb] / max(la, lb)

import re as _re

def _normalize_skill(s: str) -> str:
    s = s.lower()
    s = _re.sub(r"[○◎!'\"]", "", s)
    s = _re.sub(r"\s+", " ", s).strip()
    return s

_SKILL_MATCH_THRESHOLD = 0.80

def _is_skill_match(text: str, wishlist: List[str]) -> bool:
    norm_text = _normalize_skill(text)
    if not norm_text:
        return False
    for skill in wishlist:
        norm_skill = _normalize_skill(skill)
        if _similarity(norm_text, norm_skill) >= _SKILL_MATCH_THRESHOLD:
            return True
        skill_words = set(norm_skill.split())
        text_words = set(norm_text.split())
        if skill_words and skill_words.issubset(text_words):
            return True
    return False

class SkillsMixin:

    _skill_check_turn: int = 0

    def should_check_skills(self, current_turn: int) -> bool:
        interval = self.config.get("skill_check_interval", 8)
        wishlist = self.config.get("skill_wishlist", [])
        if not wishlist:
            return False
        if current_turn - self._skill_check_turn >= interval:
            self._skill_check_turn = current_turn
            return True
        return False

    def _defer_skill_check(self, current_turn: int):
        interval = self.config.get("skill_check_interval", 8)
        self._skill_check_turn = current_turn - interval + 1

    def is_on_skill_screen(self, screenshot=None) -> bool:
        if screenshot is None:
            screenshot = self.vision.take_screenshot()
        if self.vision.find_template("learn_btn", screenshot, threshold=0.72):
            return True
        if self.vision.find_template("confirm_btn", screenshot, threshold=0.72):
            return True
        return False

    def execute_skill_check(self, current_turn: int = 0) -> bool:
        wishlist = self.config.get("skill_wishlist", [])
        if not wishlist:
            return False

        self.logger.info(f"Skill check — wishlist: {wishlist}")
        screenshot = self.vision.take_screenshot()
        screen = self.vision.detect_screen(screenshot)

        if screen in (GameScreen.EVENT,):
            self.logger.info(
                f"Skill check deferred — currently on {screen.value} screen, will retry next turn"
            )
            self._defer_skill_check(current_turn)
            return False

        if self.vision.find_template("btn_race_start", screenshot, 0.70) or \
                self.vision.find_template("btn_race_start_ura", screenshot, 0.70):
            self.logger.info("Skill check deferred — mandatory race detected, will retry next turn")
            self._defer_skill_check(current_turn)
            return False
        screenshot = self.vision.take_screenshot()

        skills_pos = self.vision.find_template("btn_skills", screenshot, threshold=0.72)
        if not skills_pos:
            self.logger.debug("Skills button not found — skipping skill check")
            return False

        self.click_with_offset(*skills_pos)
        self.wait(1.5)

        for _ in range(6):
            if self._check_stopped():
                return False
            screenshot = self.vision.take_screenshot()
            if self.is_on_skill_screen(screenshot):
                break
            time.sleep(0.8)
        else:
            self.logger.debug("Could not reach skill screen — closing")
            self._close_skill_screen()
            return False

        shopping_list = self._scroll_and_collect_skills(wishlist)

        if shopping_list:
            self.logger.info(f"Skills selected: {shopping_list} — confirming purchase")
            screenshot = self.vision.take_screenshot()
            if not self.click_button("confirm_btn", screenshot, threshold=0.72):
                self.click_button("btn_confirm", screenshot, threshold=0.72)
            time.sleep(1.5)
            screenshot = self.vision.take_screenshot()
            if not self.click_button("learn_btn", screenshot, threshold=0.72):
                self.logger.warning("learn_btn not found after confirm")
            time.sleep(2.0)

            self.logger.info("Waiting for Skills Learned popup close button...")
            tpl_close = cv2.imread(str(Path("templates/skills/btn_close.png")))
            for attempt in range(10):
                screenshot = self.vision.take_screenshot()
                gx, gy, gw, gh = self.vision.get_game_rect(screenshot)
                game = screenshot[gy:gy+gh, gx:gx+gw]
                found = False
                if tpl_close is not None and tpl_close.shape[0] <= game.shape[0] and tpl_close.shape[1] <= game.shape[1]:
                    res = cv2.matchTemplate(game, tpl_close, cv2.TM_CCOEFF_NORMED)
                    _, mv, _, ml = cv2.minMaxLoc(res)
                    if mv >= 0.82:
                        cx = gx + ml[0] + tpl_close.shape[1] // 2
                        cy = gy + ml[1] + tpl_close.shape[0] // 2
                        self.logger.info(f"Skills Learned popup (attempt {attempt+1}) — btn_close at ({cx},{cy}) conf={mv:.3f}")
                        self.click_with_offset(cx, cy)
                        time.sleep(1.2)
                        found = True
                if not found:
                    pos = self.vision.find_template("btn_close", screenshot, threshold=0.82)
                    if pos:
                        self.logger.info(f"Skills Learned popup (attempt {attempt+1}) — btn_close fallback at {pos}")
                        self.click_with_offset(*pos)
                        time.sleep(1.2)
                        found = True
                if found:
                    break
                self.logger.info(f"Skills Learned popup (attempt {attempt+1}) — btn_close not found")
                time.sleep(0.4)
        else:
            self.logger.info("No matching skills found in wishlist — closing")

        self.logger.info("Exiting skill screen...")
        for attempt in range(8):
            if self._check_stopped():
                return bool(shopping_list)
            screenshot = self.vision.take_screenshot()
            screen = self.vision.detect_screen(screenshot)
            self.logger.info(f"Exit skill screen (attempt {attempt+1}) — screen={screen.value}")
            if screen == GameScreen.MAIN:
                self.logger.info("Skill check complete — back on main screen")
                return bool(shopping_list)
            if self.vision.find_template("btn_back", screenshot, threshold=0.72):
                self.logger.info("Skill screen: exiting via btn_back")
                self.click_button("btn_back", screenshot, threshold=0.72)
                time.sleep(1.5)
                continue
            time.sleep(0.5)

        return bool(shopping_list)

    def _scroll_and_collect_skills(self, wishlist: List[str]) -> List[str]:
        shopping_list: List[str] = []
        screenshot = self.vision.take_screenshot()
        gx, gy, gw, gh = self.vision.get_game_rect(screenshot)

        scroll_x = gx + gw // 2
        scroll_from_y = gy + int(gh * 0.65)
        scroll_to_y   = gy + int(gh * 0.45)

        prev_icon_positions = None
        stable_count = 0
        max_scrolls = 20

        for scroll_attempt in range(max_scrolls):
            if self._check_stopped():
                break

            screenshot = self.vision.take_screenshot()

            buy_icons = self.vision.find_all_template(
                "buy_skill", screenshot, threshold=0.82, min_distance=20
            )
            visible = [
                (icon_x, icon_y) for icon_x, icon_y in buy_icons
                if gy + int(gh * 0.20) < icon_y < gy + int(gh * 0.92)
            ]
            self.logger.debug(f"Scroll {scroll_attempt}: {len(visible)} buy icons")

            current_positions = tuple(sorted((x, y) for x, y in visible))
            if prev_icon_positions is not None and current_positions == prev_icon_positions:
                stable_count += 1
                if stable_count >= 2:
                    self.logger.debug("Skill screen: end of list confirmed (same icons twice)")
                    break
            else:
                stable_count = 0

            for icon_x, icon_y in visible:
                if not self._is_buy_icon_active(screenshot, icon_x, icon_y):
                    self.logger.debug(f"Icon at ({icon_x},{icon_y}) inactive (not enough SP)")
                    continue

                skill_name = self._ocr_skill_name(screenshot, icon_x, icon_y, gx, gw, gh, gy)
                self.logger.debug(f"Skill OCR: '{skill_name}'")

                if _is_skill_match(skill_name, wishlist):
                    self.logger.info(f"Wishlist match '{skill_name}' — selecting")
                    self.click_with_offset(icon_x, icon_y)
                    time.sleep(0.5)
                    shopping_list.append(skill_name)
                else:
                    self.logger.debug(f"No wishlist match: '{skill_name}'")

            prev_icon_positions = current_positions
            self._scroll_skill_list(scroll_from_y, scroll_to_y, scroll_x)
            time.sleep(1.0)

        return shopping_list

    def _ocr_skill_name(
        self, screenshot: np.ndarray,
        icon_x: int, icon_y: int,
        gx: int, gw: int, gh: int, gy: int
    ) -> str:
        x1 = gx + int(gw * 0.08 * self.vision._aspect_x_factor(gw, gh))
        x2 = gx + int(gw * 0.73 * self.vision._aspect_x_factor(gw, gh))
        search_top = max(gy, icon_y - int(gh * 0.100))
        search_bot = max(gy + 1, icon_y - int(gh * 0.008))

        scan = screenshot[search_top:search_bot, x1:x2]
        if scan.size == 0:
            return ""

        gray_scan = cv2.cvtColor(scan, cv2.COLOR_BGR2GRAY).astype(float)

        edge_rows = []
        for rel_y in range(gray_scan.shape[0]):
            grad = float(np.abs(np.diff(gray_scan[rel_y])).mean())
            if grad > 2.0:
                edge_rows.append(rel_y)

        if not edge_rows:
            return ""

        clusters = []
        cluster = [edge_rows[0]]
        for r in edge_rows[1:]:
            if r - cluster[-1] <= 4:
                cluster.append(r)
            else:
                clusters.append(cluster)
                cluster = [r]
        clusters.append(cluster)

        scan_h = scan.shape[0]
        candidates = []
        for min_dist_frac in [0.10, 0.05, 0.02, 0]:
            min_dist = max(0, int(scan_h * min_dist_frac))
            candidates = [c for c in clusters if scan_h - max(c) > min_dist]
            if candidates:
                break
        if not candidates:
            return ""

        title_cluster = candidates[-1]
        t_y1 = max(0, min(title_cluster) - 3)
        t_y2 = min(scan.shape[0], max(title_cluster) + 6)
        roi = scan[t_y1:t_y2]
        if roi.size == 0:
            return ""

        scale = 3
        big = cv2.resize(roi, (roi.shape[1] * scale, roi.shape[0] * scale),
                         interpolation=cv2.INTER_CUBIC)
        gray = cv2.cvtColor(big, cv2.COLOR_BGR2GRAY)

        best_raw = ""
        for t in [100, 120, 80]:
            _, th = cv2.threshold(gray, t, 255, cv2.THRESH_BINARY_INV)
            dark_pct = float((th > 0).sum()) / max(1, th.size) * 100
            if 2.0 <= dark_pct <= 20.0:
                try:
                    candidate = _ocr_text_raw(th).strip()
                    if len(candidate) > len(best_raw):
                        best_raw = candidate
                except Exception:
                    pass
        if not best_raw:
            _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            try:
                best_raw = _ocr_text_raw(th).strip()
            except Exception:
                pass

        return self._snap_skill_name(best_raw)

    @staticmethod
    def _snap_skill_name(raw: str) -> str:
        if not raw:
            return ""
        try:
            db_path = Path("config") / "skills.json"
            if not db_path.exists():
                return raw
            with open(db_path, encoding="utf-8") as f:
                skills = json.load(f)
            names = [s["name"] for s in skills]
            raw_words = set(raw.lower().split())
            best_name = raw
            best_score = 0.0
            for n in names:
                n_words = set(n.lower().replace("◎", "").replace("○", "").split())
                if raw_words & n_words:
                    word_score = len(raw_words & n_words) / max(1, len(n_words))
                    seq_score = SequenceMatcher(None, raw.lower(), n.lower()).ratio()
                    score = word_score * 0.6 + seq_score * 0.4
                else:
                    score = SequenceMatcher(None, raw.lower(), n.lower()).ratio()
                if score > best_score:
                    best_score = score
                    best_name = n
            return best_name if best_score >= 0.25 else raw
        except Exception:
            return raw

    def _is_buy_icon_active(self, screenshot: np.ndarray, x: int, y: int, radius: int = 18) -> bool:
        y1 = max(0, y - radius)
        y2 = min(screenshot.shape[0], y + radius)
        x1 = max(0, x - radius)
        x2 = min(screenshot.shape[1], x + radius)
        roi = screenshot[y1:y2, x1:x2]
        if roi.size == 0:
            return False
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        green_mask = (
            (hsv[:, :, 0] >= 35) & (hsv[:, :, 0] <= 85) &
            (hsv[:, :, 1] >= 60) &
            (hsv[:, :, 2] >= 100)
        )
        green_ratio = float(np.sum(green_mask)) / max(1, roi.shape[0] * roi.shape[1])
        return green_ratio >= 0.10

    def _scroll_skill_list(self, from_y: int, to_y: int, x: int):
        hwnd = self.vision.game_hwnd
        if hwnd is None or not win32gui.IsWindow(hwnd):
            return
        x, from_y, to_y = int(x), int(from_y), int(to_y)
        if self._is_steam():
            origin = win32gui.ClientToScreen(hwnd, (0, 0))
            win32gui.SendMessage(hwnd, win32con.WM_ACTIVATE, win32con.WA_ACTIVE, 0)
            win32gui.SendMessage(hwnd, win32con.WM_SETFOCUS, 0, 0)
            ctypes.windll.user32.SetCursorPos(origin[0] + x, origin[1] + from_y)
            time.sleep(0.02)
        lp_start = win32api.MAKELONG(x, from_y)
        win32gui.SendMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lp_start)
        time.sleep(0.08)
        steps = 25
        for i in range(1, steps + 1):
            interp_y = from_y + int((to_y - from_y) * i / steps)
            if self._is_steam():
                ctypes.windll.user32.SetCursorPos(origin[0] + x, origin[1] + interp_y)
            lp_move = win32api.MAKELONG(x, interp_y)
            win32gui.PostMessage(hwnd, win32con.WM_MOUSEMOVE, win32con.MK_LBUTTON, lp_move)
            time.sleep(0.04)
        lp_end = win32api.MAKELONG(x, to_y)
        win32gui.SendMessage(hwnd, win32con.WM_LBUTTONUP, 0, lp_end)
        time.sleep(0.3)

    def _close_skill_screen(self):
        for _ in range(4):
            if self._check_stopped():
                return
            screenshot = self.vision.take_screenshot()
            if self.vision.find_template("btn_close", screenshot, threshold=0.82):
                self.logger.info("Skill screen: closing popup via btn_close")
                self.click_button("btn_close", screenshot, threshold=0.82)
                self.wait(0.8)
                continue
            if self.vision.find_template("btn_back", screenshot, threshold=0.75):
                self.logger.info("Skill screen: exiting via btn_back")
                self.click_button("btn_back", screenshot, threshold=0.75)
                self.wait(1.0)
                return
            break

    @staticmethod
    def _screenshot_hash(img: np.ndarray) -> int:
        small = cv2.resize(img, (16, 16), interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        mean = np.mean(gray)
        bits = (gray > mean).flatten()
        return int(sum(int(b) << i for i, b in enumerate(bits)))

    def detect_available_skills(self, screenshot=None) -> dict:
        if screenshot is None:
            screenshot = self.vision.take_screenshot()
        gold = self.vision.detect_gold_skill(screenshot)
        white = self.vision.detect_white_skill(screenshot)
        return {"gold": gold, "white": white, "total": len(gold) + len(white)}