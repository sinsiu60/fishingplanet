"""파이팅 중 글자 예산 점검 (DESIGN.md 31장): 화면 전체 동시 1개, 6글자 이하 (판정 글자는 제외 — 31-10).

실제 낚시 화면(FishingScene)으로 기존 행동 + 신규 패턴 12종 + 전설을 파이팅시키며 매 3프레임 그려서
hud.text / big_text 호출을 모두 센다. 디버그(F1)·멈춤 카드·도움말·결과 화면은 제외.

  python tools/fight_text_check.py [pc|touch] [초=20] [all]   (all = 모든 물고기, 신규 패턴은 그 물고기 것 중 하나씩 강제)
위반이 있으면 목록을 출력하고 종료 코드 1.
"""
import collections
import re
import os
import shutil
import sys
import tempfile

mode = sys.argv[1] if len(sys.argv) > 1 else "pc"
secs = float(sys.argv[2]) if len(sys.argv) > 2 else 20.0
ALL = "all" in sys.argv[3:]
sys.argv = [sys.argv[0]] + (["--mobile-preview", "--preset", "phone20"] if mode == "touch" else [])
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
SAVE = os.path.join(tempfile.gettempdir(), f"fp_textcheck_{mode}")
shutil.rmtree(SAVE, ignore_errors=True)
os.makedirs(SAVE)
os.environ["FISHING_SAVE_DIR"] = SAVE

import random  # noqa: E402

random.seed(4)

from src.save.save_game import SaveGame, all_fish  # noqa: E402
from src.save.settings import Settings  # noqa: E402
from src.ui import tutorial as tut  # noqa: E402

sg = SaveGame(1)
sg.data["money"] = 5000
sg.save()
st = Settings()
st.data["tutorial_seen"] = sorted(set(tut.CARDS) | set(tut.GUIDES))
st.save()

from src.core.game import Game  # noqa: E402
from src.fishing.casting import CastState  # noqa: E402
from src.scene.fishing_scene import FishingScene  # noqa: E402
from src.scene.menu import start_game  # noqa: E402
from src.ui import fight_fx, fight_hud, hud, icons, pattern_fx, pattern_guide  # noqa: E402
from src.platform import touch_ui  # noqa: E402

g = Game()
start_game(g, sg)
fs = next(s for s in g.scenes.stack if isinstance(s, FishingScene))
while g.scenes.current is not fs:
    g.scenes.pop()
fs.card = None
fs.bite.update = lambda dt: None

# ── 계측 ──
orig_text, orig_big = hud.text, fight_fx.big_text
rec: list = []
skip = {"draw_debug", "draw_debug_lines"}


def rtext(canvas, s, pos, color, size=11, anchor="topleft"):
    import inspect
    fn = inspect.stack()[1].function
    if fn not in skip:
        rec.append((fn, str(s)))
    return orig_text(canvas, s, pos, color, size, anchor)


def rbig(canvas, s, center, color, scale, outline=False):
    # 판정 글자(PERFECT!·GREAT!·×N 연속·패턴 성공/실패 문구)는 원래 연출 그대로 — 예산에서 제외 (사용자 요청)
    if str(s) not in fight_fx.JUDGE_WORDS and not re.fullmatch(r"×\d+ 연속", str(s)):
        rec.append(("big_text", str(s)))
    return orig_big(canvas, s, center, color, scale, outline)


for m in (hud, fight_hud, pattern_fx, pattern_guide, fight_fx, icons, touch_ui, tut):
    if getattr(m, "text", None) is orig_text:
        m.text = rtext
fight_fx.big_text = rbig
import src.scene.fishing_scene as FS  # noqa: E402

FS.hud.text = rtext


def tick(n=1):
    for _ in range(n):
        g.scenes.current.update(1 / 60)
        f = fs.fight
        if f is not None and f.phase == "fight":
            f.line = max(f.line, f.line_max * 0.6)
            f.hook = min(f.hook, 60)
            f.stamina = max(f.stamina, f.stamina_max * 0.7)


def start(fid):
    fish = next(f for f in all_fish() if f["id"] == fid)
    fs.fight = None
    fs.cast.reset()
    fs.bite.fish = fish
    fs.bite.cast_distance = 20
    fs.cast.bx, fs.cast.bz = 0.0, 20.0
    fs.cast.state = CastState.HOOKED
    fs._start_fight()
    fs.card = None
    return fs.fight


PLAN = [("bass", None), ("snakehead", None), ("cherry_salmon", "shake"), ("rockfish", "dive"), ("sea_bass", "surface"),
        ("red_seabream", "reverse"), ("alfonsino", "twist"), ("galaxy_trout", "chain"), ("marsh_eel", "hide"),
        ("stalactite_catfish", "pump"), ("falls_salmon", "thrash"), ("lava_grouper", "bite"), ("glacier_ray", "fake"),
        ("life_trout", "dual"), ("bluefin", None), ("marlin", None), ("ignis", None)]
if ALL:
    NEW = ("shake", "dive", "surface", "reverse", "twist", "chain", "hide", "pump", "thrash", "bite")
    PLAN = []
    for fish in all_fish():
        mine = [a for a in fish.get("actions", {}) if a in NEW]
        PLAN.append((fish["id"], random.choice(mine) if mine else None))
frames, bad = 0, collections.Counter()
max_n, max_len = 0, 0
for fid, pid in PLAN:
    f = start(fid)
    if pid:
        f.brain.force_pattern(pid)
    for i in range(int(secs * 60)):
        tick()
        f = fs.fight
        if f is None or f.phase not in ("fight", "net"):
            break
        if fs.card is not None or fs.help:
            fs.card = None
            continue
        if i % 3:
            continue
        rec.clear()
        g.scenes.current.draw(g.screen.canvas)
        frames += 1
        texts = [s for _, s in rec if s.strip()]
        max_n = max(max_n, len(texts))
        for fn, s in rec:
            max_len = max(max_len, len(s))
        if len(texts) > 1 or any(len(s) > 6 for s in texts):
            bad[tuple(sorted(f"{fn}:{s}" for fn, s in rec))] += 1
print(f"[{mode}] 프레임 {frames}, 동시 글자 최대 {max_n}, 최장 {max_len}글자, 위반 프레임 {sum(bad.values())}")
for k, n in bad.most_common(12):
    print(f"  {n:>5}  {list(k)}")
sys.exit(1 if bad else 0)
