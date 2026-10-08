"""백 노인의 시험 · 공지 · 튜토리얼 순서 점검 (BAEK_EXAM 🅲, DESIGN.md 49-6). 화면 없이 실제 장면 코드로 세이브 5종을 처음부터:

  new     새 세이브 (판매 · 구매 튜토리얼 TG-07 까지 끝남)  → 상점 TG-21 → 백 노인 TG-22 → 시험 화면 TG-23 → 낚시터 TG-24 → 포획 카드 TG-25
  t3      장비 T3 옛 세이브   → 변경 공지 4쪽 → 백 노인 TG-22 → TG-23 → 포획 카드 TG-25 (TG-21 없음)
  t5      장비 T5 옛 세이브   → 변경 공지 4쪽 (T5) → TG-22 …
  t8      장비 T8 옛 세이브   → 변경 공지 3쪽 (T8 판) · 목패 · 칭호 → 시험 튜토리얼 없음 → 포획 카드 TG-25
  story   T3 옛 세이브인데 이야기 튜토리얼 진행 중 (TG-06 판매 전) → 공지 미룸 → TG-07 끝난 뒤 마을에서 공지
  python tools/exam_tut_check.py [new t3 t5 t8 story]   (스크린샷 build/exam_tut/<세이브>_<번호>.png, 결과 표 출력)
"""
import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
OUT = os.path.join(ROOT, "build", "exam_tut")
os.environ["FISHING_SAVE_DIR"] = os.path.join(OUT, "save")

import pygame  # noqa: E402

DT = 1 / 60
FAIL: list[str] = []
STORY_TG = ["TG-01", "TG-02", "TG-03", "TG-04", "TG-05", "TG-06", "TG-07"]


class Run:
    def __init__(self, name: str):
        from src.core.game import Game
        self.name = name
        self.g = Game()
        self.log: list[str] = []
        self.n = 0
        self.last = None

    # ── 기록 ──
    def shot(self, what: str) -> None:
        self.n += 1
        c = self.g.screen.canvas
        top = self.g.scenes.current
        if top is not None:
            top.draw(c)
        self.g.guide.draw(c)
        pygame.image.save(c, os.path.join(OUT, f"{self.name}_{self.n:02d}.png"))
        self.log.append(f"{self.n:02d} {what}")

    def note(self, what: str) -> None:
        self.log.append(f"   · {what}")

    # ── 진행 ──
    def frame(self) -> None:
        g = self.g
        g.guide.update(DT)
        top = g.scenes.current
        if top is not None:
            if type(top).__name__ == "FishingScene":
                top.card = None
            top.update(DT)
        c = g.screen.canvas
        if top is not None:
            top.draw(c)   # 강조 대상 자리 (그리기에서 표시)
        g.guide.draw(c)
        r = g.guide.run
        key = (r["id"], r["i"]) if r else None
        if key != self.last and r is not None:
            s = g.guide.step
            self.shot(f"{r['id']} {r['i'] + 1}단계 · {g.guide.who()} · {g.guide.text_of(s)}")
        self.last = key

    def pump(self, sec: float = 1.0, tap: bool = True) -> None:
        for _ in range(int(sec / DT)):
            self.frame()
            r = self.g.guide.run
            if tap and r is not None and r["t"] > 0.4:
                s = self.g.guide.step
                if s and s["until"] == "tap":
                    r["tapped"] = True

    def scene(self) -> str:
        return type(self.g.scenes.current).__name__ if self.g.scenes.current else "-"


def make_save(slot: int, top: int, legacy: bool, done: list[str], eldra: bool = False) -> None:
    from src.save.save_game import GEAR_KINDS, SaveGame, all_fish, equipment, new_data
    from src.story import story
    d = new_data()
    eq = equipment()
    for k in GEAR_KINDS:
        d["owned"][k] = [x["id"] for x in eq[k] if x["tier"] <= top]
        d["gear"][k] = d["owned"][k][-1]
    if legacy:
        d.pop("exam")
    if eldra:
        d["unlocked_continents"] = ["sharmion", "eldrasion"]
    d["unlocked_spots"] = ["reservoir", "valley"]
    d["money"] = 5000
    d["tutorial"] = {"done": list(done), "active": None, "enabled": True, "replay": []}
    sg = SaveGame(slot, d)
    st = story.state(sg)
    st["player_name"] = "하늘"
    st["seen_scenes"] += ["P-01", "P-02", "P-03", "P-04", "P-05"]
    f = next(x for x in all_fish() if x["id"] == "crucian")
    sg.record_catch({"fish": f, "size": 20.0, "rank": "A", "price": 10, "perfects": 0})
    sg.data["keepnet"].clear()
    with open(os.path.join(os.environ["FISHING_SAVE_DIR"], f"slot{slot}.json"), "w", encoding="utf-8") as fp:
        json.dump(sg.data, fp, ensure_ascii=False)


def check(cond: bool, what: str, run: Run) -> None:
    run.log.append(("   ok   " if cond else "   FAIL ") + what)
    if not cond:
        FAIL.append(f"{run.name}: {what}")


def start(run: Run, slot: int):
    from src.save.save_game import SaveGame
    from src.scene.menu import start_game
    s = SaveGame.load(slot)
    start_game(run.g, s)
    run.pump(0.6)
    return run.g.scenes.stack[0]   # FishingScene


def read_notice(run: Run) -> list[str]:
    pages = []
    while run.scene() == "ExamNoticeScene":
        sc = run.g.scenes.current
        run.pump(0.5, tap=False)
        run.shot(f"변경 공지 {sc.page + 1}/{len(sc.pages)} · {sc.pages[sc.page][0]} · {sc.pages[sc.page][1]}")
        pages.append(sc.keys[sc.page])
        sc.t = 1.0
        sc._next()
    return pages


def visit_shop(run: Run, fs) -> None:
    from src.scene.interior import InteriorScene
    it = InteriorScene(run.g, fs, "haru", greet=False)
    run.g.scenes.push(it)
    it.wait_menu = True
    it.fade_in = 0
    it._open_shop("buy")
    run.pump(3.0)
    run.g.scenes.current._close()
    run.g.scenes.stack.remove(it)


def visit_baek(run: Run, fs, take: bool = True):
    from src.scene.interior import InteriorScene
    it = InteriorScene(run.g, fs, "baek", greet=False)
    run.g.scenes.push(it)
    it.fade_in = 0
    it.line_done_all()   # 메뉴가 뜸 → interior_ready:baek
    run.pump(1.0, tap=False)
    r = run.g.guide.run
    if r is not None and r["id"] == "TG-22":
        it._choose("exam")    # 강조된 [시험] 을 누름
    elif take:
        it._choose("exam")
    run.pump(4.0)
    return it


def exam_fight(run: Run, fs, win: bool = True) -> None:
    from src.fishing.bite import BiteState
    from src.fishing.casting import CastState
    run.pump(2.0)   # TG-24 ① (끼워진 시험 찌)
    c = fs.cast
    c.state = CastState.LANDED
    c.bx, c.bz = 0.0, 22.0
    fs._splash()
    t = 0.0
    while fs.bite.state != BiteState.BITE and t < 20:
        run.pump(DT * 4)
        t += DT * 4
    fs._left_click()
    run.pump(1.0)
    f = fs.fight
    if win:
        f.opp, f.misses, f.line_damage = {"P": 4, "G": 1, "M": 0}, 0, 0
        f._caught()
        for _ in range(300):
            run.frame()
            if fs.landing is not None:
                fs.landing.skip()
    else:
        f._lose("snap")
        run.pump(2.0)
    fs.end_t = 99
    fs._end_fight()
    run.pump(0.8, tap=False)
    run.shot(f"시험 결과 화면 ({run.scene()})")
    res = run.g.scenes.current
    res.t = 1.0
    res._close()
    run.pump(2.0)   # exam_end → TG-24 ③


def normal_catch(run: Run, fs) -> None:
    from src.fishing.casting import CastState
    from src.save.save_game import fish_by_id
    import copy
    fs.bite.fish = copy.deepcopy(fish_by_id("carp"))
    fs.bite.cast_distance = 20
    fs.cast.bx, fs.cast.bz = 0.0, 20.0
    fs.cast.state = CastState.HOOKED
    fs._start_fight()
    run.pump(0.5)
    f = fs.fight
    f.opp, f.misses, f.line_damage = {"P": 2, "G": 2, "M": 1}, 0, 0.1
    f._caught()
    for _ in range(200):
        run.frame()
        if fs.landing is not None:
            fs.landing.skip()
    run.pump(4.0)   # catch_shown → TG-25
    fs.end_t = 99
    fs._end_fight()
    run.pump(0.5)


def to_fishing(run: Run, fs) -> None:
    while run.g.scenes.current is not fs and len(run.g.scenes.stack) > 1:
        top = run.g.scenes.current
        if hasattr(top, "leave"):
            top.leave()   # 마을 → 낚시터 (배경을 낚시터로 되돌림)
            run.pump(0.5, tap=False)
            if run.g.scenes.current is top:
                run.g.scenes.stack.remove(top)
        else:
            run.g.scenes.stack.pop()
    fs.backdrop = None
    fs.travel("reservoir") if fs.spot_id != "reservoir" else None
    run.pump(0.5)


def fill_quals(fs) -> None:
    from src.save import exam
    from src.save.save_game import all_fish
    s = fs.save
    sp = set(exam.base_spots(s))
    for i, f in enumerate([f for f in all_fish() if f["spot"] in sp and f["rarity"] != "legend"]):
        lo, hi = f["size_cm"]
        s.record_catch({"fish": f, "size": hi * 0.99 if i % 2 == 0 else (lo + hi) / 2, "rank": "S", "price": 1, "perfects": 0})
    s.data["keepnet"].clear()
    s.data["dex"].setdefault(next(f["id"] for f in all_fish() if f["spot"] in sp and f["rarity"] == "legend"), {"count": 1})


def done(run: Run) -> list[str]:
    return [t for t in run.g.guide.st()["done"] if t.startswith("TG-2")]


def case_new() -> Run:
    run = Run("new")
    make_save(1, 1, False, STORY_TG)
    fs = start(run, 1)
    check(run.scene() != "ExamNoticeScene", "공지 없음", run)
    visit_shop(run, fs)
    check("TG-21" in done(run), "상점: TG-21 잠긴 장비", run)
    from src.save import exam
    fill_quals(fs)
    it = visit_baek(run, fs)
    check("TG-22" in done(run) and "TG-23" in done(run), "백 노인: TG-22 → 시험 화면 TG-23", run)
    ex = run.g.scenes.current
    ex._action()   # 시험 보기
    run.pump(0.5)
    ex._close()
    run.g.scenes.stack.remove(it)
    to_fishing(run, fs)
    exam_fight(run, fs, win=True)
    check("TG-24" in done(run) and exam.passed(fs.save) == 2, "낚시터: TG-24 첫 시험 → 합격 → ③ 상점 버튼", run)
    normal_catch(run, fs)
    check("TG-25" in done(run), "포획 카드: TG-25 새 랭크", run)
    return run


def case_legacy(name: str, top: int, eldra: bool = False) -> Run:
    run = Run(name)
    make_save(1, top, True, STORY_TG + ["TG-12"], eldra=eldra)
    fs = start(run, 1)
    pages = read_notice(run)
    want = ["notice_1", "notice_t8", "notice_4"] if top >= 8 else ["notice_1", "notice_2", "notice_3", "notice_4"]
    check(pages == want, f"변경 공지 {len(want)}쪽 ({'T8 판' if top >= 8 else f'T{top}'})", run)
    from src.save import exam
    check(exam.passed(fs.save) == top and "TG-21" in done(run), f"자동 합격 T{top} · TG-21 건너뜀", run)
    if top < 8:
        visit_baek(run, fs)
        check("TG-22" in done(run) and "TG-23" in done(run), "백 노인: TG-22 → TG-23", run)
    else:
        titles = fs.save.data["cosmetics"]["titles"]
        check("exam_water" in titles and "exam_heir" in titles, "칭호 2개", run)
        it = visit_baek(run, fs, take=False)
        run.shot("오두막 목패 Ⅱ~Ⅷ")
        check(set(done(run)) >= {"TG-21", "TG-22", "TG-23", "TG-24"} and run.g.guide.run is None,
              "시험 튜토리얼 없음", run)
        del it
    to_fishing(run, fs)
    normal_catch(run, fs)
    check("TG-25" in done(run), "포획 카드: TG-25 새 랭크", run)
    return run


def case_story() -> Run:
    run = Run("story")
    make_save(1, 3, True, ["TG-01", "TG-02", "TG-03", "TG-04", "TG-05"])
    fs = start(run, 1)
    check(run.scene() != "ExamNoticeScene", "이야기 튜토리얼 중: 공지 미룸", run)
    run.pump(1.0)
    check(run.scene() != "ExamNoticeScene", "마을에 있어도 미룸 (TG-06 · 07 전)", run)
    run.g.guide.st()["done"] += ["TG-06", "TG-07"]   # 판매 · 구매 튜토리얼을 마침
    run.note("TG-06 · TG-07 끝남")
    run.pump(0.5, tap=False)
    pages = read_notice(run)
    check(len(pages) == 4, "그 뒤 마을에서 변경 공지 4쪽", run)
    return run


def main() -> int:
    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(os.environ["FISHING_SAVE_DIR"])
    which = sys.argv[1:] or ["new", "t3", "t5", "t8", "story"]
    runs = []
    for w in which:
        fn = {"new": case_new, "t3": lambda: case_legacy("t3", 3), "t5": lambda: case_legacy("t5", 5),
              "t8": lambda: case_legacy("t8", 8, eldra=True), "story": case_story}[w]
        runs.append(fn())
    for r in runs:
        print(f"[{r.name}]")
        for ln in r.log:
            print("  " + ln)
    print("결과:", "ok" if not FAIL else f"실패 {len(FAIL)}개 — " + " / ".join(FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
