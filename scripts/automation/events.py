import time

_POLL = 0.07
_EVENT_WINDOWS = ("event_scenario_window", "event_trainee_window", "event_support_window")

class EventMixin:

    def _find_event_choices(self, screenshot, gx, gy, gw, gh, threshold=0.75):
        ec = self.vision._calibration.get("event_choices", {})
        choice_y_min = gy + int(gh * ec.get("y1", 0.35))
        choice_y_max = gy + int(gh * ec.get("y2", 0.85))
        raw = self.vision.find_all_template("event_choice", screenshot, threshold=threshold, min_distance=30)
        choices = [c for c in raw if gx <= c[0] <= gx + gw and choice_y_min <= c[1] <= choice_y_max]
        self._choices_from_icons = False
        if not choices:
            icons = self.vision.find_all_template("event_choice_icon", screenshot, threshold=0.70, min_distance=30)
            choices = [c for c in icons if gx <= c[0] <= gx + gw and choice_y_min <= c[1] <= choice_y_max]
            if choices:
                self._choices_from_icons = True
        choices.sort(key=lambda pos: pos[1])
        return choices

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

    def _has_event_window(self, screenshot) -> bool:
        return any(self.vision.find_template(t, screenshot, 0.75) for t in _EVENT_WINDOWS)

    def handle_event(self, event_database: dict, _depth: int = 0):
        if _depth > 5:
            self.logger.warning("Too many chained events — stopping to avoid a loop.")
            return False

        screenshot = self.vision.take_screenshot()

        if self.vision.is_at_career_complete(screenshot):
            self.logger.critical("Career complete screen during event handling — aborting.")
            return False

        event_band = self.vision._detect_event_band(screenshot)
        event_type = event_band[0] if event_band else None
        band_pos = event_band[1] if event_band else None
        band_tpl = event_band[3] if event_band else None

        if not event_type:
            event_type = self.vision.detect_event_type(screenshot)
            if not event_type:
                return False

        self.logger.info(f"Event detected — type: {event_type}")

        event_title = self.vision.read_event_title(screenshot, band_pos, band_tpl)
        event_text = self.vision.read_event_text(screenshot)
        match_text = f"{event_title} {event_text}".strip() if event_title else event_text

        if event_title:
            if event_title == self._last_event_title:
                self._consecutive_event_count += 1
                if self._consecutive_event_count >= 3:
                    self.logger.warning(
                        f"Same event appeared {self._consecutive_event_count}x in a row — skipping to avoid a loop."
                    )
                    return False
            else:
                self._last_event_title = event_title
                self._consecutive_event_count = 1
            self.logger.info(f"Event title: '{event_title[:60]}'")
        else:
            self._last_event_title = ""
            self._consecutive_event_count = 0

        gx, gy, gw, gh = self.vision.get_game_rect(screenshot)
        choices = self._find_event_choices(screenshot, gx, gy, gw, gh)

        if len(choices) > 5:
            self.logger.warning(f"Too many choices detected ({len(choices)}) — likely a false positive.")
            return False

        if not choices:
            self.logger.info("No choices yet — waiting for dialogue to finish (up to 3s)...")
            deadline = time.time() + 3.0
            tapped = False
            found = False
            while time.time() < deadline:
                if self._check_stopped():
                    return False
                time.sleep(_POLL)
                screenshot = self.vision.take_screenshot()
                if not self._has_event_window(screenshot):
                    self.logger.info("Event resolved automatically.")
                    return True
                gx, gy, gw, gh = self.vision.get_game_rect(screenshot)
                choices = self._find_event_choices(screenshot, gx, gy, gw, gh)
                if 1 <= len(choices) <= 5:
                    self.logger.info(f"Choices appeared: {len(choices)} option(s).")
                    event_band = self.vision._detect_event_band(screenshot)
                    band_pos = event_band[1] if event_band else None
                    band_tpl = event_band[3] if event_band else None
                    event_title = self.vision.read_event_title(screenshot, band_pos, band_tpl)
                    event_text = self.vision.read_event_text(screenshot)
                    match_text = f"{event_title} {event_text}".strip() if event_title else event_text
                    found = True
                    break
                if not tapped and time.time() > deadline - 2.5:
                    self.logger.info("No choices found — tapping to dismiss this event.")
                    for btn in ("btn_tap", "btn_next", "btn_ok", "btn_skip"):
                        pos = self.vision.find_template(btn, screenshot, 0.72)
                        if pos:
                            self.click_with_offset(*pos)
                            break
                    else:
                        self.click_with_offset(gx + gw // 2, gy + int(gh * 0.55))
                    tapped = True
            if not found:
                self.logger.info("Event had no choices — dismissed.")
                return True

        self.logger.info(f"Event has {len(choices)} choice(s).")

        icon_pos = choices if getattr(self, '_choices_from_icons', False) else None
        choice_texts = self.vision.read_choice_texts(screenshot, choices, icon_pos)
        for i, ct in enumerate(choice_texts):
            self.logger.info(f"  Option {i + 1}: '{ct}'")

        skip_idx = self._find_tutorial_skip_index(choice_texts)
        if skip_idx >= 0:
            self.logger.info(f"Tutorial event — selecting skip option ({skip_idx + 1}).")
            self.click_with_offset(*choices[skip_idx])
            self._poll_until_event_resolved(3.0)
            return True

        is_tutorial_title = self._is_tutorial_event(event_title, len(choices))
        is_tutorial_body = self._is_tutorial_event(event_text, len(choices))
        if (is_tutorial_title or is_tutorial_body) and len(choices) <= 2:
            extra_valid = self._find_event_choices(screenshot, gx, gy, gw, gh, threshold=0.55)
            new_in_extra = [c for c in extra_valid if all(
                abs(c[0] - ex[0]) > 20 or abs(c[1] - ex[1]) > 20 for ex in choices
            )]
            if new_in_extra:
                choices = sorted(choices + new_in_extra, key=lambda p: p[1])
                choice_texts = self.vision.read_choice_texts(screenshot, choices, icon_pos)
                skip_idx = self._find_tutorial_skip_index(choice_texts)
                if skip_idx >= 0:
                    self.logger.info(f"Tutorial event — selecting skip option ({skip_idx + 1}).")
                    self.click_with_offset(*choices[skip_idx])
                    self._poll_until_event_resolved(3.0)
                    return True
            self.logger.info("Tutorial event — selecting last option to skip.")
            self.click_with_offset(*choices[-1])
            self._poll_until_event_resolved(3.0)
            return True

        if not match_text:
            self.logger.info("Could not read event text — using visual skill detection.")
            choice = self._decide_event_visually(screenshot)
        else:
            matched_data, _, _ = self.decision._find_event_match(
                match_text.lower().strip(), event_database, event_type
            )
            if matched_data and list(matched_data.get("choices", {}).keys()) == ["0"]:
                self.logger.info("Auto-resolve event — waiting for it to finish naturally.")
                self._poll_until_event_resolved(3.0)
                return True
            choice = self.decision.decide_event_choice(match_text, event_database, screenshot,
                                                        event_type=event_type)

        self.logger.info(f"Choosing option {choice} out of {len(choices)}.")
        idx = min(choice - 1, len(choices) - 1)
        self.click_with_offset(*choices[idx])

        matched_source = ""
        if match_text:
            _, matched_source, _ = self.decision._find_event_match(
                match_text.lower().strip(), event_database, event_type
            )
        is_common_event = matched_source.startswith("common") or event_type in (None, "scenario")

        if not is_common_event:
            self._poll_until_event_resolved(3.0)
        else:
            original_title = (event_title or "").strip()
            deadline = time.time() + 4.0
            while time.time() < deadline:
                if self._check_stopped():
                    return True
                time.sleep(_POLL)
                screenshot = self.vision.take_screenshot()

                if not self._has_event_window(screenshot):
                    break

                gx2, gy2, gw2, gh2 = self.vision.get_game_rect(screenshot)
                sub_choices = self._find_event_choices(screenshot, gx2, gy2, gw2, gh2)
                if not sub_choices:
                    continue

                event_band2 = self.vision._detect_event_band(screenshot)
                new_title = ""
                if event_band2:
                    new_title = (self.vision.read_event_title(screenshot, event_band2[1], event_band2[3]) or "").strip()

                if original_title and new_title and new_title != original_title:
                    self.logger.info(f"Chained event detected: '{new_title[:50]}' — waiting for it to settle.")
                    time.sleep(2.0)
                    self.handle_event(event_database, _depth=_depth + 1)
                    break
                else:
                    self.logger.info(f"Follow-up choices on same event ({len(sub_choices)} option(s)) — waiting 2s before clicking.")
                    time.sleep(2.0)
                    self.click_with_offset(*sub_choices[0])
                    deadline = time.time() + 4.0

        screenshot = self.vision.take_screenshot()
        if self.vision.find_template("btn_confirm", screenshot):
            if not self.vision.is_at_career_complete(screenshot):
                self.click_button("btn_confirm", screenshot)
                self._poll_until_event_resolved(3.0)

        return True

    def _poll_until_event_resolved(self, timeout: float = 3.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._check_stopped():
                return
            time.sleep(_POLL)
            ss = self.vision.take_screenshot()
            if not self._has_event_window(ss):
                return

    def _decide_event_visually(self, screenshot) -> int:
        gx, gy, gw, gh = self.vision.get_game_rect(screenshot)
        choices = self._find_event_choices(screenshot, gx, gy, gw, gh, threshold=0.7)
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
            for gx2, gy2 in gold_positions:
                if region_top <= gy2 <= region_bottom:
                    score += 10
            for wx, wy in white_positions:
                if region_top <= wy <= region_bottom:
                    score += 5
            if score > best_score:
                best_score = score
                best_choice = i + 1
        if best_score > 0:
            self.logger.info(f"Skill-based selection — choosing option {best_choice} (score: {best_score}).")
        return best_choice

    def check_and_handle_events(self, event_database: dict) -> bool:
        screenshot = self.vision.take_screenshot()
        if self.vision.find_template("btn_inspiration", screenshot, threshold=0.75):
            self.logger.info("Inspiration event — tapping to continue.")
            self.click_button("btn_inspiration", screenshot)
            self._poll_until_event_resolved(3.0)
            return True
        event_type = self.vision.detect_event_type(screenshot)
        if event_type:
            self.handle_event(event_database)
            return True
        return False