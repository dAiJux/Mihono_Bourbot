import sys, os, json, cv2, numpy as np
sys.path.insert(0, '.')
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.vision import VisionModule
from scripts.vision.ocr import _ocr_digits

with open('config/config.json') as f:
    config = json.load(f)
v = VisionModule(config)
v.find_game_window()
ss = v.take_screenshot()
gx, gy, gw, gh = v.get_game_rect(ss)
print(f'game rect: gx={gx}, gy={gy}, gw={gw}, gh={gh}')

buy_icons = v.find_all_template('buy_skill', ss, 0.82, min_distance=20)
visible = [(bx,by) for bx,by in buy_icons if gy + int(gh*0.20) < by < gy + int(gh*0.95)]

for i, (bx, by) in enumerate(visible):
    cost_x1 = max(0, bx - int(gw * 0.16))
    cost_x2 = max(0, bx - int(gw * 0.01))
    cost_y1 = max(0, by - int(gh * 0.022))
    cost_y2 = min(ss.shape[0], by + int(gh * 0.022))
    roi = ss[cost_y1:cost_y2, cost_x1:cost_x2]
    print(f'Skill {i}: icon=({bx},{by}) cost_roi=({cost_x1},{cost_y1})-({cost_x2},{cost_y2}) shape={roi.shape}')
    cv2.imwrite(f'logs/debug/cost_roi_{i}.png', roi)

    for expand in [0.25, 0.30, 0.40]:
        ex1 = max(0, bx - int(gw * expand))
        ex2 = max(0, bx - int(gw * 0.01))
        ey1 = max(0, by - int(gh * 0.035))
        ey2 = min(ss.shape[0], by + int(gh * 0.035))
        eroi = ss[ey1:ey2, ex1:ex2]
        cv2.imwrite(f'logs/debug/cost_expanded_{i}_{int(expand*100)}.png', eroi)
        big = cv2.resize(eroi, (eroi.shape[1]*3, eroi.shape[0]*3), interpolation=cv2.INTER_CUBIC)
        gray = cv2.cvtColor(big, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 100, 255, cv2.THRESH_BINARY_INV)
        result = _ocr_digits(thresh).strip()
        print(f'  Expand {int(expand*100)}%: ({ex1},{ey1})-({ex2},{ey2}) shape={eroi.shape} OCR="{result}"')
