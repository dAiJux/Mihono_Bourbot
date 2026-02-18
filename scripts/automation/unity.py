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

        if self.vision.find_template("btn_close", screenshot, threshold=0.7):
            self.logger.info("Team edit popup — closing")
            self.click_button("btn_close", screenshot)
            self.wait(1.0)

        self.unity_round += 1
        self.logger.info(f"Executing UNITY CUP — Round {self.unity_round}")

        is_final_round = self.unity_round >= 5

        if not self.wait_and_click("btn_unity_launch"):
            self.logger.error("Cannot find Unity Launch button")
            return
        self.wait(1.5)

        if is_final_round:
            self.logger.info("Unity Cup FINAL round")
            if not self.wait_and_click("btn_launch_final_unity", timeout=10):
                self.logger.error("Cannot find btn_launch_final_unity on final round")
                return
            self.wait(1.5)
            if not self.wait_and_click("btn_begin_showdown", timeout=10):
                self.logger.warning("btn_begin_showdown not found on final round")
                screenshot = self.vision.take_screenshot()
                self.click_button("btn_begin_showdown", screenshot)
            self.wait(2.0)
            self._finish_unity_showdown()
            return

        opponents = []
        for attempt in range(5):
            if self._check_stopped():
                return
            screenshot = self.vision.take_screenshot()
            opponents = self.vision.detect_unity_opponents(screenshot)
            if opponents:
                break
            self.logger.debug(f"Opponent detection attempt {attempt+1}/5 — not found yet")
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

        self.click_button("btn_select_opponent")
        self.wait(1.5)
        if not self.wait_and_click("btn_begin_showdown", timeout=5):
            self.logger.warning("btn_begin_showdown not found — retrying")
            screenshot = self.vision.take_screenshot()
            self.click_button("btn_begin_showdown", screenshot)
        self.wait(2.0)
        self._finish_unity_showdown()

    def _finish_unity_showdown(self):
        self.logger.info("Finishing Unity showdown...")
        self.wait_and_click("btn_see_unity_results", timeout=30)
        self.wait(1.0)

        for _ in range(5):
            s = self.vision.take_screenshot()
            if self.vision.find_template("btn_skip", s, threshold=0.7):
                self.click_button("btn_skip", s)
                self.wait(1)
            else:
                break

        for _ in range(15):
            if self._check_stopped():
                return
            screenshot = self.vision.take_screenshot()
            if self.vision.find_template("btn_next_unity", screenshot, threshold=0.7):
                self.click_button("btn_next_unity", screenshot)
                self.wait(1.0)
                return
            if self.vision.find_template("btn_race_next_finish", screenshot, threshold=0.7):
                self.click_button("btn_race_next_finish", screenshot)
                self.wait(1.0)
                return
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
            time.sleep(1.0)
