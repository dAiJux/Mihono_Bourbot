import time

class UnityMixin:

    def execute_unity_cup(self):
        if self._check_stopped():
            return
        screenshot = self.vision.take_screenshot()

        if self.vision.find_template("btn_begin_showdown", screenshot, 0.70):
            self.logger.info(f"Unity Round {self.unity_round} — Confirmation popup — clicking Begin Showdown")
            self.click_button("btn_begin_showdown", screenshot)
            self.wait(2.0)
            self._finish_unity_showdown()
            return

        if self.vision.find_template("btn_see_unity_results", screenshot, 0.70):
            self.logger.info(f"Unity Round {self.unity_round} — Results screen — resuming finish flow")
            self.click_button("btn_see_unity_results", screenshot)
            self.wait(1.0)
            self._finish_unity_showdown()
            return

        if self.vision.find_template("btn_next_unity", screenshot, 0.70):
            self.logger.info(f"Unity Round {self.unity_round} — Next screen — clicking Next")
            self.click_button("btn_next_unity", screenshot)
            self.wait(1.0)
            return

        close_pos = self.vision.find_template("btn_close", screenshot, threshold=0.7)
        if close_pos:
            has_event_win = any(
                self.vision.find_template(ew, screenshot, 0.82)
                for ew in ["event_scenario_window", "event_trainee_window", "event_support_window"]
            )
            if not has_event_win:
                self.logger.info("Team edit popup — closing")
                self.click_button("btn_close", screenshot)
                self.wait(1.0)
                screenshot = self.vision.take_screenshot()

        self.unity_round += 1
        self.logger.info(f"Executing UNITY CUP — Round {self.unity_round}")

        is_final_round = self.unity_round >= 5

        launch_found = self.wait_and_click("btn_unity_launch", timeout=10)
        if not launch_found:
            self.logger.error("Cannot find Unity Launch button")
            return
        self.wait(1.5)

        if is_final_round:
            self.logger.info("Unity Cup FINAL round")
            screenshot = self.vision.take_screenshot()
            if self.vision.find_template("btn_launch_final_unity", screenshot, 0.70):
                self.click_button("btn_launch_final_unity", screenshot)
            else:
                if not self.wait_and_click("btn_launch_final_unity", timeout=10):
                    self.logger.warning("btn_launch_final_unity not found — trying begin showdown directly")
            self.wait(1.5)
            if not self.wait_and_click("btn_begin_showdown", timeout=10):
                screenshot = self.vision.take_screenshot()
                self.click_button("btn_begin_showdown", screenshot)
            self.wait(2.0)
            self._finish_unity_showdown()
            return

        screenshot = self.vision.take_screenshot()
        if self.vision.find_template("btn_begin_showdown", screenshot, 0.70):
            self.logger.info("Begin Showdown already visible after launch — clicking")
            self.click_button("btn_begin_showdown", screenshot)
            self.wait(2.0)
            self._finish_unity_showdown()
            return

        opponents = []
        for attempt in range(6):
            if self._check_stopped():
                return
            screenshot = self.vision.take_screenshot()
            opponents = self.vision.detect_unity_opponents(screenshot)
            if opponents:
                break
            self.logger.debug(f"Opponent detection attempt {attempt+1}/6 — not found yet")
            time.sleep(1.0)
        opponents.sort(key=lambda p: p[1])

        if opponents:
            if self.unity_round == 1 and len(opponents) >= 2:
                target = opponents[1]
                self.logger.info(f"Round 1 — selecting 2nd opponent at {target}")
            else:
                target = opponents[0]
                self.logger.info(f"Round {self.unity_round} — selecting 1st opponent at {target}")
            self.click_with_offset(*target)
        else:
            self.logger.warning("No opponent cards found — clicking center of opponent zone")
            gx, gy, gw, gh = self.vision.get_game_rect(screenshot)
            uz = self.vision._calibration.get("unity_opponent_zone", {})
            cx = gx + int(gw * (uz.get("x1", 0.1) + uz.get("x2", 0.9)) / 2)
            cy = gy + int(gh * (uz.get("y1", 0.2) + uz.get("y2", 0.7)) / 2)
            self.click_with_offset(cx, cy)
        self.wait(1.0)

        screenshot = self.vision.take_screenshot()
        select_pos = self.vision.find_template("btn_select_opponent", screenshot, 0.70)
        if select_pos:
            self.click_button("btn_select_opponent", screenshot)
        self.wait(1.5)

        if not self.wait_and_click("btn_begin_showdown", timeout=8):
            self.logger.warning("btn_begin_showdown not found — retrying once")
            screenshot = self.vision.take_screenshot()
            if not self.click_button("btn_begin_showdown", screenshot):
                self.logger.error("Could not click begin showdown")
                return
        self.wait(2.0)
        self._finish_unity_showdown()

    def _finish_unity_showdown(self):
        self.logger.info("Finishing Unity showdown...")

        for _ in range(10):
            if self._check_stopped():
                return
            screenshot = self.vision.take_screenshot()
            if self.vision.find_template("btn_skip", screenshot, threshold=0.70):
                self.logger.info("Unity animation — clicking Skip")
                self.click_button("btn_skip", screenshot)
                self.wait(0.8)
            elif self.vision.find_template("btn_see_unity_results", screenshot, threshold=0.70):
                break
            else:
                time.sleep(0.6)

        found_results = self.wait_and_click("btn_see_unity_results", timeout=45)
        if not found_results:
            self.logger.warning("btn_see_unity_results not found in time — continuing")
        self.wait(1.5)

        for _ in range(8):
            if self._check_stopped():
                return
            s = self.vision.take_screenshot()
            if self.vision.find_template("btn_skip", s, threshold=0.7):
                self.click_button("btn_skip", s)
                self.wait(0.8)
            else:
                break

        for _ in range(20):
            if self._check_stopped():
                return
            screenshot = self.vision.take_screenshot()

            if self.vision.is_at_career_complete(screenshot):
                self.logger.critical("Career complete detected in unity showdown")
                return

            if self.vision.find_template("btn_next_unity", screenshot, threshold=0.7):
                self.click_button("btn_next_unity", screenshot)
                self.wait(1.0)
                return

            if self.vision.find_template("btn_race_next_finish", screenshot, threshold=0.7):
                self.click_button("btn_race_next_finish", screenshot)
                self.wait(1.0)
                return

            if self.vision.find_template("btn_inspiration", screenshot, threshold=0.75):
                self.click_button("btn_inspiration", screenshot)
                self.wait(0.5)
                continue

            if self.vision.find_template("btn_next", screenshot, threshold=0.7):
                self.click_button("btn_next", screenshot)
                self.wait(1.0)
                continue

            if self.vision.find_template("btn_tap", screenshot, threshold=0.7):
                self.click_button("btn_tap", screenshot)
                self.wait(1.0)
                continue

            if self.vision.find_template("btn_skip", screenshot, threshold=0.7):
                self.click_button("btn_skip", screenshot)
                self.wait(0.5)
                continue

            if self.vision.find_template("btn_ok", screenshot, threshold=0.7):
                self.click_button("btn_ok", screenshot)
                self.wait(0.8)
                continue

            time.sleep(1.0)