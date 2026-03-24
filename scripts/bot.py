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
        self.logger.info(f"Emergency stop key: {emergency_key}")

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
        self.logger.info("Bot paused.")
        self._pause_event.clear()

    def resume(self):
        self.logger.info("Bot resumed.")
        self._pause_event.set()

    def _wait_if_paused(self):
        while not self._pause_event.is_set():
            if not self.is_running:
                return
            time.sleep(0.2)

    def emergency_stop(self):
        self.logger.warning("Emergency stop activated!")
        self.is_running = False
        self._pause_event.set()
        if self.config["safety_settings"]["screenshot_on_error"]:
            self.vision.save_debug_screenshot("emergency_stop")

    def calibrate(self):
        self.logger.info("Looking for the game window...")
        if self.config["display_settings"]["calibration_on_start"]:
            result = self.vision.calibrate_screen()
            if result:
                self.logger.info("Game window found successfully.")
            else:
                self.logger.error("Game window not found — make sure the game is running!")
        else:
            self.logger.info("Auto-detection disabled in config.")

    def run_single_training(self):
        self.logger.info("=" * 60)
        self.logger.info(f"Starting run #{self.current_run}")
        self.logger.info("=" * 60)

        self.turn_count = 0
        self.decision.reset_caches()
        max_turns = 78
        overtime = False
        skip_retries = 0

        while self.is_running:
            self._wait_if_paused()
            if not self.is_running:
                break

            if self.turn_count >= max_turns and not overtime:
                screenshot = self.vision.take_screenshot()
                if self.vision.is_at_career_complete(screenshot):
                    self.logger.info("Career complete screen detected — ending run.")
                    break
                screen = self.vision.detect_screen(screenshot)
                if screen in (
                    GameScreen.MAIN, GameScreen.RACE, GameScreen.RACE_START,
                    GameScreen.TRAINING, GameScreen.EVENT, GameScreen.UNITY,
                    GameScreen.RACE_SELECT, GameScreen.INSUFFICIENT_FANS,
                    GameScreen.SCHEDULED_RACE_POPUP, GameScreen.STRATEGY,
                    GameScreen.INSPIRATION,
                ):
                    self.logger.warning(
                        f"Reached turn limit but game is still active ({screen.value}) — continuing in overtime."
                    )
                    overtime = True
                else:
                    self.logger.info("Turn limit reached — ending run.")
                    break

            self.turn_count += 1
            self.logger.info(
                f"\n{'='*60}\n"
                f"--- Turn {self.turn_count}"
                f"{' (overtime)' if overtime else ''} ---"
            )

            try:
                if overtime:
                    screenshot = self.vision.take_screenshot()
                    if self.vision.is_at_career_complete(screenshot):
                        self.logger.info("Career complete — ending run.")
                        break
                    if self.turn_count >= max_turns + 30:
                        self.logger.warning("Overtime safety limit reached — forcing end.")
                        break

                action, details = self.decision.decide_action()

                if action == Action.COMPLETE:
                    self.logger.info("Career complete screen detected — stopping.")
                    break

                if action == Action.SKIP:
                    skip_retries += 1
                    self.automation.advance_turn()
                    if skip_retries >= 5:
                        self.logger.warning(f"Skipped {skip_retries} turns in a row — something may be wrong.")
                        skip_retries = 0
                    self.turn_count -= 1
                    continue
                else:
                    skip_retries = 0

                if self.automation.should_check_skills(self.turn_count):
                    self.logger.info("Checking skill screen...")
                    self.automation.execute_skill_check(self.turn_count)

                turn_consumed = self.automation.execute_action(
                    action, details, self.event_database
                )

                self.automation.advance_turn()

                if not turn_consumed:
                    self.logger.warning(
                        f"Action '{action.value}' did not advance the game — retrying this turn."
                    )
                    self.turn_count -= 1

                multiplier = self.config.get("automation_settings", {}).get("sleep_time_multiplier", 1.0)
                delay_min = self.config.get("automation_settings", {}).get("action_delay_min", 1.0)
                delay_max = self.config.get("automation_settings", {}).get("action_delay_max", 3.0)
                time.sleep(random.uniform(delay_min, delay_max) * multiplier)

            except Exception as e:
                self.logger.error(f"Error on turn {self.turn_count}: {e}")
                if self.config["safety_settings"]["screenshot_on_error"]:
                    self.vision.save_debug_screenshot(f"error_turn_{self.turn_count}")
                if self._should_retry():
                    self.logger.info("Attempting to recover (waiting 5s)...")
                    time.sleep(5)
                    continue
                else:
                    self.logger.error("Critical error — aborting run.")
                    break

        self.logger.info("=" * 60)
        self.logger.info(f"Run #{self.current_run} finished. Turns played: {self.turn_count}")
        self.logger.info("=" * 60)
        self.total_runs += 1

    @staticmethod
    def _should_retry() -> bool:
        return True

    def run(self, num_runs: int = 1):
        self.is_running = True
        self.calibrate()
        self.logger.info(f"Starting bot for {num_runs} run(s). Beginning in 5 seconds...")
        for i in range(5, 0, -1):
            self.logger.info(f"{i}...")
            time.sleep(1)

        for run_num in range(1, num_runs + 1):
            if not self.is_running:
                self.logger.info("Bot stopped by user.")
                break
            self.current_run = run_num
            try:
                self.run_single_training()
                if run_num < num_runs:
                    self.logger.info("Waiting 10 seconds before the next run...")
                    time.sleep(10)
            except Exception as e:
                self.logger.error(f"Critical error during run {run_num}: {e}")
                if self.config["safety_settings"]["screenshot_on_error"]:
                    self.vision.save_debug_screenshot(f"critical_error_run_{run_num}")
                if run_num < num_runs:
                    self.logger.info("Attempting to start the next run...")
                    time.sleep(15)
                else:
                    break

        self.logger.info("\n" + "=" * 60)
        self.logger.info("SUMMARY")
        self.logger.info("=" * 60)
        self.logger.info(f"Runs completed: {self.total_runs}/{num_runs}")
        self.logger.info("Bot finished.")

    def test_vision(self):
        self.logger.info("Vision test mode — press Ctrl+C to stop.")
        self.calibrate()
        try:
            while True:
                screenshot = self.vision.take_screenshot()
                stats = self.vision.read_all_stats(screenshot)
                energy = self.vision.read_energy_percentage(screenshot)
                mood = self.vision.detect_mood(screenshot)
                has_injury = self.vision.detect_injury(screenshot)
                friendship = self.vision.count_friendship_icons(screenshot)
                self.logger.info(f"Stats: {stats}")
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
                self.logger.info(f"Burst — white: {len(bursts['white'])}, blue: {len(bursts['blue'])}")
                self.logger.info(f"Race day: {race_day}")
                self.logger.info(f"Unity Cup: {unity_cup}")
                time.sleep(5)
        except KeyboardInterrupt:
            self.logger.info("Vision test stopped.")