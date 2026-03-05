import time

class RaceMixin:

    def execute_race_action(self, race_type: str):
        self.logger.info(f"Executing RACE action ({race_type})...")

        if race_type == "raceday":
            self._execute_mandatory_race()
        else:
            self._execute_scheduled_race()

    def _execute_mandatory_race(self):
        screenshot = self.vision.take_screenshot()
        pos = self.vision.detect_race_start_button(screenshot)
        if pos:
            self.logger.info(f"Step 1: Clicking race start button at {pos}")
            self.click_with_offset(*pos)
        else:
            self.logger.error("Cannot find race start button on mandatory race page")
            return
        self.wait(1.5)

        self._click_race_on_race_select()
        self._click_race_on_confirm_popup()
        self._wait_for_race_prep()

        if not self.first_race_done:
            self._change_strategy()
            self.first_race_done = True
        self.wait(1.0)

        self._run_race_via_view_results(allow_try_again=True)

    def _execute_scheduled_race(self):
        self._click_race_on_race_select()
        self._click_race_on_confirm_popup()
        self._wait_for_race_prep()

        if not self.first_race_done:
            self._change_strategy()
            self.first_race_done = True
        self.wait(1.0)

        self._run_race_via_view_results(allow_try_again=False)

    def _click_race_on_race_select(self):
        for _ in range(10):
            if self._check_stopped():
                return
            screenshot = self.vision.take_screenshot()
            race_btn = self.vision.find_race_select_button(screenshot)
            if not race_btn:
                race_btn = self.vision.find_template("btn_race", screenshot, 0.80)
                if race_btn and self.vision.find_template("btn_race_launch", screenshot, 0.70):
                    race_btn = None
            if race_btn:
                self.logger.info(f"Step 2: Clicking Race on race_select at {race_btn}")
                self.click_at(*race_btn)
                self.wait(1.5)
                return
            time.sleep(0.5)
        self.logger.warning("Could not find Race button on race_select")

    def _click_race_on_confirm_popup(self):
        for _ in range(10):
            if self._check_stopped():
                return
            screenshot = self.vision.take_screenshot()

            prep_indicators = [
                "race_view_results_on", "race_view_results_off",
                "btn_change_strategy", "btn_race_launch",
            ]
            if any(self.vision.find_template(t, screenshot, 0.70) for t in prep_indicators):
                self.logger.info("Already on race prep — skipping confirm popup")
                return

            race_btn = self.vision.find_race_select_button(screenshot)
            if not race_btn:
                race_btn = self.vision.find_template("btn_race", screenshot, 0.80)
                if race_btn and self.vision.find_template("btn_race_launch", screenshot, 0.70):
                    race_btn = None
            if race_btn:
                self.logger.info(f"Step 3: Clicking Race on confirm popup at {race_btn}")
                self.click_at(*race_btn)
                self.wait(1.5)
                return
            time.sleep(0.5)
        self.logger.warning("Could not find Race button on confirm popup")

    def _wait_for_race_prep(self):
        prep_indicators = [
            "race_view_results_on", "race_view_results_off",
            "btn_change_strategy", "btn_race_launch",
        ]
        for _ in range(15):
            if self._check_stopped():
                return
            screenshot = self.vision.take_screenshot()
            if any(self.vision.find_template(t, screenshot, 0.70) for t in prep_indicators):
                self.logger.info("Race prep screen detected")
                return

            strat_count = sum(
                1 for s in ["strategy_end", "strategy_late", "strategy_pace", "strategy_front"]
                if self.vision.find_template(s, screenshot, 0.80)
            )
            if strat_count >= 4:
                self.logger.info("Strategy screen detected — selecting strategy")
                self._select_strategy_on_screen(screenshot)
                self.wait(1.0)
                continue

            time.sleep(1.0)
        self.logger.warning("Timed out waiting for race prep screen")

    def _run_race_via_view_results(self, allow_try_again=True):
        if self._check_stopped():
            return
        screenshot = self.vision.take_screenshot()

        vr_on = self.vision.find_template("race_view_results_on", screenshot, threshold=0.75)
        if vr_on:
            self.logger.info("Step 5: View Results ON — clicking")
            self.click_button("race_view_results_on", screenshot)
        else:
            vr_off = self.vision.find_template("race_view_results_off", screenshot, threshold=0.70)
            if vr_off:
                self.logger.info("View Results OFF — toggling ON first")
                self.click_button("race_view_results_off", screenshot)
                self.wait(1.0)
                screenshot = self.vision.take_screenshot()
                self.click_button("race_view_results_on", screenshot)
            else:
                self.logger.warning("View Results button not found — cannot launch race")
                return

        gx, gy, gw, gh = self.vision.get_game_rect(self.vision.take_screenshot())
        tap_x = gx + gw // 2
        tap_y = gy + int(gh * 0.83)

        if allow_try_again:
            self._process_mandatory_results(tap_x, tap_y)
        else:
            self._process_scheduled_results(tap_x, tap_y)

    def _tap_center(self, tap_x, tap_y):
        time.sleep(3.0)
        self.click_with_offset(tap_x, tap_y)
        self.wait(1.5)

    def _reclick_result(self, btn_name):
        screenshot = self.vision.take_screenshot()
        self._click_result_button(btn_name, screenshot)
        self.wait(1.5)

    def _process_mandatory_results(self, tap_x, tap_y):
        self.logger.info("Step 6: Tapping center")
        self._tap_center(tap_x, tap_y)

        for attempt in range(3):
            if attempt > 0:
                self.logger.info(f"Step 6: Retrying tap (attempt {attempt + 1})")
                self._tap_center(tap_x, tap_y)
            found = None
            for _ in range(15):
                if self._check_stopped():
                    return
                screenshot = self.vision.take_screenshot()
                if self.vision.find_template("btn_try_again", screenshot, threshold=0.75):
                    found = "try_again"
                    break
                if self._click_result_button("btn_next", screenshot):
                    found = "next"
                    break
                time.sleep(0.5)
            if found:
                break
        else:
            self.logger.warning("Step 7: Failed to detect results after retries")
            return

        if found == "try_again":
            self.logger.info("Step 7.1: Try Again — clicking")
            self.click_button("btn_try_again", screenshot, threshold=0.75)
            self.wait(2.0)
            self._run_race_via_view_results(allow_try_again=True)
            return

        self.logger.info("Step 7.2: Results — btn_next clicked")
        self.wait(1.5)

        self._wait_and_click("btn_race_next_finish", "Step 8", lambda: self._reclick_result("btn_next"))
        self._wait_and_click("btn_next", "Step 9", lambda: self._reclick_result("btn_race_next_finish"))
        self._wait_and_click("btn_next", "Step 10", lambda: self._reclick_result("btn_next"))

    def _process_scheduled_results(self, tap_x, tap_y):
        self.logger.info("Step 6: Tapping center")
        self._tap_center(tap_x, tap_y)

        for attempt in range(3):
            if attempt > 0:
                self.logger.info(f"Step 6: Retrying tap (attempt {attempt + 1})")
                self._tap_center(tap_x, tap_y)
            found = False
            for _ in range(15):
                if self._check_stopped():
                    return
                screenshot = self.vision.take_screenshot()
                if self._click_result_button("btn_next", screenshot):
                    found = True
                    break
                time.sleep(0.5)
            if found:
                break
        else:
            self.logger.warning("Step 7: Failed to detect results after retries")
            return

        self.logger.info("Step 7: Results — btn_next clicked")
        self.wait(1.5)

        self._wait_and_click("btn_race_next_finish", "Step 8", lambda: self._reclick_result("btn_next"))

    def _click_result_button(self, btn_name, screenshot):
        pos = self.vision.find_template(btn_name, screenshot, threshold=0.70)
        if pos:
            gx, _, gw, _ = self.vision.get_game_rect(screenshot)
            if gx <= pos[0] <= gx + gw:
                self.click_button(btn_name, screenshot, threshold=0.70)
                return True
        return False

    def _wait_and_click(self, btn_name, step_label, retry_fn=None, retries=3):
        for attempt in range(retries):
            if attempt > 0 and retry_fn:
                self.logger.info(f"{step_label}: Retrying previous step (attempt {attempt + 1})")
                retry_fn()
            for _ in range(15):
                if self._check_stopped():
                    return True
                screenshot = self.vision.take_screenshot()
                if self._click_result_button(btn_name, screenshot):
                    self.logger.info(f"{step_label}: {btn_name} clicked")
                    self.wait(1.5)
                    return True
                time.sleep(0.5)
        self.logger.warning(f"{step_label}: Timed out after {retries} retries")
        return False

    def _handle_race_selection(self, screenshot=None):
        if screenshot is None:
            screenshot = self.vision.take_screenshot()

        race_btn = self.vision.find_race_select_button(screenshot)
        if race_btn:
            self.logger.info(f"Clicking Race button at {race_btn}")
            self.click_at(*race_btn)
        else:
            self.logger.warning("Race button not found — clicking btn_race_confirm fallback")
            self.click_button("btn_race_confirm", screenshot)
        self.wait(1.5)
        self._click_race_on_confirm_popup()
        self._wait_for_race_prep()

        if not self.first_race_done:
            self._change_strategy()
            self.first_race_done = True
        self.wait(1.0)
        self._run_race_via_view_results(allow_try_again=False)

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