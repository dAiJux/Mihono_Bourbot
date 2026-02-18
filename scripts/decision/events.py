from typing import Optional

class EventDecisionMixin:

    def decide_event_choice(
        self, event_text: str, event_database: dict, screenshot=None
    ) -> int:
        text_lower = event_text.lower().strip()
        matched_data = None
        matched_source = ""

        for char_name, char_events in event_database.get("character_events", {}).items():
            for event_name, data in char_events.items():
                if event_name.lower() in text_lower:
                    matched_data = data
                    matched_source = f"character ({char_name}): {event_name}"
                    break
            if matched_data:
                break

        if not matched_data:
            for card_name, card_data in event_database.get("support_card_events", {}).items():
                for event_name, data in card_data.get("events", {}).items():
                    if event_name.lower() in text_lower:
                        matched_data = data
                        matched_source = f"support ({card_name}): {event_name}"
                        break
                if matched_data:
                    break

        if not matched_data:
            for event_name, data in event_database.get("common_events", {}).items():
                if event_name.lower() in text_lower:
                    matched_data = data
                    matched_source = f"common: {event_name}"
                    break

        if matched_data:
            choices = matched_data.get("choices", {})
            if not choices:
                self.logger.info(f"Matched {matched_source} but no choices data")
                return 1
            if len(choices) == 1 and "0" in choices:
                self.logger.info(f"Automatic event: {matched_source}")
                return 1
            best_num = self._score_event_choices(choices, screenshot)
            self.logger.info(f"Matched {matched_source} -> Choice {best_num}")
            return best_num

        if screenshot is not None:
            visual = self._decide_event_by_skills(screenshot)
            if visual:
                return visual

        patterns = event_database.get("generic_patterns", {})

        skill_kw = ["skill point", "skill pt", "hint"]
        if any(kw in text_lower for kw in skill_kw):
            self.logger.info("Skill keywords detected -> Choice 1 (skill priority)")
            return 1

        energy_kw = patterns.get("energy_keywords", [])
        if any(kw in text_lower for kw in energy_kw):
            c = event_database.get("default_strategy", {}).get("if_contains_energy", 1)
            self.logger.info(f"Energy keywords detected -> Choice {c}")
            return c

        training_kw = patterns.get("training_keywords", [])
        if any(kw in text_lower for kw in training_kw):
            c = event_database.get("default_strategy", {}).get("if_contains_training", 2)
            self.logger.info(f"Training keywords detected -> Choice {c}")
            return c

        positive_kw = patterns.get("positive_keywords", [])
        if any(kw in text_lower for kw in positive_kw):
            self.logger.info("Positive keywords detected -> Choice 1")
            return 1

        default = event_database.get("default_strategy", {}).get("if_unknown", 1)
        self.logger.info(f"Unknown event -> Default choice {default}")
        return default

    def _score_event_choices(self, choices: dict, screenshot=None) -> int:
        current_mood = "unknown"
        if screenshot is not None:
            current_mood = self.vision.detect_mood(screenshot)

        worst_conditions = {
            "night owl", "slow metabolism", "overweight", "fragile", "lazy",
            "practice bad", "bad practice", "sleepyhead", "reckless",
            "unfocused", "distracted",
        }
        best_conditions = {
            "practice perfect", "charming", "fast learner", "sharp",
            "good practice", "headstrong", "focused", "rising star",
            "passionate", "stout heart",
        }

        best_num = 1
        best_score = -9999

        for num_str, choice_data in choices.items():
            if num_str == "0":
                continue
            num = int(num_str) if num_str.isdigit() else 1

            if "outcomes" in choice_data:
                success = choice_data["outcomes"].get("success", {})
                fail = choice_data["outcomes"].get("fail", {})
                s_score = self._score_outcome(success, current_mood, best_conditions, worst_conditions)
                f_score = self._score_outcome(fail, current_mood, best_conditions, worst_conditions)
                score = s_score * 0.65 + f_score * 0.35
            else:
                score = self._score_outcome(choice_data, current_mood, best_conditions, worst_conditions)

            if score > best_score:
                best_score = score
                best_num = num

        return best_num

    def _score_outcome(self, outcome: dict, mood: str, best_conds: set, worst_conds: set) -> float:
        eff = outcome.get("effects", {})
        score = 0.0

        for cond in outcome.get("conditions", []):
            cl = cond.lower()
            if cl in worst_conds:
                score -= 60.0
            elif cl in best_conds:
                score += 50.0

        skills = outcome.get("skills", [])
        for s in skills:
            if isinstance(s, dict):
                score += 20.0 + s.get("level", 1) * 3.0
            else:
                score += 20.0

        score += eff.get('skill_pts', 0) * 0.7

        mood_val = eff.get('mood', 0)
        if mood_val > 0 and mood.lower() in ("great", "unknown"):
            score += 0.0
        elif mood_val > 0:
            score += mood_val * 12.0
        elif mood_val < 0:
            score += mood_val * 15.0

        for stat in ['speed', 'stamina', 'power', 'guts', 'wit']:
            val = eff.get(stat, 0)
            weight = 1.0
            if stat in self.stat_priority:
                rank = self.stat_priority.index(stat)
                weight = 1.0 + (len(self.stat_priority) - rank) * 0.15
            if val >= 0:
                score += val * weight
            else:
                score += val * weight * 1.5

        energy_val = eff.get('energy', 0)
        if energy_val >= 0:
            score += energy_val * 0.4
        else:
            score += energy_val * 0.3

        score += eff.get('max_energy', 0) * 1.5

        friendship_val = eff.get('friendship', 0)
        if friendship_val >= 0:
            score += friendship_val * 0.3
        else:
            score += friendship_val * 0.5

        return score

    def _decide_event_by_skills(self, screenshot) -> Optional[int]:
        choices = self.vision.find_all_template("event_choice", screenshot, threshold=0.7)
        choices.sort(key=lambda pos: pos[1])
        if not choices:
            return None

        gold_pos = self.vision.detect_gold_skill(screenshot)
        white_pos = self.vision.detect_white_skill(screenshot)

        if not gold_pos and not white_pos:
            return None

        best_choice = None
        best_score = 0

        for i, (cx, cy) in enumerate(choices):
            score = 0
            top = cy - 60
            bot = cy + 60

            for gx, gy in gold_pos:
                if top <= gy <= bot:
                    score += 10

            for wx, wy in white_pos:
                if top <= wy <= bot:
                    score += 5

            if score > best_score:
                best_score = score
                best_choice = i + 1

        if best_choice:
            self.logger.info(
                f"Skill visual detection -> Choice {best_choice} (score={best_score})"
            )
        return best_choice
