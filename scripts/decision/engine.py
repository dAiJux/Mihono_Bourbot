from typing import Dict, Optional, Tuple

from ..models import GameScreen, Action

class EngineMixin:
    def _get_stat_tolerance(self):
        return self.config.get("training_targets", {}).get("tolerance", 50)


    TRAINING_STAT_GAINS = {
        "speed":   {"speed": 1.0, "power": 0.3},
        "stamina": {"stamina": 1.0, "guts": 0.3},
        "power":   {"power": 1.0, "stamina": 0.3},
        "guts":    {"guts": 1.0, "speed": 0.15, "power": 0.15},
        "wit":     {"wit": 1.0, "speed": 0.15},
    }

    END_OF_RUN_BONUS = 63
    STAT_CAP = 1200

    def decide_action(self) -> Tuple[Action, Optional[str]]:
        screenshot = self.vision.take_screenshot()

        race_popup = self.vision.find_template("btn_race", screenshot, 0.80)
        if race_popup:
            self.logger.info("Scheduled race popup detected — returning SKIP")
            return (Action.SKIP, None)

        screen = self.vision.detect_screen(screenshot)
        if screen not in (GameScreen.MAIN, GameScreen.RACE, GameScreen.UNITY, GameScreen.CAREER_COMPLETE):
            self.logger.info(f"Not on main screen ({screen.value}) — returning SKIP to let advance_turn handle it")
            return (Action.SKIP, None)

        if self.vision.is_at_career_complete(screenshot):
            self.logger.info("Complete Career screen detected — stopping bot")
            return (Action.COMPLETE, None)

        if self.vision.detect_race_day(screenshot):
            self.logger.info("PRIORITY 0: Race day — mandatory race")
            return (Action.RACE, "raceday")

        if self.vision.detect_unity_cup(screenshot):
            scenario = self.config.get("scenario", "unity_cup")
            if scenario != "ura":
                self.logger.info("PRIORITY 0: Unity Cup day detected")
                return (Action.UNITY_CUP, None)
            else:
                self.logger.info("Unity Cup detected but scenario is URA — skipping")

        stats = self.vision.read_all_stats(screenshot)
        energy = self.vision.read_energy_percentage(screenshot)
        mood = self.vision.detect_mood(screenshot)
        has_injury = self.vision.detect_injury(screenshot)
        friendship = self.vision.count_friendship_icons(screenshot)

        date_info = self.vision.read_game_date(screenshot)
        is_summer = self.vision.is_summer_period(date_info)
        is_junior = not date_info or date_info.get("year") == "junior"
        is_finale = date_info is not None and date_info.get("year") == "finale"
        current_turn = date_info.get("turn", 0) if date_info else 0
        is_pre_summer = date_info is not None and current_turn < 37
        date_str = (
            f"{date_info['year'].title()} {date_info['half'].title()} "
            f"{date_info['month'].title()} (T{current_turn})"
            if date_info else "unknown"
        )

        if not hasattr(self, "_infirmary_cooldown"):
            self._infirmary_cooldown = 0
        if self._infirmary_cooldown > 0:
            self._infirmary_cooldown -= 1
            self.logger.info(f"Infirmary cooldown active ({self._infirmary_cooldown} turns remaining) — skipping injury check")
            has_injury = False

        self.logger.info(
            f"State — Energy: {energy:.0f}%, Mood: {mood}, Injury: {has_injury}, "
            f"Friendship partial: {friendship['partial']}, orange: {friendship.get('orange', 0)}, "
            f"maxed: {friendship['max']}, "
            f"Date: {date_str}, Summer: {is_summer}, PreSummer: {is_pre_summer}, Finale: {is_finale}"
        )

        if self.vision.detect_target_race(screenshot):
            if not has_injury:
                self.logger.info("PRIORITY 1: Target race detected -> RACE")
                return (Action.RACE, "target")
            else:
                self.logger.info("Target race detected but injured — INFIRMARY first")

        if self.vision.detect_scheduled_race(screenshot):
            if not has_injury:
                self.logger.info("PRIORITY 1: Scheduled race detected -> RACE")
                return (Action.RACE, "scheduled")
            else:
                self.logger.info("Scheduled race detected but injured — INFIRMARY first")

        if has_injury:
            self.logger.info("PRIORITY 1: Injury detected -> INFIRMARY")
            self._infirmary_cooldown = 10
            return (Action.INFIRMARY, None)

        if energy < 30:
            self.logger.info(f"Energy critically low ({energy:.0f}% < 30%) -> hard REST")
            return (Action.REST, "summer" if is_summer else None)

        if mood.lower() == "awful":
            self.logger.info(f"Mood '{mood}' is awful -> hard RECREATION")
            return (Action.RECREATION, None)

        if not is_junior and mood.lower() != "great":
            self.logger.info(f"Mood '{mood}' not Great in Classic/Senior -> RECREATION")
            return (Action.RECREATION, None)

        target_stat = self._determine_training_stat(stats, friendship)
        self.logger.info(
            f"Going to training to evaluate scores "
            f"(suggested: {target_stat or 'default'}, energy={energy:.0f}%, mood={mood})"
        )
        return (Action.TRAINING, {"stat": target_stat, "energy": energy, "mood": mood})

    def score_training_slots(self, screenshot, is_pre_summer: bool = False) -> Dict[str, Dict]:
        gx, gy, gw, gh = self.vision.get_game_rect(screenshot)

        slot_centers = {}
        for stat in ["speed", "stamina", "power", "guts", "wit"]:
            cal = self.vision._calibration.get(f"train_{stat}")
            if cal and "x" in cal:
                slot_centers[stat] = gx + int(gw * cal["x"])

        if len(slot_centers) < 3:
            return {}

        sorted_names = sorted(slot_centers, key=slot_centers.get)
        boundaries = {}
        for i, name in enumerate(sorted_names):
            if i == 0:
                left = gx
            else:
                left = (slot_centers[sorted_names[i - 1]] + slot_centers[name]) // 2
            if i == len(sorted_names) - 1:
                right = gx + gw
            else:
                right = (slot_centers[name] + slot_centers[sorted_names[i + 1]]) // 2
            boundaries[name] = (left, right)

        bursts = self.vision.detect_burst_training(screenshot)

        results = {}
        for stat in sorted_names:
            left, right = boundaries[stat]
            r = self.vision.count_rainbows_for_training(screenshot, stat)
            b = sum(1 for x, y in bursts.get("blue", []) if left <= x <= right)
            w = sum(1 for x, y in bursts.get("white", []) if left <= x <= right)
            results[stat] = {
                "score": 0, "rainbow": r, "blue": b, "white": w,
                "friendship": 0, "char_count": 0,
            }

        return results

    def score_single_training(
        self, stat: str, screenshot, is_pre_summer: bool = False,
        current_stats: Optional[Dict[str, int]] = None,
    ) -> Dict:
        friendship_pts = 9 if is_pre_summer else 5

        friend_count = self.vision.count_support_friendship(screenshot)

        bursts = self.vision.detect_burst_training(screenshot)
        b = len(bursts.get("blue", []))
        w = len(bursts.get("white", []))

        r = self.vision.count_rainbows_for_training(screenshot, stat)

        base_score = r * 10 + b * 8 + w * 3 + friend_count * friendship_pts
        bonus_types = sum([r > 0, b > 0, w > 0, friend_count > 0])

        secondary_bonus = 0.0
        gains = self.TRAINING_STAT_GAINS.get(stat, {})
        n = len(self.stat_priority)
        for contrib_stat, contrib_weight in gains.items():
            prio_idx = self.stat_priority.index(contrib_stat) if contrib_stat in self.stat_priority else n
            prio_w = 1.0 + (n - prio_idx) * 0.3
            if current_stats:
                projected = min(
                    current_stats.get(contrib_stat, 0) + self.END_OF_RUN_BONUS,
                    self.STAT_CAP,
                )
                target = self.targets.get(contrib_stat, 0)
                deficit = max(0, target - projected)
                if deficit > 0:
                    secondary_bonus += contrib_weight * prio_w * (1.0 + deficit / max(target, 1))
                elif current_stats.get(contrib_stat, 0) >= self.STAT_CAP:
                    secondary_bonus -= contrib_weight * 2.0
            else:
                secondary_bonus += contrib_weight * prio_w

        score = base_score + secondary_bonus * 3

        self.logger.info(
            f"  {stat}: R={r} B={b} W={w} F={friend_count} "
            f"secondary={secondary_bonus:.1f} → {score:.0f}pts"
        )

        return {
            "score": score, "bonus_types": bonus_types,
            "rainbow": r, "blue": b, "white": w,
            "friendship": friend_count,
            "secondary_bonus": secondary_bonus,
        }

    def _is_wit_training_attractive(
        self, bursts: Dict, rainbow_count: int,
        friendship: Dict, screenshot
    ) -> bool:
        wit_pos = self.vision.find_template("training_wit", screenshot, threshold=0.7)
        if wit_pos is None:
            return False

        wit_y = wit_pos[1]
        wit_range = 80

        blue_near = any(
            abs(by - wit_y) < wit_range
            for _, by in bursts.get("blue", [])
        )
        if blue_near:
            return True

        white_near = sum(
            1 for _, wy in bursts.get("white", [])
            if abs(wy - wit_y) < wit_range
        )
        if white_near >= 2:
            return True

        return False

    def _determine_training_stat(
        self, current_stats: Dict[str, int], friendship: Dict[str, int]
    ) -> Optional[str]:
        adjusted = {}
        for stat in self.vision.STAT_NAMES:
            raw = current_stats.get(stat, 0)
            projected = min(raw + self.END_OF_RUN_BONUS, self.STAT_CAP)
            adjusted[stat] = projected

        tolerance = self._get_stat_tolerance()
        
        stat_status = {}
        for stat in self.vision.STAT_NAMES:
            current = current_stats.get(stat, 0)
            target = self.targets.get(stat, 0)
            
            if current >= self.STAT_CAP:
                stat_status[stat] = "max"
            elif target > 0 and current >= target:
                stat_status[stat] = "target_reached"
            elif target > 0 and current >= (target - tolerance):
                stat_status[stat] = "near_target"
            else:
                stat_status[stat] = "trainable"
        
        all_targets_met = all(
            stat_status[s] in ("max", "target_reached", "near_target")
            for s in self.stat_priority if self.targets.get(s, 0) > 0
        )
        
        if all_targets_met:
            any_not_max = any(
                stat_status[s] != "max"
                for s in self.stat_priority
            )
            if not any_not_max:
                self.logger.info("All stats at max (1200)")
                return None
            self.logger.info("All targets met but can still train non-maxed stats")

        deficits = {}
        for stat in self.vision.STAT_NAMES:
            target = self.targets.get(stat, 0)
            current = adjusted[stat]
            deficit = max(0, target - current)
            deficits[stat] = deficit

        nonzero_targets = [s for s in self.vision.STAT_NAMES if self.targets.get(s, 0) > 0]
        distances = [deficits[s] for s in nonzero_targets]
        avg_distance = sum(distances) / len(distances) if distances else 0
        boost_stats = set()
        for s in nonzero_targets:
            if avg_distance > 0 and deficits[s] > 2 * avg_distance:
                boost_stats.add(s)

        priority_weights = {}
        n = len(self.stat_priority)
        for i, stat in enumerate(self.stat_priority):
            base = 1.0 + (n - i) * 0.5
            if stat in boost_stats:
                base *= 2.0
            priority_weights[stat] = base

        best_training = None
        best_score = -999.0

        for training_type in self.vision.STAT_NAMES:
            if stat_status[training_type] == "max":
                self.logger.debug(f"Training {training_type}: BLOCKED (at max 1200)")
                continue
                
            gains = self.TRAINING_STAT_GAINS.get(training_type, {})
            score = 0.0
            
            for stat, contribution in gains.items():
                current = current_stats.get(stat, 0)
                
                if stat_status[stat] == "max":
                    score -= contribution * 10.0
                    continue
                    
                if stat_status[stat] == "target_reached":
                    score += contribution * priority_weights.get(stat, 0.5) * 0.33
                    continue
                    
                if stat_status[stat] == "near_target":
                    score += contribution * priority_weights.get(stat, 0.5) * 0.5
                    continue
                
                deficit = deficits.get(stat, 0)
                prio_w = priority_weights.get(stat, 0.5)
                deficit_ratio = deficit / max(self.targets.get(stat, 600), 1)
                score += contribution * prio_w * (1.0 + deficit_ratio)

            self.logger.debug(f"Training {training_type}: balanced_score={score:.2f}")
            if score > best_score:
                best_score = score
                best_training = training_type

        if friendship["partial"] > 0:
            self.logger.info(
                f"Friendship building phase: {friendship['partial']} non-maxed supports — "
                f"scoring on training screen will also prioritize friendship"
            )

        self.logger.info(
            f"Balanced training selection: {best_training} (score={best_score:.2f})"
        )
        return best_training

    def should_continue_run(self, turn_count: int) -> bool:
        max_turns = 78
        if turn_count >= max_turns:
            self.logger.warning(f"Turn limit reached ({turn_count} >= {max_turns})")
            return False
        return True

    def evaluate_training_option(
        self, training_type: str, stats_gain: Dict[str, int],
        current_stats: Optional[Dict[str, int]] = None,
    ) -> float:
        score = 0.0
        n = len(self.stat_priority)
        priority_weights = {
            s: 1.0 + (n - i) * 0.4 for i, s in enumerate(self.stat_priority)
        }
        gains = self.TRAINING_STAT_GAINS.get(training_type, {})

        for stat, gain in stats_gain.items():
            weight = priority_weights.get(stat, 0.5)
            if current_stats:
                projected = min(
                    current_stats.get(stat, 0) + self.END_OF_RUN_BONUS,
                    self.STAT_CAP,
                )
                target = self.targets.get(stat, 0)
                deficit = max(0, target - projected)
                if deficit > 0:
                    score += gain * weight * (1.0 + deficit / max(target, 1))
                else:
                    if current_stats.get(stat, 0) + gain > self.STAT_CAP:
                        score -= gain * 0.5
                    else:
                        score += gain * 0.3
            else:
                score += gain * weight

        for stat, contribution in gains.items():
            if stat not in stats_gain:
                prio = priority_weights.get(stat, 0.5)
                score += contribution * prio * 0.5

        return score
    