import time
import random
import ctypes
import win32gui
import win32con
import numpy as np
from typing import Dict, Tuple

from ..models import GameScreen

class TrainingMixin:

    def _get_training_positions(self, screenshot: np.ndarray) -> Dict[str, Tuple[int, int]]:
        gx, gy, gw, gh = self.vision.get_game_rect(screenshot)
        xf = self.vision._aspect_x_factor(gw, gh)
        cal = self.vision._calibration
        defaults = {
            "speed": (0.145, 0.843), "stamina": (0.322, 0.843),
            "power": (0.500, 0.843), "guts": (0.678, 0.843),
            "wit": (0.855, 0.843),
        }
        positions = {}
        for name, (def_x, def_y) in defaults.items():
            tp = cal.get(f"train_{name}", {})
            px = gx + int(gw * tp.get("x", def_x) * xf)
            py = gy + int(gh * tp.get("y", def_y))
            positions[name] = (px, py)
        return positions

    def execute_training_action(self, training_info=None):
        if isinstance(training_info, dict):
            training_type = training_info.get("stat")
            cached_energy = training_info.get("energy", -1)
            cached_mood = training_info.get("mood", "unknown")
        else:
            training_type = training_info
            cached_energy = -1
            cached_mood = "unknown"
        self.logger.info(f"Executing TRAINING (suggested={training_type})...")

        screenshot = self.vision.take_screenshot()
        screen = self.vision.detect_screen(screenshot)
        self.logger.info(f"Screen before training: {screen.value}")

        if screen == GameScreen.EVENT:
            self.logger.info("Event screen detected before training — handling event first")
            self.handle_event(self._event_db)
            self.wait(0.5)
            screenshot = self.vision.take_screenshot()
            screen = self.vision.detect_screen(screenshot)

        if screen == GameScreen.MAIN:
            if not self.click_button("btn_training", screenshot):
                self.logger.error("Cannot find Training button on main screen")
                return "failed"
            self.wait(2.0)
            screenshot = self.vision.take_screenshot()
            screen = self.vision.detect_screen(screenshot)

            race_popup = self.vision.find_template("btn_race", screenshot, 0.80)
            if race_popup and not self.vision.find_template("btn_race_launch", screenshot, 0.75):
                self.logger.info("Scheduled race popup appeared after Training click — launching race instead")
                self.click_with_offset(*race_popup)
                self.wait(1.5)
                return None

        if screen == GameScreen.EVENT:
            self.logger.info("Event appeared after clicking training — handling")
            self.handle_event(self._event_db)
            self.wait(0.5)
            screenshot = self.vision.take_screenshot()
            screen = self.vision.detect_screen(screenshot)

        if screen != GameScreen.TRAINING:
            self.logger.warning(f"Not on training screen ({screen.value}), attempting navigation")

            race_popup = self.vision.find_template("btn_race", screenshot, 0.80)
            if race_popup and not self.vision.find_template("btn_race_launch", screenshot, 0.75):
                self.logger.info("Scheduled race popup detected mid-training — launching race")
                self.click_with_offset(*race_popup)
                self.wait(1.5)
                return None

            if self.click_button("btn_training", screenshot):
                self.wait(2.0)
                screenshot = self.vision.take_screenshot()
            else:
                self.logger.error("Cannot reach training screen")
                return "failed"

        date_info = self.vision.read_game_date(screenshot)
        current_turn = date_info.get("turn", 0) if date_info else 0
        is_pre_summer = date_info is not None and current_turn < 37
        is_summer = self.vision.is_summer_period(date_info)
        is_junior = not date_info or date_info.get("year") == "junior"

        template_positions = self.vision.get_training_options(screenshot)
        found_templates = {k: v for k, v in template_positions.items() if v is not None}
        self.logger.info(f"Template-matched icons: {list(found_templates.keys())} ({len(found_templates)}/5)")

        fallback_positions = self._get_training_positions(screenshot)

        icon_positions = {}
        for name in ["speed", "stamina", "power", "guts", "wit"]:
            tpl_pos = found_templates.get(name)
            fb_pos = fallback_positions[name]
            if tpl_pos:
                gx, _, gw, _ = self.vision.get_game_rect(screenshot)
                if gx <= tpl_pos[0] <= gx + gw:
                    icon_positions[name] = tpl_pos
                else:
                    icon_positions[name] = fb_pos
            else:
                icon_positions[name] = fb_pos

        self.vision.save_debug_screenshot("training_screen")

        energy = cached_energy if cached_energy >= 0 else self.vision.read_energy_percentage(screenshot)
        mood = cached_mood if cached_mood != "unknown" else self.vision.detect_mood(screenshot)
        energy_training = self.config.get("thresholds", {}).get("energy_training", 50)
        energy_low = self.config.get("thresholds", {}).get("energy_low", 40)

        if energy < energy_training:
            self.logger.info(
                f"Energy low ({energy:.0f}% < {energy_training}%) — checking wit only"
            )
            wit_pos = icon_positions.get("wit", fallback_positions["wit"])
            self.click_with_offset(*wit_pos)
            self.wait(0.7)
            screenshot = self.vision.take_screenshot()
            wit_info = self.decision.score_single_training("wit", screenshot, is_pre_summer)
            wit_score = wit_info.get("score", 0)

            if energy >= energy_low and wit_score >= 25:
                self.logger.info(
                    f"Wit has {wit_score}pts >= 25 — Wit restores energy, proceeding"
                )
                self._last_selected_training = "wit"
                self.click_with_offset(*wit_pos)
                self.wait(0.5)
                return None
            else:
                self.logger.info(
                    f"Energy {energy:.0f}% and wit {wit_score}pts — aborting to REST"
                )
                self.navigate_to_main_screen(screenshot)
                return "rest_summer" if is_summer else "rest"

        pre_selected = self._last_selected_training or "speed"
        others = [n for n in icon_positions if n != pre_selected and n != "speed"]
        scan_order = others
        if "speed" != pre_selected:
            scan_order.append("speed")
        scan_order.append(pre_selected)

        training_scores = {}
        for stat in scan_order:
            pos = icon_positions[stat]
            self.logger.info(f"  Clicking {stat} at {pos}")
            self.click_with_offset(*pos)
            self.wait(0.7)
            screenshot = self.vision.take_screenshot()

            slot_info = self.decision.score_single_training(stat, screenshot, is_pre_summer)
            training_scores[stat] = slot_info

        best_slot = max(training_scores, key=lambda s: training_scores[s]["score"]) if training_scores else None
        best_score = training_scores[best_slot]["score"] if best_slot else 0
        slot_summary = ", ".join(f"{s}={training_scores[s]['score']}pts" for s in training_scores)
        self.logger.info(f"Training scores — {slot_summary} | Best: {best_slot} ({best_score}pts)")

        if not is_junior and mood.lower() != "great":
            fallback = "rest_summer" if is_summer else "recreation"
            self.logger.info(
                f"Mood '{mood}' not Great in Classic/Senior — aborting to {fallback.upper()}"
            )
            self.navigate_to_main_screen(screenshot)
            return fallback

        if is_summer and best_score < 10 and energy < 80:
            self.logger.info(
                f"Summer: weak training ({best_score}pts) energy {energy:.0f}% "
                f"-> aborting to REST"
            )
            self.navigate_to_main_screen(screenshot)
            return "rest_summer"

        if best_slot and best_score > 0:
            target = best_slot
        elif training_type:
            target = training_type
        else:
            target = self.config.get("stat_priority", ["speed"])[0]

        currently_selected = scan_order[-1]
        self._last_selected_training = target
        target_pos = icon_positions.get(target, fallback_positions.get(target, fallback_positions["speed"]))
        info = training_scores.get(target, {})
        self.logger.info(
            f"Selecting training '{target}' at {target_pos} "
            f"(score={info.get('score', 0)}pts R={info.get('rainbow', 0)} "
            f"B={info.get('blue', 0)} W={info.get('white', 0)} F={info.get('friendship', 0)})"
        )

        if target != currently_selected:
            self.logger.info(f"Switching from {currently_selected} to {target}")
            self.click_with_offset(*target_pos)
            if self._interruptible_sleep(1.0):
                return None
            screenshot = self.vision.take_screenshot()
            new_pos = self.vision.find_template(f"training_{target}", screenshot, 0.55)
            if new_pos:
                target_pos = new_pos
                self.logger.info(f"Verified {target} at {new_pos}")

        self.logger.info(f"Confirming training '{target}' at {target_pos}")
        self.click_with_offset(*target_pos)
        if self._is_steam():
            time.sleep(random.uniform(0.05, 0.10))
            self.click_with_offset(*target_pos)
        for attempt in range(8):
            if self._interruptible_sleep(0.5):
                return None
            if self._check_stopped():
                return None
            ss = self.vision.take_screenshot()
            if self.vision.detect_screen(ss) != GameScreen.TRAINING:
                break
            if attempt == 2:
                self.logger.info(f"Re-clicking training '{target}' (click may have been missed)")
                self.click_with_offset(*target_pos)
        if self._handle_scheduled_race_popup():
            self.logger.info("Scheduled race preserved — navigating to main for race")
            self.navigate_to_main_screen(self.vision.take_screenshot())
            return "scheduled_race"
        return None

    def _handle_scheduled_race_popup(self) -> bool:
        screenshot = self.vision.take_screenshot()
        cancel_pos = self.vision.find_template("btn_cancel", screenshot, threshold=0.75)
        ok_pos = self.vision.find_template("btn_ok", screenshot, threshold=0.75)
        if cancel_pos and ok_pos:
            self.logger.info("Scheduled race conflict popup — clicking Cancel to preserve race")
            self.click_with_offset(*cancel_pos)
            self.wait(0.8)
            return True
        return False

    def execute_rest_action(self):
        self.logger.info("Executing REST action...")
        screenshot = self.vision.take_screenshot()
        rest_btn = "btn_rest"
        if self.vision.find_template("btn_rest_summer", screenshot, threshold=0.75):
            rest_btn = "btn_rest_summer"
            self.logger.info("Summer period — using Rest & Recreation button")
        if not self.click_button(rest_btn, screenshot):
            if rest_btn == "btn_rest_summer" and self.click_button("btn_rest", screenshot):
                pass
            else:
                self.logger.error("Cannot find Rest button")
                return
        self.wait(2.0)
        if self._handle_scheduled_race_popup():
            return
        self._handle_claw_machine()

    def _handle_claw_machine(self):
        screenshot = self.vision.take_screenshot()
        if not self.vision.find_template("btn_claw_machine", screenshot, threshold=0.7):
            return
        self.logger.info("Claw Machine mini-game detected!")
        for round_num in range(1, 4):
            if self._check_stopped():
                return
            self.logger.info(f"Claw Machine round {round_num}/3")
            pos = None
            for attempt in range(5):
                screenshot = self.vision.take_screenshot()
                pos = self.vision.find_template("btn_claw_machine", screenshot, threshold=0.7)
                if pos:
                    break
                if self._interruptible_sleep(1.0):
                    return
            if not pos:
                self.logger.warning(f"Claw machine button not found for round {round_num}")
                continue
            client_x = pos[0] - self.vision._client_offset_x
            client_y = pos[1] - self.vision._client_offset_y
            lp = self._make_lparam(client_x, client_y)
            hwnd = self.vision.game_hwnd
            if self._is_steam():
                origin = win32gui.ClientToScreen(hwnd, (0, 0))
                win32gui.SendMessage(hwnd, win32con.WM_ACTIVATE, win32con.WA_ACTIVE, 0)
                win32gui.SendMessage(hwnd, win32con.WM_SETFOCUS, 0, 0)
                ctypes.windll.user32.SetCursorPos(origin[0] + client_x, origin[1] + client_y)
                time.sleep(0.045)
            win32gui.SendMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lp)
            for _ in range(20):
                time.sleep(0.1)
                win32gui.PostMessage(hwnd, win32con.WM_MOUSEMOVE, win32con.MK_LBUTTON, lp)
            win32gui.SendMessage(hwnd, win32con.WM_LBUTTONUP, 0, lp)
            self.logger.info(f"Claw Machine round {round_num} — held 2 seconds")
            if self._interruptible_sleep(3.0):
                return
        self.logger.info("Claw Machine done — waiting for OK button")
        self.wait_and_click("btn_ok", timeout=15)

    def execute_infirmary_action(self):
        self.logger.info("Executing INFIRMARY action...")
        screenshot = self.vision.take_screenshot()
        if not self.vision.detect_injury(screenshot):
            self.logger.warning("Infirmary action requested but no injury detected — skipping")
            return
        if not self.click_button("btn_infirmary", screenshot):
            self.logger.error("Cannot find Infirmary button")
            return
        self.wait(0.5)

    def _handle_pal_recreation_popup(self) -> bool:
        screenshot = self.vision.take_screenshot()

        if not self.vision.find_template("recreation_popup", screenshot, 0.70):
            return False

        self.logger.info("PAL recreation popup detected — analysing rows...")

        popup_pos = self.vision.find_template("recreation_popup", screenshot, 0.70)
        click_x = popup_pos[0] if popup_pos else None

        empty_arrows = self.vision.find_all_template("arrow_empty", screenshot, 0.65, min_distance=15)
        filled_arrows = self.vision.find_all_template("arrow_filled", screenshot, 0.80, min_distance=15)

        EXCLUSION_DIST = 20
        empty_arrows = [
            ep for ep in empty_arrows
            if not any(abs(ep[0] - fp[0]) <= EXCLUSION_DIST and abs(ep[1] - fp[1]) <= EXCLUSION_DIST
                       for fp in filled_arrows)
        ]

        if empty_arrows:
            sorted_arrows = sorted(empty_arrows, key=lambda p: p[1])
            rows, cur = [], [sorted_arrows[0]]
            for pt in sorted_arrows[1:]:
                if abs(pt[1] - cur[-1][1]) <= 50:
                    cur.append(pt)
                else:
                    rows.append(cur)
                    cur = [pt]
            rows.append(cur)

            if click_x is None:
                click_x = int(sum(p[0] for p in rows[0]) / len(rows[0]))
            click_y = int(sum(p[1] for p in rows[0]) / len(rows[0]))
            self.logger.info(f"  {len(rows)} PAL row(s) — clicking topmost at ({click_x}, {click_y})")
            self.click_with_offset(click_x, click_y)
            self.wait(0.8)
            return True

        trainee_pos = self.vision.find_template("trainee_uma", screenshot, 0.70)
        if trainee_pos:
            self.logger.info(f"All PAL recreations complete — falling back to trainee row at {trainee_pos}")
            self.click_with_offset(*trainee_pos)
            self.wait(0.8)
            return True

        self.logger.warning("PAL popup detected but no arrows or trainee label — cancelling")
        cancel_pos = self.vision.find_template("btn_cancel", screenshot, 0.70)
        if cancel_pos:
            self.click_with_offset(*cancel_pos)
            self.wait(0.5)
        return False

    def execute_recreation_action(self):
        self.logger.info("Executing RECREATION action...")
        screenshot = self.vision.take_screenshot()
        if not self.click_button("btn_recreation", screenshot):
            self.logger.error("Cannot find Recreation button")
            return
        self.wait(0.8)

        if self._handle_scheduled_race_popup():
            return

        if self._handle_pal_recreation_popup():
            self.logger.info("PAL special recreation selected")
            return

        self.logger.info("No PAL popup — standard recreation")

    def execute_rainbow_training(self):
        self.logger.info("Executing RAINBOW TRAINING action...")
        screenshot = self.vision.take_screenshot()
        screen = self.vision.detect_screen(screenshot)
        if screen == GameScreen.MAIN:
            if not self.click_button("btn_training", screenshot):
                self.logger.error("Cannot find Training button")
                return
            self.wait(0.5)
            screenshot = self.vision.take_screenshot()

        rainbow_pos = self.vision.find_template("rainbow_training", screenshot, threshold=0.7)
        if rainbow_pos:
            self.click_with_offset(*rainbow_pos)
            self.wait(0.5)
            self.click_with_offset(*rainbow_pos)
            self.wait(0.5)
        else:
            self.logger.warning("Rainbow not found — fallback to burst")
            bursts = self.vision.detect_burst_training(screenshot)
            if bursts["blue"]:
                self.click_with_offset(*bursts["blue"][0])
                self.wait(0.5)
                self.click_with_offset(*bursts["blue"][0])
                self.wait(0.5)
            elif bursts["white"]:
                self.click_with_offset(*bursts["white"][0])
                self.wait(0.5)
                self.click_with_offset(*bursts["white"][0])
                self.wait(0.5)
            else:
                self.logger.warning("No burst found either")