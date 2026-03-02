import cv2
import numpy as np
from typing import Tuple, Optional, List, Dict

class TrainingAnalysisMixin:

    _TYPE_TEMPLATES = [
        "type_speed", "type_stamina", "type_power", "type_guts", "type_wit", "type_pal",
    ]

    _TYPE_HUE_VERIFY: Dict[str, list] = {
        "speed":   [(85, 125)],
        "stamina": [(0, 15), (165, 179)],
        "power":   [(10, 35)],
        "guts":    [(130, 170)],
        "wit":     [(40, 90)],
    }

    _BAR_Y_OFFSET = 62
    _BAR_HALF_H = 5

    _type_icons_cache: tuple = (None, [])

    def detect_burst_training(self, screenshot: np.ndarray) -> Dict[str, List[Tuple[int, int]]]:
        white = self.find_all_template("burst_white", screenshot, 0.70, min_distance=30)
        blue = self.find_all_template("burst_blue", screenshot, 0.70, min_distance=30)
        return {"white": white, "blue": blue}

    def count_friendship_icons(self, screenshot: np.ndarray) -> Dict[str, int]:
        return {
            "partial": len(self.find_all_template("friend_bar_partial", screenshot, 0.70, min_distance=30)),
            "orange": len(self.find_all_template("friend_bar_orange", screenshot, 0.70, min_distance=30)),
            "max": len(self.find_all_template("friend_bar_max", screenshot, 0.70, min_distance=30)),
            "burst": len(self.find_all_template("friend_bar_burst", screenshot, 0.70, min_distance=30)),
        }

    def count_rainbows_for_training(self, screenshot: np.ndarray, training_stat: str) -> int:
        bar_info = self._count_support_bars(screenshot)
        card_types = self.detect_card_types(screenshot)
        count = 0
        for i, card_type in enumerate(card_types):
            if i < len(bar_info["bars"]):
                _, _, bar_type = bar_info["bars"][i]
                if bar_type in ("orange", "gold") and card_type == training_stat:
                    count += 1
        return count

    def get_friendship_bar_positions(self, screenshot: np.ndarray) -> Dict[str, List[Tuple[int, int]]]:
        return {
            "partial": self.find_all_template("friend_bar_partial", screenshot, 0.70, min_distance=30),
            "orange": self.find_all_template("friend_bar_orange", screenshot, 0.70, min_distance=30),
            "max": self.find_all_template("friend_bar_max", screenshot, 0.70, min_distance=30),
        }

    def count_support_friendship(self, screenshot: np.ndarray) -> int:
        return self._count_support_bars(screenshot)["total"]

    def _detect_type_icons(
        self, screenshot: np.ndarray
    ) -> List[Tuple[int, str, float]]:
        ss_id = id(screenshot)
        if self._type_icons_cache[0] == ss_id:
            return self._type_icons_cache[1]

        region = self._calibration.get("support_region")
        if not region:
            self._type_icons_cache = (ss_id, [])
            return []

        gx, gy, gw, gh = self.get_game_rect(screenshot)
        xf = self._aspect_x_factor(gw, gh)
        x1 = max(0, gx + int(gw * region["x1"] * xf))
        y1 = max(0, gy + int(gh * region["y1"]))
        x2 = min(screenshot.shape[1], gx + int(gw * region["x2"] * xf))
        y2 = min(screenshot.shape[0], gy + int(gh * region["y2"]))
        crop = screenshot[y1:y2, x1:x2]
        if crop.size == 0:
            self._type_icons_cache = (ss_id, [])
            return []

        hsv_crop = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)

        all_matches: list = []

        for tpl_name in self._TYPE_TEMPLATES:
            templ = self._get_scaled_template(tpl_name)
            if templ is None:
                continue
            th, tw = templ.shape[:2]

            type_name = tpl_name.replace("type_", "")
            threshold = 0.70

            for scale in (1.0, 0.95, 1.05, 0.90, 1.10):
                if scale == 1.0:
                    t_img = templ
                else:
                    nw, nh = int(tw * scale), int(th * scale)
                    if nw <= 0 or nh <= 0:
                        continue
                    t_img = cv2.resize(templ, (nw, nh),
                                       interpolation=cv2.INTER_AREA)
                t_h, t_w = t_img.shape[:2]
                if crop.shape[0] < t_h or crop.shape[1] < t_w:
                    continue

                res = cv2.matchTemplate(crop, t_img, cv2.TM_CCOEFF_NORMED)
                loc = np.where(res >= threshold)
                for py, px in zip(*loc):
                    score = float(res[py, px])
                    cy = py + t_h // 2

                    patch = hsv_crop[py:py + t_h, px:px + t_w]
                    sat_mask = (patch[:, :, 1] > 80) & (patch[:, :, 2] > 80)
                    if np.sum(sat_mask) < 10:
                        continue
                    med_hue = float(np.median(patch[:, :, 0][sat_mask]))
                    if type_name != "pal" and not self._verify_type_hue(type_name, med_hue):
                        continue

                    all_matches.append((cy, type_name, score))

        if not all_matches:
            self.logger.debug("Type icons: none detected")
            self._type_icons_cache = (ss_id, [])
            return []

        all_matches.sort(key=lambda m: m[0])
        group_dist = self._scale_px(25)
        groups: list = [[all_matches[0]]]
        for m in all_matches[1:]:
            if m[0] - groups[-1][0][0] < group_dist:
                groups[-1].append(m)
            else:
                groups.append([m])

        results = [max(g, key=lambda m: m[2]) for g in groups]

        self.logger.debug(
            "Type icons: %d — %s",
            len(results),
            ", ".join(f"{t}@y={y}({s:.2f})" for y, t, s in results),
        )
        self._type_icons_cache = (ss_id, results)
        return results

    @classmethod
    def _verify_type_hue(cls, type_name: str, hue: float) -> bool:
        ranges = cls._TYPE_HUE_VERIFY.get(type_name, [])
        return any(lo <= hue <= hi for lo, hi in ranges)

    def detect_card_types(self, screenshot: np.ndarray) -> List[str]:
        icons = self._detect_type_icons(screenshot)
        return [t for _, t, _ in icons]

    def _count_support_bars(self, screenshot: np.ndarray) -> Dict:
        region = self._calibration.get("support_region")
        if not region or "x1" not in region:
            return {"total": 0, "bars": []}

        gx, gy, gw, gh = self.get_game_rect(screenshot)
        xf = self._aspect_x_factor(gw, gh)
        x1 = max(0, gx + int(gw * region["x1"] * xf))
        y1 = max(0, gy + int(gh * region["y1"]))
        x2 = min(screenshot.shape[1], gx + int(gw * region["x2"] * xf))
        y2 = min(screenshot.shape[0], gy + int(gh * region["y2"]))
        crop = screenshot[y1:y2, x1:x2]
        if crop.size == 0:
            return {"total": 0, "bars": []}

        icons = self._detect_type_icons(screenshot)
        if not icons:
            self.logger.debug("Support bars: no type icons → 0 bars")
            return {"total": 0, "bars": []}

        h, w = crop.shape[:2]
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        margin_x = max(1, int(w * 0.20))

        bar_y_off = self._scale_px(self._BAR_Y_OFFSET)
        bar_half = self._scale_px(self._BAR_HALF_H)
        bars: list = []
        for icon_y, icon_type, _ in icons:
            bar_y1 = icon_y + bar_y_off - bar_half
            bar_y2 = icon_y + bar_y_off + bar_half
            if bar_y1 < 0 or bar_y2 >= h:
                continue

            strip = hsv[bar_y1:bar_y2, margin_x:w - margin_x]
            s_vals = strip[:, :, 1].ravel()
            v_vals = strip[:, :, 2].ravel()
            h_vals = strip[:, :, 0].ravel()

            coloured = (s_vals > 130) & (v_vals > 100)
            n_coloured = int(np.sum(coloured))

            if n_coloured > 10:
                med_hue = float(np.median(h_vals[coloured]))
                med_sat = float(np.median(s_vals[coloured]))
                med_val = float(np.median(v_vals[coloured]))
                if 30 <= med_hue <= 80:
                    bar_type = "green"
                elif 80 < med_hue <= 120:
                    bar_type = "blue"
                elif med_hue <= 30 or med_hue >= 165:
                    if med_sat < 180 and med_val > 200:
                        bar_type = "gold"
                    else:
                        bar_type = "orange"
                else:
                    bar_type = "green"
            else:
                bar_type = "empty"

            bars.append((bar_y1, bar_y2, bar_type))

        self.logger.debug(
            "Support bars: %d — %s",
            len(bars),
            ", ".join(f"y={s}-{e}({t})" for s, e, t in bars),
        )
        return {"total": len(bars), "bars": bars}

    def count_characters_per_training(self, screenshot: np.ndarray) -> Dict[str, int]:
        gx, gy, gw, gh = self.get_game_rect(screenshot)
        xf = self._aspect_x_factor(gw, gh)
        results = {}
        for stat in ["speed", "stamina", "power", "guts", "wit"]:
            region = self._calibration.get(f"training_{stat}")
            if not region or "x1" not in region:
                results[stat] = 0
                continue
            x1 = gx + int(gw * region["x1"] * xf)
            y1 = gy + int(gh * region["y1"])
            x2 = gx + int(gw * region["x2"] * xf)
            y2 = gy + int(gh * region["y2"])
            crop = screenshot[y1:y2, x1:x2]
            if crop.size == 0:
                results[stat] = 0
                continue
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            circles = cv2.HoughCircles(
                blurred, cv2.HOUGH_GRADIENT, 1.2, self._scale_px(15),
                param1=80, param2=30,
                minRadius=self._scale_px(10), maxRadius=self._scale_px(28),
            )
            if circles is not None:
                face_circles = [c for c in circles[0]
                                if c[1] < crop.shape[0] * 0.85]
                results[stat] = len(face_circles)
            else:
                results[stat] = 0
            self.logger.debug(f"  chars_on_{stat}: {results[stat]}")
        return results

    def count_support_icons_near(self, screenshot: np.ndarray, training_pos: Tuple[int, int], radius: int = 100) -> int:
        gx, gy, gw, gh = self.get_game_rect(screenshot)
        xf = self._aspect_x_factor(gw, gh)
        sr = self._calibration.get("support_region", {})
        col_left = gx + int(gw * sr.get("x1", 0.82) * xf)
        col_right = gx + int(gw * sr.get("x2", 0.98) * xf)
        col_top = gy + int(gh * sr.get("y1", 0.10))
        col_bottom = gy + int(gh * sr.get("y2", 0.48))
        if col_top >= col_bottom or col_left >= col_right:
            return 0
        region = screenshot[col_top:col_bottom, col_left:col_right]
        if region.size == 0:
            return 0
        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        segment_h = self._scale_px(70)
        count = 0
        for y_start in range(0, edges.shape[0] - segment_h + 1, segment_h):
            segment = edges[y_start:y_start + segment_h, :]
            edge_density = np.sum(segment > 0) / segment.size
            if edge_density > 0.08:
                count += 1
        return count

    def get_training_options(self, screenshot: np.ndarray) -> Dict[str, Optional[Tuple[int, int]]]:
        options = {}
        for train in ["speed", "stamina", "power", "guts", "wit"]:
            pos = self.find_template(f"training_{train}", screenshot, 0.60)
            options[train] = pos
            if pos:
                self.logger.debug(f"Training '{train}' found at {pos}")
        return options

    def get_burst_status(self, screenshot: np.ndarray) -> Dict[str, list]:
        return self.detect_burst_training(screenshot)

    def get_friendship_status(self, screenshot: np.ndarray) -> Dict[str, int]:
        return self.count_friendship_icons(screenshot)

    def has_target_race(self, screenshot: np.ndarray) -> bool:
        return self.detect_target_race(screenshot)

    def has_scheduled_race(self, screenshot: np.ndarray) -> bool:
        return self.detect_scheduled_race(screenshot)