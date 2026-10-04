"""PC 회귀 검사용 결정적 리플레이 (DESIGN.md 26-9).

고정 시계(60fps)·고정 난수·고정 시각·스크립트 마우스/키보드로 타이틀 → 낚시 3번 → 상점·도감·지도·상자·일시정지·설정
→ 타이틀 → 불러오기 → 새 게임까지 돌리고, 매 프레임 화면 해시를 JSON으로 남긴다.
코드를 바꾸기 전·후 두 체크아웃에서 돌려 결과 파일이 같으면 PC 동작(입력·화면)이 그대로라는 뜻.

사용: PYTHONHASHSEED=0 python tools/pc_replay.py <저장소 경로> <결과.json> <sharmion|eldra>
  (git worktree add ../base HEAD 로 기준 체크아웃을 만든 뒤 양쪽에서 실행 → JSON 비교)
"""
import hashlib
import itertools
import json
import os
import random
import shutil
import tempfile
import sys

repo, out, scen = sys.argv[1], sys.argv[2], sys.argv[3]
OUTDIR = os.getcwd()
sys.path.insert(0, repo)
os.chdir(repo)
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
SAVE = os.path.join(tempfile.gettempdir(), f"fp_replay_{scen}_{abs(hash(repo)) % 1000}")
shutil.rmtree(SAVE, ignore_errors=True)
os.makedirs(SAVE)
os.environ["FISHING_SAVE_DIR"] = SAVE

_seed = itertools.count(1000)
_R = random.Random


class SeededRandom(_R):
    def __init__(self, x=None):
        super().__init__(next(_seed) if x is None else x)


random.Random = SeededRandom
import time
time.time = lambda: 1_790_000_000.0
random.seed(7)

import pygame  # noqa: E402


class FakeClock:
    def tick(self, fps=0):
        return 1000 / 60

    def get_fps(self):
        return 60.0


pygame.time.Clock = FakeClock

# 스크립트 입력 상태
STATE = {"pos": (240, 150), "buttons": [False, False, False], "events": []}
SCALE = 2
pygame.mouse.get_pos = lambda: scr(STATE["pos"])
pygame.mouse.get_pressed = lambda num_buttons=3: tuple(STATE["buttons"])
_real_get = pygame.event.get


def fake_get(*a, **k):
    _real_get()
    ev, STATE["events"] = STATE["events"], []
    return ev


pygame.event.get = fake_get

from src.save.save_game import SaveGame  # noqa: E402
from src.save.settings import Settings  # noqa: E402
from src.ui import tutorial as tut  # noqa: E402

# 세이브 준비
sg = SaveGame(1)
sg.data["money"] = 50000
for k in ("rod", "reel", "line", "net"):
    pass
if scen == "eldra":
    sg.unlock_continent("eldrasion")
    sg.data["unlocked_spots"] += ["valley", "breakwater"]
    sg.data["money"] = 400000
    sg.data["scales"] = 6
    sg.data["chests"] = {"common": 2, "rare": 1}
    sg.data["spot"] = "marsh"
else:
    sg.data["chests"] = {"common": 1}
# 스토리(DESIGN.md 36): 프롤로그는 이미 본 세이브로 (새 세이브면 프롤로그 컷신부터 시작해 아래 스크립트와 어긋난다)
from src.story import story  # noqa: E402
_st = story.state(sg)
_st["seen_scenes"] = ["P-01", "P-02", "P-03", "P-04", "P-05"]
_st["player_name"], _st["chapter"] = "하늘", 1
sg.save()
st = Settings()
st.data["tutorial_seen"] = sorted(set(tut.CARDS) | set(tut.GUIDES))
st.data["scale"] = SCALE
st.save()

from src.core.game import Game  # noqa: E402

game = Game()
canvas = game.screen.canvas


def scr(p):
    k = game.screen.scale
    return (p[0] * k + k // 2, p[1] * k + k // 2)


def mdown(p, b=1):
    STATE["pos"] = p
    STATE["buttons"][b - 1] = True
    STATE["events"].append(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=scr(p), button=b))


def mup(p, b=1):
    STATE["pos"] = p
    STATE["buttons"][b - 1] = False
    STATE["events"].append(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=scr(p), button=b))


def click(p, b=1):
    mdown(p, b)
    mup(p, b)


def key(k):
    STATE["events"].append(pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode="", scancode=0))
    STATE["events"].append(pygame.event.Event(pygame.KEYUP, key=k, mod=0, unicode="", scancode=0))


def wheel(y):
    STATE["events"].append(pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=y, flipped=False, precise_x=0.0,
                                              precise_y=float(y), touch=False))
    b = 4 if y > 0 else 5
    STATE["events"].append(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=scr(STATE["pos"]), button=b))
    STATE["events"].append(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=scr(STATE["pos"]), button=b))


def move(p):
    STATE["pos"] = p
    STATE["events"].append(pygame.event.Event(pygame.MOUSEMOTION, pos=scr(p), rel=(0, 0), buttons=(0, 0, 0)))


trace = []


def step(n=1):
    for _ in range(n):
        yield


def scene():
    return game.scenes.current


def btn(label_part):
    for b in getattr(scene(), "buttons", []):
        if label_part in b.label:
            return b.rect.center
    raise RuntimeError(f"no button {label_part} in {type(scene()).__name__}")


def fishing():
    from src.scene.fishing_scene import FishingScene
    for s in game.scenes.stack:
        if isinstance(s, FishingScene):
            return s


def log(tag):
    print(tag, [type(x).__name__ for x in game.scenes.stack], flush=True)


def wait_until(cond, limit):
    for _ in range(limit):
        if cond():
            return True
        yield
    return False


def scenario():
    yield from step(30)
    click(btn("이어하기"))
    yield from step(60)
    fs = fishing()
    assert fs is not None
    from src.fishing.casting import CastState  # noqa: E402
    from src.fishing.bite import BiteState  # noqa: E402

    key(pygame.K_h); yield from step(20); click((200, 100)); yield from step(10)
    move((5, 150)); yield from step(50); move((475, 150)); yield from step(50); move((240, 150)); yield from step(20)
    key(pygame.K_t); yield from step(5); key(pygame.K_t); yield from step(5)
    key(pygame.K_F1); yield from step(10); key(pygame.K_F1); yield from step(5)
    key(pygame.K_F2); yield from step(10); key(pygame.K_F2); yield from step(5)


    def one_fish(tag):
        fs = fishing()
        # 캐스팅
        move((300, 140)); yield from step(5)
        mdown((300, 140)); yield from step(45); mup((300, 140)); yield from step(5)
        if not (yield from wait_until(lambda: fs.cast.state == CastState.LANDED, 400)):
            return
        # 입질 기다리기 (최대 ~40초)
        t = 0
        while t < 2400:
            if fs.bite.state == BiteState.BITE:
                click(STATE["pos"]); yield from step(3)
                break
            if fs.bite.state in (BiteState.MISSED, BiteState.SCARED):
                click(STATE["pos"], 3); yield from step(30)
                return
            yield from step(); t += 1
        if fs.fight is None:
            click(STATE["pos"], 3); yield from step(30)
            return
        f = fs.fight
        print("  start", f.fish["id"], f.phase, fs.card, flush=True)
        t = 0
        x = 240
        while fs.fight is not None and t < 60 * 120:
            if t % 600 == 0:
                print("  t", t, f.phase, round(f.tension), round(f.stamina), round(f.line), fs.card and fs.card.get("key"), flush=True)
            if f.phase == "fight":
                want = f.tension < 62
                if want and not STATE["buttons"][0]:
                    mdown((x, 150))
                elif not want and STATE["buttons"][0]:
                    mup((x, 150))
                if t % 97 == 0:
                    click((x, 150), 3)
                if t % 211 == 0:
                    key(pygame.K_q)
                if t % 223 == 0:
                    key(pygame.K_e)
                if t % 301 == 0:
                    wheel(1)
                if t % 307 == 0:
                    wheel(-1)
                if t % 150 == 0:
                    x = 120 if x > 240 else 360
                    move((x, 150))
                if t % 400 == 200:
                    move((x - 60, 150)); yield from step(); t += 1; move((x + 30, 150))
                if t == 500:
                    key(pygame.K_1)
            elif f.phase == "net":
                if STATE["buttons"][0]:
                    mup((x, 150))
                cyc = f.net_period + f.net_pause
                if f.net_t % cyc >= f.net_period + 0.03:
                    click((240, 150))
            else:
                if STATE["buttons"][0]:
                    mup((x, 150))
                if t % 20 == 0:
                    click((240, 150))
            yield from step(); t += 1
        yield from step(40)
        print("fish", tag, fs.cast.state, fs.bite.state, fs.fight and fs.fight.phase, fs.landing, fs.save.data["stats"], flush=True)


    for i in range(3):
        yield from one_fish(i)

    # 메뉴들
    fs = fishing()
    key(pygame.K_b); yield from step(20); log('key(pygame.K_b')
    from src.scene.shop import ShopScene, TABS as SHOP_TABS  # noqa: E402
    sh = scene()
    if isinstance(sh, ShopScene):
        for i, r in enumerate(sh.tabs.rects):
            click(r.center); yield from step(6)
            click((100, 70)); yield from step(4); click((100, 90)); yield from step(4)
            wheel(-1); yield from step(3); wheel(1); yield from step(3)
            click(sh.action_btn.rect.center); yield from step(6)
            click(sh.action_btn.rect.center); yield from step(6)
        click(sh.tabs.rects[0].center); yield from step(4)
        key(pygame.K_ESCAPE); yield from step(10)
    key(pygame.K_TAB); yield from step(20); log('key(pygame.K_T')
    dx = scene()
    if hasattr(dx, "tabs"):
        for r in dx.tabs.rects:
            click(r.center); yield from step(5); click((100, 100)); yield from step(5)
        if hasattr(dx, "cont_btn"):
            click(dx.cont_btn.rect.center); yield from step(5)
    key(pygame.K_TAB); yield from step(10)
    key(pygame.K_m); yield from step(20); log('key(pygame.K_m')
    mp = scene()
    for p in ((120, 120), (240, 140), (300, 90), (380, 160)):
        click(p); yield from step(5)
    key(pygame.K_ESCAPE); yield from step(10)
    key(pygame.K_c); yield from step(20); log('key(pygame.K_c')
    ch = scene()
    if hasattr(ch, "tabs"):
        for r in ch.tabs.rects:
            click(r.center); yield from step(5); click((100, 80)); yield from step(5); wheel(-1); yield from step(3)
        click(ch.tabs.rects[0].center); yield from step(5)
        click((100, 70)); yield from step(5)
        for _ in range(3):
            btns = [b for b in getattr(ch, "buttons", []) if b.enabled]
            if hasattr(ch, "open_btn"):
                click(ch.open_btn.rect.center)
            yield from step(30)
            key(pygame.K_SPACE); yield from step(20); click((240, 135)); yield from step(40)
    key(pygame.K_c); yield from step(10); log('key(pygame.K_c')
    key(pygame.K_ESCAPE); yield from step(15); log('key(pygame.K_E')
    click(btn("설정")); yield from step(10)
    for b in [b for b in getattr(scene(), "buttons", [])[:-1] if b.label != "열기"]:  # 세이브 옮기기는 따로
        click(b.rect.center); yield from step(4)
        click(b.rect.center); yield from step(4)
    key(pygame.K_ESCAPE); yield from step(10)
    key(pygame.K_ESCAPE); yield from step(10)
    yield from one_fish(9)
    for _ in range(12):
        log("to title")
        n = type(scene()).__name__
        if n == "TitleScene":
            break
        fz = fishing()
        if n == "PauseScene":
            click(btn("타이틀"))
        elif n == "FishingScene" and (fz.landing is not None or fz.card is not None or fz.help):
            print("  busy", fz.landing, fz.card and fz.card.get("key"), fz.help, fz.fight and fz.fight.phase, flush=True)
            click((240, 135))
        else:
            key(pygame.K_ESCAPE)
        yield from step(20)
    yield from step(20)
    click(btn("불러오기")); yield from step(15)
    key(pygame.K_ESCAPE); yield from step(10)
    click(btn("새 게임")); yield from step(15)
    click((240, 80)); yield from step(10); click((240, 80)); yield from step(60)
    yield from step(30)



gen = scenario()
frame = [0]
done = [False]


def fake_get(*a, **k):
    _real_get()
    if frame[0] > 0:
        name = type(game.scenes.current).__name__ if game.scenes.current else "-"
        h = hashlib.md5(pygame.image.tobytes(canvas, "RGB")).hexdigest()[:10]
        trace.append([frame[0], name, h])
    frame[0] += 1
    try:
        next(gen)
    except StopIteration:
        game.running = False
    ev, STATE["events"] = STATE["events"], []
    return ev


pygame.event.get = fake_get
game.run()
with open(os.path.join(OUTDIR, out), "w") as fp:
    json.dump(trace, fp)
print("frames", len(trace), "last scene", trace[-1][1], "fights caught", 0)
