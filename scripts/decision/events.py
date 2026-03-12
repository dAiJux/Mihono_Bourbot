from typing import Optional
from difflib import SequenceMatcher

FUZZY_THRESHOLD = 0.80

_QUOTE_TABLE = str.maketrans({
    "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
    "\u00b4": "'", "\u0060": "'", "\u2032": "'", "\u2033": '"',
})

_STOPWORDS = frozenset({
    "a", "an", "the", "and", "or", "of", "to", "in", "on", "at",
    "by", "for", "is", "it", "my", "no", "so", "up", "if", "do",
    "be", "as", "but", "not", "you", "all", "can", "had", "her",
    "was", "one", "our", "out", "are", "has", "his", "how", "its",
    "may", "new", "now", "old", "see", "way", "who", "did", "get",
    "let", "say", "she", "too", "use",
})


def _normalize(text: str) -> str:
    return text.lower().translate(_QUOTE_TABLE)


class EventDecisionMixin:

    def _fuzzy_match(self, event_name: str, text_lower: str) -> float:
        name_lower = _normalize(event_name)
        text_lower = _normalize(text_lower)
        if name_lower in text_lower:
            return 1.0
        if len(name_lower) < 3:
            return 0.0
        ratio = SequenceMatcher(None, name_lower, text_lower).ratio()
        if ratio >= FUZZY_THRESHOLD:
            return ratio
        name_len = len(name_lower)
        text_len = len(text_lower)
        if text_len > name_len + 5:
            best = 0.0
            window = name_len + 4
            for start in range(0, text_len - name_len + 5, 2):
                chunk = text_lower[start:start + window]
                r = SequenceMatcher(None, name_lower, chunk).ratio()
                if r > best:
                    best = r
            ratio = max(ratio, best)
        name_words = [w for w in name_lower.split() if len(w) > 2 and w not in _STOPWORDS]
        if len(name_words) >= 2:
            text_words = text_lower.split()
            hits = sum(1 for w in name_words if any(
                SequenceMatcher(None, w, tw).ratio() >= 0.75 for tw in text_words
            ))
            word_ratio = hits / len(name_words)
            if word_ratio >= 0.6 and hits >= 2:
                ratio = max(ratio, 0.5 + word_ratio * 0.4)
        return ratio

    def _find_event_match(self, text_lower: str, event_database: dict,
                           event_type: str = None):
        best_data = None
        best_source = ""
        best_ratio = 0.0

        search_character = event_type in (None, "choice", "scenario", "trainee")
        search_support = event_type in (None, "choice", "support")

        if search_character:
            for char_name, char_events in event_database.get("character_events", {}).items():
                for event_name, data in char_events.items():
                    ratio = self._fuzzy_match(event_name, text_lower)
                    if ratio > best_ratio:
                        best_ratio = ratio
                        best_data = data
                        best_source = f"character ({char_name}): {event_name}"
                        if ratio >= 1.0:
                            return best_data, best_source, best_ratio

        if search_support:
            for card_name, card_data in event_database.get("support_card_events", {}).items():
                for event_name, data in card_data.get("events", {}).items():
                    ratio = self._fuzzy_match(event_name, text_lower)
                    if ratio > best_ratio:
                        best_ratio = ratio
                        best_data = data
                        best_source = f"support ({card_name}): {event_name}"
                        if ratio >= 1.0:
                            return best_data, best_source, best_ratio

        for event_name, data in event_database.get("common_events", {}).items():
            ratio = self._fuzzy_match(event_name, text_lower)
            if ratio > best_ratio:
                best_ratio = ratio
                best_data = data
                best_source = f"common: {event_name}"
                if ratio >= 1.0:
                    return best_data, best_source, best_ratio

        if best_ratio >= FUZZY_THRESHOLD:
            return best_data, best_source, best_ratio
        return None, "", best_ratio

    def get_title_match_ratio(self, title: str, event_database: dict,
                              event_type: str = None) -> float:
        _, _, ratio = self._find_event_match(title.lower().strip(), event_database,
                                             event_type)
        return ratio

    def decide_event_choice(
        self, event_text: str, event_database: dict, screenshot=None,
        event_type: str = None,
    ) -> int:
        text_lower = event_text.lower().strip()

        matched_data, matched_source, match_ratio = self._find_event_match(
            text_lower, event_database, event_type
        )

        if matched_data:
            choices = matched_data.get("choices", {})
            if not choices:
                self.logger.info(f"Matched {matched_source} but no choices data")
                return 1
            if len(choices) == 1 and "0" in choices:
                self.logger.info(f"Automatic event: {matched_source}")
                return 1
            preferred = matched_data.get("preferred_choice")
            if preferred:
                pct = int(match_ratio * 100)
                self.logger.info(
                    f"Matched {matched_source} ({pct}%) -> Choice {preferred} (preferred)"
                )
                return int(preferred)
            best_num = self._score_event_choices(choices, screenshot)
            pct = int(match_ratio * 100)
            self.logger.info(
                f"Matched {matched_source} ({pct}%) -> Choice {best_num}"
            )
            return best_num

        if screenshot is not None:
            visual = self._decide_event_by_skills(screenshot)
            if visual:
                return visual

        self.logger.info("Unknown event -> Default choice 1")
        return 1

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
                if success.get("chain_end") or fail.get("chain_end"):
                    score = -9000
                else:
                    s_score = self._score_outcome(success, current_mood, best_conditions, worst_conditions)
                    f_score = self._score_outcome(fail, current_mood, best_conditions, worst_conditions)
                    score = s_score * 0.65 + f_score * 0.35
            else:
                if choice_data.get("chain_end"):
                    score = -9000
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
