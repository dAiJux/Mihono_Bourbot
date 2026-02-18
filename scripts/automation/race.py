import time

class RaceMixin:

    def execute_race_action(self, race_type: str):
        self.logger.info(f"Executing RACE action ({race_type})...")
        screenshot = self.vision.take_screenshot()

        if race_type == "raceday":
            if self.click_button("btn_race", screenshot):
                self.logger.info("Race day popup clicked")
                self.wait(1.5)
            else:
                pos = self.vision.detect_race_start_button(screenshot)
                if pos:
                    self.logger.info(f"Race start button clicked at {pos}")
                    self.click_with_offset(*pos)
                    self.wait(1.5)
                else:
                    self.logger.error("Cannot find any race start button on race day")
                    return
        elif race_type == "scheduled":
            if not self.click_button("btn_race_scheduled", screenshot):
                if not self.click_button("btn_races", screenshot):
                    self.logger.error("Cannot find Race button for scheduled race")
                    return
        else:
            if not self.click_button("btn_races", screenshot):
                self.logger.error("Cannot find Races button")
                return

        self.wait(1.0)
        self._handle_race_selection()
        self.wait(1.5)

        for _ in range(10):
            if self._check_stopped():
                return
            screenshot = self.vision.take_screenshot()
            cancel = self.vision.find_template("btn_cancel", screenshot, 0.80)
            if cancel:
                self.logger.info("Race confirmation popup detected — clicking Race")
                race_btn = self.vision.find_race_select_button(screenshot)
                if race_btn:
                    self.click_at(*race_btn)
                else:
                    self.click_button("btn_race_confirm", screenshot)
                self.wait(1.5)
                continue

            prep_indicators = ["btn_race_launch", "race_view_results_on",
                               "race_view_results_off", "btn_change_strategy"]
            on_prep = any(self.vision.find_template(t, screenshot, 0.70) for t in prep_indicators)
            if on_prep:
                self.logger.info("Race prep screen detected")
                break

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
            if goal_pos:
                self.logger.info(f"Clicking Goal race at {goal_pos}")
                self.click_at(*goal_pos)
                self.wait(0.8)
                screenshot = self.vision.take_screenshot()

        race_btn = self.vision.find_race_select_button(screenshot)
        if race_btn:
            self.logger.info(f"Clicking Race button at {race_btn}")
            self.click_at(*race_btn)
        else:
            self.logger.warning("Race button not found — clicking btn_race_confirm fallback")
            self.click_button("btn_race_confirm", screenshot)

    def _select_strategy_on_screen(self, screenshot=None):
        strategy = self.config.get("race_strategy", {}).get("default", "front")
        strategy_btn = f"strategy_{strategy.lower()}"
        self.logger.info(f"Selecting strategy: {strategy_btn}")
        if not self.click_button(strategy_btn, screenshot):
            self.logger.warning(f"Could not find strategy button: {strategy_btn}")
        self.wait(0.8)
        self.click_button("btn_confirm")
        self.wait(1.0)

    def _change_strategy(self):
        strategy = self.config["race_strategy"]["default"]
        self.logger.info(f"First race — changing strategy to: {strategy}")
        if not self.click_button("btn_change_strategy"):
            self.logger.warning("btn_change_strategy not found")
            return
        self.wait(1.0)
        strategy_btn = f"strategy_{strategy.lower()}"
        if not self.click_button(strategy_btn):
            self.logger.warning(f"Could not find strategy button: {strategy_btn}")
        self.wait(1.0)
        self.click_button("btn_confirm")
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
            self.wait(5.0)
        else:
            vr_off = self.vision.find_template("race_view_results_off", screenshot, threshold=0.70)
            if vr_off:
                self.logger.info("View Results OFF — toggling ON first")
                self.click_button("race_view_results_off", screenshot)
                self.wait(1.0)
                screenshot = self.vision.take_screenshot()
                if self.click_button("race_view_results_on", screenshot):
                    skip_animation = True
                    self.wait(5.0)

            if not skip_animation:
                self.logger.info("Launching race with animation")
                screenshot = self.vision.take_screenshot()
                if self.click_button("btn_race_launch", screenshot):
                    self.logger.info("btn_race_launch clicked — race starting")
                elif self.click_button("btn_race_start", screenshot):
                    self.logger.info("btn_race_start clicked — race starting")
                elif self.click_button("btn_race_start_ura", screenshot):
                    self.logger.info("btn_race_start_ura clicked — race starting")
                else:
                    self.logger.warning("No race launch button found")
                self.wait(2.0)

        if not skip_animation:
            for _ in range(15):
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
            time.sleep(4.0)
        else:
            self.logger.info("Waiting for race results screen...")

        for _ in range(15):
            if self._check_stopped():
                return
            s = self.vision.take_screenshot()
            for btn in ("btn_race_next_finish", "btn_tap", "btn_next", "btn_skip", "btn_ok"):
                if self.vision.find_template(btn, s, threshold=0.70):
                    self.logger.info(f"Race results screen detected ({btn})")
                    break
            else:
                time.sleep(1.5)
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

            if self.vision.is_at_career_complete(screenshot):
                self.logger.critical("CAREER COMPLETE in race results — stopping")
                return

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
                if no_button_count >= 3 and not center_tapped:
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
        