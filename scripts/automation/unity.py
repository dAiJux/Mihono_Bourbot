import time

class UnityMixin:

    def execute_unity_cup(self):
        if self._check_stopped():
            return

        self.unity_round += 1
        is_final = self.unity_round >= 5
        self.logger.info(
            f"Unity Cup — round {self.unity_round}{' (FINAL)' if is_final else ''}."
        )

        if self.unity_round == 1:
            self._unity_close_popup()

        self._unity_click_launch()

        if is_final:
            self._unity_final_round()
        else:
            self._unity_normal_round()

        self._unity_showdown_results()

    def _unity_close_popup(self):
        for _ in range(10):
            if self._check_stopped():
                return
            screenshot = self.vision.take_screenshot()
            if self.vision.find_template("btn_unity_launch", screenshot, 0.70):
                if not self.vision.find_template("btn_close", screenshot, 0.70):
                    return
            close_pos = self.vision.find_template("btn_close", screenshot, 0.70)
            if close_pos:
                has_event_win = any(
                    self.vision.find_template(ew, screenshot, 0.82)
                    for ew in ["event_scenario_window", "event_trainee_window", "event_support_window"]
                )
                if not has_event_win:
                    self.logger.info("Closing Unity Cup intro popup.")
                    self.click_button("btn_close", screenshot)
                    self.wait(1.0)
                    continue
            time.sleep(0.5)
        self.logger.warning("Timed out closing Unity Cup popup.")

    def _unity_click_launch(self):
        for _ in range(10):
            if self._check_stopped():
                return
            screenshot = self.vision.take_screenshot()
            if self.vision.find_template("btn_unity_launch", screenshot, 0.70):
                self.logger.info("Launching Unity Cup showdown.")
                self.click_button("btn_unity_launch", screenshot)
                self.wait(2.0)
                return
            time.sleep(0.5)
        self.logger.warning("Unity Cup launch button not found.")

    def _unity_normal_round(self):
        opponents = []
        for attempt in range(6):
            if self._check_stopped():
                return
            screenshot = self.vision.take_screenshot()
            if self.vision.find_template("btn_unity_launch", screenshot, 0.70):
                self.logger.info("Launch button still visible — re-clicking.")
                self.click_button("btn_unity_launch", screenshot)
                self.wait(2.0)
                continue
            opponents = self.vision.detect_unity_opponents(screenshot)
            if opponents:
                break
            time.sleep(1.5)

        opponents.sort(key=lambda p: p[1])
        if opponents:
            if self.unity_round == 1 and len(opponents) >= 2:
                target = opponents[1]
                self.logger.info("Round 1 — selecting second opponent.")
            else:
                target = opponents[0]
                self.logger.info(f"Round {self.unity_round} — selecting first opponent.")
            self.click_with_offset(*target)
        else:
            self.logger.warning("No opponents detected — clicking center of opponent area.")
            screenshot = self.vision.take_screenshot()
            gx, gy, gw, gh = self.vision.get_game_rect(screenshot)
            xf = self.vision._aspect_x_factor(gw, gh)
            uz = self.vision._calibration.get("unity_opponent_zone", {})
            cx = gx + int(gw * (uz.get("x1", 0.1) + uz.get("x2", 0.9)) / 2 * xf)
            cy = gy + int(gh * (uz.get("y1", 0.2) + uz.get("y2", 0.7)) / 2)
            self.click_with_offset(cx, cy)
        self.wait(2.0)

        self.wait_and_click("btn_select_opponent", timeout=8)
        self.wait(2.0)
        self.wait_and_click("btn_begin_showdown", timeout=8)
        self.wait(2.0)

    def _unity_final_round(self):
        self.logger.info("Starting Unity Cup final.")
        self.wait_and_click("btn_launch_final_unity", timeout=8)
        self.wait(2.0)
        self.wait_and_click("btn_begin_showdown", timeout=8)
        self.wait(2.0)

    def _unity_showdown_results(self):
        self.logger.info("Waiting for Unity Cup results...")
        time.sleep(3.0)
        self.wait_and_click("btn_see_unity_results", timeout=45)
        self.wait(1.5)

        self._wait_and_click_result("btn_skip", "skip animations")
        self._wait_and_click_result("btn_next", "next after skip")
        self._wait_and_click_result("btn_next_unity", "next unity")
        self._wait_and_click_result("btn_next", "final next")

    def _wait_and_click_result(self, btn_name, step_label):
        for _ in range(15):
            if self._check_stopped():
                return
            screenshot = self.vision.take_screenshot()
            pos = self.vision.find_template(btn_name, screenshot, threshold=0.70)
            if pos:
                gx, _, gw, _ = self.vision.get_game_rect(screenshot)
                if gx <= pos[0] <= gx + gw:
                    self.click_button(btn_name, screenshot, threshold=0.70)
                    self.wait(1.5)
                    return
            time.sleep(0.5)
        self.logger.warning(f"Timed out waiting for Unity result step: {step_label}.")