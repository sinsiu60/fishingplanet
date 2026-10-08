"""성능 측정 (DESIGN.md 44): 실제 게임 장면을 화면 없이 돌려 장면별 프레임 시간(로직 · 그리기 · 화면 출력)과 느린 함수를 잰다.

폰과 같은 길로: --mobile 이면 모바일 캔버스(540x270)·모바일 설정(입자 상한 등)으로, 출력은 기기 해상도(2400x1080) 확대까지 잰다.
PC 숫자는 폰보다 5~10배 빠르므로 '비율'과 '전후 비교'로 본다.

사용: python tools/perf_bench.py [--mobile] [--prof] [--only 이름,...] [--frames 180] [--json 결과.json]
      --prof  장면마다 그리기 cProfile 상위 함수 (자기 시간 기준)
"""
import cProfile
import json
import os
import pstats
import random
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
SAVE = os.path.join(ROOT, "build", "perf_save")
os.makedirs(SAVE, exist_ok=True)
os.environ["FISHING_SAVE_DIR"] = SAVE
MOBILE = "--mobile" in sys.argv
if MOBILE and "--mobile-preview" not in sys.argv:
    sys.argv.append("--mobile-preview")   # src/platform/detect.PREVIEW → 모바일 캔버스 · 설정

import pygame  # noqa: E402

FRAMES = int(sys.argv[sys.argv.index("--frames") + 1]) if "--frames" in sys.argv else 180
ONLY = sys.argv[sys.argv.index("--only") + 1].split(",") if "--only" in sys.argv else None
PROF = "--prof" in sys.argv


def make_game():
    random.seed(7)
    from src.core.game import Game
    from src.save.save_game import SaveGame
    g = Game(start_scene=lambda game: __import__("src.scene.base", fromlist=["Scene"]).Scene(game))
    g._acc, g._frames = 0.0, 0
    g.save = SaveGame(1)
    d = g.save.data
    d["money"] = 10 ** 7
    d["unlocked_spots"] = sorted({s["id"] for s in __import__("src.core.config", fromlist=["load_json"]).load_json("spots.json")["spots"]})
    try:
        g.guide.enabled = lambda: False
        g.guide.frozen = lambda: False
    except Exception:
        pass
    return g


def fishing(g, spot, hour=12.0, weather="clear"):
    from src.scene.fishing_scene import FishingScene
    from src.ui import tutorial as tut
    g.scenes.stack.clear()
    sc = FishingScene(g)
    g.scenes.push(sc)
    for k in list(tut.CARDS) + list(tut.GUIDES):
        sc.tutorial.seen.add(k)
    sc._set_spot(spot)
    try:
        g.save.data["hour"] = hour
        sc.clock.hour = hour
    except Exception:
        pass
    try:
        sc.weather.set(weather)
    except Exception:
        try:
            sc.weather.current = weather
        except Exception:
            pass
    return sc


def training(sc, entry):
    from src.scene.training import TrainingTank
    sc.training = TrainingTank(sc)
    sc.training.entries = [entry]
    sc.training.index = 0
    sc.training.start()


def legend_fight(sc, fid):
    import copy
    from src.fishing.casting import CastState
    fish = next(f for f in sc.all_fish if f["id"] == fid)
    sc._set_spot(fish["spot"])
    sc.bite.fish = copy.deepcopy(fish)
    sc.bite.cast_distance = 20
    sc.cast.state = CastState.HOOKED
    sc._start_fight()


def scenarios():
    """(이름, 준비 함수(g) → 매 프레임 전에 부를 함수 또는 None)."""
    out = []

    def keep(sc):
        g = sc.game
        def pre():
            sc.card = None
            sc.help = False
            g.guide.abort()   # 가이드 튜토리얼 화면은 빼고 잼 (abort = 패턴 튜토리얼이 비운 물고기 행동 목록도 되돌림)
        return pre

    for spot, hour, w in (("reservoir", 12.0, "clear"), ("reservoir", 21.0, "rain"), ("valley", 2.0, "storm"),
                          ("offshore", 17.5, "clear"), ("deep", 12.0, "clear"), ("world_tree", 20.0, "clear"),
                          ("crystal_cave", 12.0, "clear"), ("ice_sea", 22.0, "snow")):
        out.append((f"낚시대기:{spot}:{int(hour)}h:{w}", lambda g, s=spot, h=hour, ww=w: keep(fishing(g, s, h, ww))))
    for ent in (("pat", "rush"), ("pat", "jump"), ("pat", "turn")):
        def prep(g, e=ent):
            sc = fishing(g, "reservoir", 12.0)
            training(sc, e)
            return keep(sc)
        out.append((f"훈련파이팅:{ent[1]}", prep))
    for fid in ("golden_carp", "dragon_carp", "orsiel"):
        def prep(g, f=fid):
            sc = fishing(g, "reservoir", 12.0)
            legend_fight(sc, f)
            return keep(sc)
        out.append((f"전설파이팅:{fid}", prep))

    def menu(cls_path, *a):
        def prep(g):
            mod, cls = cls_path.rsplit(".", 1)
            C = getattr(__import__(mod, fromlist=[cls]), cls)
            fs = fishing(g, "reservoir", 12.0)
            try:
                scene = C(g)
            except TypeError:
                scene = C(g, fs)
            g.scenes.push(scene)
            return lambda: setattr(g.guide, "run", None)
        return prep
    out += [("타이틀", menu("src.scene.menu.TitleScene")), ("지도", menu("src.scene.map_scene.MapScene")),
            ("상점", menu("src.scene.shop.ShopScene")), ("도감", menu("src.scene.dex.DexScene")),
            ("마을", menu("src.scene.village.VillageScene"))]
    return out


def present_cost(g, n=60) -> float:
    """폰 출력: 캔버스 → 기기 해상도(2400x1080) 확대 1회 (ms)."""
    src = g.screen.canvas
    dst = pygame.Surface((2400, 1080), 0, 32)
    w, h = src.get_size()
    sc = min(2400 / w, 1080 / h)
    size = (int(w * sc), int(h * sc))
    t = time.perf_counter()
    for _ in range(n):
        pygame.transform.scale(src, size, dst.subsurface(pygame.Rect(0, 0, *size)))
    return (time.perf_counter() - t) / n * 1000


def run_one(g, name, prep):
    try:
        pre = prep(g)
    except Exception as e:
        return {"name": name, "error": f"{type(e).__name__}: {e}"}
    scene = g.scenes.current
    canvas = g.screen.canvas
    for _ in range(30):   # 데우기 (글꼴 · 캐시)
        if pre:
            pre()
        g.scenes.current.update(1 / 60)
        g.scenes.current.draw(canvas)
    ups, draws = [], []
    prof = cProfile.Profile() if PROF else None
    for _ in range(FRAMES):
        if pre:
            pre()
        t0 = time.perf_counter()
        g.scenes.current.update(1 / 60)
        g.sfx.update(1 / 60)
        g.adaptive.update(1 / 60)
        g.boss.update(1 / 60)
        t1 = time.perf_counter()
        if prof:
            prof.enable()
        g.scenes.current.draw(canvas)
        g.guide.draw(canvas)
        if prof:
            prof.disable()
        t2 = time.perf_counter()
        ups.append((t1 - t0) * 1000)
        draws.append((t2 - t1) * 1000)
    ups.sort()
    draws.sort()
    r = {"name": name, "scene": type(scene).__name__, "update_ms": round(sum(ups) / len(ups), 2),
         "draw_ms": round(sum(draws) / len(draws), 2), "draw_p95": round(draws[int(len(draws) * 0.95)], 2),
         "update_p95": round(ups[int(len(ups) * 0.95)], 2)}
    if prof:
        st = pstats.Stats(prof).stats
        rows = sorted(st.items(), key=lambda kv: -kv[1][2])[:14]
        r["top"] = [f"{v[2] / FRAMES * 1000:6.2f}ms {v[1] // FRAMES:5d}회 {os.path.relpath(k[0], ROOT) if k[0].startswith(ROOT) else k[0]}:{k[1]} {k[2]}"
                    for k, v in rows]
        rows = sorted(st.items(), key=lambda kv: -kv[1][3])[:14]
        r["cum"] = [f"{v[3] / FRAMES * 1000:6.2f}ms {os.path.relpath(k[0], ROOT) if k[0].startswith(ROOT) else k[0]}:{k[1]} {k[2]}"
                    for k, v in rows if k[0].startswith(ROOT)]
    return r


def main():
    g = make_game()
    print(f"pygame {pygame.version.ver} · 캔버스 {g.screen.canvas.get_size()} · {'모바일' if MOBILE else 'PC'} · 프레임 {FRAMES}")
    print(f"출력 확대(2400x1080) {present_cost(g):.2f}ms")
    res = []
    for name, prep in scenarios():
        if ONLY and not any(o in name for o in ONLY):
            continue
        r = run_one(g, name, prep)
        res.append(r)
        if "error" in r:
            print(f"{name:34} 오류 {r['error']}")
            continue
        print(f"{name:34} 로직 {r['update_ms']:6.2f} (p95 {r['update_p95']:6.2f}) · 그리기 {r['draw_ms']:6.2f} (p95 {r['draw_p95']:6.2f}) ms")
        for ln in r.get("top", []):
            print("      ", ln)
        if r.get("cum"):
            print("      누적:")
            for ln in r["cum"][:8]:
                print("      ", ln)
    if "--json" in sys.argv:
        json.dump(res, open(sys.argv[sys.argv.index("--json") + 1], "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
