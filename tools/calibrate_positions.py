import cv2
import numpy as np
import json
from pathlib import Path
from collections import OrderedDict

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.vision import VisionModule

CAL_FILE = Path("config", "calibration.json")
SIDEBAR_W = 260
WINDOW_NAME = "Bot Calibration"

FULL = {"x1": 0.0, "y1": 0.0, "x2": 1.0, "y2": 1.0}
BOT  = {"x1": 0.0, "y1": 0.70, "x2": 1.0, "y2": 1.0}
TOP  = {"x1": 0.0, "y1": 0.0,  "x2": 1.0, "y2": 0.20}
TOPR = {"x1": 0.50, "y1": 0.0,  "x2": 1.0, "y2": 0.15}
MID  = {"x1": 0.0, "y1": 0.20, "x2": 1.0, "y2": 0.80}

def _r(x1, y1, x2, y2):
    return {"x1": x1, "y1": y1, "x2": x2, "y2": y2}

def _p(x, y):
    return {"x": x, "y": y}

CATEGORIES = OrderedDict([
    ("Game Area", [
        ("game_rect", "gr", _r(0.34, 0.0, 0.66, 1.0)),
    ]),
    ("ROI Zones", [
        ("energy_bar",     "roi", _r(0.33, 0.082, 0.69, 0.098)),
        ("support_region", "roi", _r(0.82, 0.10, 0.98, 0.48)),
        ("date_display",   "roi", _r(0.02, 0.005, 0.55, 0.035)),
    ]),
    ("Stats ROI", [
        ("stat_speed",   "roi", _r(0.05, 0.27, 0.19, 0.29)),
        ("stat_stamina", "roi", _r(0.24, 0.27, 0.38, 0.29)),
        ("stat_power",   "roi", _r(0.43, 0.27, 0.57, 0.29)),
        ("stat_guts",    "roi", _r(0.62, 0.27, 0.76, 0.29)),
        ("stat_wit",     "roi", _r(0.81, 0.27, 0.95, 0.29)),
    ]),
    ("Training Pos.", [
        ("train_speed",   "pt", _p(0.145, 0.843)),
        ("train_stamina", "pt", _p(0.322, 0.843)),
        ("train_power",   "pt", _p(0.500, 0.843)),
        ("train_guts",    "pt", _p(0.678, 0.843)),
        ("train_wit",     "pt", _p(0.855, 0.843)),
    ]),
    ("Training TPL", [
        ("training_zone",        "tpl", BOT),
        ("training_speed",       "tpl", BOT),
        ("training_stamina",     "tpl", BOT),
        ("training_power",       "tpl", BOT),
        ("training_guts",        "tpl", BOT),
        ("training_wit",         "tpl", BOT),
    ]),
    ("Events", [
        ("event_type_window", "tpl", _r(0.0, 0.0, 1.0, 0.30)),
        ("event_title",       "roi", _r(0.10, 0.13, 0.90, 0.22)),
        ("event_choices",     "roi", _r(0.05, 0.35, 0.95, 0.85)),
    ]),
    ("Mood", [
        ("mood_zone",  "tpl", TOPR),
    ]),
    ("Main Buttons", [
        ("btn_training",   "tpl", BOT),
        ("btn_rest",       "tpl", BOT),
        ("btn_recreation", "tpl", BOT),
        ("btn_races",      "tpl", TOP),
        ("btn_infirmary",  "tpl", BOT),
    ]),
    ("Race", [
        ("btn_race_start",        "tpl", BOT),
        ("btn_race_confirm",      "tpl", BOT),
        ("btn_race_confirm_2",    "tpl", BOT),
        ("btn_race_confirm_3",    "tpl", BOT),
        ("btn_race_launch",       "tpl", BOT),
        ("btn_race_scheduled",    "tpl", FULL),
        ("btn_race_next_finish",  "tpl", BOT),
        ("btn_change_strategy",   "tpl", FULL),
        ("race_view_results",     "tpl", FULL),
        ("target_race",           "tpl", FULL),
        ("scheduled_race",        "tpl", FULL),
        ("strategy_front",        "tpl", MID),
        ("strategy_end",          "tpl", MID),
        ("strategy_late",         "tpl", MID),
        ("strategy_pace",         "tpl", MID),
    ]),
    ("Buttons", [
        ("btn_confirm",       "tpl", BOT),
        ("btn_ok",            "tpl", FULL),
        ("btn_close",         "tpl", FULL),
        ("btn_cancel",        "tpl", FULL),
        ("btn_try_again",     "tpl", FULL),
        ("btn_skip",          "tpl", BOT),
        ("btn_tap",           "tpl", BOT),
        ("btn_next",          "tpl", BOT),
        ("btn_back",          "tpl", TOP),
        ("btn_claw_machine",  "tpl", FULL),
        ("btn_inspiration",   "tpl", FULL),
    ]),
    ("Unity", [
        ("btn_unity_launch",       "tpl", FULL),
        ("btn_begin_showdown",     "tpl", BOT),
        ("btn_select_opponent",    "tpl", FULL),
        ("btn_see_unity_results",  "tpl", FULL),
        ("btn_launch_final_unity", "tpl", FULL),
        ("btn_next_unity",         "tpl", BOT),
        ("unity_opponent_zone",    "tpl", FULL),
    ]),
    ("Other", [
        ("complete_career",       "tpl", FULL),
    ]),
])

ITEM_LOOKUP = {}
for _ci, (_cn, _citems) in enumerate(CATEGORIES.items()):
    for _name, _itype, _idef in _citems:
        ITEM_LOOKUP[_name] = (_itype, _idef, _ci)

CAT_COLORS = [
    (0,255,0),(255,100,0),(255,200,50),(0,0,255),(200,200,0),
    (0,200,255),(200,50,255),(0,255,200),(255,50,150),(100,255,100),
    (255,150,0),(150,150,255),
]

class CalibrationTool:
    HS = 8
    GM = 14

    def __init__(self):
        with open(os.path.join("config", "config.json"), encoding="utf-8") as f:
            cfg = json.load(f)
        self.vision = VisionModule(cfg)

        self.screenshot = None
        self.sw, self.sh = 800, 900
        self.grpx = (0, 0, 100, 100)
        self.dscale = 1.0
        self.dw, self.dh = 600, 900

        self.cat_idx = 0
        self.item_idx = 0
        self.data = {}
        self.visible = set()

        self.drag_mode = None
        self.drag_anchor = None
        self.status = "Press SPACE to capture a screenshot"
        self.unsaved = False
        self._quit_flag = False
        self._has_cal = CAL_FILE.exists()

        self._load()

    def _load(self):
        for items in CATEGORIES.values():
            for name, _, default in items:
                self.data[name] = dict(default)
        if CAL_FILE.exists():
            try:
                with open(CAL_FILE, encoding="utf-8") as f:
                    saved = json.load(f)
                for name, val in saved.items():
                    if name in self.data:
                        self.data[name] = val
            except Exception:
                pass

    def _save(self):
        out = {}
        for name, val in self.data.items():
            out[name] = {k: round(v, 4) for k, v in val.items()}
        with open(CAL_FILE, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2, ensure_ascii=False)
        self.unsaved = False
        self._has_cal = True
        self.status = f"SAVED {len(out)} items to {CAL_FILE}"
        print(f"\nCalibration saved: {CAL_FILE} ({len(out)} items)")

    def _current(self):
        cat = list(CATEGORIES.values())[self.cat_idx]
        if 0 <= self.item_idx < len(cat):
            return cat[self.item_idx]
        return None

    def _current_name(self):
        c = self._current()
        return c[0] if c else None

    def take_screenshot(self):
        self.vision.find_game_window()
        if not self.vision.game_hwnd:
            self.status = "ERROR: Game window not found!"
            return
        self.screenshot = self.vision.take_screenshot()
        h, w = self.screenshot.shape[:2]
        self.sw, self.sh = w, h

        if not self._has_cal:
            gw = h * 9 / 16
            gx = (w - gw) / 2
            self.data["game_rect"] = {
                "x1": round(gx / w, 4), "y1": 0.0,
                "x2": round((gx + gw) / w, 4), "y2": 1.0,
            }

        self._sync_gr()
        self.dh = min(920, h)
        self.dscale = self.dh / h
        self.dw = int(w * self.dscale)
        self.status = f"Captured {w}x{h}  game={self.grpx[2]}x{self.grpx[3]}"

    def _sync_gr(self):
        gr = self.data["game_rect"]
        w, h = self.sw, self.sh
        gx = int(w * gr["x1"])
        gy = int(h * gr["y1"])
        self.grpx = (gx, gy, max(1, int(w * gr["x2"]) - gx),
                     max(1, int(h * gr["y2"]) - gy))

    def _to_img(self, name, rx, ry):
        """Zone-relative → image display pixel (on the screenshot portion)."""
        if name == "game_rect":
            sx, sy = self.sw * rx, self.sh * ry
        else:
            gx, gy, gw, gh = self.grpx
            sx, sy = gx + gw * rx, gy + gh * ry
        return int(sx * self.dscale), int(sy * self.dscale)

    def _to_win(self, name, rx, ry):
        ix, iy = self._to_img(name, rx, ry)
        return ix + SIDEBAR_W, iy

    def _from_win(self, name, wx, wy):
        sx = (wx - SIDEBAR_W) / self.dscale
        sy = wy / self.dscale
        if name == "game_rect":
            return sx / max(1, self.sw), sy / max(1, self.sh)
        gx, gy, gw, gh = self.grpx
        return (sx - gx) / max(1, gw), (sy - gy) / max(1, gh)

    def draw(self):
        tw = SIDEBAR_W + self.dw
        canvas = np.zeros((self.dh, tw, 3), dtype=np.uint8)

        self._draw_sidebar(canvas)

        if self.screenshot is not None:
            img = cv2.resize(self.screenshot, (self.dw, self.dh))
            self._draw_overlays(img)
            canvas[0:self.dh, SIDEBAR_W:SIDEBAR_W + self.dw] = img
        else:
            self._text(canvas, "Press SPACE", (SIDEBAR_W + 30, self.dh // 2 - 20),
                       (200, 200, 200), 0.7)
            self._text(canvas, "to capture game screenshot",
                       (SIDEBAR_W + 30, self.dh // 2 + 20), (150, 150, 150), 0.5)

        self._draw_status(canvas)
        return canvas

    def _draw_sidebar(self, canvas):
        h = canvas.shape[0]
        cv2.rectangle(canvas, (0, 0), (SIDEBAR_W - 1, h), (35, 35, 35), -1)
        cv2.line(canvas, (SIDEBAR_W - 1, 0), (SIDEBAR_W - 1, h), (80, 80, 80), 1)

        cat_names = list(CATEGORIES.keys())
        cat_name = cat_names[self.cat_idx]
        items = list(CATEGORIES.values())[self.cat_idx]
        color = CAT_COLORS[self.cat_idx % len(CAT_COLORS)]

        y = 22
        self._text(canvas, f"< {cat_name} >", (8, y), color, 0.5, False)
        y += 18
        self._text(canvas, f"({self.cat_idx+1}/{len(cat_names)})  Tab=switch",
                   (8, y), (120, 120, 120), 0.3, False)
        y += 25

        for i, (name, itype, _) in enumerate(items):
            is_cur = (i == self.item_idx)
            is_vis = name in self.visible
            prefix = ">" if is_cur else " "
            suffix = " [V]" if is_vis else ""
            if is_cur:
                fg = (255, 255, 255)
            elif is_vis:
                fg = color
            else:
                fg = (100, 100, 100)
            self._text(canvas, f"{prefix} {name}{suffix}", (6, y), fg, 0.36, False)
            y += 17

        y += 12
        self._text(canvas, "V=toggle  S=save  R=reset", (8, y), (90, 90, 90), 0.3, False)
        y += 16
        self._text(canvas, "Space=screenshot  Q=quit", (8, y), (90, 90, 90), 0.3, False)
        y += 16
        self._text(canvas, "Up/Down=nav  Tab=category", (8, y), (90, 90, 90), 0.3, False)
        y += 16
        self._text(canvas, "Click sidebar item to toggle", (8, y), (90, 90, 90), 0.3, False)

    def _draw_overlays(self, img):
        cur = self._current_name()
        if "game_rect" in self.visible:
            self._draw_zone_rect(img, "game_rect", CAT_COLORS[0],
                                 cur == "game_rect")

        for name in self.visible:
            if name == "game_rect":
                continue
            if name not in ITEM_LOOKUP:
                continue
            itype, _, ci = ITEM_LOOKUP[name]
            color = CAT_COLORS[ci % len(CAT_COLORS)]
            is_sel = (name == cur and name in self.visible)
            if itype == "pt":
                self._draw_point(img, name, color, is_sel)
            else:
                self._draw_zone_rect(img, name, color, is_sel)

    def _draw_zone_rect(self, img, name, color, is_sel):
        d = self.data[name]
        p1 = self._to_img(name, d["x1"], d["y1"])
        p2 = self._to_img(name, d["x2"], d["y2"])
        th = 3 if is_sel else 1
        cv2.rectangle(img, p1, p2, color, th)
        self._text(img, name, (p1[0], p1[1] - 8), color, 0.33)

        if is_sel:
            hs = self.HS
            for cx, cy in [p1, (p2[0], p1[1]), (p1[0], p2[1]), p2]:
                cv2.rectangle(img, (cx - hs, cy - hs), (cx + hs, cy + hs), color, -1)
            txt = f"({d['x1']:.3f},{d['y1']:.3f})-({d['x2']:.3f},{d['y2']:.3f})"
            self._text(img, txt, (p1[0], p2[1] + 14), color, 0.3)

    def _draw_point(self, img, name, color, is_sel):
        d = self.data[name]
        cx, cy = self._to_img(name, d["x"], d["y"])
        r = 16 if is_sel else 10
        th = 3 if is_sel else 1
        cv2.circle(img, (cx, cy), r, color, th)
        cv2.line(img, (cx - r, cy), (cx + r, cy), color, 1)
        cv2.line(img, (cx, cy - r), (cx, cy + r), color, 1)
        label = name
        if is_sel:
            label += f" ({d['x']:.3f},{d['y']:.3f})"
        self._text(img, label, (cx - 20, cy - r - 6), color, 0.33)

    def _draw_status(self, canvas):
        h = canvas.shape[0]
        y = h - 18
        color = (100, 255, 100) if "SAVED" in self.status else (255, 255, 255)
        if "ERROR" in self.status:
            color = (0, 0, 255)
        tag = " *UNSAVED*" if self.unsaved else ""
        self._text(canvas, f"{self.status}{tag}", (SIDEBAR_W + 8, y), color, 0.4, True)

    def _text(self, img, text, pos, color, scale=0.45, bg=True):
        font = cv2.FONT_HERSHEY_SIMPLEX
        (tw, th), _ = cv2.getTextSize(text, font, scale, 1)
        x, y = int(pos[0]), int(pos[1])
        if bg:
            cv2.rectangle(img, (x - 2, y - th - 4), (x + tw + 2, y + 4), (0, 0, 0), -1)
        cv2.putText(img, text, (x, y), font, scale, color, 1, cv2.LINE_AA)

    def _mouse(self, event, x, y, flags):
        if self.screenshot is None:
            return
        if event == cv2.EVENT_LBUTTONDOWN:
            self._on_mouse_down(x, y)
        elif event == cv2.EVENT_MOUSEMOVE and (flags & cv2.EVENT_FLAG_LBUTTON):
            self._on_mouse_drag(x, y)
        elif event == cv2.EVENT_LBUTTONUP:
            self.drag_mode = None
            self.drag_anchor = None

    def _on_mouse_down(self, wx, wy):
        if wx < SIDEBAR_W:
            self._sidebar_click(wy)
            return

        name = self._current_name()
        if not name or name not in self.visible:
            return
        d = self.data[name]
        itype = ITEM_LOOKUP[name][0]
        M = self.GM

        if itype == "pt":
            px, py = self._to_win(name, d["x"], d["y"])
            if abs(wx - px) < 22 and abs(wy - py) < 22:
                self.drag_mode = "move_pt"
            return

        p1 = self._to_win(name, d["x1"], d["y1"])
        p2 = self._to_win(name, d["x2"], d["y2"])

        for mode, (cx, cy) in [("resize_tl", p1), ("resize_tr", (p2[0], p1[1])),
                                ("resize_bl", (p1[0], p2[1])), ("resize_br", p2)]:
            if abs(wx - cx) < M and abs(wy - cy) < M:
                self.drag_mode = mode
                return

        if p1[0] - M < wx < p2[0] + M:
            if abs(wy - p1[1]) < M:
                self.drag_mode = "resize_t"; return
            if abs(wy - p2[1]) < M:
                self.drag_mode = "resize_b"; return
        if p1[1] - M < wy < p2[1] + M:
            if abs(wx - p1[0]) < M:
                self.drag_mode = "resize_l"; return
            if abs(wx - p2[0]) < M:
                self.drag_mode = "resize_r"; return

        if p1[0] < wx < p2[0] and p1[1] < wy < p2[1]:
            self.drag_mode = "move"
            self.drag_anchor = self._from_win(name, wx, wy)

    def _sidebar_click(self, wy):
        y_start = 65
        items = list(CATEGORIES.values())[self.cat_idx]
        idx = (wy - y_start) // 17
        if 0 <= idx < len(items):
            self.item_idx = idx
            name = items[idx][0]
            self.visible.symmetric_difference_update({name})

    def _on_mouse_drag(self, wx, wy):
        if not self.drag_mode:
            return
        name = self._current_name()
        if not name:
            return

        self.unsaved = True
        d = self.data[name]
        rx, ry = self._from_win(name, wx, wy)
        MIN = 0.005

        if self.drag_mode == "move_pt":
            d["x"] = max(0.0, min(1.0, rx))
            d["y"] = max(0.0, min(1.0, ry))
        elif self.drag_mode == "move":
            orx, ory = self.drag_anchor
            dx, dy = rx - orx, ry - ory
            w, h = d["x2"] - d["x1"], d["y2"] - d["y1"]
            d["x1"] += dx; d["y1"] += dy
            d["x2"] = d["x1"] + w; d["y2"] = d["y1"] + h
            self.drag_anchor = (rx, ry)
        elif "tl" in self.drag_mode:
            d["x1"] = min(rx, d["x2"] - MIN); d["y1"] = min(ry, d["y2"] - MIN)
        elif "tr" in self.drag_mode:
            d["x2"] = max(rx, d["x1"] + MIN); d["y1"] = min(ry, d["y2"] - MIN)
        elif "bl" in self.drag_mode:
            d["x1"] = min(rx, d["x2"] - MIN); d["y2"] = max(ry, d["y1"] + MIN)
        elif "br" in self.drag_mode:
            d["x2"] = max(rx, d["x1"] + MIN); d["y2"] = max(ry, d["y1"] + MIN)
        elif self.drag_mode == "resize_t":
            d["y1"] = min(ry, d["y2"] - MIN)
        elif self.drag_mode == "resize_b":
            d["y2"] = max(ry, d["y1"] + MIN)
        elif self.drag_mode == "resize_l":
            d["x1"] = min(rx, d["x2"] - MIN)
        elif self.drag_mode == "resize_r":
            d["x2"] = max(rx, d["x1"] + MIN)

        if name == "game_rect":
            self._sync_gr()

    def _reset_current(self):
        cur = self._current()
        if not cur:
            return
        name, itype, default = cur
        if name == "game_rect" and self.screenshot is not None:
            gw = self.sh * 9 / 16
            gx = (self.sw - gw) / 2
            self.data[name] = {"x1": round(gx / self.sw, 4), "y1": 0.0,
                               "x2": round((gx + gw) / self.sw, 4), "y2": 1.0}
            self._sync_gr()
        else:
            self.data[name] = dict(default)
        self.unsaved = True
        self.status = f"Reset {name} to default"

    def run(self):
        cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_AUTOSIZE)
        cv2.setMouseCallback(WINDOW_NAME,
                             lambda e, x, y, f, p: self._mouse(e, x, y, f))

        cat_count = len(CATEGORIES)
        print("=" * 55)
        print("   CALIBRATION TOOL")
        print("   Space=screenshot  Tab=category  V=toggle  S=save")
        print("=" * 55)

        while True:
            canvas = self.draw()
            cv2.imshow(WINDOW_NAME, canvas)
            key = cv2.waitKeyEx(30)
            if key == -1:
                continue
            kl = key & 0xFF

            if kl in (ord("q"), 27):
                if self.unsaved and not self._quit_flag:
                    self.status = "Unsaved! Q again to quit, S to save."
                    self._quit_flag = True
                    continue
                break
            self._quit_flag = False

            if kl == ord(" "):
                self.take_screenshot()
            elif kl == ord("s"):
                self._save()
            elif kl == ord("v"):
                name = self._current_name()
                if name:
                    self.visible.symmetric_difference_update({name})
            elif kl == ord("r"):
                self._reset_current()
            elif key == 9:
                self.cat_idx = (self.cat_idx + 1) % cat_count
                self.item_idx = 0
            elif kl == 8:
                self.cat_idx = (self.cat_idx - 1) % cat_count
                self.item_idx = 0
            elif key == 2490368:
                self.item_idx = max(0, self.item_idx - 1)
            elif key == 2621440:
                cat = list(CATEGORIES.values())[self.cat_idx]
                self.item_idx = min(len(cat) - 1, self.item_idx + 1)

        cv2.destroyAllWindows()
        print("Calibration tool closed.")

def main():
    tool = CalibrationTool()
    tool.run()

if __name__ == "__main__":
    main()
