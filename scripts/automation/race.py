import time

class RaceMixin:

    def execute_race_action(self, race_type: str):
        self.logger.info(f"Starting race ({race_type})...")
        if race_type == "raceday":
            self._execute_mandatory_race()
        else:
            self._execute_scheduled_race()

    def _execute_mandatory_race(self):
        screenshot = self.vision.take_screenshot()
        is_ura = self.vision.find_template("btn_race_start_ura", screenshot, 0.70) is not None
        pos = self.vision.detect_race_start_button(screenshot)
        if pos:
            self.logger.info(f"Race day — clicking start button{' (URA finale)' if is_ura else ''}.")
            self.click_with_offset(*pos)
        else:
            self.logger.error("Could not find the race start button.")
            return
        self.wait(1.5)

        self._click_race_on_race_select()
        self._click_race_on_confirm_popup()
        self._wait_for_race_prep()

        if not self.first_race_done:
            self._change_strategy()
            self.first_race_done = True
        self.wait(1.0)

        self._run_race_via_view_results(allow_try_again=True, is_ura=is_ura)

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
        for attempt in range(10):
            if self._check_stopped():
                return
            screenshot = self.vision.take_screenshot()
            race_btn = self.vision.find_race_select_button(screenshot)
            if not race_btn:
                race_btn = self.vision.find_template("btn_race", screenshot, 0.80)
                if race_btn and self.vision.find_template("btn_race_launch", screenshot, 0.70):
                    race_btn = None
            if race_btn:
                self.logger.info("Selecting race from the list.")
                self.click_at(*race_btn)
                self.wait(1.5)
                return
            time.sleep(0.5)
        self.logger.warning("Could not find the race selection button.")

    def _click_race_on_confirm_popup(self):
        for attempt in range(10):
            if self._check_stopped():
                return
            screenshot = self.vision.take_screenshot()
            prep_indicators = [
                "race_view_results_on", "race_view_results_off",
                "btn_change_strategy", "btn_race_launch",
            ]
            if any(self.vision.find_template(t, screenshot, 0.70) for t in prep_indicators):
                return
            race_btn = self.vision.find_race_select_button(screenshot)
            if not race_btn:
                race_btn = self.vision.find_template("btn_race", screenshot, 0.80)
                if race_btn and self.vision.find_template("btn_race_launch", screenshot, 0.70):
                    race_btn = None
            if race_btn:
                self.logger.info("Confirming race entry.")
                self.click_at(*race_btn)
                self.wait(1.5)
                return
            time.sleep(0.5)
        self.logger.warning("Could not confirm race entry.")

    def _wait_for_race_prep(self):
        prep_indicators = [
            "race_view_results_on", "race_view_results_off",
            "btn_change_strategy", "btn_race_launch",
        ]
        for attempt in range(15):
            if self._check_stopped():
                return
            screenshot = self.vision.take_screenshot()
            if any(self.vision.find_template(t, screenshot, 0.70) for t in prep_indicators):
                self.logger.info("Race preparation screen ready.")
                return
            strat_count = sum(
                1 for s in ["strategy_end", "strategy_late", "strategy_pace", "strategy_front"]
                if self.vision.find_template(s, screenshot, 0.80)
            )
            if strat_count >= 4:
                self.logger.info("Strategy screen appeared — selecting strategy.")
                self._select_strategy_on_screen(screenshot)
                self.wait(1.0)
                continue
            time.sleep(1.0)
        self.logger.warning("Timed out waiting for race preparation screen.")

    def _run_race_via_view_results(self, allow_try_again=True, is_ura=False):
        if self._check_stopped():
            return
        screenshot = self.vision.take_screenshot()

        vr_on = self.vision.find_template("race_view_results_on", screenshot, threshold=0.75)
        if vr_on:
            self.logger.info("Launching race...")
            self.click_button("race_view_results_on", screenshot)
        else:
            vr_off = self.vision.find_template("race_view_results_off", screenshot, threshold=0.70)
            if vr_off:
                self.logger.info("Enabling result display, then launching race...")
                self.click_button("race_view_results_off", screenshot)
                self.wait(1.0)
                screenshot = self.vision.take_screenshot()
                self.click_button("race_view_results_on", screenshot)
            else:
                self.logger.warning("Could not find the race launch button.")
                return

        gx, gy, gw, gh = self.vision.get_game_rect(self.vision.take_screenshot())
        tap_x = gx + gw // 2
        tap_y = gy + int(gh * 0.83)

        if allow_try_again:
            self._process_mandatory_results(tap_x, tap_y, is_ura=is_ura)
        else:
            self._process_scheduled_results(tap_x, tap_y)

    def _tap_center(self, tap_x, tap_y):
        self.logger.info("Waiting for race to finish...")
        time.sleep(3.0)
        self.click_with_offset(tap_x, tap_y)
        self.wait(1.5)

    def _reclick_result(self, btn_name):
        screenshot = self.vision.take_screenshot()
        self._click_result_button(btn_name, screenshot)
        self.wait(1.5)

    def _process_mandatory_results(self, tap_x, tap_y, is_ura=False):
        self._tap_center(tap_x, tap_y)

        found = None
        for attempt in range(3):
            if attempt > 0:
                self.logger.info(f"Retrying result screen tap (attempt {attempt + 1})...")
                self._tap_center(tap_x, tap_y)
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
            self.logger.warning("Could not detect race result screen.")
            return

        if found == "try_again":
            self.logger.info("Race failed — trying again.")
            self.click_button("btn_try_again", screenshot, threshold=0.75)
            self.wait(2.0)
            self._run_race_via_view_results(allow_try_again=True, is_ura=is_ura)
            return

        self.logger.info("Race finished — advancing through results.")
        self.wait(1.5)
        self._wait_and_click("btn_race_next_finish", "result step 1", lambda: self._reclick_result("btn_next"))
        if not is_ura:
            self._wait_and_click("btn_next", "result step 2", lambda: self._reclick_result("btn_race_next_finish"))
            self._wait_and_click("btn_next", "result step 3", lambda: self._reclick_result("btn_next"))
        else:
            self.logger.info("URA finale — skipping extra result screens.")

    def _process_scheduled_results(self, tap_x, tap_y):
        self._tap_center(tap_x, tap_y)

        found = False
        for attempt in range(3):
            if attempt > 0:
                self.logger.info(f"Retrying result screen tap (attempt {attempt + 1})...")
                self._tap_center(tap_x, tap_y)
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
            self.logger.warning("Could not detect race result screen.")
            return

        self.wait(1.5)
        self._wait_and_click("btn_race_next_finish", "result step 1", lambda: self._reclick_result("btn_next"))

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
                self.logger.info(f"Retrying {step_label} (attempt {attempt + 1})...")
                retry_fn()
            for _ in range(15):
                if self._check_stopped():
                    return True
                screenshot = self.vision.take_screenshot()
                if self._click_result_button(btn_name, screenshot):
                    self.wait(1.5)
                    return True
                time.sleep(0.5)
        self.logger.warning(f"Timed out on {step_label}.")
        return False

    def _handle_race_selection(self, screenshot=None):
        if screenshot is None:
            screenshot = self.vision.take_screenshot()
        self.logger.info("Handling race selection...")
        race_btn = self.vision.find_race_select_button(screenshot)
        if race_btn:
            self.click_at(*race_btn)
        else:
            self.logger.warning("Race button not found — using confirm button fallback.")
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
        self.logger.info(f"Selecting strategy: {strategy}.")
        if not self.click_button(strategy_btn, screenshot):
            self.logger.warning(f"Strategy button '{strategy}' not found.")
        self.wait(0.8)
        screenshot = self.vision.take_screenshot()
        if not self.click_button("btn_confirm", screenshot):
            self.click_button("btn_ok", screenshot)
        self.wait(1.0)

    def _change_strategy(self):
        strategy = self.config["race_strategy"]["default"]
        self.logger.info(f"Setting race strategy to: {strategy}.")
        screenshot = self.vision.take_screenshot()
        if not self.vision.find_template("btn_change_strategy", screenshot, 0.75):
            self.logger.debug("Strategy button not visible — skipping.")
            return
        if not self.click_button("btn_change_strategy"):
            self.logger.warning("Could not open strategy menu.")
            return
        self.wait(2.0)
        strategy_btn = f"strategy_{strategy.lower()}"
        if not self.click_button(strategy_btn):
            self.logger.warning(f"Strategy button '{strategy}' not found.")
        self.wait(1.0)
        screenshot = self.vision.take_screenshot()
        if not self.click_button("btn_confirm", screenshot):
            self.click_button("btn_ok", screenshot)
        self.wait(1.0)

    def _run_race(self):
        self.logger.info("Launching race from preparation screen.")
        self._run_race_via_view_results(allow_try_again=True)