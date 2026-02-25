import time
from typing import Optional

from ..models import GameScreen, Action

class NavigationMixin:

    def navigate_to_main_screen(self, screenshot=None) -> bool:
        if screenshot is None:
            screenshot = self.vision.take_screenshot()

        for attempt in range(3):
            screen = self.vision.detect_screen(screenshot)
            self.logger.info(f"navigate_to_main: screen={screen.value} (attempt {attempt+1})")

            if screen == GameScreen.MAIN:
                return True

            if screen == GameScreen.TRAINING:
                if self.click_button("btn_back", screenshot):
                    self.logger.info("Clicked btn_back to return to main")
                else:
                    gx, gy, gw, gh = self.vision.get_game_rect(screenshot)
                    back_x = gx + int(gw * 0.06)
                    back_y = gy + int(gh * 0.02)
                    self.logger.info(f"btn_back not found, clicking fallback ({back_x}, {back_y})")
                    self.click_at(back_x, back_y)
                self.wait(1.0)
                screenshot = self.vision.take_screenshot()
                continue

            if screen == GameScreen.EVENT:
                self.logger.info("On event screen, cannot navigate to main directly")
                return False

            for btn in ["btn_next", "btn_tap", "btn_race_next_finish", "btn_skip", "btn_close", "btn_back"]:
                if self.vision.find_template(btn, screenshot, 0.75):
                    self.click_button(btn, screenshot)
                    self.wait(0.5)
                    break

            self.wait(0.5)
            screenshot = self.vision.take_screenshot()

        return self.vision.detect_screen(screenshot) == GameScreen.MAIN

    def _handle_try_again_cancel(self):
        screenshot = self.vision.take_screenshot()
        try_again = self.vision.find_template("btn_try_again", screenshot, threshold=0.75)
        if try_again:
            self.logger.info("Try Again dialog detected — clicking Try Again")
            self.click_button("btn_try_again", screenshot, threshold=0.75)
            self.wait(2.0)
            return True
        return False

    def execute_action(self, action: Action, details: Optional[str] = None, event_database: dict = None) -> bool:
        self.logger.info(f"Executing action: {action.value.upper()}")
        if event_database:
            self._event_db = event_database

        if action == Action.RACE:
            self.execute_race_action(details or "target")
            return True
        elif action == Action.INFIRMARY:
            self.execute_infirmary_action()
            return True
        elif action == Action.RAINBOW_TRAINING:
            self.execute_rainbow_training()
            return True
        elif action == Action.REST:
            self.execute_rest_action()
            return True
        elif action == Action.RECREATION:
            self.execute_recreation_action()
            return True
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
            else:
                return False
        elif action == Action.UNITY_CUP:
            self.execute_unity_cup()
            return True
        elif action == Action.CLAW_MACHINE:
            self.execute_claw_machine()
            return False
        elif action == Action.COMPLETE:
            self.logger.info("Complete Career reached")
            return False
        elif action == Action.SKIP:
            self.logger.info("Skipping — screen not ready, advance_turn will handle transitions")
            return False
        else:
            self.logger.warning(f"Unknown action: {action}")
            return False

    def execute_claw_machine(self):
        self.logger.info("Executing claw machine...")
        screenshot = self.vision.take_screenshot()

        claw_pos = self.vision.find_template("btn_claw_machine", screenshot, threshold=0.72)
        if not claw_pos:
            self.logger.debug("Claw machine button not found")
            return

        self.click_with_offset(*claw_pos)
        self.wait(2.0)

        for _ in range(5):
            if self._check_stopped():
                return
            screenshot = self.vision.take_screenshot()

            for btn in ("btn_ok", "btn_confirm", "btn_next", "btn_tap", "btn_close"):
                pos = self.vision.find_template(btn, screenshot, threshold=0.72)
                if pos:
                    gx, _, gw, _ = self.vision.get_game_rect(screenshot)
                    if gx <= pos[0] <= gx + gw:
                        self.click_button(btn, screenshot, threshold=0.72)
                        self.wait(1.0)
                        break
            else:
                gx, gy, gw, gh = self.vision.get_game_rect(screenshot)
                self.click_with_offset(gx + gw // 2, gy + int(gh * 0.7))
                self.wait(1.0)

            screen = self.vision.detect_screen(screenshot)
            if screen == GameScreen.MAIN:
                break

        self.logger.info("Claw machine sequence finished")

    def advance_turn(self):
        idle_count = 0
        event_fail_count = 0
        for _ in range(15):
            if self._check_stopped():
                return
            screenshot = self.vision.take_screenshot()

            if self.vision.is_at_career_complete(screenshot):
                self.logger.critical("CAREER COMPLETE detected in advance_turn — STOPPING IMMEDIATELY")
                return

            race_popup = self.vision.find_template("btn_race", screenshot, 0.80)
            if race_popup and not self.vision.find_template("btn_race_launch", screenshot, 0.75):
                self.logger.info("Scheduled race popup detected — clicking Race")
                self.click_with_offset(*race_popup)
                self.wait(1.0)
                screenshot = self.vision.take_screenshot()
                for btn in ("btn_ok", "btn_confirm"):
                    pos = self.vision.find_template(btn, screenshot, threshold=0.75)
                    if pos:
                        self.logger.info(f"Race confirmation popup in advance_turn — clicking {btn}")
                        self.click_with_offset(*pos)
                        self.wait(0.8)
                        break
                idle_count = 0
                continue

            close_pos = self.vision.find_template("btn_close", screenshot, 0.80)
            if close_pos:
                has_event_win = any(
                    self.vision.find_template(ew, screenshot, 0.82)
                    for ew in ["event_scenario_window", "event_trainee_window", "event_support_window"]
                )
                has_race_popup = bool(self.vision.find_template("btn_race", screenshot, 0.75))
                if not has_event_win and not has_race_popup:
                    self.logger.info("Popup with Close button detected — dismissing")
                    self.click_with_offset(*close_pos)
                    self.wait(0.8)
                    idle_count = 0
                    continue

            strat_count = sum(1 for s in ["strategy_end", "strategy_late", "strategy_pace", "strategy_front"]
                              if self.vision.find_template(s, screenshot, 0.80))
            if strat_count >= 4:
                self.logger.info("Strategy screen detected in advance_turn — selecting strategy")
                self._select_strategy_on_screen(screenshot)
                idle_count = 0
                continue

            is_skill_screen = (
                self.vision.find_template("learn_btn", screenshot, 0.72) or
                self.vision.find_template("buy_skill", screenshot, 0.82)
            )
            if not is_skill_screen and self.vision.find_template("btn_race_confirm", screenshot, 0.65):
                self.logger.info("Race selection screen detected in advance_turn — handling")
                self._handle_race_selection(screenshot)
                idle_count = 0
                continue

            if self.vision.find_template("race_view_results_on", screenshot, 0.75) or \
               self.vision.find_template("race_view_results_off", screenshot, 0.70) or \
               self.vision.find_template("btn_change_strategy", screenshot, 0.75):
                self.logger.info("Race preparation screen in advance_turn — running race")
                self._run_race()
                idle_count = 0
                continue

            unity_buttons = [
                "btn_begin_showdown", "btn_see_unity_results",
                "btn_next_unity", "btn_launch_final_unity",
                "btn_unity_launch", "btn_select_opponent",
            ]
            is_unity = any(self.vision.find_template(ub, screenshot, 0.70) for ub in unity_buttons)
            if is_unity:
                self.logger.info("Unity screen detected in advance_turn — executing Unity Cup")
                self.execute_unity_cup()
                idle_count = 0
                continue

            if self.vision.find_template("btn_inspiration", screenshot, threshold=0.75):
                self.click_button("btn_inspiration", screenshot)
                self.wait(0.5)
                idle_count = 0
                continue

            claw_pos = self.vision.find_template("btn_claw_machine", screenshot, threshold=0.72)
            if claw_pos:
                self.logger.info("Claw machine button detected in advance_turn — executing")
                self.execute_claw_machine()
                idle_count = 0
                continue

            if self.vision.find_template("btn_try_again", screenshot, threshold=0.75):
                self.logger.info("Try Again screen detected in advance_turn")
                self._handle_try_again_cancel()
                idle_count = 0
                continue

            found_btn = False
            for btn in ("btn_next", "btn_tap", "btn_race_next_finish", "btn_skip", "btn_ok"):
                pos = self.vision.find_template(btn, screenshot, threshold=0.75)
                if pos:
                    gx, _, gw, _ = self.vision.get_game_rect(screenshot)
                    if gx <= pos[0] <= gx + gw:
                        self.click_button(btn, screenshot)
                        self.wait(0.5)
                        found_btn = True
                        idle_count = 0
                        break
            if found_btn:
                continue

            event_type = self.vision.detect_event_type(screenshot)
            if event_type:
                handled = self.handle_event(self._event_db)
                if handled:
                    idle_count = 0
                    event_fail_count = 0
                else:
                    event_fail_count += 1
                    if event_fail_count >= 2:
                        self.logger.info("Event detected but unhandable twice — treating as transition")
                        gx, gy, gw, gh = self.vision.get_game_rect(screenshot)
                        self.click_with_offset(gx + gw // 2, gy + int(gh * 0.5))
                        self.wait(1.0)
                        event_fail_count = 0
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
                is_non_event = any(
                    self.vision.find_template(b, screenshot, 0.70) for b in non_event_buttons
                )
                if is_non_event:
                    self.logger.info("Event choices detected but non-event button visible — ignoring")
                    idle_count += 1
                    continue
                is_race_schedule = (
                    self.vision.find_template("scheduled_race", screenshot, 0.75) or
                    self.vision.find_template("target_race", screenshot, 0.75) or
                    self.vision.find_template("btn_race_confirm", screenshot, 0.65)
                )
                if is_race_schedule:
                    self.logger.info("Event choices detected on race schedule screen — ignoring")
                    idle_count += 1
                    continue
                gx, gy, gw, gh = self.vision.get_game_rect(screenshot)
                ec = self.vision._calibration.get("event_choices", {})
                y_min = gy + int(gh * ec.get("y1", 0.35))
                y_max = gy + int(gh * ec.get("y2", 0.85))
                valid = [c for c in choices if gx <= c[0] <= gx + gw and y_min <= c[1] <= y_max]
                if 1 <= len(valid) <= 5:
                    self.logger.info(f"Event choices detected ({len(valid)}) without event type — handling as event")
                    handled = self.handle_event(self._event_db)
                    if handled:
                        idle_count = 0
                    continue

            screen = self.vision.detect_screen(screenshot)
            if screen == GameScreen.MAIN:
                break
            if screen == GameScreen.TRAINING:
                self.logger.info("advance_turn: on training screen, navigating back to main")
                self.navigate_to_main_screen(screenshot)
                break

            idle_count += 1
            if idle_count >= 8:
                self.logger.warning("Stuck in unknown state for too long")
                break
            self.logger.debug(f"No actionable UI found — waiting (idle {idle_count}/8)")
            self.wait(1.5)