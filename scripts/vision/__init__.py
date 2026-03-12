import cv2
import ctypes
import json
import numpy as np
import logging
from typing import Optional, Dict
from pathlib import Path

from .capture import CaptureMixin
from .detection import DetectionMixin
from .ocr import OcrMixin
from .training import TrainingAnalysisMixin

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

class VisionModule(CaptureMixin, DetectionMixin, OcrMixin, TrainingAnalysisMixin):
    GAME_WINDOW_TITLES = ["umamusume", "ウマ娘", "pretty derby", "dmm"]
    EXCLUDED_WINDOW_KEYWORDS = [
        "umamusume bot", "umamusume_bot", "mihono_bourbot", "mihono bourbot",
        "explorateur", "explorer", "python", "code", "vscode",
    ]
    MAIN_SCREEN_BUTTONS = [
        "btn_training", "btn_rest", "btn_recreation", "btn_races",
        "btn_rest_summer",
    ]
    TRAINING_TEMPLATES = [
        "training_speed", "training_stamina", "training_power",
        "training_guts", "training_wit",
    ]

    _CAL_ALIASES = {
        "mood_great": "mood_zone", "mood_good": "mood_zone",
        "mood_normal": "mood_zone", "mood_bad": "mood_zone",
        "mood_awful": "mood_zone",
        "btn_training": "main_buttons",
        "btn_rest": "main_buttons",
        "btn_rest_summer": "main_buttons",
        "btn_recreation": "main_buttons",
        "btn_races": "main_buttons",
        "btn_infirmary": "main_buttons",
        "race_view_results_on": "race_view_results",
        "race_view_results_off": "race_view_results",
        "training_selected": "training_zone",
        "rainbow_training": "training_zone",
        "white_burst": "training_zone",
        "icon_rainbow": "training_zone",
        "burst_white": "support_region",
        "burst_blue": "support_region",
        "friend_bar_partial": "support_region",
        "friend_bar_orange": "support_region",
        "friend_bar_max": "support_region",
        "friend_bar_burst": "support_region",
        "unity_opponent_card": "unity_opponent_zone",
        "event_scenario_window": "event_type_window",
        "event_trainee_window": "event_type_window",
        "event_support_window": "event_type_window",
        "event_choice": "event_choices",
        "event_choice_icon": "event_choices",
        "btn_race_start_ura": "btn_race_start",
    }

    _TPL_FILE_ALIASES = {
        "btn_race_scheduled": "btn_race_start",
        "burst_blue": "blue_burst",
        "burst_white": "white_burst",
    }

    _GRAYSCALE_TEMPLATES: set = {"event_choice_icon"}

    _STRUCTURAL_TEMPLATES = {"event_choice"}
    
    _CHARACTER_OVERLAY_TEMPLATES = {
        "complete_career",
        "btn_race_next_finish",
    }

    _GOAL_HUE_LO = 5
    _GOAL_HUE_HI = 30
    _GOAL_SAT_MIN = 100
    _GOAL_VAL_MIN = 100
    _GOAL_MIN_PX = 200
    _GOAL_SCAN_Y1 = 0.12
    _GOAL_SCAN_Y2 = 0.80
    _GOAL_STRIP_H = 20

    def __init__(self, config: dict):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.game_hwnd = None
        self.window_rect = None
        self.templates: Dict[str, np.ndarray] = {}
        self._raw_templates: Dict[str, np.ndarray] = {}
        self.last_screenshot: Optional[np.ndarray] = None
        self.templates_dir = Path("templates")
        self._template_paths: Dict[str, Path] = {}
        self._index_templates()
        self._ref_width: Optional[int] = None
        self._ref_height: Optional[int] = None
        self._load_ref_dimensions()
        self._current_scale: float = 1.0
        self._scaled_for_width: Optional[int] = None
        self._client_offset_x = 0
        self._client_offset_y = 0
        self._calibration = self._load_calibration()

    def _load_ref_dimensions(self):
        meta = self.templates_dir / "meta.json"
        if meta.exists():
            try:
                with open(meta, encoding="utf-8") as f:
                    data = json.load(f)
                self._ref_width = data.get("reference_width")
                self._ref_height = data.get("reference_height")
            except Exception:
                pass

    def save_ref_width(self, width: int, height: int = 0):
        meta = self.templates_dir / "meta.json"
        data = {}
        if meta.exists():
            try:
                with open(meta, encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                pass
        data["reference_width"] = width
        if height > 0:
            data["reference_height"] = height
        with open(meta, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        self._ref_width = width
        if height > 0:
            self._ref_height = height
        self.logger.info("Reference template dimensions saved: %dx%d", width, height or 0)

    def _update_scale(self, screenshot: np.ndarray):
        if self._ref_width is None:
            self._auto_calibrate(screenshot)
            if self._ref_width is None:
                return
        _, _, gw, gh = self.get_game_rect(screenshot)
        if gw == self._scaled_for_width:
            return
        self._scaled_for_width = gw
        platform = self.config.get("platform", "google_play")
        if platform in self._TRANSFORMED_PLATFORMS:
            self._current_scale = self._find_best_scale(screenshot)
        else:
            self._current_scale = gw / self._ref_width
        self.templates.clear()
        if abs(self._current_scale - 1.0) > 0.01:
            self.logger.info("Template scale: %.3f (game %dx%d, ref %dx%d)",
                             self._current_scale, gw, gh,
                             self._ref_width, self._ref_height or 0)

    def _find_best_scale(self, screenshot: np.ndarray) -> float:
        gx, gy, gw, gh = self.get_game_rect(screenshot)
        game_area = screenshot[gy:gy + gh, gx:gx + gw]
        anchors = []
        for name in self._CALIBRATION_TEMPLATES:
            fn = self._TPL_FILE_ALIASES.get(name, name)
            if fn not in self._raw_templates:
                path = self.get_template_path(fn)
                if path is None:
                    continue
                img = cv2.imread(str(path))
                if img is None:
                    continue
                self._raw_templates[fn] = img
            anchors.append(self._raw_templates[fn])
        if not anchors:
            return gw / self._ref_width
        base = gw / self._ref_width
        candidates = sorted(set(
            round(base + d, 3)
            for d in [-0.2, -0.15, -0.1, -0.05, 0, 0.05, 0.1, 0.15, 0.2]
            if base + d > 0.3
        ))
        if abs(base - 1.0) > 0.05 and 1.0 not in candidates:
            candidates.append(1.0)
            candidates.sort()
        best_scale, best_score = base, 0.0
        for scale in candidates:
            total = 0.0
            count = 0
            for tpl in anchors:
                nw = max(1, int(tpl.shape[1] * scale))
                nh = max(1, int(tpl.shape[0] * scale))
                if nh > game_area.shape[0] or nw > game_area.shape[1]:
                    continue
                interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
                scaled = cv2.resize(tpl, (nw, nh), interpolation=interp)
                res = cv2.matchTemplate(game_area, scaled, cv2.TM_CCOEFF_NORMED)
                _, mv, _, _ = cv2.minMaxLoc(res)
                total += mv
                count += 1
            if count > 0:
                avg = total / count
                if avg > best_score:
                    best_score = avg
                    best_scale = scale
        self.logger.info("Platform scale search: base=%.3f → best=%.3f (score=%.3f)",
                         base, best_scale, best_score)
        if best_score < 0.65:
            self.logger.info("Scale score too low (%.3f < 0.65), using native scale 1.0",
                             best_score)
            return 1.0
        return best_scale

    def _scale_px(self, px: int) -> int:
        return max(1, int(round(px * self._current_scale)))

    _CALIBRATION_TEMPLATES = [
        "btn_training", "btn_rest", "btn_races", "btn_recreation",
        "btn_race_confirm", "btn_race_launch",
    ]

    def _auto_calibrate(self, screenshot: np.ndarray):
        """Auto-detect reference width via multi-scale matching."""
        _, _, gw, _ = self.get_game_rect(screenshot)
        game_area = screenshot[
            :, max(0, int(screenshot.shape[1] * 0.1)):int(screenshot.shape[1] * 0.9)
        ]

        anchors = []
        for name in self._CALIBRATION_TEMPLATES:
            fn = self._TPL_FILE_ALIASES.get(name, name)
            path = self.get_template_path(fn)
            if path is None:
                continue
            img = cv2.imread(str(path))
            if img is not None:
                anchors.append((name, img))
        if not anchors:
            self.logger.warning("No calibration templates — auto-calibration skipped")
            return

        coarse_scales = [round(s * 0.1, 2) for s in range(5, 26)]
        best_scale, best_score = 1.0, 0.0

        for scale in coarse_scales:
            total = 0.0
            for _name, tpl in anchors:
                nw = max(1, int(tpl.shape[1] * scale))
                nh = max(1, int(tpl.shape[0] * scale))
                if nh > game_area.shape[0] or nw > game_area.shape[1]:
                    continue
                interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
                scaled = cv2.resize(tpl, (nw, nh), interpolation=interp)
                res = cv2.matchTemplate(game_area, scaled, cv2.TM_CCOEFF_NORMED)
                _, mv, _, _ = cv2.minMaxLoc(res)
                total += mv
            avg = total / len(anchors)
            if avg > best_score:
                best_score = avg
                best_scale = scale

        for delta in [-0.05, -0.03, -0.02, 0.02, 0.03, 0.05]:
            scale = round(best_scale + delta, 3)
            if scale <= 0.1:
                continue
            total = 0.0
            for _name, tpl in anchors:
                nw = max(1, int(tpl.shape[1] * scale))
                nh = max(1, int(tpl.shape[0] * scale))
                if nh > game_area.shape[0] or nw > game_area.shape[1]:
                    continue
                interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
                scaled = cv2.resize(tpl, (nw, nh), interpolation=interp)
                res = cv2.matchTemplate(game_area, scaled, cv2.TM_CCOEFF_NORMED)
                _, mv, _, _ = cv2.minMaxLoc(res)
                total += mv
            avg = total / len(anchors)
            if avg > best_score:
                best_score = avg
                best_scale = scale

        ref_w = max(1, int(round(gw / best_scale)))
        _, _, _, gh_cal = self.get_game_rect(screenshot)
        ref_h = max(1, int(round(gh_cal / best_scale)))
        self.logger.info(
            "Auto-calibrated: best scale=%.3f, score=%.3f → ref=%dx%d (game=%dx%d)",
            best_scale, best_score, ref_w, ref_h, gw, gh_cal,
        )
        self.save_ref_width(ref_w, ref_h)

    def _get_scaled_template(self, template_name: str) -> Optional[np.ndarray]:
        """Return a template scaled to match the current game window size."""
        if template_name in self.templates:
            return self.templates[template_name]

        file_name = self._TPL_FILE_ALIASES.get(template_name, template_name)
        if file_name not in self._raw_templates:
            path = self.get_template_path(file_name)
            if path is None:
                return None
            img = cv2.imread(str(path))
            if img is None:
                return None
            self._raw_templates[file_name] = img

        raw = self._raw_templates[file_name]
        scale = self._current_scale
        if abs(scale - 1.0) > 0.01:
            nw = max(1, int(raw.shape[1] * scale))
            nh = max(1, int(raw.shape[0] * scale))
            interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
            scaled = cv2.resize(raw, (nw, nh), interpolation=interp)
        else:
            scaled = raw
        self.templates[template_name] = scaled
        return scaled

    def _index_templates(self):
        """Build a name→path index scanning all sub-folders of templates_dir."""
        self._template_paths.clear()
        if not self.templates_dir.exists():
            return
        for p in self.templates_dir.rglob("*.png"):
            name = p.stem
            self._template_paths[name] = p

    def get_template_path(self, template_name: str) -> Optional[Path]:
        """Return the path for a template name, searching sub-folders."""
        if template_name in self._template_paths:
            return self._template_paths[template_name]
        flat = self.templates_dir / f"{template_name}.png"
        if flat.exists():
            self._template_paths[template_name] = flat
            return flat
        return None
    