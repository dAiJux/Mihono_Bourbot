import time

class RaceMixin:

    def execute_race_action(self, race_type: str):
        self.logger.info(f"Executing RACE action ({race_type})...")
        screenshot = self.vision.take_screenshot()

        if race_type == "raceday":
            pos = self.vision.detect_race_start_button(screenshot)
            if pos:
                self.logger.info(f"Race start button clicked at {pos}")
                self.click_with_offset(*pos)
            elif not self.click_button("btn_race", screenshot):
                self.logger.error("Cannot find any race start button on race day")
                return
            self.wait(1.0)
            self._dismiss_race_confirm_popup()
            self.wait(1.0)
            self._handle_mandatory_race_flow()
            return

        elif race_type == "scheduled":
            if not self.click_button("btn_races", screenshot):
                self.logger.error("Cannot find Races button for scheduled race")
                return
            self.wait(1.0)
            self._dismiss_race_confirm_popup()

        else:
            if not self.click_button("btn_races", screenshot):
                self.logger.error("Cannot find Races button")
                return
            self.wait(1.0)
            self._dismiss_race_confirm_popup()

        self._wait_for_race_prep_or_selection()

    def _dismiss_race_confirm_popup(self):
        screenshot = self.vision.take_screenshot()
        for btn in ("btn_ok", "btn_confirm", "btn_race"):
            pos = self.vision.find_template(btn, screenshot, threshold=0.75)
            if pos and not self.vision.find_template("btn_race_launch", screenshot, 0.75):
                self.logger.info(f"Race confirmation popup — clicking {btn}")
                self.click_with_offset(*pos)
                self.wait(2.0)
                return

    def _handle_mandatory_race_flow(self):
        for _ in range(15):
            if self._check_stopped():
                return
            screenshot = self.vision.take_screenshot()
            race_btn = self.vision.find_race_select_button(screenshot)
            if race_btn:
                self.click_at(*race_btn)
                self.wait(1.0)
                break
            time.sleep(0.5)
        for _ in range(10):
            if self._check_stopped():
                return
            screenshot = self.vision.take_screenshot()
            if self.vision.find_template("btn_race_confirm", screenshot, 0.80):
                self.click_button("btn_race_confirm", screenshot)
                self.wait(1.0)
                break
            time.sleep(0.5)
        self._wait_for_race_prep_or_selection()

    def _wait_for_race_prep_or_selection(self):
        last_goal_pos = None
        last_goal_time = 0
        for _ in range(15):
            if self._check_stopped():
                return
            screenshot = self.vision.take_screenshot()

            prep_indicators = [
                "btn_race_launch", "race_view_results_on",
                "race_view_results_off", "btn_change_strategy",
                "btn_race_start", "btn_race_start_ura",
            ]
            on_prep = any(self.vision.find_template(t, screenshot, 0.70) for t in prep_indicators)
            if on_prep:
                self.logger.info("Race prep screen detected")
                break

            strat_count = sum(
                1 for s in ["strategy_end", "strategy_late", "strategy_pace", "strategy_front"]
                if self.vision.find_template(s, screenshot, 0.80)
            )
            if strat_count >= 4:
                self.logger.info("Strategy screen detected — selecting strategy")
                self._select_strategy_on_screen(screenshot)
                self.wait(1.0)
                continue

            if self.vision.find_template("btn_cancel", screenshot, 0.80):
                self.logger.info("Race confirmation popup detected")
                race_btn = self.vision.find_race_select_button(screenshot)
                if race_btn:
                    self.click_at(*race_btn)
                else:
                    self.click_button("btn_race_confirm", screenshot)
                self.wait(1.5)
                continue

            goal_pos = self.vision.detect_goal_race(screenshot)
            now = time.time()
            if goal_pos:
                if last_goal_pos is not None:
                    dx = abs(goal_pos[0] - last_goal_pos[0])
                    dy = abs(goal_pos[1] - last_goal_pos[1])
                else:
                    dx = dy = 9999
                if dx < 10 and dy < 10 and (now - last_goal_time) < 5:
                    self.logger.debug("Already clicked on goal race recently, skipping.")
                    time.sleep(0.5)
                else:
                    self.logger.info(f"Goal race detected at {goal_pos} — clicking")
                    self.click_at(*goal_pos)
                    last_goal_pos = goal_pos
                    last_goal_time = now
                    self.wait(2.0)
                continue

            self.logger.debug("Waiting for race prep screen...")
            time.sleep(1.0)

        if not self.first_race_done:
            self._change_strategy()
            self.first_race_done = True
        self.wait(1.0)
        self._run_race()

    def _handle_race_selection(self, screenshot=None):
        if screenshot is None:
            screenshot = self.vision.take_screenshot()

        cancel = self.vision.find_template("btn_cancel", screenshot, 0.80)
        if not cancel:
            goal_pos = self.vision.detect_goal_race(screenshot)
            now = time.time()
            if not hasattr(self, '_last_goal_pos_sel'):
                self._last_goal_pos_sel = None
                self._last_goal_time_sel = 0
            if goal_pos:
                if self._last_goal_pos_sel is not None:
                    dx = abs(goal_pos[0] - self._last_goal_pos_sel[0])
                    dy = abs(goal_pos[1] - self._last_goal_pos_sel[1])
                else:
                    dx = dy = 9999
                if dx < 10 and dy < 10 and (now - self._last_goal_time_sel) < 2:
                    pass
                else:
                    self.logger.info(f"Clicking Goal race at {goal_pos}")
                    self.click_at(*goal_pos)
                    self._last_goal_pos_sel = goal_pos
                    self._last_goal_time_sel = now
                    self.wait(0.8)
                    screenshot = self.vision.take_screenshot()

        race_btn = self.vision.find_race_select_button(screenshot)
        if race_btn:
            self.logger.info(f"Clicking Race button at {race_btn}")
            self.click_at(*race_btn)
        else:
            self.logger.warning("Race button not found — clicking btn_race_confirm fallback")
            self.click_button("btn_race_confirm", screenshot)
        self.wait(1.5)

    def _select_strategy_on_screen(self, screenshot=None):
        strategy = self.config.get("race_strategy", {}).get("default", "front")
        strategy_btn = f"strategy_{strategy.lower()}"
        if screenshot is None:
            screenshot = self.vision.take_screenshot()
        self.logger.info(f"Selecting strategy: {strategy_btn}")
        if not self.click_button(strategy_btn, screenshot):
            self.logger.warning(f"Could not find strategy button: {strategy_btn}")
        self.wait(0.8)
        screenshot = self.vision.take_screenshot()
        if not self.click_button("btn_confirm", screenshot):
            self.click_button("btn_ok", screenshot)
        self.wait(1.0)

    def _change_strategy(self):
        strategy = self.config["race_strategy"]["default"]
        self.logger.info(f"First race — changing strategy to: {strategy}")
        screenshot = self.vision.take_screenshot()
        if not self.vision.find_template("btn_change_strategy", screenshot, 0.75):
            self.logger.debug("No btn_change_strategy visible, skipping strategy change")
            return
        if not self.click_button("btn_change_strategy"):
            self.logger.warning("btn_change_strategy not found")
            return
        self.wait(2.0)
        strategy_btn = f"strategy_{strategy.lower()}"
        if not self.click_button(strategy_btn):
            self.logger.warning(f"Could not find strategy button: {strategy_btn}")
        self.wait(1.0)
        screenshot = self.vision.take_screenshot()
        if not self.click_button("btn_confirm", screenshot):
            self.click_button("btn_ok", screenshot)
        self.wait(1.0)

    def _run_race(self):
        if self._check_stopped():
            return
        screenshot = self.vision.take_screenshot()

        skip_animation = False
        vr_on = self.vision.find_template("race_view_results_on", screenshot, threshold=0.75)
        if vr_on:
            self.logger.info("View Results available — clicking to skip race animation")
            self.click_button("race_view_results_on", screenshot)
            skip_animation = True
            self.wait(2.0)
        else:
            vr_off = self.vision.find_template("race_view_results_off", screenshot, threshold=0.70)
            if vr_off:
                self.logger.info("View Results OFF — toggling ON first")
                self.click_button("race_view_results_off", screenshot)
                self.wait(1.0)
                screenshot = self.vision.take_screenshot()
                if self.click_button("race_view_results_on", screenshot):
                    skip_animation = True
                    self.wait(2.0)

            if not skip_animation:
                self.logger.info("Launching race with animation")
                screenshot = self.vision.take_screenshot()
                launched = False
                for btn in ("btn_race_launch", "btn_race_start", "btn_race_start_ura"):
                    if self.click_button(btn, screenshot):
                        self.logger.info(f"{btn} clicked — race starting")
                        launched = True
                        break
                if not launched:
                    pos = self.vision.detect_race_start_button(screenshot)
                    if pos:
                        self.click_with_offset(*pos)
                        self.logger.info("Race start via HSV fallback")
                    else:
                        self.logger.warning("No race launch button found")
                self.wait(2.0)

        if not skip_animation:
            for _ in range(20):
                if self._check_stopped():
                    return
                s = self.vision.take_screenshot()
                if self.vision.find_template("btn_skip", s, threshold=0.7):
                    self.click_button("btn_skip", s)
                    self.wait(1)
                    break
                time.sleep(2)
            for _ in range(10):
                if self._check_stopped():
                    return
                s = self.vision.take_screenshot()
                if self.vision.find_template("btn_skip", s, threshold=0.7):
                    self.click_button("btn_skip", s)
                time.sleep(1)

        if skip_animation:
            self.logger.info("Waiting for race results screen (post-View Results)...")
            time.sleep(1.0)
        else:
            self.logger.info("Waiting for race results screen...")

        for _ in range(20):
            if self._check_stopped():
                return
            s = self.vision.take_screenshot()
            for btn in ("btn_race_next_finish", "btn_tap", "btn_next", "btn_skip", "btn_ok"):
                if self.vision.find_template(btn, s, threshold=0.70):
                    self.logger.info(f"Race results screen detected ({btn})")
                    break
            else:
                time.sleep(0.8)
                continue
            break

        self._finish_race_results()

    def _finish_race_results(self):
        self.logger.info("Processing race results...")
        no_button_count = 0
        center_tapped = False
        for attempt in range(30):
            if self._check_stopped():
                return
            screenshot = self.vision.take_screenshot()

            if self.vision.find_template("btn_try_again", screenshot, threshold=0.75):
                self.logger.info("Try Again screen detected during results")
                self._handle_try_again_cancel()
                return

            if self.vision.find_template("btn_inspiration", screenshot, threshold=0.75):
                self.logger.info("Inspiration detected during race results — clicking")
                self.click_button("btn_inspiration", screenshot)
                self.wait(0.5)
                no_button_count = 0
                continue

            found = False
            for btn in ("btn_race_next_finish", "btn_tap", "btn_next", "btn_skip", "btn_ok"):
                pos = self.vision.find_template(btn, screenshot, threshold=0.70)
                if pos:
                    gx, _, gw, _ = self.vision.get_game_rect(screenshot)
                    if gx <= pos[0] <= gx + gw:
                        self.click_button(btn, screenshot, threshold=0.70)
                        if btn == "btn_race_next_finish":
                            self.wait(1.0)
                            self._handle_try_again_cancel()
                            return
                        self.wait(0.8)
                        found = True
                        no_button_count = 0
                        center_tapped = False
                        break

            if not found:
                no_button_count += 1
                if no_button_count >= 2 and not center_tapped:
                    gx, gy, gw, gh = self.vision.get_game_rect(screenshot)
                    tap_x = gx + gw // 2
                    tap_y = gy + int(gh * 0.83)
                    self.logger.info(f"No button found — tapping center once ({tap_x}, {tap_y})")
                    self.click_with_offset(tap_x, tap_y)
                    self.wait(1.0)
                    center_tapped = True
                    no_button_count = 0
                else:
                    time.sleep(0.5)

        self.logger.warning("Race results processing timed out")