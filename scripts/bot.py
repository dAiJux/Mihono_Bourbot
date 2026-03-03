import sys
import os
import json
import logging
import time
import random
import threading
import keyboard
from pathlib import Path

from .models import GameScreen, Action
from .vision import VisionModule
from .decision import DecisionModule
from .automation import AutomationModule

class MihonoBourbot:

    def __init__(self, config_path: str = os.path.join("config", "config.json")):
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)

        self._setup_logging()

        self.logger.info("=" * 60)
        self.logger.info("Mihono Bourbot — Umamusume Pretty Derby Automation")
        self.logger.info("=" * 60)

        event_path = os.path.join("config", "event_database.json")
        with open(event_path, "r", encoding="utf-8") as f:
            self.event_database = json.load(f)

        self.logger.info("Initialising modules...")
        self.vision = VisionModule(self.config)
        self.decision = DecisionModule(self.config, self.vision)
        self.automation = AutomationModule(self.config, self.vision, self.decision)

        self.is_running = False
        self._pause_event = threading.Event()
        self._pause_event.set()
        self.automation.set_control_flags(lambda: self.is_running, self._pause_event)
        self.current_run = 0
        self.total_runs = 0
        self.turn_count = 0

        emergency_key = self.config["safety_settings"]["emergency_stop_key"]
        keyboard.add_hotkey(emergency_key, self.emergency_stop)
        self.logger.info(f"Emergency stop key set to: {emergency_key}")

    def _setup_logging(self):
        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        Path("logs").mkdir(exist_ok=True)
        logging.basicConfig(
            level=logging.INFO,
            format=log_format,
            handlers=[
                logging.FileHandler("logs/bot.log", encoding="utf-8"),
                logging.StreamHandler(sys.stdout),
            ],
        )
        self.logger = logging.getLogger(__name__)

    def pause(self):
        self.logger.info("PAUSE requested")
        self._pause_event.clear()

    def resume(self):
        self.logger.info("RESUME requested")
        self._pause_event.set()

    def _wait_if_paused(self):
        while not self._pause_event.is_set():
            if not self.is_running:
                return
            time.sleep(0.2)

    def emergency_stop(self):
        self.logger.warning("EMERGENCY STOP ACTIVATED")
        self.is_running = False
        self._pause_event.set()
        if self.config["safety_settings"]["screenshot_on_error"]:
            self.vision.save_debug_screenshot("emergency_stop")

    def calibrate(self):
        self.logger.info("Calibrating game window...")
        if self.config["display_settings"]["calibration_on_start"]:
            result = self.vision.calibrate_screen()
            if result:
                self.logger.info("Calibration successful")
            else:
                self.logger.error(
                    "Calibration failed — make sure the game is running!"
                )
        else:
            self.logger.info("Calibration disabled in config")

    def run_single_training(self):
        self.logger.info("=" * 60)
        self.logger.info(f"STARTING RUN #{self.current_run}")
        self.logger.info("=" * 60)

        self.turn_count = 0
        max_turns = 78
        overtime = False

        skip_retries = 0
        while self.is_running:
            self._wait_if_paused()
            if not self.is_running:
                break

            if self.turn_count >= max_turns and not overtime:
                self.logger.info(
                    f"Turn {self.turn_count} reached — checking if career is actually over..."
                )
                screenshot = self.vision.take_screenshot()
                if self.vision.is_at_career_complete(screenshot):
                    self.logger.info("Career Complete confirmed at max turns — ending run")
                    break
                screen = self.vision.detect_screen(screenshot)
                if screen in (
                    GameScreen.MAIN, GameScreen.RACE, GameScreen.RACE_START,
                    GameScreen.TRAINING,
                    GameScreen.EVENT, GameScreen.UNITY, GameScreen.RACE_SELECT,
                    GameScreen.INSUFFICIENT_FANS, GameScreen.SCHEDULED_RACE_POPUP,
                    GameScreen.STRATEGY,
                    GameScreen.INSPIRATION,
                ):
                    self.logger.warning(
                        f"Turn {self.turn_count} but still on {screen.value} — "
                        f"continuing in overtime mode"
                    )
                    overtime = True
                else:
                    self.logger.info(f"Max turns reached on {screen.value} — ending run")
                    break

            self.turn_count += 1
            self.logger.info(
                f"\n--- Turn {self.turn_count}"
                f"{' (overtime)' if overtime else ''} ---"
            )

            try:
                if overtime:
                    screenshot = self.vision.take_screenshot()
                    if self.vision.is_at_career_complete(screenshot):
                        self.logger.info(
                            "Career Complete detected in overtime — ending run"
                        )
                        break
                    if self.turn_count >= max_turns + 30:
                        self.logger.warning(
                            "Overtime safety limit (30 extra turns) — forcing end"
                        )
                        break

                action, details = self.decision.decide_action()

                if action == Action.COMPLETE:
                    self.logger.info("Run finished — Complete Career reached")
                    break

                if self.automation.should_check_skills(self.turn_count):
                    self.logger.info("Skill check triggered")
                    self.automation.execute_skill_check(self.turn_count)

                if action == Action.SKIP:
                    skip_retries += 1
                    self.automation.advance_turn()
                    if skip_retries >= 5:
                        self.logger.warning(
                            f"SKIP returned {skip_retries} times in a row"
                        )
                        skip_retries = 0
                    self.turn_count -= 1
                    continue
                else:
                    skip_retries = 0

                turn_consumed = self.automation.execute_action(
                    action, details, self.event_database
                )

                self.automation.advance_turn()

                if not turn_consumed:
                    self.logger.warning(
                        f"Action {action.value} did not consume a turn — retrying same turn"
                    )
                    self.turn_count -= 1

                time.sleep(random.uniform(
                    self.config["automation_settings"]["action_delay_min"],
                    self.config["automation_settings"]["action_delay_max"],
                ))

            except Exception as e:
                self.logger.error(f"Error during turn {self.turn_count}: {e}")
                if self.config["safety_settings"]["screenshot_on_error"]:
                    self.vision.save_debug_screenshot(
                        f"error_turn_{self.turn_count}"
                    )
                if self._should_retry():
                    self.logger.info("Attempting recovery...")
                    time.sleep(5)
                    continue
                else:
                    self.logger.error("Critical error — aborting run")
                    break

        self.logger.info("=" * 60)
        self.logger.info(
            f"END OF RUN #{self.current_run} (Turns played: {self.turn_count})"
        )
        self.logger.info("=" * 60)
        self.total_runs += 1

    @staticmethod
    def _should_retry() -> bool:
        return True

    def run(self, num_runs: int = 1):
        self.is_running = True
        self.calibrate()

        self.logger.info(f"Starting bot for {num_runs} run(s)")
        self.logger.info("Bot will start in 5 seconds...")

        for i in range(5, 0, -1):
            self.logger.info(f"{i}...")
            time.sleep(1)

        for run_num in range(1, num_runs + 1):
            if not self.is_running:
                self.logger.info("Bot stopped by user")
                break

            self.current_run = run_num
            try:
                self.run_single_training()
                if run_num < num_runs:
                    self.logger.info("Pausing 10 s before next run...")
                    time.sleep(10)
            except Exception as e:
                self.logger.error(f"Critical error during run {run_num}: {e}")
                if self.config["safety_settings"]["screenshot_on_error"]:
                    self.vision.save_debug_screenshot(
                        f"critical_error_run_{run_num}"
                    )
                if run_num < num_runs:
                    self.logger.info("Attempting to start next run...")
                    time.sleep(15)
                else:
                    break

        self.logger.info("\n" + "=" * 60)
        self.logger.info("SUMMARY")
        self.logger.info("=" * 60)
        self.logger.info(f"Runs completed: {self.total_runs}/{num_runs}")
        self.logger.info("Bot finished.")

    def test_vision(self):
        self.logger.info("TEST MODE — Visual Recognition")
        self.logger.info("Press Ctrl+C to stop")

        self.calibrate()

        try:
            while True:
                screenshot = self.vision.take_screenshot()
                stats = self.vision.read_all_stats(screenshot)
                energy = self.vision.read_energy_percentage(screenshot)
                mood = self.vision.detect_mood(screenshot)
                has_injury = self.vision.detect_injury(screenshot)
                friendship = self.vision.count_friendship_icons(screenshot)

                self.logger.info(f"\nStats: {stats}")
                self.logger.info(f"Energy: {energy:.0f}%")
                self.logger.info(f"Mood: {mood}")
                self.logger.info(f"Injury: {has_injury}")
                self.logger.info(f"Friendship: {friendship}")

                has_target = self.vision.detect_target_race(screenshot)
                has_scheduled = self.vision.detect_scheduled_race(screenshot)
                rainbow_count = self.vision.detect_rainbow_training(screenshot)
                event_type = self.vision.detect_event_type(screenshot)
                bursts = self.vision.detect_burst_training(screenshot)
                race_day = self.vision.detect_race_day(screenshot)
                unity_cup = self.vision.detect_unity_cup(screenshot)

                self.logger.info(f"Target race: {has_target}")
                self.logger.info(f"Scheduled race: {has_scheduled}")
                self.logger.info(f"Rainbow training: {rainbow_count}")
                self.logger.info(f"Event type: {event_type}")
                self.logger.info(
                    f"Bursts white: {len(bursts['white'])}, blue: {len(bursts['blue'])}"
                )
                self.logger.info(f"Race day: {race_day}")
                self.logger.info(f"Unity Cup: {unity_cup}")

                time.sleep(5)
        except KeyboardInterrupt:
            self.logger.info("\nTest stopped by user")