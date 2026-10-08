"""스토리 장면 실행 (DESIGN.md 36): 기존 화면 흐름의 신호에 장면을 끼워 넣는다.

- prologue: 새 게임 → P-01~P-04 컷신 → P-05 하루네 낚시점(상점 메뉴 숨김, 이름 입력) → 윤슬 마을
- interior 장면: InteriorScene(script) — 대본 안의 {do: name|closeup|letter} 단계는 step() 이 화면을 띄우고 이어 간다
- after_travel: 용문 폭포 첫 방문 컷신 뒤 C3-02 · 세계수 뿌리 샘 첫 방문 뒤 C5-04 (+마지막 장 종이 + 자막)
- after_dragon_ending: 등용 엔딩 → C3-04(오두막 대화 → 편지 → 대화) → 기존 출항 컷신 (엘드라시온의 소문 연출 대신)
- before_final_ending / after_final_ending: C5-05 선택 → 기존 최종 엔딩 → E-01
- replay: 추억에서 다시 보기 (결과·기록은 바꾸지 않음)
"""
from src.story import story


def _lines(sid: str) -> list:
    return [tuple(x) if isinstance(x, list) else x for x in story.scene(sid)["lines"]]


def interior_script(game, sid: str):
    """장소 장면의 대본 (InteriorScene script)."""
    return _lines(sid)


def step(interior, item: dict, resume) -> None:
    """대본 속 특수 단계: 이름 입력 · 손잡이 클로즈업 · 편지."""
    game = interior.game
    if item["do"] == "name":
        from src.story.ui import NameInputScene

        def done(nm):
            if not getattr(interior, "replay", False):
                story.state(game.save)["player_name"] = nm
                game.save_now()
            resume()
        game.scenes.push(NameInputScene(game, done, backdrop=interior.draw))
    elif item["do"] == "closeup":
        from src.story.cutscene import CutsceneScene
        game.scenes.push(CutsceneScene(game, "CLOSEUP", on_done=resume, skippable=False))
    elif item["do"] == "letter":
        from src.story.ui import PaperScene
        body = story.load_json("story/letters.json")[item.get("id", "letter")]
        game.scenes.push(PaperScene(game, body, on_done=resume, backdrop=interior.draw))
    else:
        resume()


# ───────────────────────── 프롤로그 ─────────────────────────
def prologue(game, fishing) -> None:
    from src.story.cutscene import CutsceneScene
    chain = ["P-01", "P-02", "P-03", "P-04"]

    def nxt(i=0):
        if i < len(chain):
            game.scenes.push(CutsceneScene(game, chain[i], on_done=lambda: nxt(i + 1)))
        else:
            p05()

    def p05():
        from src.scene.interior import InteriorScene

        def done(sc):
            story.complete(game, "P-01")
            for sid in ("P-01", "P-02", "P-03", "P-04"):
                story.complete(game, sid)
            story.complete(game, "P-05")
            from src.scene import dialogue
            dialogue.state(game.save)["heard"].append("haru_greet_first")   # 이미 만났으니 첫 인사는 건너뜀
            if sc in game.scenes.stack:
                game.scenes.stack.remove(sc)
            from src.scene.village import VillageScene
            game.scenes.push(VillageScene(game, fishing, "sharmion"))
            game.fade_in(0.8)
        sc = InteriorScene(game, fishing, "haru", script=interior_script(game, "P-05"), on_done=done, menu=False)
        sc.fade_col = (255, 255, 255)   # 흰 화면에서 페이드 인
        game.scenes.push(sc)
    nxt()


# ───────────────────────── 첫 방문 · 엔딩 ─────────────────────────
def _world_snapshot(game, fishing):
    import pygame
    surf = pygame.Surface(game.screen.canvas.get_size())
    old = fishing.scenic
    fishing.scenic = True
    fishing.draw(surf)
    fishing.scenic = old
    return surf


def rock_scene(game, fishing):
    """C3-02 전용 컷신 그림 (STORY_ROCK.md): 낚시 화면 스냅샷 대신 폭포 · 바위 · 손을 따로 그림. 손 = 낚시 화면 손 색 + 계절 장갑."""
    from src.render.palette import Palette
    from src.render.story_rock import StoryRock
    w, h = game.screen.canvas.get_size()
    look = fishing._hand_look() if hasattr(fishing, "_hand_look") else None
    return StoryRock(w, h, Palette().sample(13.0), look, reduce=bool(game.settings.get("reduce_fx")))


def after_travel(game, fishing, spot_id: str) -> bool:
    """첫 방문 이동 컷신(타이틀까지) 바로 뒤. 장면을 띄웠으면 True."""
    save = game.save
    if not story.active(save):
        return False
    if spot_id == "secret" and not story.seen(save, "C3-02"):
        from src.story.cutscene import CutsceneScene
        game.scenes.push(CutsceneScene(game, "C3-02", world=rock_scene(game, fishing),
                                       on_done=lambda: (story.complete(game, "C3-02"), game.fade_in(0.6))))
        return True
    if spot_id == "world_tree" and not story.seen(save, "C5-04"):
        play_c504(game, fishing)
        return True
    return False


def play_c504(game, fishing, replay: bool = False) -> None:
    from src.story.cutscene import CutsceneScene, SubtitleScene, draw_c504
    from src.story.ui import PaperScene
    sc = story.scene("C5-04")
    body = story.load_json("story/letters.json")["last_page"]

    def bg(canvas):
        draw_c504(canvas, 3.0, sc)

    def after_paper():
        def end():
            story.complete(game, "C5-04", replay)
            game.fade_in(0.6)
        game.scenes.push(SubtitleScene(game, sc["subs"][0], 3.0, backdrop=bg, on_done=end))

    game.scenes.push(CutsceneScene(game, "C5-04", on_done=lambda: game.scenes.push(PaperScene(game, body, on_done=after_paper,
                                                                                               backdrop=bg))))


def after_dragon_ending(game, fishing) -> bool:
    """등용 엔딩이 끝난 직후: C3-04 → 기존 출항 컷신 (편지 '엘드라시온의 소문' 대신)."""
    save = game.save
    if not story.active(save) or story.seen(save, "C3-04"):
        return False
    from src.scene.interior import InteriorScene
    from src.scene.voyage import VoyageScene

    def done(sc):
        story.complete(game, "C3-04")
        if sc in game.scenes.stack:
            game.scenes.stack.remove(sc)
        game.scenes.push(VoyageScene(game, fishing, skip_letter=True))
    game.scenes.push(InteriorScene(game, fishing, "baek", script=interior_script(game, "C3-04"), on_done=done, menu=False))
    return True


def before_final_ending(game, fishing, fish: dict, size: float, then) -> bool:
    """오르시엘 포획 연출 직후, 기존 최종 엔딩 직전: C5-05 선택 (건너뛰기 없음)."""
    save = game.save
    if not story.active(save) or story.seen(save, "C5-05"):
        return False
    from src.story.finale import ChoiceScene
    game.scenes.push(ChoiceScene(game, fish, size, world=_world_snapshot(game, fishing), on_done=then))
    return True


def after_final_ending(game, fishing) -> bool:
    """기존 최종 엔딩(통계 포함) 직후 1회: E-01 — 대륙 이동 짧은 컷신 → 윤슬 마을 … → 자유 플레이."""
    save = game.save
    if not story.active(save) or story.seen(save, "E-01"):
        return False
    play_epilogue(game, fishing)
    return True


def play_epilogue(game, fishing, replay: bool = False) -> None:
    from src.scene.travel import TravelScene
    from src.scene.village import VillageScene
    from src.story.finale import EpilogueScene

    def arrive():
        v = VillageScene(game, fishing, "sharmion")
        game.scenes.push(v)
        game.scenes.push(EpilogueScene(game, v, replay=replay))
    t = TravelScene(game, fishing, "voyage", cont="sharmion", on_done=arrive)
    game.scenes.push(t)


def escape_shop(game, fishing) -> bool:
    """엘드라시온 찌 부족 도주 튜토리얼의 [상점으로 가기]: 아스테라 수정 공방에서 C4-02 조건 A."""
    save = game.save
    if not story.active(save):
        return False
    st = story.state(save)
    st["flags"]["eldra_escape"] = True
    story.poll(save)
    if story.seen(save, "C4-02A"):
        return False
    from src.scene.interior import InteriorScene
    game.scenes.push(InteriorScene(game, fishing, "ella"))   # 들어가면 대기 중인 C4-02A 가 먼저
    return True


# ───────────────────────── 추억 (다시 보기) ─────────────────────────
def replay(game, fishing, sid: str) -> None:
    sc = story.scene(sid)
    place = sc["place"]
    if place.startswith("interior:"):
        from src.scene.interior import InteriorScene
        npc = place.split(":", 1)[1]
        s = InteriorScene(game, fishing, npc, script=interior_script(game, sid), menu=False, replay=True,
                          on_done=lambda sc_: None)
        game.scenes.push(s)
        return
    from src.story.cutscene import CutsceneScene
    if sid == "C5-04":
        play_c504(game, fishing, replay=True)
    elif sid == "E-01":
        play_epilogue(game, fishing, replay=True)
    elif sid == "C5-05":
        from src.save.save_game import fish_by_id
        from src.story.finale import ChoiceScene
        cs = ChoiceScene(game, fish_by_id("orsiel"), 300.0, world=None, on_done=None)
        cs.replay = True
        game.scenes.push(cs)
    elif sid == "C4-01":
        from src.story.cutscene import SubtitleScene
        game.scenes.push(SubtitleScene(game, sc["subs"][0], 3.0))
    elif sid == "C3-02":
        game.scenes.push(CutsceneScene(game, "C3-02", world=rock_scene(game, fishing)))
    else:
        game.scenes.push(CutsceneScene(game, sid))
