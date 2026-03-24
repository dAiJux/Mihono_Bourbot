import time
from typing import Optional

from ..models import GameScreen, Action

_POLL = 0.07
_IDLE_MAX = 100
_FAST_FAIL_BEFORE_DETECT = 8

_MAIN_BTNS     = ("btn_training", "btn_rest", "btn_recreation")
_TRAINING_BTNS = ("training_speed", "training_stamina", "training_power")
_EVENT_WINDOWS = ("event_scenario_window", "event_trainee_window", "event_support_window")

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

class NavigationMixin:

    def navigate_to_main_screen(self, screenshot=None) -> bool:
        if screenshot is None:
            screenshot = self.vision.take_screenshot()

        for attempt in range(5):
            if self._check_stopped():
                return False

            if _fast_is_main(self.vision, screenshot):
                return True

            if _fast_is_training(self.vision, screenshot):
                self.logger.info("On the training screen — going back to main.")
                if self.click_button("btn_back", screenshot):
                    pass
                else:
                    gx, gy, gw, gh = self.vision.get_game_rect(screenshot)
                    xf = self.vision._aspect_x_factor(gw, gh)
                    self.click_at(gx + int(gw * 0.06 * xf), gy + int(gh * 0.02))
                deadline = time.time() + 4.0
                while time.time() < deadline:
                    time.sleep(_POLL)
                    ss = self.vision.take_screenshot()
                    if _fast_is_main(self.vision, ss):
                        return True
                screenshot = self.vision.take_screenshot()
                continue

            if _fast_has_event(self.vision, screenshot):
                self.logger.info("Event screen — cannot navigate away during an event.")
                return False

            for btn in ["btn_next", "btn_tap", "btn_race_next_finish", "btn_skip", "btn_close", "btn_back"]:
                if self.vision.find_template(btn, screenshot, 0.75):
                    self.click_button(btn, screenshot)
                    time.sleep(_POLL)
                    break
            else:
                time.sleep(_POLL)

            deadline = time.time() + 2.0
            while time.time() < deadline:
                time.sleep(_POLL)
                ss = self.vision.take_screenshot()
                if _fast_is_main(self.vision, ss):
                    return True
            screenshot = self.vision.take_screenshot()

        return _fast_is_main(self.vision, screenshot)

    def _handle_try_again_cancel(self):
        time.sleep(_POLL)
        screenshot = self.vision.take_screenshot()
        try_again = self.vision.find_template("btn_try_again", screenshot, threshold=0.75)
        if try_again:
            self.logger.info("Race failed — clicking Try Again.")
            self.click_button("btn_try_again", screenshot, threshold=0.75)
            self.wait(2.0)
            return True
        return False

    def execute_action(self, action: Action, details: Optional[str] = None, event_database: dict = None) -> bool:
        self.logger.info(f"Action: {action.value.upper()}")
        if event_database:
            self._event_db = event_database

        if action == Action.RACE:
            self.execute_race_action(details or "target")
        elif action == Action.INFIRMARY:
            self.execute_infirmary_action()
        elif action == Action.RAINBOW_TRAINING:
            self.execute_rainbow_training()
        elif action == Action.REST:
            self.execute_rest_action()
        elif action == Action.RECREATION:
            self.execute_recreation_action()
        elif action == Action.TRAINING:
            fallback = self.execute_training_action(details)
            if fallback is None:
                return True
            elif fallback in ("rest", "rest_summer"):
                self.execute_rest_action()
                return True
            elif fallback == "recreation":
                self.execute_recreation_action()
                return True
            elif fallback == "scheduled_race":
                self.execute_race_action("scheduled")
                return True
            else:
                return False
        elif action == Action.UNITY_CUP:
            self.execute_unity_cup()
        elif action == Action.CLAW_MACHINE:
            self.execute_claw_machine()
            return False
        elif action == Action.COMPLETE:
            return False
        elif action == Action.SKIP:
            return False
        else:
            self.logger.warning(f"Unknown action: {action}")
            return False

        return True

    def execute_claw_machine(self):
        self.logger.info("Running claw machine mini-game...")
        self._handle_claw_machine()

    def advance_turn(self):
        idle_count = 0
        event_fail_count = 0
        fast_fail_streak = 0

        for _ in range(200):
            if self._check_stopped():
                return

            screenshot = self.vision.take_screenshot()

            if self.vision.is_at_career_complete(screenshot):
                self.logger.critical("Career complete screen detected — stopping bot.")
                self.is_running = False
                return

            if _fast_is_main(self.vision, screenshot):
                resolved = self._handle_main_with_popups(screenshot)
                if resolved == "return":
                    return
                elif resolved == "continue":
                    idle_count = 0
                    fast_fail_streak = 0
                    continue
                else:
                    return

            if _fast_has_event(self.vision, screenshot):
                handled = self.handle_event(self._event_db)
                if handled:
                    idle_count = 0
                    event_fail_count = 0
                    fast_fail_streak = 0
                else:
                    event_fail_count += 1
                    if event_fail_count >= 2:
                        self.logger.info("Event could not be handled — tapping to dismiss.")
                        gx, gy, gw, gh = self.vision.get_game_rect(screenshot)
                        self.click_with_offset(gx + gw // 2, gy + int(gh * 0.5))
                        time.sleep(_POLL)
                        event_fail_count = 0
                fast_fail_streak = 0
                continue

            if _fast_is_training(self.vision, screenshot):
                idle_count += 1
                fast_fail_streak = 0
                if idle_count >= _IDLE_MAX:
                    self.logger.warning("Stuck on the training screen — navigating back to main.")
                    self.navigate_to_main_screen(screenshot)
                    break
                time.sleep(_POLL)
                continue

            if _fast_is_race_start(self.vision, screenshot):
                self.logger.info("Mandatory race day detected — starting race.")
                self.execute_race_action("raceday")
                idle_count = 0
                fast_fail_streak = 0
                continue

            fast_fail_streak += 1

            if fast_fail_streak < _FAST_FAIL_BEFORE_DETECT:
                if _fast_is_unity(self.vision, screenshot):
                    self.logger.info("Unity Cup detected — running Unity Cup.")
                    self.execute_unity_cup()
                    idle_count = 0
                    fast_fail_streak = 0
                    continue
                idle_count += 1
                if idle_count >= _IDLE_MAX:
                    self.logger.warning("Stuck on an unknown screen — giving up.")
                    break
                time.sleep(_POLL)
                continue

            fast_fail_streak = 0
            screen = self.vision.detect_screen(screenshot)

            if screen == GameScreen.MAIN:
                return

            if screen == GameScreen.EVENT:
                handled = self.handle_event(self._event_db)
                if handled:
                    idle_count = 0
                    event_fail_count = 0
                else:
                    event_fail_count += 1
                    if event_fail_count >= 2:
                        gx, gy, gw, gh = self.vision.get_game_rect(screenshot)
                        self.click_with_offset(gx + gw // 2, gy + int(gh * 0.5))
                        time.sleep(_POLL)
                        event_fail_count = 0
                continue

            if screen == GameScreen.TRAINING:
                idle_count += 1
                if idle_count >= _IDLE_MAX:
                    self.logger.warning("Stuck on training screen — navigating back.")
                    self.navigate_to_main_screen(screenshot)
                    break
                time.sleep(_POLL)
                continue

            if screen == GameScreen.SCHEDULED_RACE_POPUP:
                self.logger.info("Scheduled race popup — accepting race.")
                race_btn = self.vision.find_template("btn_race", screenshot, 0.80)
                if race_btn:
                    self.click_with_offset(*race_btn)
                else:
                    cancel_pos = self.vision.find_template("btn_cancel", screenshot, 0.70)
                    gx, gy, gw, gh = self.vision.get_game_rect(screenshot)
                    if cancel_pos:
                        center_x = gx + gw // 2
                        self.click_with_offset(center_x + (center_x - cancel_pos[0]), cancel_pos[1])
                self.wait(1.5)
                self._execute_scheduled_race()
                idle_count = 0
                continue

            if screen == GameScreen.INSUFFICIENT_FANS:
                self._handle_insufficient_fans(screenshot)
                idle_count = 0
                continue

            if screen == GameScreen.STRATEGY:
                self.logger.info("Strategy screen detected — selecting strategy.")
                self._select_strategy_on_screen(screenshot)
                idle_count = 0
                continue

            if screen == GameScreen.RACE_SELECT:
                self.logger.info("Race selection screen — picking a race.")
                self._handle_race_selection(screenshot)
                idle_count = 0
                continue

            if screen == GameScreen.RACE_START:
                self.logger.info("Race day screen — starting the race.")
                self.execute_race_action("raceday")
                idle_count = 0
                continue

            if screen == GameScreen.RACE:
                if self.vision.find_template("btn_race_confirm", screenshot, 0.65) or \
                   (self.vision.find_template("btn_race", screenshot, 0.80) and
                    not self.vision.find_template("btn_race_launch", screenshot, 0.75)):
                    self._handle_race_selection(screenshot)
                else:
                    self.logger.info("Race preparation screen — launching race.")
                    self._run_race_via_view_results(allow_try_again=True)
                idle_count = 0
                continue

            if screen == GameScreen.RACE_RESULT:
                for btn in ("btn_next", "btn_tap", "btn_race_next_finish", "btn_skip"):
                    pos = self.vision.find_template(btn, screenshot, threshold=0.75)
                    if pos:
                        gx, _, gw, _ = self.vision.get_game_rect(screenshot)
                        if gx <= pos[0] <= gx + gw:
                            self.click_button(btn, screenshot)
                            self.wait(2.0)
                            break
                idle_count = 0
                continue

            if screen == GameScreen.UNITY:
                self.logger.info("Unity Cup screen — running Unity Cup.")
                self.execute_unity_cup()
                idle_count = 0
                continue

            if screen == GameScreen.CLAW_MACHINE:
                self.logger.info("Claw machine detected — playing.")
                self.execute_claw_machine()
                idle_count = 0
                continue

            if screen == GameScreen.INSPIRATION:
                self.click_button("btn_inspiration", screenshot)
                time.sleep(_POLL)
                idle_count = 0
                continue

            if screen == GameScreen.TRY_AGAIN:
                self.logger.info("Try Again screen detected.")
                self._handle_try_again_cancel()
                idle_count = 0
                continue

            if screen in (GameScreen.RECREATION, GameScreen.SKILL_SELECT):
                time.sleep(_POLL)
                continue

            close_pos = self.vision.find_template("btn_close", screenshot, 0.80)
            if close_pos:
                has_event_win = _fast_has_event(self.vision, screenshot)
                has_race_popup = bool(
                    self.vision.find_template("btn_race", screenshot, 0.75) or
                    self.vision.find_template("scheduled_race_popup", screenshot, 0.75)
                )
                if not has_event_win and not has_race_popup:
                    self.logger.info("Closing a popup.")
                    self.click_with_offset(*close_pos)
                    time.sleep(_POLL)
                    idle_count = 0
                    continue

            cancel_pos = self.vision.find_template("btn_cancel", screenshot, threshold=0.75)
            ok_pos = self.vision.find_template("btn_ok", screenshot, threshold=0.75)
            if cancel_pos and ok_pos:
                self.logger.info("Conflict popup — cancelling to preserve scheduled race.")
                self.click_with_offset(*cancel_pos)
                time.sleep(_POLL)
                idle_count = 0
                continue

            if self.vision.find_template("race_view_results_on", screenshot, 0.75) or \
               self.vision.find_template("race_view_results_off", screenshot, 0.70) or \
               self.vision.find_template("btn_change_strategy", screenshot, 0.75):
                self.logger.info("Race preparation screen — launching race.")
                self._run_race()
                idle_count = 0
                continue

            found_btn = False
            for btn in ("btn_next", "btn_tap", "btn_race_next_finish", "btn_skip", "btn_ok"):
                pos = self.vision.find_template(btn, screenshot, threshold=0.75)
                if pos:
                    gx, _, gw, _ = self.vision.get_game_rect(screenshot)
                    if gx <= pos[0] <= gx + gw:
                        self.click_button(btn, screenshot)
                        time.sleep(_POLL)
                        found_btn = True
                        idle_count = 0
                        break
            if found_btn:
                continue

            choices = self.vision.find_all_template("event_choice", screenshot, threshold=0.75, min_distance=30)
            if choices:
                non_event_buttons = [
                    "btn_ok", "btn_claw_machine", "btn_race_launch",
                    "btn_race_start", "btn_race_start_ura", "btn_race_next_finish",
                    "btn_begin_showdown", "btn_see_unity_results", "btn_next_unity",
                    "btn_launch_final_unity", "btn_unity_launch", "btn_select_opponent",
                    "btn_try_again", "btn_cancel",
                ]
                clicked_non_event = False
                for b in non_event_buttons:
                    pos = self.vision.find_template(b, screenshot, 0.70)
                    if pos:
                        gx_t, _, gw_t, _ = self.vision.get_game_rect(screenshot)
                        if gx_t <= pos[0] <= gx_t + gw_t:
                            self.click_with_offset(*pos)
                            time.sleep(_POLL)
                            clicked_non_event = True
                            idle_count = 0
                            break
                if clicked_non_event:
                    continue
                is_race_schedule = (
                    self.vision.find_template("scheduled_race", screenshot, 0.75) or
                    self.vision.find_template("scheduled_race_popup", screenshot, 0.75) or
                    self.vision.find_template("target_race", screenshot, 0.75) or
                    self.vision.find_template("btn_race_confirm", screenshot, 0.65)
                )
                if not is_race_schedule:
                    gx, gy, gw, gh = self.vision.get_game_rect(screenshot)
                    ec = self.vision._calibration.get("event_choices", {})
                    y_min = gy + int(gh * ec.get("y1", 0.35))
                    y_max = gy + int(gh * ec.get("y2", 0.85))
                    valid = [c for c in choices if gx <= c[0] <= gx + gw and y_min <= c[1] <= y_max]
                    if 1 <= len(valid) <= 5:
                        handled = self.handle_event(self._event_db)
                        if handled:
                            idle_count = 0
                        continue

            idle_count += 1
            self.logger.debug(f"Waiting for screen to settle... ({idle_count}/{_IDLE_MAX})")
            if idle_count >= _IDLE_MAX:
                self.logger.warning("Stuck on an unknown screen for too long — giving up.")
                break
            time.sleep(_POLL)

    def _handle_main_with_popups(self, screenshot) -> str:
        race_popup = self.vision.find_template("btn_race", screenshot, 0.80)
        insuf_icon = self.vision.find_template("insufficient_fans_icon", screenshot, 0.80)
        sched_popup = self.vision.find_template("scheduled_race_popup", screenshot, 0.70)

        if (race_popup and not self.vision.find_template("btn_race_launch", screenshot, 0.75)) or sched_popup:
            self.logger.info("Scheduled race popup over main screen — accepting race.")
            if race_popup:
                self.click_with_offset(*race_popup)
            else:
                cancel_pos = self.vision.find_template("btn_cancel", screenshot, 0.70)
                gx, gy, gw, gh = self.vision.get_game_rect(screenshot)
                if cancel_pos:
                    center_x = gx + gw // 2
                    self.click_with_offset(center_x + (center_x - cancel_pos[0]), cancel_pos[1])
            self.wait(1.5)
            self._execute_scheduled_race()
            return "continue"

        if insuf_icon:
            self.logger.info("Insufficient fans popup — handling.")
            self._handle_insufficient_fans(screenshot)
            return "continue"

        close_pos = self.vision.find_template("btn_close", screenshot, 0.80)
        if close_pos:
            has_event_win = _fast_has_event(self.vision, screenshot)
            if not has_event_win:
                self.logger.info("Closing a popup on the main screen.")
                self.click_with_offset(*close_pos)
                time.sleep(_POLL)
                return "continue"

        return "return"

    def _handle_insufficient_fans(self, screenshot):
        insuf_pos = self.vision.find_template("insufficient_fans", screenshot, 0.70)
        force = self.config.get("race_strategy", {}).get("force_race_insufficient_fans", True)
        cancel_pos = self.vision.find_template("btn_cancel", screenshot, 0.70)
        gx, gy, gw, gh = self.vision.get_game_rect(screenshot)
        if force:
            self.logger.info("Insufficient fans warning — forcing race entry.")
            if cancel_pos:
                center_x = gx + gw // 2
                self.click_with_offset(center_x + (center_x - cancel_pos[0]), cancel_pos[1])
            elif insuf_pos:
                xf = self.vision._aspect_x_factor(gw, gh)
                self.click_with_offset(gx + int(gw * 0.65 * xf), insuf_pos[1] + int(gh * 0.30))
            self.wait(1.0)
            self._execute_scheduled_race()
        else:
            self.logger.info("Insufficient fans warning — declining race.")
            if cancel_pos:
                self.click_with_offset(*cancel_pos)
            elif insuf_pos:
                xf = self.vision._aspect_x_factor(gw, gh)
                self.click_with_offset(gx + int(gw * 0.35 * xf), insuf_pos[1] + int(gh * 0.30))
            self.wait(1.0)