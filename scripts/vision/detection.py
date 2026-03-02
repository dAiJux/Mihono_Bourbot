import cv2
import numpy as np
from typing import Tuple, Optional, List

from ..models import GameScreen

class DetectionMixin:

    def _create_character_mask(self, template: np.ndarray, template_name: str = "") -> np.ndarray:
        h, w = template.shape[:2]
        mask = np.ones((h, w), dtype=np.uint8) * 255
        
        mask_percentages = {
            "btn_race_next_finish": 0.65,
            "complete_career": 0.65,
            "btn_training": 0.50,
            "btn_recreation": 0.45,
        }
        
        mask_pct = mask_percentages.get(template_name, 0.50)
        char_zone_height = int(h * mask_pct)
        
        mask[0:char_zone_height, :] = 0
        return mask

    def detect_screen(self, screenshot: np.ndarray = None) -> GameScreen:
        if screenshot is None:
            screenshot = self.take_screenshot()

        if self.find_template("recreation_popup", screenshot, 0.70):
            return GameScreen.RECREATION

        strat_count = sum(1 for s in ["strategy_end", "strategy_late", "strategy_pace", "strategy_front"]
                          if self.find_template(s, screenshot, 0.80))
        if strat_count >= 2:
            return GameScreen.STRATEGY

        if self.find_template("buy_skill", screenshot, 0.82) or \
           self.find_template("learn_btn", screenshot, 0.72) or \
           self.find_template("confirm_btn", screenshot, 0.72):
            return GameScreen.SKILL_SELECT

        for tpl, thr in [("btn_race_start", 0.70), ("btn_race_start_ura", 0.70)]:
            if self.find_template(tpl, screenshot, thr):
                return GameScreen.RACE

        banner = self.identify_popup_banner(screenshot)
        if banner == "insufficient_fans":
            return GameScreen.INSUFFICIENT_FANS
        if banner == "scheduled_race":
            return GameScreen.SCHEDULED_RACE_POPUP

        if self.find_template("btn_race", screenshot, 0.80):
            if not self.find_template("btn_race_launch", screenshot, 0.75):
                return GameScreen.RACE_SELECT

        main_found = 0
        for tpl in self.MAIN_SCREEN_BUTTONS:
            if self.find_template(tpl, screenshot, 0.70):
                main_found += 1
                if main_found >= 2:
                    return GameScreen.MAIN

        training_found = 0
        for tpl in self.TRAINING_TEMPLATES:
            if self.find_template(tpl, screenshot, 0.60):
                training_found += 1
                if training_found >= 2:
                    return GameScreen.TRAINING

        if self.config.get("scenario", "unity_cup") != "ura":
            if self.find_template("white_burst", screenshot, 0.65):
                return GameScreen.TRAINING

        if self.find_template("btn_inspiration", screenshot, 0.70):
            return GameScreen.INSPIRATION

        if self.config.get("scenario", "unity_cup") != "ura":
            if self.find_template("btn_unity_launch", screenshot, 0.75) or \
               self.find_template("btn_select_opponent", screenshot, 0.75) or \
               self.find_template("btn_begin_showdown", screenshot, 0.75) or \
               self.find_template("btn_see_unity_results", screenshot, 0.75) or \
               self.find_template("btn_next_unity", screenshot, 0.75) or \
               self.find_template("btn_launch_final_unity", screenshot, 0.75):
                return GameScreen.UNITY

        if self.find_template("btn_race_confirm", screenshot, 0.65):
            return GameScreen.RACE_SELECT

        if self.find_template("btn_race_launch", screenshot, 0.75):
            return GameScreen.RACE

        for tpl in ["btn_race_next_finish", "btn_tap"]:
            if self.find_template(tpl, screenshot, 0.75):
                return GameScreen.RACE_RESULT
        if self.find_template("btn_next", screenshot, 0.75):
            has_event_win = any(
                self.find_template(ew, screenshot, 0.82)
                for ew in ["event_scenario_window", "event_trainee_window", "event_support_window"]
            )
            if not has_event_win:
                return GameScreen.RACE_RESULT

        if self.is_at_career_complete(screenshot):
            return GameScreen.CAREER_COMPLETE

        if self.detect_event_type(screenshot):
            return GameScreen.EVENT

        self.logger.debug("Screen detected: UNKNOWN")
        return GameScreen.UNKNOWN

    _BRIGHTNESS_GATED_TEMPLATES = {
        "btn_infirmary": 189,
    }

    def _check_brightness_gate(self, template_name, search_img, match_loc, templ_shape):
        min_v = self._BRIGHTNESS_GATED_TEMPLATES.get(template_name)
        if min_v is None:
            return True
        th, tw = templ_shape[:2]
        x1, y1 = match_loc
        x2 = min(x1 + tw, search_img.shape[1])
        y2 = min(y1 + th, search_img.shape[0])
        roi = search_img[y1:y2, x1:x2]
        if roi.size == 0:
            return True
        avg_v = float(np.mean(cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)[:, :, 2]))
        result = avg_v >= min_v
        self.logger.debug(f"Brightness gate '{template_name}': V={avg_v:.1f} min={min_v} -> {'PASS' if result else 'REJECT (button is OFF)'}")
        return result

    def find_template(self, template_name: str, screenshot: np.ndarray = None, threshold: float = 0.8) -> Optional[Tuple[int, int]]:
        pos, _ = self.find_template_conf(template_name, screenshot, threshold)
        return pos

    def find_template_conf(self, template_name: str, screenshot: np.ndarray = None, threshold: float = 0.8) -> Tuple[Optional[Tuple[int, int]], float]:
        if screenshot is None:
            screenshot = self.take_screenshot()
        self._update_scale(screenshot)
        templ = self._get_scaled_template(template_name)
        if templ is None:
            return None, 0.0

        search_img, off_x, off_y = self._get_search_area(template_name, screenshot)
        if search_img.shape[0] < templ.shape[0] or search_img.shape[1] < templ.shape[1]:
            need_h = max(0, templ.shape[0] - search_img.shape[0])
            need_w = max(0, templ.shape[1] - search_img.shape[1])
            new_y1 = max(0, off_y - (need_h + 1) // 2)
            new_x1 = max(0, off_x - (need_w + 1) // 2)
            new_y2 = min(screenshot.shape[0], off_y + search_img.shape[0] + need_h // 2 + 1)
            new_x2 = min(screenshot.shape[1], off_x + search_img.shape[1] + need_w // 2 + 1)
            search_img = screenshot[new_y1:new_y2, new_x1:new_x2]
            off_x, off_y = new_x1, new_y1
            if search_img.shape[0] < templ.shape[0] or search_img.shape[1] < templ.shape[1]:
                return None, 0.0

        use_gray = template_name in self._GRAYSCALE_TEMPLATES
        use_mask = template_name in self._CHARACTER_OVERLAY_TEMPLATES

        if use_mask:
            mask = self._create_character_mask(templ, template_name)
            if use_gray:
                s_img = cv2.cvtColor(search_img, cv2.COLOR_BGR2GRAY)
                t_img = cv2.cvtColor(templ, cv2.COLOR_BGR2GRAY)
            else:
                s_img, t_img = search_img, templ
            res = cv2.matchTemplate(s_img, t_img, cv2.TM_CCOEFF_NORMED, mask=mask)
        else:
            if use_gray:
                s_img = cv2.cvtColor(search_img, cv2.COLOR_BGR2GRAY)
                t_img = cv2.cvtColor(templ, cv2.COLOR_BGR2GRAY)
            else:
                s_img, t_img = search_img, templ
            res = cv2.matchTemplate(s_img, t_img, cv2.TM_CCOEFF_NORMED)

        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        if max_val >= threshold:
            if not self._check_brightness_gate(template_name, search_img, max_loc, templ.shape):
                return None, max_val
            return (max_loc[0] + templ.shape[1] // 2 + off_x, max_loc[1] + templ.shape[0] // 2 + off_y), max_val

        if max_val < threshold * 0.6:
            return None, max_val

        best_val = max_val
        best_loc = None
        best_shape = templ.shape
        for scale in [0.95, 1.05, 0.9, 1.1]:
            new_w = int(templ.shape[1] * scale)
            new_h = int(templ.shape[0] * scale)
            if new_w <= 0 or new_h <= 0:
                continue
            if new_h > search_img.shape[0] or new_w > search_img.shape[1]:
                continue
            scaled = cv2.resize(templ, (new_w, new_h), interpolation=cv2.INTER_AREA)
            if use_mask:
                scaled_mask = cv2.resize(mask, (new_w, new_h), interpolation=cv2.INTER_NEAREST)
            if use_gray:
                scaled = cv2.cvtColor(scaled, cv2.COLOR_BGR2GRAY)
            if use_mask:
                res = cv2.matchTemplate(s_img, scaled, cv2.TM_CCOEFF_NORMED, mask=scaled_mask)
            else:
                res = cv2.matchTemplate(s_img, scaled, cv2.TM_CCOEFF_NORMED)
            _, mv, _, ml = cv2.minMaxLoc(res)
            if mv > best_val:
                best_val = mv
                best_loc = ml
                best_shape = (new_h, new_w)

        if best_val >= threshold and best_loc is not None:
            if not self._check_brightness_gate(template_name, search_img, best_loc, best_shape):
                return None, best_val
            return (best_loc[0] + best_shape[1] // 2 + off_x, best_loc[1] + best_shape[0] // 2 + off_y), best_val
        return None, best_val

    def find_all_template(self, template_name: str, screenshot: np.ndarray = None, threshold: float = 0.8, min_distance: int = 0) -> List[Tuple[int, int]]:
        if screenshot is None:
            screenshot = self.take_screenshot()

        if template_name in self._STRUCTURAL_TEMPLATES:
            return self._detect_choice_bands(screenshot)
        self._update_scale(screenshot)
        templ = self._get_scaled_template(template_name)
        if templ is None:
            return []

        search_img, off_x, off_y = self._get_search_area(template_name, screenshot)
        if search_img.shape[0] < templ.shape[0] or search_img.shape[1] < templ.shape[1]:
            return []

        use_gray = template_name in self._GRAYSCALE_TEMPLATES
        if use_gray:
            s_img = cv2.cvtColor(search_img, cv2.COLOR_BGR2GRAY)
            t_img = cv2.cvtColor(templ, cv2.COLOR_BGR2GRAY)
        else:
            s_img, t_img = search_img, templ

        res = cv2.matchTemplate(s_img, t_img, cv2.TM_CCOEFF_NORMED)
        _, best_val, _, _ = cv2.minMaxLoc(res)
        loc = np.where(res >= threshold)
        points = [(pt[0] + templ.shape[1] // 2 + off_x,
                    pt[1] + templ.shape[0] // 2 + off_y)
                   for pt in zip(*loc[::-1])]

        if not points and best_val >= threshold * 0.55:
            for scale in [0.95, 1.05, 0.9, 1.1, 0.85, 1.15]:
                nw = int(templ.shape[1] * scale)
                nh = int(templ.shape[0] * scale)
                if nw <= 0 or nh <= 0:
                    continue
                if nh > search_img.shape[0] or nw > search_img.shape[1]:
                    continue
                scaled = cv2.resize(templ, (nw, nh), interpolation=cv2.INTER_AREA)
                if use_gray:
                    scaled = cv2.cvtColor(scaled, cv2.COLOR_BGR2GRAY)
                res2 = cv2.matchTemplate(s_img, scaled, cv2.TM_CCOEFF_NORMED)
                loc2 = np.where(res2 >= threshold)
                if len(loc2[0]) > 0:
                    points = [(pt[0] + nw // 2 + off_x,
                               pt[1] + nh // 2 + off_y)
                              for pt in zip(*loc2[::-1])]
                    break

        if min_distance > 0 and len(points) > 1:
            scaled_dist = self._scale_px(min_distance)
            filtered = [points[0]]
            for p in points[1:]:
                if all(abs(p[0] - f[0]) > scaled_dist or abs(p[1] - f[1]) > scaled_dist for f in filtered):
                    filtered.append(p)
            return filtered
        return points

    def _detect_choice_bands(self, screenshot: np.ndarray) -> List[Tuple[int, int]]:
        search_img, off_x, off_y = self._get_search_area("event_choice", screenshot)
        h, w = search_img.shape[:2]
        if h < 30 or w < 50:
            return []

        hsv = cv2.cvtColor(search_img, cv2.COLOR_BGR2HSV)

        margin = max(1, int(w * 0.15))
        centre = hsv[:, margin:w - margin, :]

        bright = (centre[:, :, 2] > 180) & (centre[:, :, 1] < 70)
        row_cov = np.mean(bright, axis=1)
        is_bright = row_cov > 0.55
        bands: list = []
        in_band = False
        start = 0
        gap = 0
        max_gap = self._scale_px(4)
        band_min = self._scale_px(35)
        band_max = self._scale_px(140)

        for y in range(h):
            if is_bright[y]:
                if not in_band:
                    start = y
                    in_band = True
                gap = 0
            else:
                if in_band:
                    gap += 1
                    if gap > max_gap:
                        end = y - gap
                        bh = end - start + 1
                        if band_min <= bh <= band_max:
                            bands.append((start, end))
                        in_band = False
                        gap = 0

        if in_band:
            end = h - 1 - gap
            bh = end - start + 1
            if band_min <= bh <= band_max:
                bands.append((start, end))

        centres = []
        for bs, be in bands:
            bh = be - bs + 1
            high_cov_rows = int(np.sum(row_cov[bs:be + 1] > 0.80))
            if high_cov_rows < bh * 0.55:
                continue
            cx = off_x + w // 2
            cy = off_y + (bs + be) // 2
            centres.append((cx, cy))

        self.logger.debug(
            f"Choice bands: {len(centres)} found "
            + ", ".join(f"y={s}-{e}" for s, e in bands)
        )
        return centres

    def detect_event_type(self, screenshot: np.ndarray) -> Optional[str]:
        gx, gy, gw, gh = self.get_game_rect(screenshot)
        ec = self._calibration.get("event_choices", {})
        choice_y_min = gy + int(gh * ec.get("y1", 0.35))
        choice_y_max = gy + int(gh * ec.get("y2", 0.85))

        for tpl in ["event_scenario_window", "event_trainee_window", "event_support_window"]:
            pos = self.find_template(tpl, screenshot, 0.82)
            if pos and gx <= pos[0] <= gx + gw:
                choices = self.find_all_template("event_choice", screenshot, 0.75)
                real_choices = [
                    c for c in choices
                    if gx <= c[0] <= gx + gw and choice_y_min <= c[1] <= choice_y_max
                ]
                if 1 <= len(real_choices) <= 5:
                    return "choice"
                self.logger.debug(f"Event window '{tpl}' matched but {len(real_choices)} choices found — ignoring")

        choices = self.find_all_template("event_choice", screenshot, 0.75)
        real_choices = [
            c for c in choices
            if gx <= c[0] <= gx + gw and choice_y_min <= c[1] <= choice_y_max
        ]
        if 2 <= len(real_choices) <= 5:
            non_event_buttons = [
                "btn_ok", "btn_claw_machine", "btn_race_launch",
                "btn_race_start", "btn_race_start_ura", "btn_race_next_finish",
                "btn_begin_showdown", "btn_see_unity_results", "btn_next_unity",
                "btn_launch_final_unity", "btn_unity_launch", "btn_select_opponent",
                "btn_try_again", "btn_cancel",
            ]
            is_non_event = any(
                self.find_template(b, screenshot, 0.70) for b in non_event_buttons
            )
            if is_non_event:
                self.logger.debug(
                    f"Choice-only fallback suppressed — non-event button visible")
                return None
            if self.is_at_career_complete(screenshot):
                self.logger.debug("Choice-only fallback suppressed — career complete screen")
                return None
            self.logger.debug(
                f"Event detected by choice-only fallback ({len(real_choices)} choices)")
            return "choice"
        return None

    def detect_race_day(self, screenshot: Optional[np.ndarray] = None) -> bool:
        if screenshot is None:
            screenshot = self.take_screenshot()
        return (self.find_template("btn_race_start", screenshot, 0.70) is not None or
                self.find_template("btn_race_start_ura", screenshot, 0.70) is not None)

    def detect_target_race(self, screenshot: np.ndarray) -> bool:
        return self.find_template("target_race", screenshot, 0.8) is not None

    def detect_scheduled_race(self, screenshot: np.ndarray) -> bool:
        return self.find_template("scheduled_race", screenshot, 0.8) is not None

    def identify_popup_banner(self, screenshot: np.ndarray) -> Optional[str]:
        _, sched_conf = self.find_template_conf("scheduled_race_popup", screenshot, 0.65)
        _, insuf_conf = self.find_template_conf("insufficient_fans", screenshot, 0.65)
        if sched_conf < 0.70 and insuf_conf < 0.70:
            return None
        if sched_conf >= 0.70 and insuf_conf >= 0.70:
            self.logger.info(
                f"Both banners matched: scheduled={sched_conf:.3f} insufficient={insuf_conf:.3f}"
            )
            return "scheduled_race" if sched_conf >= insuf_conf else "insufficient_fans"
        if sched_conf >= 0.70:
            return "scheduled_race"
        return "insufficient_fans"

    def detect_unity_cup(self, screenshot: Optional[np.ndarray] = None) -> bool:
        if screenshot is None:
            screenshot = self.take_screenshot()
        return self.find_template("btn_unity_launch", screenshot, 0.75) is not None

    def detect_unity_opponents(self, screenshot: np.ndarray) -> List[Tuple[int, int]]:
        if not self.find_template("btn_select_opponent", screenshot, 0.70):
            return []

        gx, gy, gw, gh = self.get_game_rect(screenshot)
        uz = self._calibration.get("unity_opponent_zone", {})
        if not uz:
            return []
        xf = self._aspect_x_factor(gw, gh)
        x1 = max(0, gx + int(gw * uz.get("x1", 0) * xf))
        y1 = max(0, gy + int(gh * uz.get("y1", 0)))
        x2 = min(screenshot.shape[1], gx + int(gw * uz.get("x2", 1) * xf))
        y2 = min(screenshot.shape[0], gy + int(gh * uz.get("y2", 1)))
        zone = screenshot[y1:y2, x1:x2]
        if zone.size == 0:
            return []

        gray = cv2.cvtColor(zone, cv2.COLOR_BGR2GRAY)
        _, white_mask = cv2.threshold(gray, 220, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(white_mask, cv2.RETR_EXTERNAL,
                                       cv2.CHAIN_APPROX_SIMPLE)
        opponents: List[Tuple[int, int]] = []
        for c in sorted(contours, key=cv2.contourArea, reverse=True):
            bx, by, bw, bh = cv2.boundingRect(c)
            if bw > 200 and bh > 100 and cv2.contourArea(c) > 20000:
                cx = x1 + bx + bw // 2
                cy = y1 + by + bh // 2
                opponents.append((cx, cy))
        opponents.sort(key=lambda p: p[1])

        merged: List[Tuple[int, int]] = []
        for pt in opponents:
            if merged and abs(pt[1] - merged[-1][1]) < 80:
                prev = merged[-1]
                merged[-1] = ((prev[0] + pt[0]) // 2, (prev[1] + pt[1]) // 2)
            else:
                merged.append(pt)

        self.logger.debug(f"Unity opponents detected: {len(merged)} cards at {merged} (raw: {len(opponents)})")
        return merged

    def detect_gold_skill(self, screenshot: Optional[np.ndarray] = None) -> List[Tuple[int, int]]:
        if screenshot is None:
            screenshot = self.take_screenshot()
        return self.find_all_template("gold_skill", screenshot, 0.7)

    def detect_white_skill(self, screenshot: Optional[np.ndarray] = None) -> List[Tuple[int, int]]:
        if screenshot is None:
            screenshot = self.take_screenshot()
        return self.find_all_template("white_skill", screenshot, 0.7)

    def is_at_career_complete(self, screenshot: Optional[np.ndarray] = None) -> bool:
        if screenshot is None:
            screenshot = self.take_screenshot()
        if self.find_template("complete_career", screenshot, 0.9) is not None:
            return True
        return False

    def detect_injury(self, screenshot: np.ndarray) -> bool:
        self._update_scale(screenshot)
        t_on = self._get_scaled_template("btn_infirmary")
        if t_on is None:
            return False

        search, ox, oy = self._get_search_area("btn_infirmary", screenshot)
        if search is None or search.shape[0] < t_on.shape[0] or search.shape[1] < t_on.shape[1]:
            return False

        res = cv2.matchTemplate(search, t_on, cv2.TM_CCOEFF_NORMED)
        _, mv_on, _, ml_on = cv2.minMaxLoc(res)

        if mv_on < 0.60:
            self.logger.debug(f"Infirmary: score ON too low ({mv_on:.3f}) → NO INJURY")
            return False

        th, tw = t_on.shape[:2]
        x1, y1 = ml_on
        roi = search[y1:y1 + th, x1:x1 + tw]
        if roi.size == 0:
            return False

        ref_brightness = float(np.mean(cv2.cvtColor(t_on, cv2.COLOR_BGR2GRAY)))
        roi_brightness = float(np.mean(cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)))

        if ref_brightness == 0:
            return False

        brightness_diff = abs(roi_brightness - ref_brightness) / ref_brightness
        injury = brightness_diff <= 0.15

        self.logger.debug(
            f"Infirmary — score={mv_on:.3f}, "
            f"ref={ref_brightness:.1f}, roi={roi_brightness:.1f}, "
            f"diff={brightness_diff:.3f} → {'INJURY' if injury else 'NO INJURY (button OFF)'}"
        )
        return injury

    def detect_race_start_button(self, screenshot: np.ndarray) -> Optional[Tuple[int, int]]:
        for tpl in ("btn_race_start", "btn_race_start_ura"):
            pos = self.find_template(tpl, screenshot, 0.70)
            if pos:
                self.logger.info(f"Race start button found via template ({tpl}) at {pos}")
                return pos

        gx, gy, gw, gh = self.get_game_rect(screenshot)
        game = screenshot[gy:gy+gh, gx:gx+gw]
        hsv = cv2.cvtColor(game, cv2.COLOR_BGR2HSV)

        pink_mask = cv2.inRange(
            hsv,
            np.array([140, 60, 180]),
            np.array([175, 255, 255])
        )

        scan_y1 = int(gh * 0.75)
        scan_y2 = int(gh * 1.00)
        xf = self._aspect_x_factor(gw, gh)
        scan_x1 = int(gw * 0.10 * xf)
        scan_x2 = int(gw * 0.90 * xf)
        region_mask = pink_mask[scan_y1:scan_y2, scan_x1:scan_x2]

        if np.sum(region_mask > 0) < 800:
            self.logger.debug("Race start button: HSV fallback found no pink region")
            return None

        cols = np.sum(region_mask > 0, axis=0)
        rows = np.sum(region_mask > 0, axis=1)
        col_idx = np.where(cols > 5)[0]
        row_idx = np.where(rows > 5)[0]
        if len(col_idx) == 0 or len(row_idx) == 0:
            return None

        cx = gx + scan_x1 + int(np.mean(col_idx))
        cy = gy + scan_y1 + int(np.mean(row_idx))
        self.logger.info(f"Race start button found via HSV pink detection at ({cx}, {cy})")
        return (cx, cy)

    def detect_rainbow_training(self, screenshot: np.ndarray) -> int:
        return len(self.find_all_template("icon_rainbow", screenshot, 0.75))

    def detect_goal_race(self, screenshot: Optional[np.ndarray] = None) -> Optional[Tuple[int, int]]:
        if screenshot is None:
            screenshot = self.take_screenshot()
        gx, gy, gw, gh = self.get_game_rect(screenshot)
        game = screenshot[gy:gy + gh, gx:gx + gw]
        hsv = cv2.cvtColor(game, cv2.COLOR_BGR2HSV)

        y1 = int(gh * self._GOAL_SCAN_Y1)
        y2 = int(gh * self._GOAL_SCAN_Y2)

        best_count = 0
        best_cy = None

        strip_h = self._scale_px(self._GOAL_STRIP_H)
        for y in range(y1, y2, strip_h):
            y_end = min(y + strip_h, y2)
            strip = hsv[y:y_end, :, :]
            mask = (
                (strip[:, :, 0] >= self._GOAL_HUE_LO)
                & (strip[:, :, 0] <= self._GOAL_HUE_HI)
                & (strip[:, :, 1] >= self._GOAL_SAT_MIN)
                & (strip[:, :, 2] >= self._GOAL_VAL_MIN)
            )
            count = int(np.sum(mask))
            if count > best_count:
                best_count = count
                best_cy = (y + y_end) // 2

        if best_count < self._GOAL_MIN_PX or best_cy is None:
            self.logger.debug(f"No Goal marker found (best orange px = {best_count})")
            return None

        cx = gx + gw // 2
        cy = gy + best_cy
        self.logger.info(f"Goal race detected at y={best_cy} (orange px = {best_count})")
        return (cx, cy)

    def detect_card_types_with_pal(self, screenshot: np.ndarray) -> list:
        return self.detect_card_types(screenshot)

    def count_support_friendship_leveled(self, screenshot: np.ndarray) -> dict:
        bar_info = self._count_support_bars(screenshot)
        icons = self._detect_type_icons(screenshot)

        partial = 0
        orange_plus = 0
        pal_orange = 0
        pal_present = any(t == "pal" for _, t, _ in icons)

        for i, (_, _, bar_type) in enumerate(bar_info["bars"]):
            icon_type = icons[i][1] if i < len(icons) else "unknown"
            if bar_type in ("orange", "gold"):
                if icon_type == "pal":
                    pal_orange += 1
                else:
                    orange_plus += 1
            elif bar_type in ("green", "blue"):
                partial += 1

        return {"partial": partial, "orange_plus": orange_plus, "pal_orange": pal_orange, "pal": 1 if pal_present else 0}

    def find_race_select_button(self, screenshot: Optional[np.ndarray] = None) -> Optional[Tuple[int, int]]:
        if screenshot is None:
            screenshot = self.take_screenshot()

        cancel = self.find_template("btn_cancel", screenshot, 0.80)
        if cancel:
            gx, gy, gw, gh = self.get_game_rect(screenshot)
            tpl = self._get_scaled_template("btn_race_confirm")
            if tpl is None:
                return None
            band_y1 = max(0, cancel[1] - tpl.shape[0] // 2 - 60)
            band_y2 = min(screenshot.shape[0], cancel[1] + tpl.shape[0] // 2 + 60)
            band = screenshot[band_y1:band_y2, :]
            if band.shape[0] < tpl.shape[0] or band.shape[1] < tpl.shape[1]:
                return None
            res = cv2.matchTemplate(band, tpl, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)
            if max_val >= 0.65:
                cx = max_loc[0] + tpl.shape[1] // 2
                cy = band_y1 + max_loc[1] + tpl.shape[0] // 2
                self.logger.debug(
                    f"Popup Race button found at ({cx},{cy}) val={max_val:.3f}")
                return (cx, cy)
            return None

        return self.find_template("btn_race_confirm", screenshot, 0.65)