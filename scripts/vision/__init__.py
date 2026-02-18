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
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    ctypes.windll.user32.SetProcessDPIAware()

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
        "btn_infirmary_on": "btn_infirmary", "btn_infirmary_off": "btn_infirmary",
        "btn_rest_summer": "btn_rest",
        "race_view_results_on": "race_view_results",
        "race_view_results_off": "race_view_results",
        "training_selected": "training_zone",
        "rainbow_training": "training_zone",
        "unity_training": "training_zone",
        "spirit_burst": "training_zone",
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
        "btn_race_start_ura": "btn_race_start",
    }

    _TPL_FILE_ALIASES = {
        "btn_race_scheduled": "btn_race_start",
        "burst_blue": "blue_burst",
        "burst_white": "unity_training",
    }

    _GRAYSCALE_TEMPLATES: set = set()

    _STRUCTURAL_TEMPLATES = {"event_choice"}
    
    _CHARACTER_OVERLAY_TEMPLATES = {
        "btn_training", "btn_races", "complete_career",
        "btn_race_next_finish", "btn_recreation"
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
        self._ref_width: Optional[int] = self._load_ref_width()
        self._current_scale: float = 1.0
        self._scaled_for_width: Optional[int] = None
        self._client_offset_x = 0
        self._client_offset_y = 0
        self._calibration = self._load_calibration()
        self._setup_tesseract()

    def _load_ref_width(self) -> Optional[int]:
        """Load the reference game width templates were captured at."""
        meta = self.templates_dir / "meta.json"
        if meta.exists():
            try:
                with open(meta, encoding="utf-8") as f:
                    return json.load(f).get("reference_width")
            except Exception:
                pass
        return None

    def save_ref_width(self, width: int):
        """Save the current game width as the reference for template scaling."""
        meta = self.templates_dir / "meta.json"
        data = {}
        if meta.exists():
            try:
                with open(meta, encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                pass
        data["reference_width"] = width
        with open(meta, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        self._ref_width = width
        self.logger.info("Reference template width saved: %d", width)

    def _update_scale(self, screenshot: np.ndarray):
        """Recompute template scale factor if game width changed."""
        if self._ref_width is None:
            self._auto_calibrate(screenshot)
            if self._ref_width is None:
                return
        _, _, gw, _ = self.get_game_rect(screenshot)
        if gw == self._scaled_for_width:
            return
        self._scaled_for_width = gw
        self._current_scale = gw / self._ref_width
        if abs(self._current_scale - 1.0) > 0.01:
            self.logger.info("Template scale: %.3f (game %dpx, ref %dpx)",
                             self._current_scale, gw, self._ref_width)
            self.templates.clear()

    def _scale_px(self, px: int) -> int:
        """Scale a pixel value by the current resolution factor."""
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
        self.logger.info(
            "Auto-calibrated: best scale=%.3f, score=%.3f → ref_width=%d (game_w=%d)",
            best_scale, best_score, ref_w, gw,
        )
        self.save_ref_width(ref_w)

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
    