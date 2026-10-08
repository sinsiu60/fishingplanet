"""보스전 무대 확인 (BOSS_ARENA.md 🅰, DESIGN.md 51-2): 실제 낚시 화면을 화면 없이 돌려 스크린샷 · 녹화 · 성능 · 규칙 검사.

  python tools/boss_arena_check.py            검사 + 스크린샷 (보스 13종 × 강도 1 · 3 = 26장 + 위기 1장 + 일반 파이팅 1장)
  python tools/boss_arena_check.py --record   30초 녹화 3개 (여우비 · 일섬 · 환상) → build/boss_arena/*.mp4 (ffmpeg)
  python tools/boss_arena_check.py --perf     그리기 시간: 무대 켬 / 끔 (BA1 기준 +15% 이내인지)
모두 모바일 미리보기 캔버스 (perf_bench 와 같은 길). 결과물은 build/boss_arena/.
"""
import copy
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
if "--mobile" not in sys.argv:
    sys.argv.append("--mobile")
import perf_bench as pb  # noqa: E402  (모바일 미리보기 · 세이브 폴더 · 더미 화면)
import pygame  # noqa: E402

OUT = os.path.join(ROOT, "build", "boss_arena")
os.makedirs(OUT, exist_ok=True)
DT = 1 / 60
LEGENDS = ["golden_carp", "tiger_mandarin", "silver_bass", "marlin", "coelacanth", "dragon_carp", "silva", "prisia",
           "aeris", "ignis", "borealis", "orsiel"]
PHANTOM = "moon_shadow_carp"
FAILS: list[str] = []


def check(ok: bool, msg: str) -> None:
    print(("  ok  " if ok else "  FAIL ") + msg)
    if not ok:
        FAILS.append(msg)


def start(g, fid: str):
    from src.core.config import load_json
    from src.fishing.casting import CastState
    sc = pb.fishing(g, "reservoir", 12.0)
    if fid == PHANTOM or fid.startswith("phantom:"):
        pid = PHANTOM if fid == PHANTOM else fid.split(":", 1)[1]
        fish = copy.deepcopy(next(f for f in load_json("phantom.json")["fish"] if f["id"] == pid))
        fish.setdefault("rarity", "phantom")
        sc._set_spot(fish["spot"])
        sc.bite.fish = fish
        sc.bite.phantom = fish
    else:
        fish = copy.deepcopy(next(f for f in sc.all_fish if f["id"] == fid))
        sc._set_spot(fish["spot"])
        sc.bite.fish = fish
    sc.bite.cast_distance = 20
    sc.cast.state = CastState.HOOKED
    sc._start_fight()
    sc.fight._lose = lambda reason: None   # 녹화 · 스크린샷 동안 놓치지 않게
    return sc


def keep(sc):
    sc.card = None
    sc.help = False
    sc.game.guide.run = None
    f = sc.fight
    if f is not None:
        f.line = float(f.line_max)


def step(g, sc, sec: float, draw: bool = True, frame=None, pre=None):
    """sec 초 동안 60fps: 게임 루프와 같은 순서 (히트스톱 · 슬로우모션 포함)."""
    n = int(round(sec * 60))
    canvas = g.screen.canvas
    for i in range(n):
        keep(sc)
        if pre:
            pre(sc)
        if g.hit_timer > 0:
            g.hit_timer -= DT
        else:
            if g.slow_timer > 0:
                g.slow_timer -= DT
                if g.slow_timer <= 0:
                    g.time_scale = 1.0
            g._acc += DT * g.time_scale
        while g._acc >= g.tick_dt:
            g.scenes.current.update(g.tick_dt)
            g._acc -= g.tick_dt
        g.boss.update(DT)
        g.sfx.update(DT)
        sc._arena_rt = time.perf_counter() - DT   # 무대는 실제 시간으로 흐름 → 가짜 실제 시간
        if draw or (frame and i == n - 1):
            g.scenes.current.draw(canvas)
            if frame:
                frame(canvas)


def to_level3(g, sc):
    f = sc.fight
    if f.fish.get("rarity") == "phantom":
        sc.p2_on = True   # 2페이즈 컷신 뒤 (컷신은 녹화에서 실제로 돎)
        sc.p2_aura = 1.0
        f.p2_bar = True
        return
    at = f.fish.get("phase_at", f.brain.legend_cfg["phase_at"])
    for _ in range(len(f.brain.phases) - 1):
        f.stamina = f.stamina_max * (at[min(f.brain.phase, len(at) - 1)] - 0.03)
        step(g, sc, 2.6, draw=False)


def shot(g, name):
    pygame.image.save(g.screen.canvas, os.path.join(OUT, name + ".png"))


def shots(g):
    from src.render import boss_arena
    print("스크린샷 (강도 1 · 3):")
    for fid in LEGENDS + [PHANTOM]:
        sc = start(g, fid)
        ar = sc.arena
        check(ar.active, f"{fid}: 무대 켜짐")
        step(g, sc, 0.6, draw=True)
        check(ar.card_on and ar.bar_px() == 12, f"{fid}: 0.6초 이름 카드 · 띠 12px")
        step(g, sc, 1.9)
        check(not ar.card_on and ar.level_int() == 1, f"{fid}: 2.5초 카드 끝 · 강도 1")
        shot(g, f"{fid}_1")
        to_level3(g, sc)
        step(g, sc, 1.2)
        check(ar.level_int() == 3, f"{fid}: 강도 3 (레벨 {ar.level:.2f})")
        if fid == "borealis":
            check(not any(p[0] == "aurora" for p in ar.parts), "보레알리스: 오로라 없음")
        shot(g, f"{fid}_3")
        sc._end_fight()
        check(not ar.active, f"{fid}: 파이팅 끝 → 무대 꺼짐")
    # 위기
    sc = start(g, "golden_carp")
    step(g, sc, 2.5, draw=False)

    def crisis(s):
        s.fight.line = s.fight.line_max * 0.25
    step(g, sc, 1.5, pre=crisis)
    check(sc.arena.crisis_k > 0.5, "위기 덧씌움")
    shot(g, "crisis_golden_carp")
    sc._end_fight()
    # 화면 효과 줄이기 (BA4): 색 · 비네트 · 띠 · 이름 카드만
    g.settings.set("reduce_fx", True)
    sc = start(g, "golden_carp")
    step(g, sc, 2.5)
    to_level3(g, sc)
    step(g, sc, 1.2)
    check(not sc.arena.parts and sc.arena.shake_offset() == (0, 0), "줄이기 강도 3: 파티클 · 흔들림 없음")
    shot(g, "reduce_golden_carp_3")
    sc._end_fight()
    g.settings.set("reduce_fx", False)
    # 일반 파이팅: 무대 없음
    sc = start(g, "lenok")
    step(g, sc, 1.0)
    check(not sc.arena.active and sc.screen_fx.extra_vignettes == [], "일반 파이팅: 무대 없음 (그대로)")
    check(sc.arena.palette({"sky_top": (1, 2, 3)}) == {"sky_top": (1, 2, 3)}, "일반 파이팅: 팔레트 그대로")
    shot(g, "normal_lenok")
    sc._end_fight()
    # 보라 = 환상 전용
    for fid in LEGENDS:
        c = boss_arena.color_of(boss_arena.entry({"id": fid, "rarity": "legend"}))
        check(not (c[2] > c[1] + 40 and c[0] > c[1] + 20), f"{fid}: 무대 색이 보라가 아님 {c}")


def rules(g):
    """규칙: 보호 칸 · 화면 효과 줄이기 · 번쩍임 3초 · 히트스톱 · 예고 중 펄스 끔."""
    print("규칙:")
    sc = start(g, "marlin")
    ar = sc.arena
    step(g, sc, 2.5, draw=False)
    to_level3(g, sc)
    step(g, sc, 1.0)
    # 보호 칸 안 픽셀이 무대 그리기(draw_fx)로 안 바뀌는지
    canvas = g.screen.canvas
    sc.draw(canvas)
    holes = sc._arena_holes()
    before = canvas.copy()
    ar.rgb_t, ar.flash_t, ar.bright_t = 0.08, 0.02, 0.15
    ar.rings.append([canvas.get_width() / 2, canvas.get_height() / 2, 0.1])
    ar.last_flash = -99
    ar.draw_fx(canvas, holes)
    same = all(pygame.image.tobytes(canvas.subsurface(h.clip(canvas.get_rect())), "RGB") ==
               pygame.image.tobytes(before.subsurface(h.clip(canvas.get_rect())), "RGB") for h in holes if h.clip(canvas.get_rect()).w)
    check(same, f"보호 칸 {len(holes)}개 안은 무대 효과가 픽셀을 바꾸지 않음 (색 갈라짐 · 번쩍임 · 박자 · 충격파)")
    changed = pygame.image.tobytes(canvas, "RGB") != pygame.image.tobytes(before, "RGB")
    check(changed, "보호 칸 밖은 바뀜")
    # 번쩍임 3초에 1번
    ar.last_flash = -99
    n0 = ar.flashes
    for _ in range(5):
        ar.impact("jump_land", (100, 150), 1)
    check(ar.flashes - n0 == 1, "번쩍임: 3초 안 여러 번 → 1번")
    # 히트스톱: 슬로우모션을 덮어쓰지 않음
    g.slowmo(0.6, 0.35)
    g.hitstop(0.06)
    t0 = sc.fight.t if hasattr(sc.fight, "t") else None
    acc0 = g._acc
    step(g, sc, 0.05, draw=False)
    check(g.time_scale == 0.35 and g.slow_timer > 0.5, "히트스톱 뒤 슬로우모션 이어감")
    step(g, sc, 0.8)
    # 예고 중 박자 펄스 끔
    ar.bright_t = 0
    ar.beat("bar", telegraph=True)
    check(ar.bright_t == 0, "예고 중 박자 펄스 없음")
    ar.beat("bar", telegraph=False)
    check(ar.bright_t > 0, "강도 3 마디 첫 박 → 밝기 펄스")
    # 화면 효과 줄이기
    sc.settings.set("reduce_fx", True)
    step(g, sc, 0.3)
    r = ar.impact("action:rush", (100, 150), 1)
    check(r["hitstop"] == 0 and ar.shake_offset() == (0, 0) and not ar.parts, "줄이기: 히트스톱 · 흔들림 · 파티클 없음")
    check(ar.vignettes() and ar.palette({"sky_top": (100, 120, 160)})["sky_top"] != (100, 120, 160), "줄이기: 색 · 비네트는 남음")
    sc.settings.set("reduce_fx", False)
    sc._end_fight()
    # 박자 이벤트 (SUNO 곡이 실제로 돌면)
    sc = start(g, "golden_carp")
    got = []

    def grab(s):
        got.extend(s.game.boss.suno.beat_events)
        s.game.boss.suno.beat_events.clear()
    step(g, sc, 12.0, draw=False, pre=grab)
    if g.boss.suno.active:
        check(got.count("bar") >= 3 and got.count("beat") >= got.count("bar") * 3,
              f"SUNO 박자 이벤트: 마디 {got.count('bar')} · 박 {got.count('beat')} (12초)")
    else:
        print("  -- SUNO 곡이 돌지 않음 (오디오 없음) — 박자 이벤트 검사 건너뜀")
    sc._end_fight()


def record(g):
    print("녹화 30초 × 3:")
    for fid, name in (("golden_carp", "yeoubi"), ("marlin", "ilseom"), (PHANTOM, "phantom")):
        folder = os.path.join(OUT, "rec_" + name)
        os.makedirs(folder, exist_ok=True)
        for fn in os.listdir(folder):
            os.remove(os.path.join(folder, fn))
        sc = start(g, fid)
        k = [0]

        def frame(c):
            if k[0] % 2 == 0:   # 30fps
                pygame.image.save(c, os.path.join(folder, f"{k[0] // 2:05d}.png"))
            k[0] += 1

        def pre(s, _t=[0.0]):
            _t[0] += DT
            f = s.fight
            t = _t[0]
            phases = len(f.brain.phases or [])
            at = f.fish.get("phase_at", f.brain.legend_cfg["phase_at"])
            if phases and f.brain.phase < phases - 1 and t > 9.0 * (f.brain.phase + 1):
                f.stamina = min(f.stamina, f.stamina_max * (at[min(f.brain.phase, len(at) - 1)] - 0.03))   # 9초 · 18초에 다음 페이즈
            if 24.0 < t < 28.0:
                f.line = f.line_max * 0.25   # 위기
        step(g, sc, 30.0, frame=frame, pre=pre)
        sc._end_fight()
        mp4 = os.path.join(OUT, f"{name}.mp4")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "30", "-i", os.path.join(folder, "%05d.png"),
                        "-vf", "scale=1200:-2:flags=neighbor", "-pix_fmt", "yuv420p", mp4], check=False)
        print(f"  {mp4} ({k[0] // 2} 프레임)")


def perf(g):
    """같은 장면을 무대 켬 / 끔으로 3번씩 번갈아 (컨테이너 잡음 — 가장 낮은 평균), 큰 행동 임팩트 2초에 1번."""
    from src.core import fxq
    print("그리기 시간 (모바일 캔버스, 300프레임 × 3회, 화질 높음, 임팩트 2초에 1번):")
    rows = []
    for fid in ("golden_carp", "marlin", "dragon_carp", "orsiel", PHANTOM):
        res = {True: [], False: []}
        for rep in range(3):
            for on in (True, False):
                fxq.set_level(2)
                sc = start(g, fid)
                if not on:
                    sc.arena.stop()
                step(g, sc, 2.5)   # 그리기까지 (무대는 그리기마다 실제 시간으로 흐름 — 등장이 끝난 뒤 잼)
                to_level3(g, sc)
                step(g, sc, 1.5)
                ts = []
                for i in range(300):
                    keep(sc)
                    g.scenes.current.update(DT)
                    g.boss.update(DT)
                    if on and i % 120 == 0:
                        sc._arena_event("action:rush")
                    sc._arena_rt = time.perf_counter() - DT
                    t0 = time.perf_counter()
                    g.scenes.current.draw(g.screen.canvas)
                    ts.append((time.perf_counter() - t0) * 1000)
                ts.sort()
                res[on].append((sum(ts) / len(ts), ts[int(len(ts) * 0.95)]))
                sc._end_fight()
        a, b = min(res[True]), min(res[False])
        d = (a[0] / b[0] - 1) * 100
        rows.append((fid, a, b, d))
        print(f"  {fid:16} 무대 {a[0]:5.2f} (p95 {a[1]:5.2f}) · 끔 {b[0]:5.2f} (p95 {b[1]:5.2f}) ms · {d:+.0f}%")
    return rows


def main():
    g = pb.make_game()
    if "--record" in sys.argv:
        record(g)
    elif "--perf" in sys.argv:
        perf(g)
    else:
        shots(g)
        rules(g)
        print(f"\n실패 {len(FAILS)}개" if FAILS else "\n모두 통과")
        sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
