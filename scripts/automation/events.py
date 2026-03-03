from ..models import GameScreen


class EventMixin:

    def _is_tutorial_event(self, event_text: str, num_choices: int) -> bool:
        text_lower = event_text.lower() if event_text else ""
        if "tutorial" in text_lower:
            return True
        if "no, thank" in text_lower or "no thank" in text_lower:
            return True
        if "that's all" in text_lower or "c'est tout" in text_lower:
            return True
        return False

    def _find_tutorial_skip_index(self, choice_texts: list) -> int:
        skip_keywords = ["no, thank", "no thank", "that's all", "c'est tout", "non, merci", "non merci"]
        for i, text in enumerate(choice_texts):
            text_lower = text.lower()
            for kw in skip_keywords:
                if kw in text_lower:
                    return i
        return -1

    def handle_event(self, event_database: dict):
        self.logger.info("Event detected, analysing...")
        screenshot = self.vision.take_screenshot()

        if self.vision.is_at_career_complete(screenshot):
            self.logger.critical("CAREER COMPLETE detected — aborting event handling!")
            return False

        screen_check = self.vision.detect_screen(screenshot)
        if screen_check not in (GameScreen.EVENT, GameScreen.UNKNOWN,
                                GameScreen.INSUFFICIENT_FANS, GameScreen.SCHEDULED_RACE_POPUP):
            self.logger.info(f"handle_event called but screen is {screen_check.value} — aborting")
            self._last_event_title = ""
            self._consecutive_event_count = 0
            return False

        event_title = self.vision.read_event_title(screenshot)
        event_text = self.vision.read_event_text(screenshot)
        match_text = f"{event_title} {event_text}".strip() if event_title else event_text

        self.logger.info(f"Event title: '{event_title[:60]}'") if event_title else None

        TITLE_GUARD_THRESHOLD = 0.55
        if event_title and len(event_title.strip()) > 3:
            title_ratio = self.decision.get_title_match_ratio(event_title, event_database)
            if title_ratio < TITLE_GUARD_THRESHOLD:
                title_key = event_title.lower().strip()
                if title_key == self._last_event_title:
                    self._consecutive_event_count += 1
                else:
                    self._last_event_title = title_key
                    self._consecutive_event_count = 1

                if self._consecutive_event_count < 2:
                    self.logger.info(
                        f"Title guard: '{event_title[:40]}' best match "
                        f"{title_ratio:.0%} < {TITLE_GUARD_THRESHOLD:.0%} — likely false detection"
                    )
                    return False
                else:
                    self.logger.info(
                        f"Title guard: '{event_title[:40]}' seen "
                        f"{self._consecutive_event_count}x consecutively — proceeding"
                    )
            else:
                self._last_event_title = ""
                self._consecutive_event_count = 0

        gx, gy, gw, gh = self.vision.get_game_rect(screenshot)
        ec = self.vision._calibration.get("event_choices", {})
        choice_y_min = gy + int(gh * ec.get("y1", 0.35))
        choice_y_max = gy + int(gh * ec.get("y2", 0.85))
        raw_choices = self.vision.find_all_template("event_choice", screenshot, threshold=0.75, min_distance=30)
        choices = [
            c for c in raw_choices
            if gx <= c[0] <= gx + gw and choice_y_min <= c[1] <= choice_y_max
        ]
        choices.sort(key=lambda pos: pos[1])
        if len(choices) > 5:
            self.logger.warning(f"Too many choices detected ({len(choices)}), likely false positives — ignoring")
            return False

        if not choices:
            self.logger.info("No choices yet — waiting for dialogue to finish...")
            for attempt in range(4):
                self.wait(1.5)
                screenshot = self.vision.take_screenshot()
                event_type = self.vision.detect_event_type(screenshot)
                if not event_type:
                    self.logger.info("Event window disappeared during wait — auto-resolved")
                    return True
                gx, gy, gw, gh = self.vision.get_game_rect(screenshot)
                raw_choices = self.vision.find_all_template("event_choice", screenshot, threshold=0.75, min_distance=30)
                choices = [
                    c for c in raw_choices
                    if gx <= c[0] <= gx + gw and choice_y_min <= c[1] <= choice_y_max
                ]
                choices.sort(key=lambda pos: pos[1])
                if 1 <= len(choices) <= 5:
                    self.logger.info(f"Choices appeared after {(attempt + 1) * 1.5:.1f}s wait ({len(choices)} found)")
                    event_title = self.vision.read_event_title(screenshot)
                    event_text = self.vision.read_event_text(screenshot)
                    match_text = f"{event_title} {event_text}".strip() if event_title else event_text
                    break
            else:
                self.logger.warning("Choices never appeared after 6s — giving up")
                return False

        self.logger.info(f"Found {len(choices)} event choices, text: {match_text[:80] if match_text else 'N/A'}")

        choice_texts = self.vision.read_choice_texts(screenshot, choices)
        for i, ct in enumerate(choice_texts):
            self.logger.info(f"  Choice {i + 1} at {choices[i]}: '{ct}'")

        skip_idx = self._find_tutorial_skip_index(choice_texts)
        if skip_idx >= 0:
            self.logger.info(f"Tutorial skip choice found at index {skip_idx}: '{choice_texts[skip_idx]}'")
            self.click_with_offset(*choices[skip_idx])
            self.wait(0.5)
            return True

        is_tutorial_title = self._is_tutorial_event(event_title, len(choices))
        is_tutorial_body = self._is_tutorial_event(event_text, len(choices))

        if (is_tutorial_title or is_tutorial_body) and len(choices) <= 2:
            extra_choices = self.vision.find_all_template(
                "event_choice", screenshot, threshold=0.55, min_distance=30
            )
            extra_valid = [
                c for c in extra_choices
                if gx <= c[0] <= gx + gw and choice_y_min <= c[1] <= choice_y_max
            ]
            extra_valid.sort(key=lambda pos: pos[1])
            new_in_extra = [c for c in extra_valid if all(
                abs(c[0] - ex[0]) > 20 or abs(c[1] - ex[1]) > 20 for ex in choices
            )]
            if new_in_extra:
                self.logger.info(
                    f"Tutorial: found {len(new_in_extra)} extra choices with lower threshold"
                )
                choices = sorted(choices + new_in_extra, key=lambda p: p[1])
                choice_texts = self.vision.read_choice_texts(screenshot, choices)
                for i, ct in enumerate(choice_texts):
                    self.logger.info(f"  Choice {i + 1} at {choices[i]}: '{ct}'")
                skip_idx = self._find_tutorial_skip_index(choice_texts)
                if skip_idx >= 0:
                    self.logger.info(
                        f"Tutorial skip found after retry at index {skip_idx}: '{choice_texts[skip_idx]}'"
                    )
                    self.click_with_offset(*choices[skip_idx])
                    self.wait(0.5)
                    return True

            self.logger.info(
                f"Tutorial detected — selecting LAST choice ({len(choices)}) to skip"
            )
            self.click_with_offset(*choices[-1])
            self.wait(0.5)
            return True

        if not match_text:
            self.logger.warning("Could not read event text — using visual skill detection")
            choice = self._decide_event_visually(screenshot)
        else:
            choice = self.decision.decide_event_choice(match_text, event_database, screenshot)

        self.logger.info(f"Selecting choice {choice}/{len(choices)}")
        idx = min(choice - 1, len(choices) - 1)
        self.click_with_offset(*choices[idx])
        self.wait(1.0)

        if self.vision.find_template("btn_confirm"):
            if self.vision.is_at_career_complete():
                self.logger.critical("CAREER COMPLETE detected — refusing to click confirm!")
                return False
            self.click_button("btn_confirm")
            self.wait(1.0)
        return True

    def _decide_event_visually(self, screenshot) -> int:
        choices = self.vision.find_all_template("event_choice", screenshot, threshold=0.7)
        choices.sort(key=lambda pos: pos[1])
        if not choices:
            return 1

        gold_positions = self.vision.detect_gold_skill(screenshot)
        white_positions = self.vision.detect_white_skill(screenshot)
        best_choice = 1
        best_score = -1

        for i, (cx, cy) in enumerate(choices):
            score = 0
            region_top = cy - 60
            region_bottom = cy + 60
            for gx, gy in gold_positions:
                if region_top <= gy <= region_bottom:
                    score += 10
            for wx, wy in white_positions:
                if region_top <= wy <= region_bottom:
                    score += 5
            if score > best_score:
                best_score = score
                best_choice = i + 1

        if best_score > 0:
            self.logger.info(f"Visual skill detection -> Choice {best_choice} (score={best_score})")
        return best_choice

    def check_and_handle_events(self, event_database: dict) -> bool:
        screenshot = self.vision.take_screenshot()
        if self.vision.find_template("btn_inspiration", screenshot, threshold=0.75):
            self.logger.info("Inspiration event — clicking to continue")
            self.click_button("btn_inspiration", screenshot)
            self.wait(1.0)
            return True
        event_type = self.vision.detect_event_type(screenshot)
        if event_type:
            self.logger.info(f"Event type: {event_type}")
            self.handle_event(event_database)
            return True
        return False
