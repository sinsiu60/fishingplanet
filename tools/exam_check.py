"""백 노인의 시험 점검 (DESIGN.md 49-3, BAEK_EXAM.md EX3). 화면 없이 실제 장면 코드로:

  flow    새 세이브 → 저수지 자격 채움 → 백 노인 [시험] → 시험 찌 → 저수지 착수 → 시험 물고기 →
          놓침(불합격 · 하루 대기) → 회수(미루기 확인) → 합격 → T2 구매. 가방 · 도감 · 통계 제외 확인.
  legacy  시험 이전 세이브 (장비 T3 · T5+상자 전설 낚싯대 · T8) 불러오기 → 자동 합격 · 안내 한 번 · 잠금.
  letter  엘라 [백 노인의 편지] (T6 부터) · 3번 불합격 → 힌트 + 훈련 수조 바로가기.
  python tools/exam_check.py [flow|legacy|letter]   (기본 = 전부, 스크린샷 build/exam_check/*.png)
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
OUT = os.path.join(ROOT, "build", "exam_check")
os.environ["FISHING_SAVE_DIR"] = os.path.join(OUT, "save")

import pygame  # noqa: E402

FAIL: list[str] = []


def check(cond: bool, what: str) -> None:
    print(("  ok   " if cond else "  FAIL ") + what)
    if not cond:
        FAIL.append(what)


def _game():
    from src.core.game import Game
    from src.save.save_game import SaveGame
    from src.scene.fishing_scene import FishingScene
    from src.ui import tutorial as tut
    shutil.rmtree(os.environ["FISHING_SAVE_DIR"], ignore_errors=True)
    os.makedirs(os.environ["FISHING_SAVE_DIR"])
    g = Game()
    g.save = SaveGame(1)
    g.save.data["tutorial"]["enabled"] = False
    g.scenes.stack.clear()
    sc = FishingScene(g)
    g.scenes.push(sc)
    for k in list(tut.CARDS) + list(tut.GUIDES):
        sc.tutorial.seen.add(k)
    return g, sc


def _shot(g, name: str, scene=None) -> None:
    c = g.screen.canvas
    (scene or g.scenes.stack[-1]).draw(c)
    pygame.image.save(c, os.path.join(OUT, f"{name}.png"))


def _upd(sc, n: int = 1) -> None:
    for _ in range(n):
        sc.card = None   # 첫 만남 · 환영 카드 (튜토리얼) 는 건너뜀
        sc.update(1 / 60)


def flow() -> None:
    print("[flow] 새 세이브 T2 시험")
    from src.fishing.bite import BiteState
    from src.fishing.casting import CastState
    from src.save import exam
    from src.save.save_game import all_fish, find_gear
    from src.scene.interior import InteriorScene
    g, sc = _game()
    s = g.save
    glass = find_gear("rod", "glass")
    check(s.buy("rod", glass) == "locked" and "T2" in (s.gear_locked_reason(glass) or ""), "상점: T2 낚싯대 잠김")
    fish = [f for f in all_fish() if f["spot"] == "reservoir" and f["rarity"] != "legend"]
    for i, f in enumerate(fish[:7]):
        lo, hi = f["size_cm"]
        s.record_catch({"fish": f, "size": hi * 0.99 if i < 1 else (lo + hi) / 2, "rank": "S" if i < 4 else "A",
                        "price": 10, "perfects": 0})
    check(exam.eligible(s), "자격 ① 7/8 · ② 12/40 → 응시 가능")
    stats0, dex0, keep0 = json.dumps(s.data["stats"]), len(s.data["dex"]), len(s.data["keepnet"])
    it = InteriorScene(g, sc, "baek", greet=False)
    g.scenes.push(it)
    it.wait_menu = True
    check("exam" in it._menu_items(), "백 노인 메뉴 [시험]")
    it._choose("exam")
    ex = g.scenes.stack[-1]
    for _ in range(30):
        ex.update(1 / 60)
    _shot(g, "exam_ready")
    ex._action()
    check(exam.active(s) is not None, "시험 찌 지급")
    _shot(g, "exam_given")
    ex._close()
    g.scenes.stack.remove(it)

    def cast_and_hook():
        c = sc.cast
        c.state = CastState.LANDED
        c.bx, c.bz = 0.0, 22.0
        sc._splash()
        t = 0.0
        while sc.bite.state != BiteState.BITE and t < 20:
            _upd(sc)
            t += 1 / 60
        sc._left_click()
        _upd(sc, 30)
        return sc.fight, t

    f, t = cast_and_hook()
    check(f is not None and f.fish.get("exam") == 2, f"3초 대기 뒤 시험 물고기 ({f.fish['name'] if f else '-'}, 입질까지 {t:.1f}초)")
    check(f.gear["rod_tier"] == 2 and f.gear["line_red_mult"] == 1.0 and sc.quest_run is None,
          "빌린 T2 장비 · 부적 효과 없음 · 의뢰 없음")
    f._lose("snap")
    _upd(sc, 90)
    _shot(g, "exam_lost")
    sc._end_fight()
    check(type(g.scenes.stack[-1]).__name__ == "ExamResultScene", "놓침 → 백 노인 불합격 화면")
    g.scenes.stack.pop()
    check(exam.retry_wait(s, sc.clock.day) and not exam.retry_wait(s, sc.clock.day + 1), "불합격: 게임 하루 대기")
    sc.clock.day += 1
    exam.give_float(s)
    c = sc.cast
    c.state = CastState.LANDED
    c.bx, c.bz = 0.0, 22.0
    sc._splash()
    sc._right_click()
    conf = g.scenes.stack[-1]
    check(type(conf).__name__ == "ConfirmScene", "시험 찌 회수 → '시험을 미루겠나?'")
    conf._yes()
    check(exam.active(s) is None and exam.fails(s) == 1, "미루기: 찌 반납, 불합격으로 안 침")
    exam.give_float(s)
    f, _ = cast_and_hook()
    _upd(sc, 120)
    f.opp, f.misses, f.line_damage = {"P": 4, "G": 1, "M": 0}, 0, 0
    f._caught()
    for _ in range(480):
        _upd(sc)
        if sc.landing is not None:
            sc.landing.skip()
    _shot(g, "exam_caught_card")
    check(bool((sc.catch_news or {}).get("exam", {}).get("pass")), f"합격 판정 ({f.result['rank']})")
    sc._end_fight()
    for _ in range(40):
        g.scenes.stack[-1].update(1 / 60)
    _shot(g, "exam_pass_baek")
    g.scenes.stack.pop()
    check(exam.passed(s) == 2 and s.gear_locked_reason(glass) is None
          and "T3" in (s.gear_locked_reason(find_gear("rod", "carbon")) or ""), "합격 T2 → T2 장비 풀림, T3 잠김")
    check(json.dumps(s.data["stats"]) == stats0 and len(s.data["dex"]) == dex0 and len(s.data["keepnet"]) == keep0
          and "lenok" not in s.data["dex"], "시험 물고기: 통계 · 도감 · 살림망 제외")
    s.data["money"] = 1000
    check(s.buy("rod", glass) == "ok", "T2 낚싯대 구매")
    from src.save import item_use, treasure
    treasure.give_item(s, "dragon_scale_rod")   # 상자 전설 낚싯대 (샤르미온 = T5 수치)
    it = treasure.item_info("dragon_scale_rod")
    lab, ok = item_use.item_state(s, it)
    s.equip("rod", "dragon_scale_rod")
    check(not ok and "T5" in lab and s.data["gear"]["rod"] == "glass", f"상자 장비: 보관만 · 장착 잠금 ({lab})")


def legacy() -> None:
    print("[legacy] 시험 이전 세이브")
    from src.save import exam
    from src.save.save_game import GEAR_KINDS, SaveGame, equipment, new_data
    from src.scene.menu import start_game
    g, _ = _game()
    eq = equipment()
    cases = {1: ("T3", 3, False, None), 2: ("T5 + 상자 전설 낚싯대", 5, False, "dragon_scale_rod"), 3: ("T8", 8, True, None)}
    for slot, (label, top, eldra, treasure) in cases.items():
        d = new_data()
        d.pop("exam")
        for k in GEAR_KINDS:
            d["owned"][k] = [x["id"] for x in eq[k] if x["tier"] <= top]
            d["gear"][k] = d["owned"][k][-1]
        if eldra:
            d["unlocked_continents"] = ["sharmion", "eldrasion"]
        if treasure:
            d["items"]["owned"].append(treasure)
            d["items"]["origin"] = {treasure: "sharmion"}
            d["gear"]["rod"] = treasure
        d["unlocked_spots"] = ["reservoir", "valley"]
        d["dex"] = {"carp": {"count": 3}}
        d["stats"]["catches"] = 3
        with open(os.path.join(os.environ["FISHING_SAVE_DIR"], f"slot{slot}.json"), "w", encoding="utf-8") as fp:
            json.dump(d, fp, ensure_ascii=False)
        s = SaveGame.load(slot)
        check(exam.passed(s) == top and exam.legacy_notice(s) == top, f"{label}: 자동 합격 T{top} · 안내 대기")
        check(all(s.equip_locked(k, s.data["gear"][k]) is None for k in GEAR_KINDS), f"{label}: 장착 중인 장비 잠기지 않음")
        want = [tid for t, tid in exam.cfg()["titles"].items() if int(t) <= top]
        titles = s.data.get("cosmetics", {}).get("titles", [])
        check(all(t in titles for t in want) and not [t for t in exam.cfg()["titles"].values() if t in titles and t not in want],
              f"{label}: 칭호 {want or '없음'}")
        nxt = exam.next_tier(s)
        if nxt and nxt <= 5:
            check(s.buy("rod", next(x for x in eq["rod"] if x["tier"] == nxt)) == "locked", f"{label}: T{nxt} 구매 잠김")
        start_game(g, s)
        top_sc = g.scenes.stack[-1]
        check(type(top_sc).__name__ == "ExamNoticeScene", f"{label}: 시작 때 백 노인 안내")
        for _ in range(40):
            top_sc.update(1 / 60)
        _shot(g, f"legacy_{slot}")
        top_sc._close()
        check(exam.legacy_notice(SaveGame.load(slot)) is None, f"{label}: 안내는 한 번만")


def letter() -> None:
    print("[letter] 엘라 편지 · 3번 불합격 힌트")
    from src.save import exam
    from src.scene.exam_scene import ExamResultScene
    from src.scene.interior import InteriorScene
    g, sc = _game()
    s = g.save
    s.data["unlocked_continents"] = ["sharmion", "eldrasion"]
    for p, want in ((4, False), (5, True)):
        exam.state(s)["passed"] = p
        it = InteriorScene(g, sc, "ella", greet=False)
        check(("letter" in it._menu_items()) == want, f"합격 T{p}: 엘라 [백 노인의 편지] {'있음' if want else '없음'}")
    it = InteriorScene(g, sc, "ella", greet=False)
    g.scenes.push(it)
    it.wait_menu = True
    it._choose("letter")
    ex = g.scenes.stack[-1]
    for _ in range(30):
        ex.update(1 / 60)
    _shot(g, "ella_letter_panel")
    check(type(ex).__name__ == "ExamScene" and ex.letter, "엘라 편지 = 같은 시험 화면")
    ex._close()
    g.scenes.stack.remove(it)
    exam.give_float(s)
    res = exam.finish(s, True, 1, {})
    r = ExamResultScene(g, sc, res)
    check(r.letter, "T6 결과 = 백 노인의 편지")
    check(res["titles"] == ["물을 아는 자"], f"T4 이상 합격 → 칭호 '물을 아는 자' ({res['titles']})")
    g.scenes.push(r)
    for _ in range(60):
        r.update(1 / 60)
    _shot(g, "letter_pass")
    g.scenes.stack.remove(r)
    for i in range(3):
        exam.give_float(s)
        exam.finish(s, False, 1 + i, {"twist": 3, "jump": 1})
    check(exam.show_hint(s) == "twist", "3번 불합격 → 가장 많이 놓친 패턴 = 줄 비틀기")
    sc.clock.day = 10
    b = InteriorScene(g, sc, "baek", greet=False)
    g.scenes.push(b)
    b.wait_menu = True
    b._choose("exam")
    ex = g.scenes.stack[-1]
    for _ in range(30):
        ex.update(1 / 60)
    _shot(g, "baek_hint")
    check("줄 비틀기" in b.react_line[1] and ex.train_btn in ex._buttons(), "백 노인 힌트 대사 + [훈련 수조에서 연습]")
    ex._train()
    check(sc.training is not None and sc.training.label() == "줄 비틀기", "훈련 수조: 그 패턴이 골라진 채로")


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    which = sys.argv[1:] or ["flow", "legacy", "letter"]
    for w in which:
        {"flow": flow, "legacy": legacy, "letter": letter}[w]()
    print("결과:", "ok" if not FAIL else f"실패 {len(FAIL)}개")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
