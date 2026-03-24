import time
import random
import ctypes
import win32gui
import win32con
import numpy as np
from typing import Dict, Tuple

from ..models import GameScreen

_POLL = 0.07
_EVENT_WINDOWS = ("event_scenario_window", "event_trainee_window", "event_support_window")
_MAIN_BTNS     = ("btn_training", "btn_rest", "btn_recreation")
_TRAINING_BTNS = ("training_speed", "training_stamina", "training_power")

def _fast_is_main(vision, screenshot) -> bool:
    return sum(1 for t in _MAIN_BTNS if vision.find_template(t, screenshot, 0.80)) >= 2

def _fast_is_training(vision, screenshot) -> bool:
    return sum(1 for t in _TRAINING_BTNS if vision.find_template(t, screenshot, 0.60)) >= 2

def _fast_has_event(vision, screenshot) -> bool:
    return any(vision.find_template(t, screenshot, 0.75) for t in _EVENT_WINDOWS)

def _fast_is_race_start(vision, screenshot) -> bool:
    return (vision.find_template("btn_race_start", screenshot, 0.70) is not None or
            vision.find_template("btn_race_start_ura", screenshot, 0.70) is not None)

def _fast_is_unity(vision, screenshot) -> bool:
    return (vision.find_template("btn_unity_launch", screenshot, 0.75) is not None or
            vision.find_template("btn_begin_showdown", screenshot, 0.75) is not None)

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

    def _wait_for_training_screen(self, timeout: float = 3.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._check_stopped():
                return False
            ss = self.vision.take_screenshot()
            if _fast_is_training(self.vision, ss):
                return True
            if _fast_has_event(self.vision, ss):
                return False
            time.sleep(_POLL)
        return False

    def _has_event_window(self, screenshot) -> bool:
        return _fast_has_event(self.vision, screenshot)

    def _poll_until_main(self, timeout: float = 3.0):
        """
        Poll until main screen, handling events along the way.
        Used after rest and recreation — only outcomes are MAIN and EVENT.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._check_stopped():
                return
            ss = self.vision.take_screenshot()
            if _fast_has_event(self.vision, ss):
                self.logger.info("An event appeared — handling it.")
                self.handle_event(self._event_db)
                deadline = time.time() + 3.0
                continue
            if _fast_is_main(self.vision, ss):
                return
            time.sleep(_POLL)

    def _poll_until_training_resolved(self, timeout: float = 8.0):
        """
        Poll after training confirm is clicked.
        Possible outcomes: MAIN, EVENT, RACE_START (mandatory race), UNITY.
        Fast-checks each before falling through to idle wait.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._check_stopped():
                return
            ss = self.vision.take_screenshot()

            if _fast_has_event(self.vision, ss):
                self.logger.info("An event appeared after training — handling it.")
                self.handle_event(self._event_db)
                deadline = time.time() + 8.0
                continue

            if _fast_is_main(self.vision, ss):
                return

            if _fast_is_race_start(self.vision, ss):
                self.logger.info("Mandatory race day triggered after training — starting race.")
                self.execute_race_action("raceday")
                return

            if _fast_is_unity(self.vision, ss):
                self.logger.info("Unity Cup triggered after training — running Unity Cup.")
                self.execute_unity_cup()
                return

            time.sleep(_POLL)
        else:
            self.logger.warning("Timed out waiting to return to main screen after training.")

    def execute_training_action(self, training_info=None):
        if isinstance(training_info, dict):
            training_type = training_info.get("stat")
            cached_energy = training_info.get("energy", -1)
            cached_mood = training_info.get("mood", "unknown")
            cached_stats = training_info.get("stats")
        else:
            training_type = training_info
            cached_energy = -1
            cached_mood = "unknown"
            cached_stats = None

        screenshot = self.vision.take_screenshot()

        if _fast_is_main(self.vision, screenshot):
            screen = GameScreen.MAIN
        elif _fast_is_training(self.vision, screenshot):
            screen = GameScreen.TRAINING
        elif _fast_has_event(self.vision, screenshot):
            screen = GameScreen.EVENT
        else:
            screen = self.vision.detect_screen(screenshot)

        if screen == GameScreen.EVENT:
            self.logger.info("An event appeared before training — handling it first.")
            self.handle_event(self._event_db)
            time.sleep(_POLL)
            screenshot = self.vision.take_screenshot()
            if _fast_is_main(self.vision, screenshot):
                screen = GameScreen.MAIN
            elif _fast_is_training(self.vision, screenshot):
                screen = GameScreen.TRAINING
            else:
                screen = self.vision.detect_screen(screenshot)

        if screen == GameScreen.MAIN:
            if not self.click_button("btn_training", screenshot):
                self.logger.warning("Could not find the Training button.")
                if self.vision.detect_screen(screenshot) == GameScreen.EVENT:
                    self.handle_event(self._event_db)
                    return "failed"
                return "failed"
            self.logger.info("Opened the training screen.")

            self._wait_for_training_screen(timeout=3.0)
            screenshot = self.vision.take_screenshot()
            if _fast_is_training(self.vision, screenshot):
                screen = GameScreen.TRAINING
            elif _fast_has_event(self.vision, screenshot):
                screen = GameScreen.EVENT
            else:
                screen = self.vision.detect_screen(screenshot)

            race_popup = self.vision.find_template("btn_race", screenshot, 0.80)
            if race_popup and not self.vision.find_template("btn_race_launch", screenshot, 0.75):
                self.logger.info("A race popup appeared — heading to the race instead.")
                self.click_with_offset(*race_popup)
                self.wait(1.5)
                return None

        if screen == GameScreen.EVENT:
            self.logger.info("An event appeared after opening training — handling it.")
            self.handle_event(self._event_db)
            time.sleep(_POLL)
            screenshot = self.vision.take_screenshot()
            screen = GameScreen.TRAINING if _fast_is_training(self.vision, screenshot) else self.vision.detect_screen(screenshot)

        if screen != GameScreen.TRAINING:
            self.logger.warning(f"Expected training screen but got '{screen.value}' — trying again.")
            race_popup = self.vision.find_template("btn_race", screenshot, 0.80)
            if race_popup and not self.vision.find_template("btn_race_launch", screenshot, 0.75):
                self.click_with_offset(*race_popup)
                self.wait(1.5)
                return None
            if self.click_button("btn_training", screenshot):
                self._wait_for_training_screen(timeout=3.0)
                screenshot = self.vision.take_screenshot()
            else:
                self.logger.error("Could not reach the training screen.")
                return "failed"

        date_info = self.decision._get_cached_date(screenshot)
        current_turn = date_info.get("turn", 0) if date_info else 0
        is_pre_summer = date_info is not None and current_turn < 37
        is_summer = self.vision.is_summer_period(date_info)
        is_junior = not date_info or date_info.get("year") == "junior"
        is_senior = date_info is not None and date_info.get("year") in ("senior", "finale")

        template_positions = self.vision.get_training_options(screenshot)
        found_templates = {k: v for k, v in template_positions.items() if v is not None}
        self.logger.info(f"Training icons detected: {list(found_templates.keys())}")

        fallback_positions = self._get_training_positions(screenshot)
        icon_positions = {}
        for name in ["speed", "stamina", "power", "guts", "wit"]:
            tpl_pos = found_templates.get(name)
            fb_pos = fallback_positions[name]
            if tpl_pos:
                gx, _, gw, _ = self.vision.get_game_rect(screenshot)
                icon_positions[name] = tpl_pos if gx <= tpl_pos[0] <= gx + gw else fb_pos
            else:
                icon_positions[name] = fb_pos

        self.vision.save_debug_screenshot("training_screen")

        energy = cached_energy if cached_energy >= 0 else self.vision.read_energy_percentage(screenshot)
        mood = cached_mood if cached_mood != "unknown" else self.vision.detect_mood(screenshot)
        energy_training = self.config.get("thresholds", {}).get("energy_training", 50)
        energy_low = self.config.get("thresholds", {}).get("energy_low", 40)

        if energy < energy_training:
            self.logger.info(f"Energy too low ({energy:.0f}%) — checking Wit training only.")
            wit_pos = icon_positions.get("wit", fallback_positions["wit"])
            self.click_with_offset(*wit_pos)
            time.sleep(0.35)
            screenshot = self.vision.take_screenshot()
            wit_info = self.decision.score_single_training("wit", screenshot, is_pre_summer)
            wit_score = wit_info.get("score", 0)
            if energy >= energy_low and wit_score >= 25:
                self.logger.info(f"Wit is worthwhile (score: {wit_score:.0f}) — training Wit.")
                self._last_selected_training = "wit"
                self.click_with_offset(*wit_pos)
                time.sleep(_POLL)
                return None
            else:
                result = "rest_summer" if is_summer else "rest"
                self.logger.info(f"Wit not worth it (score: {wit_score:.0f}) — resting instead.")
                self.navigate_to_main_screen(screenshot)
                return result

        pre_selected = self._last_selected_training or "speed"
        others = [n for n in icon_positions if n != pre_selected and n != "speed"]
        scan_order = others
        if "speed" != pre_selected:
            scan_order.append("speed")
        scan_order.append(pre_selected)

        training_scores = {}
        for stat in scan_order:
            pos = icon_positions[stat]
            self.click_with_offset(*pos)
            time.sleep(0.35)
            screenshot = self.vision.take_screenshot()
            slot_info = self.decision.score_single_training(
                stat, screenshot, is_pre_summer,
                current_stats=cached_stats, is_senior=is_senior,
            )
            training_scores[stat] = slot_info
            self.logger.info(
                f"  {stat.title()}: {slot_info['score']:.0f} pts "
                f"(rainbow={slot_info['rainbow']}, blue={slot_info['blue']}, "
                f"white={slot_info['white']}, friends={slot_info['friendship']})"
            )

        best_slot = max(training_scores, key=lambda s: training_scores[s]["score"]) if training_scores else None
        best_score = training_scores[best_slot]["score"] if best_slot else 0

        if not is_junior and mood.lower() != "great":
            fallback = "rest_summer" if is_summer else "recreation"
            self.logger.info(f"Mood is '{mood}' (not Great) — switching to {fallback}.")
            self.navigate_to_main_screen(screenshot)
            return fallback

        if is_summer and best_score < 10 and energy < 80:
            self.logger.info(f"Summer break: training not worth it ({best_score:.0f} pts) — resting.")
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
        self.logger.info(f"Selected training: {target.title()} ({best_score:.0f} pts)")

        if target != currently_selected:
            self.click_with_offset(*target_pos)
            time.sleep(0.35)
            screenshot = self.vision.take_screenshot()
            new_pos = self.vision.find_template(f"training_{target}", screenshot, 0.55)
            if new_pos:
                target_pos = new_pos

        self.logger.info(f"Confirming {target.title()} training...")
        self.click_with_offset(*target_pos)
        if self._is_steam():
            time.sleep(random.uniform(0.05, 0.10))
            self.click_with_offset(*target_pos)

        deadline_confirm = time.time() + 6.0
        reclicked = False
        while time.time() < deadline_confirm:
            if self._check_stopped():
                return None
            ss = self.vision.take_screenshot()
            if not _fast_is_training(self.vision, ss):
                break
            if not reclicked and (deadline_confirm - time.time()) < 4.5:
                self.logger.info("Training confirm seems missed — clicking again.")
                self.click_with_offset(*target_pos)
                reclicked = True
            time.sleep(_POLL)
        else:
            self.logger.warning("Training confirmation timed out (6s).")

        if self._handle_scheduled_race_popup():
            self.logger.info("Scheduled race detected — navigating to race.")
            self.navigate_to_main_screen(self.vision.take_screenshot())
            return "scheduled_race"

        self._poll_until_training_resolved(timeout=8.0)

        return None

    def _handle_scheduled_race_popup(self) -> bool:
        screenshot = self.vision.take_screenshot()
        cancel_pos = self.vision.find_template("btn_cancel", screenshot, threshold=0.75)
        ok_pos = self.vision.find_template("btn_ok", screenshot, threshold=0.75)
        if cancel_pos and ok_pos:
            self.logger.info("Race conflict popup — cancelling to keep the scheduled race.")
            self.click_with_offset(*cancel_pos)
            self.wait(0.8)
            return True
        return False

    def execute_rest_action(self):
        self.logger.info("Resting...")
        screenshot = self.vision.take_screenshot()
        rest_btn = "btn_rest"
        if self.vision.find_template("btn_rest_summer", screenshot, threshold=0.75):
            rest_btn = "btn_rest_summer"
            self.logger.info("Summer break — using the summer rest option.")
        if not self.click_button(rest_btn, screenshot):
            if rest_btn == "btn_rest_summer" and self.click_button("btn_rest", screenshot):
                pass
            else:
                self.logger.warning("Rest button not found.")
                if self.vision.detect_screen(screenshot) == GameScreen.EVENT:
                    self.handle_event(self._event_db)
                    return
                self.logger.error("Could not perform rest action.")
                return
        self._poll_until_main(timeout=3.0)

    def _handle_claw_machine(self):
        screenshot = self.vision.take_screenshot()
        if not self.vision.find_template("btn_claw_machine", screenshot, threshold=0.7):
            if self.vision.find_template("claw_prizes", screenshot, 0.80):
                self.logger.info("Claw machine results — dismissing.")
                self.click_button("btn_ok", screenshot, threshold=0.65)
                self.wait(2.0)
            return
        self.logger.info("Claw machine mini-game starting!")
        if self._interruptible_sleep(5.0):
            return
        for round_num in range(1, 4):
            if self._check_stopped():
                return
            self.logger.info(f"Claw machine — round {round_num}/3")
            pos = None
            for attempt in range(8):
                screenshot = self.vision.take_screenshot()
                pos = self.vision.find_template("btn_claw_machine", screenshot, threshold=0.7)
                if pos:
                    break
                if self._interruptible_sleep(1.0):
                    return
            if not pos:
                self.logger.warning(f"Claw machine button not found for round {round_num}.")
                continue
            self._claw_hold_button(pos)
            self.logger.info(f"Claw machine round {round_num} complete.")
            if self._interruptible_sleep(5.0):
                return
        self.logger.info("Claw machine done — waiting for result screen.")
        for _ in range(15):
            if self._check_stopped():
                return
            if self.click_button("btn_ok", threshold=0.65):
                return
            time.sleep(1.0)
        self.logger.warning("Claw machine result screen timed out.")

    def _claw_hold_button(self, pos):
        hwnd = self.vision.game_hwnd
        client_x = pos[0] - self.vision._client_offset_x
        client_y = pos[1] - self.vision._client_offset_y
        if self._is_ldplayer():
            child = self._find_render_child(hwnd)
            target = child if child else hwnd
            if child:
                p_origin = win32gui.ClientToScreen(hwnd, (0, 0))
                c_origin = win32gui.ClientToScreen(child, (0, 0))
                client_x = client_x - (c_origin[0] - p_origin[0])
                client_y = client_y - (c_origin[1] - p_origin[1])
            lp = self._make_lparam(client_x, client_y)
            win32gui.PostMessage(target, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lp)
            for _ in range(20):
                time.sleep(0.1)
                win32gui.PostMessage(target, win32con.WM_MOUSEMOVE, win32con.MK_LBUTTON, lp)
            win32gui.PostMessage(target, win32con.WM_LBUTTONUP, 0, lp)
        elif self._is_steam():
            origin = win32gui.ClientToScreen(hwnd, (0, 0))
            win32gui.SendMessage(hwnd, win32con.WM_ACTIVATE, win32con.WA_ACTIVE, 0)
            win32gui.SendMessage(hwnd, win32con.WM_SETFOCUS, 0, 0)
            ctypes.windll.user32.SetCursorPos(origin[0] + client_x, origin[1] + client_y)
            time.sleep(0.045)
            lp = self._make_lparam(client_x, client_y)
            win32gui.SendMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lp)
            for _ in range(20):
                time.sleep(0.1)
                win32gui.PostMessage(hwnd, win32con.WM_MOUSEMOVE, win32con.MK_LBUTTON, lp)
            win32gui.SendMessage(hwnd, win32con.WM_LBUTTONUP, 0, lp)
        else:
            lp = self._make_lparam(client_x, client_y)
            win32gui.SendMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lp)
            for _ in range(20):
                time.sleep(0.1)
                win32gui.PostMessage(hwnd, win32con.WM_MOUSEMOVE, win32con.MK_LBUTTON, lp)
            win32gui.SendMessage(hwnd, win32con.WM_LBUTTONUP, 0, lp)

    def execute_infirmary_action(self):
        self.logger.info("Visiting the infirmary...")
        screenshot = self.vision.take_screenshot()
        if not self.vision.detect_injury(screenshot):
            self.logger.warning("No injury detected — skipping infirmary.")
            return
        if not self.click_button("btn_infirmary", screenshot):
            if self.vision.detect_screen(screenshot) == GameScreen.EVENT:
                self.handle_event(self._event_db)
                return
            self.logger.error("Could not find the infirmary button.")
            return
        time.sleep(_POLL)

    def _handle_pal_recreation_popup(self) -> bool:
        screenshot = self.vision.take_screenshot()
        if not self.vision.find_template("recreation_popup", screenshot, 0.70):
            return False
        self.logger.info("PAL recreation popup detected.")
        popup_pos = self.vision.find_template("recreation_popup", screenshot, 0.70)
        if not popup_pos:
            return False
        empty_arrows = self.vision.find_all_template("arrow_empty", screenshot, 0.70, min_distance=15)
        if empty_arrows:
            sorted_e = sorted(empty_arrows, key=lambda p: p[1])
            rows, cur = [], [sorted_e[0]]
            for pt in sorted_e[1:]:
                if abs(pt[1] - cur[-1][1]) <= 50:
                    cur.append(pt)
                else:
                    rows.append(cur)
                    cur = [pt]
            rows.append(cur)
            avg_y = int(sum(p[1] for p in rows[0]) / len(rows[0]))
            self.click_with_offset(popup_pos[0], avg_y)
        else:
            trainee_pos = self.vision.find_template("trainee_uma", screenshot, 0.70)
            if trainee_pos:
                self.click_with_offset(*trainee_pos)
            else:
                cancel_pos = self.vision.find_template("btn_cancel", screenshot, 0.75)
                if cancel_pos:
                    self.click_with_offset(*cancel_pos)
                return False
        time.sleep(_POLL)
        return True

    def execute_recreation_action(self):
        self.logger.info("Taking a recreation break...")
        screenshot = self.vision.take_screenshot()

        if self.vision.find_template("recreation_popup", screenshot, 0.70):
            self._handle_pal_recreation_popup()
        elif not self.click_button("btn_recreation", screenshot):
            self.logger.warning("Recreation button not found.")
            if self.vision.detect_screen(screenshot) == GameScreen.EVENT:
                self.handle_event(self._event_db)
                return
            self.logger.error("Could not perform recreation action.")
            return

        deadline = time.time() + 3.0
        while time.time() < deadline:
            if self._check_stopped():
                return
            ss = self.vision.take_screenshot()
            if self.vision.find_template("btn_claw_machine", ss, 0.70):
                self.logger.info("Claw machine appeared after recreation.")
                self._handle_claw_machine()
                break
            if _fast_is_main(self.vision, ss):
                return
            time.sleep(_POLL)

        self._poll_until_main(timeout=3.0)

    def execute_rainbow_training(self):
        self.logger.info("Executing rainbow training...")
        screenshot = self.vision.take_screenshot()
        if not _fast_is_training(self.vision, screenshot):
            if _fast_is_main(self.vision, screenshot):
                if not self.click_button("btn_training", screenshot):
                    self.logger.error("Could not open training screen for rainbow.")
                    return
                self._wait_for_training_screen(timeout=3.0)
        screenshot = self.vision.take_screenshot()
        gx, gy, gw, gh = self.vision.get_game_rect(screenshot)
        xf = self.vision._aspect_x_factor(gw, gh)
        cal = self.vision._calibration
        rainbow_positions = self.vision.count_rainbows_for_all(screenshot)
        if not rainbow_positions:
            self.logger.warning("No rainbow training found — falling back to normal training.")
            self.navigate_to_main_screen(screenshot)
            return
        best_stat = max(rainbow_positions, key=lambda s: rainbow_positions[s])
        defaults = {
            "speed": (0.145, 0.843), "stamina": (0.322, 0.843),
            "power": (0.500, 0.843), "guts": (0.678, 0.843),
            "wit": (0.855, 0.843),
        }
        tp = cal.get(f"train_{best_stat}", {})
        px = gx + int(gw * tp.get("x", defaults[best_stat][0]) * xf)
        py = gy + int(gh * tp.get("y", defaults[best_stat][1]))
        self.logger.info(f"Rainbow training — selecting {best_stat.title()}.")
        self.click_with_offset(px, py)
        time.sleep(0.35)
        self.click_with_offset(px, py)
        if self._is_steam():
            time.sleep(random.uniform(0.05, 0.10))
            self.click_with_offset(px, py)
        deadline = time.time() + 6.0
        while time.time() < deadline:
            if self._check_stopped():
                return
            if not _fast_is_training(self.vision, self.vision.take_screenshot()):
                break
            time.sleep(_POLL)