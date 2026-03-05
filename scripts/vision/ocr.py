import cv2
import numpy as np
import warnings
import easyocr as _easyocr
from collections import Counter
from typing import Tuple, Optional, List, Dict
from pathlib import Path

warnings.filterwarnings(
    "ignore",
    message=".*pin_memory.*no accelerator.*",
    category=UserWarning,
    module="torch",
)

_reader = None

def _get_reader():
    global _reader
    if _reader is None:
        _reader = _easyocr.Reader(['en'], gpu=False, verbose=False)
    return _reader


def _ocr_digits(img_np: np.ndarray) -> str:
    reader = _get_reader()
    results = reader.readtext(img_np, allowlist='0123456789', text_threshold=0.3)
    if not results:
        return ''
    results.sort(key=lambda r: r[0][0][0])
    return results[0][1]


def _ocr_text_raw(img_np: np.ndarray) -> str:
    reader = _get_reader()
    results = reader.readtext(img_np, text_threshold=0.3)
    results.sort(key=lambda r: r[0][0][1])
    return ' '.join(r[1] for r in results)


def _ocr_text_horizontal(img_np: np.ndarray) -> str:
    reader = _get_reader()
    results = reader.readtext(img_np, text_threshold=0.3)
    results.sort(key=lambda r: r[0][0][0])
    return ' '.join(r[1] for r in results)


class OcrMixin:

    _MONTH_MAP = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    }

    _YEAR_ORDER = {"junior": 0, "classic": 1, "senior": 2}

    STAT_NAMES = ["speed", "stamina", "power", "guts", "wit"]

    _STAT_COLUMNS = {
        "speed":   (0.138, 0.270),
        "stamina": (0.270, 0.402),
        "power":   (0.402, 0.533),
        "guts":    (0.533, 0.662),
        "wit":     (0.662, 0.796),
    }

    _MOOD_HUE_RANGES = {
        "great":  (155, 180),
        "good":   (3, 14),
        "normal": (14, 40),
        "bad":    (85, 120),
        "awful":  (120, 155),
    }
    _MIN_BADGE_PX = 300

    def read_all_stats(self, screenshot: np.ndarray) -> Dict[str, int]:
        return {s: self.read_stat_value(s, screenshot) for s in ["speed", "stamina", "power", "guts", "wit"]}

    def read_stat_value(self, stat_name: str, screenshot: np.ndarray) -> int:
        gx, gy, gw, gh = self.get_game_rect(screenshot)
        xf = self._aspect_x_factor(gw, gh)
        cal = self._calibration.get(f"stat_{stat_name}", {})
        if cal and "x1" in cal:
            x = gx + int(gw * cal["x1"] * xf)
            y = gy + int(gh * cal["y1"])
            rw = int(gw * (cal["x2"] - cal["x1"]) * xf)
            rh = int(gh * (cal["y2"] - cal["y1"]))
        else:
            defaults = {
                "speed": (0.05, 0.27, 0.14, 0.02), "stamina": (0.24, 0.27, 0.14, 0.02),
                "power": (0.43, 0.27, 0.14, 0.02), "guts": (0.62, 0.27, 0.14, 0.02),
                "wit": (0.81, 0.27, 0.14, 0.02),
            }
            if stat_name not in defaults:
                return 0
            rx, ry, rwr, rhr = defaults[stat_name]
            x, y = gx + int(gw * rx * xf), gy + int(gh * ry)
            rw, rh = int(gw * rwr * xf), int(gh * rhr)
        roi = screenshot[y:y+rh, x:x+rw]
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        scale = 3
        try:
            reader = _get_reader()
            best_val = 0
            best_conf = 0.0
            for thresh_val in (160, 140, 200):
                _, thresh = cv2.threshold(gray, thresh_val, 255, cv2.THRESH_BINARY_INV)
                big = cv2.resize(thresh, (thresh.shape[1] * scale, thresh.shape[0] * scale),
                                 interpolation=cv2.INTER_CUBIC)
                raw = reader.readtext(big, detail=1, allowlist='0123456789')
                for (_, text, conf) in raw:
                    digits = ''.join(c for c in text if c.isdigit())
                    if not digits:
                        continue
                    for length in range(min(4, len(digits)), 0, -1):
                        s = digits[:length]
                        if s[0] == "0" and length > 1:
                            continue
                        v = int(s)
                        if 1 <= v <= 1200 and conf > best_conf:
                            best_val = v
                            best_conf = conf
                            break
                if best_conf >= 0.95:
                    return best_val
                raw_full = reader.readtext(big, detail=1)
                for (_, text, conf) in raw_full:
                    if conf >= 0.3 and "max" in text.lower():
                        return 1200
            return best_val
        except Exception:
            return 0

    def read_energy_percentage(self, screenshot: np.ndarray) -> float:
        gx, gy, gw, gh = self.get_game_rect(screenshot)
        eb = self._calibration.get("energy_bar", {})
        xf = self._aspect_x_factor(gw, gh)

        bar_y1 = gy + int(gh * eb.get("y1", 0.082))
        bar_y2 = gy + int(gh * eb.get("y2", 0.098))
        bar_x1 = gx + int(gw * eb.get("x1", 0.33) * xf)
        bar_x2 = gx + int(gw * eb.get("x2", 0.69) * xf)

        roi = screenshot[bar_y1:bar_y2, bar_x1:bar_x2]
        if roi.size == 0:
            return 50.0

        Path("logs/debug").mkdir(parents=True, exist_ok=True)
        cv2.imwrite("logs/debug/energy_roi.png", roi)

        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        total_width = roi.shape[1]
        if total_width <= 0:
            return 50.0

        bar_h = roi.shape[0]
        margin = max(1, bar_h // 4)
        inner_hsv = hsv[margin:bar_h - margin, :, :]
        if inner_hsv.shape[0] <= 0:
            inner_hsv = hsv

        color_mask = (inner_hsv[:, :, 1] > 40) & (inner_hsv[:, :, 2] > 60)
        col_has_color = np.mean(color_mask, axis=0) > 0.30

        if not np.any(col_has_color):
            gray_mask = (inner_hsv[:, :, 1] < 30) & (inner_hsv[:, :, 2] > 50) & (inner_hsv[:, :, 2] < 200)
            if np.sum(np.any(gray_mask, axis=0)) > total_width * 0.3:
                self.logger.info(f"Energy: roi=({bar_x1},{bar_y1})-({bar_x2},{bar_y2}), no color found, gray bar -> 0.0%")
                return 0.0
            return 50.0

        filled_right = int(len(col_has_color) - 1 - np.argmax(col_has_color[::-1]))
        filled_width = filled_right + 1

        percentage = (filled_width / total_width) * 100
        if percentage > 95.0:
            percentage = 100.0
        result = min(max(round(float(percentage), 1), 0.0), 100.0)
        self.logger.info(f"Energy: roi=({bar_x1},{bar_y1})-({bar_x2},{bar_y2}), filled={filled_width}px, total={total_width}px -> {result}%")
        return result

    def detect_mood(self, screenshot: np.ndarray) -> str:
        gx, gy, gw, gh = self.get_game_rect(screenshot)
        mz = self._calibration.get("mood_zone", {})
        y1 = gy + int(gh * mz.get("y1", 0.095))
        y2 = gy + int(gh * mz.get("y2", 0.155))
        x1 = gx + int(gw * mz.get("x1", 0.70))
        x2 = gx + int(gw * mz.get("x2", 0.90))
        roi = screenshot[y1:y2, x1:x2]
        if roi.size == 0:
            return "unknown"

        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        sat_mask = cv2.inRange(hsv, np.array([0, 70, 120]), np.array([180, 255, 255]))
        sat_count = cv2.countNonZero(sat_mask)
        if sat_count < roi.shape[0] * roi.shape[1] * 0.08:
            return "unknown"

        hues = hsv[:, :, 0][sat_mask > 0]

        non_blue = {
            "great":  int(np.sum(hues >= 155)),
            "good":   int(np.sum((hues >= 3) & (hues < 14))),
            "normal": int(np.sum((hues >= 14) & (hues < 40))),
        }
        for mood in ("great", "good", "normal"):
            if non_blue[mood] >= self._MIN_BADGE_PX:
                self.logger.info(f"Mood color: {mood} ({non_blue[mood]} px)")
                return mood

        median_h = float(np.median(hues))
        if median_h >= 120:
            self.logger.info(f"Mood color: awful (median H={median_h:.0f})")
            return "awful"
        self.logger.info(f"Mood color: bad (median H={median_h:.0f})")
        return "bad"

    def read_event_title(self, screenshot: np.ndarray) -> str:
        gx, gy, gw, gh = self.get_game_rect(screenshot)
        xf = self._aspect_x_factor(gw, gh)
        et = self._calibration.get("event_title", {})
        y1 = gy + int(gh * et.get("y1", 0.13))
        y2 = gy + int(gh * et.get("y2", 0.22))
        x1 = gx + int(gw * et.get("x1", 0.10) * xf)
        x2 = gx + int(gw * et.get("x2", 0.90) * xf)
        title_roi = screenshot[y1:y2, x1:x2]
        if title_roi.size == 0:
            return ""
        try:
            Path("logs/debug").mkdir(parents=True, exist_ok=True)
            cv2.imwrite("logs/debug/event_title_roi.png", title_roi)
            gray = cv2.cvtColor(title_roi, cv2.COLOR_BGR2GRAY)
            _, thresh_light = cv2.threshold(gray, 140, 255, cv2.THRESH_BINARY_INV)
            _, thresh_dark = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
            text_light = _ocr_text_horizontal(thresh_light).strip()
            text_dark = _ocr_text_horizontal(thresh_dark).strip()
            title = text_light if len(text_light) > len(text_dark) else text_dark
            self.logger.debug(f"Event title OCR: '{title}'")
            return title
        except Exception:
            return ""

    def read_game_date(self, screenshot: np.ndarray = None) -> Optional[Dict]:
        if screenshot is None:
            screenshot = self.take_screenshot()
        gx, gy, gw, gh = self.get_game_rect(screenshot)
        xf = self._aspect_x_factor(gw, gh)
        dd = self._calibration.get("date_display", {})
        y1 = gy + int(gh * dd.get("y1", 0.025))
        y2 = gy + int(gh * dd.get("y2", 0.060))
        x1 = gx + int(gw * dd.get("x1", 0.15) * xf)
        x2 = gx + int(gw * dd.get("x2", 0.85) * xf)
        roi = screenshot[y1:y2, x1:x2]
        if roi.size == 0:
            return None
        try:
            Path("logs/debug").mkdir(parents=True, exist_ok=True)
            cv2.imwrite("logs/debug/date_display_roi.png", roi)
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            scale = 3
            best_text = ""
            for thresh_val, inv in [(160, False), (200, False), (160, True), (120, False)]:
                mode = cv2.THRESH_BINARY_INV if inv else cv2.THRESH_BINARY
                _, thresh = cv2.threshold(gray, thresh_val, 255, mode)
                big = cv2.resize(thresh, (thresh.shape[1] * scale, thresh.shape[0] * scale),
                                 interpolation=cv2.INTER_CUBIC)
                big = cv2.copyMakeBorder(big, 8, 8, 8, 8, cv2.BORDER_CONSTANT, value=0 if inv else 255)
                candidate = _ocr_text_raw(big).strip().lower()
                if len(candidate) > len(best_text):
                    best_text = candidate
            self.logger.debug(f"Date OCR raw: '{best_text}'")
            result = self._parse_game_date(best_text)
            if result is None:
                _, otsu_thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                big_otsu = cv2.resize(otsu_thresh, (otsu_thresh.shape[1] * scale, otsu_thresh.shape[0] * scale),
                                      interpolation=cv2.INTER_CUBIC)
                otsu_text = _ocr_text_raw(big_otsu).strip().lower()
                self.logger.debug(f"Date OCR OTSU: '{otsu_text}'")
                result = self._parse_game_date(otsu_text)
            return result
        except Exception:
            return None

    def _parse_game_date(self, text: str) -> Optional[Dict]:
        text = text.replace(",", " ").replace(".", " ").replace("-", " ").strip()
        if "finale" in text or "final" in text:
            result = {"year": "finale", "half": "", "month": "", "turn": 73}
            self.logger.debug(f"Parsed date: {result} (finale detected)")
            return result
        year = None
        for y in ("junior", "classic", "senior"):
            if y in text:
                year = y
                break
        if year and ("pre" in text or "debut" in text):
            result = {"year": year, "half": "pre-debut", "month": "", "turn": 0}
            self.logger.debug(f"Parsed date: {result} (pre-debut detected)")
            return result
        half = None
        for h in ("early", "late"):
            if h in text:
                half = h
                break
        month = None
        for m_name, m_num in self._MONTH_MAP.items():
            if m_name in text:
                month = m_name
                break
        if not year or not half or not month:
            self.logger.debug(f"Date parse incomplete: year={year}, half={half}, month={month}")
            return None
        turn = self._date_to_turn(year, half, month)
        result = {"year": year, "half": half, "month": month, "turn": turn}
        self.logger.debug(f"Parsed date: {result}")
        return result

    def _date_to_turn(self, year: str, half: str, month: str) -> int:
        month_num = self._MONTH_MAP.get(month, 1)
        year_idx = self._YEAR_ORDER.get(year, 0)
        turn = year_idx * 24
        turn += (month_num - 1) * 2
        if half == "late":
            turn += 1
        return turn + 1

    def is_summer_period(self, date_info: Optional[Dict] = None) -> bool:
        if date_info is None:
            date_info = self.read_game_date()
        if not date_info:
            return False
        month = date_info.get("month", "")
        half = date_info.get("half", "")
        if month == "jul" and half == "early":
            return True
        if month == "jul" and half == "late":
            return True
        if month == "aug" and half == "early":
            return True
        if month == "aug" and half == "late":
            return True
        return False

    def read_event_text(self, screenshot: np.ndarray) -> str:
        gx, gy, gw, gh = self.get_game_rect(screenshot)
        xf = self._aspect_x_factor(gw, gh)
        et = self._calibration.get("event_text", {})
        body_roi = screenshot[
            gy + int(gh * et.get("y1", 0.28)):gy + int(gh * et.get("y2", 0.55)),
            gx + int(gw * et.get("x1", 0.08) * xf):gx + int(gw * et.get("x2", 0.82) * xf)
        ]
        try:
            Path("logs/debug").mkdir(parents=True, exist_ok=True)
            cv2.imwrite("logs/debug/event_text_roi.png", body_roi)

            gray = cv2.cvtColor(body_roi, cv2.COLOR_BGR2GRAY)
            _, thresh_light = cv2.threshold(gray, 140, 255, cv2.THRESH_BINARY_INV)
            _, thresh_dark = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)

            text_light = _ocr_text_raw(thresh_light).strip()
            text_dark = _ocr_text_raw(thresh_dark).strip()

            text = text_light if len(text_light) > len(text_dark) else text_dark
            self.logger.debug(f"Event OCR ({len(text)} chars): {text[:120]}")
            return text
        except Exception:
            return ""

    def read_choice_texts(self, screenshot: np.ndarray, choice_positions: List[Tuple[int, int]]) -> List[str]:
        h, w = screenshot.shape[:2]
        texts = []
        for cx, cy in choice_positions:
            roi_left = max(0, int(cx - w * 0.30))
            roi_right = min(w, int(cx + w * 0.30))
            roi_top = max(0, cy - 25)
            roi_bottom = min(h, cy + 25)
            roi = screenshot[roi_top:roi_bottom, roi_left:roi_right]
            if roi.size == 0:
                texts.append("")
                continue
            try:
                gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
                _, thresh = cv2.threshold(gray, 140, 255, cv2.THRESH_BINARY_INV)
                text = _ocr_text_raw(thresh).strip()
                texts.append(text)
            except Exception:
                texts.append("")
        self.logger.debug(f"Choice texts: {texts}")
        return texts

    def read_stats(self, screenshot: np.ndarray) -> Optional[Dict[str, int]]:
        stats = self.read_all_stats(screenshot)
        if not stats or len([v for v in stats.values() if v > 0]) < 3:
            return None
        self.logger.info(
            "Stats: " + " / ".join(
                f"{n}={stats.get(n, '?')}" for n in self.STAT_NAMES))
        return stats