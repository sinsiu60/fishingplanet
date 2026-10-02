"""입력 → 소리 지연 측정 (DESIGN.md 32-14, Phase S8).

게임 코드 안에서 입력이 들어온 뒤 Channel.play 까지 몇 틱이 걸리는지 실제 장면으로 재고,
출력 버퍼 지연(버퍼 샘플 ÷ 44100, SDL은 보통 버퍼 2개 = ×2)과 소리 어택 시각을 더해 '귀에 닿는 시간'을 PC·모바일로 계산한다.

  python tools/sound_latency.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("FISHING_SAVE_DIR", os.path.join(ROOT, "build", "latency_save"))


def main() -> int:
    import pygame
    from src.audio import sfx as sfxmod
    from src.core.config import load_json
    from src.core.game import Game
    from src.save.save_game import SaveGame
    from src.save.settings import Settings
    from src.scene.fishing_scene import FishingScene
    from src.scene.training import TrainingTank
    from src.fishing.bite import BiteState
    from src.ui import tutorial as tut

    os.makedirs(os.environ["FISHING_SAVE_DIR"], exist_ok=True)
    log: list[tuple[int, str]] = []
    tick = [0]
    orig = sfxmod.Sfx._play

    def _play(self, name, volume, pan):
        log.append((tick[0], name))
        return orig(self, name, volume, pan)
    sfxmod.Sfx._play = _play
    st = Settings()
    st.data["tutorial_seen"] = sorted(set(tut.CARDS) | set(tut.GUIDES))
    st.save()
    g = Game()
    g.save = SaveGame(1)
    g.scenes.stack.clear()
    sc = FishingScene(g)
    g.scenes.push(sc)
    for k in list(tut.CARDS) + list(tut.GUIDES):
        sc.tutorial.seen.add(k)
    S = g.screen.scale
    pos = (240 * S, 150 * S)
    state = {"held": False}
    pygame.mouse.get_pos = lambda: pos
    pygame.mouse.get_pressed = lambda num_buttons=3: (state["held"], False, False)

    def step(n=1):
        for _ in range(n):
            sc.card = None
            sc.update(g.tick_dt)
            tick[0] += 1

    def ev(t, **kw):
        sc.handle_event(pygame.event.Event(t, pos=pos, **kw))

    def first(name_prefix: str, since: int) -> int | None:
        return next((t - since for t, n in log if t >= since and n.startswith(name_prefix)), None)

    results = []
    # 1) 챔질: 진짜 입질에 클릭
    ev(pygame.MOUSEBUTTONDOWN, button=1); step(25); ev(pygame.MOUSEBUTTONUP, button=1)
    guard = 0
    while sc.bite.state != BiteState.BITE and guard < 60 * 120:
        step(); guard += 1
    t0 = tick[0]
    ev(pygame.MOUSEBUTTONDOWN, button=1)
    step(2)
    results.append(("챔질 클릭 → 챔질 소리", first("sfx_hook", t0), "sfx_hook_success"))
    ev(pygame.MOUSEBUTTONUP, button=1)
    # 2) 릴 감기: 파이팅 중 누르기 시작 → 첫 클릭
    sc.training = TrainingTank(sc)
    sc.training.entries = [("pat", "jump")]
    sc.training.index = 0
    sc.training.start()
    step(30)
    state["held"] = False
    step(30)
    t0 = tick[0]
    state["held"] = True
    ev(pygame.MOUSEBUTTONDOWN, button=1)
    step(10)
    results.append(("감기 누름 → 릴 클릭", first("sfx_reel_click", t0), "sfx_reel_click#2"))
    # 3) 점프 정점에 우클릭 → 판정 소리
    f = sc.fight
    guard = 0
    while not (f.brain.state == "jump" and f.brain.time_to_apex() <= 0.01) and guard < 60 * 30:
        step(); guard += 1
    t0 = tick[0]
    ev(pygame.MOUSEBUTTONDOWN, button=3)
    step(3)
    results.append(("정점 우클릭 → 퍼펙트/그레잇", first("sfx_perfect", t0) if first("sfx_perfect", t0) is not None else first("sfx_great", t0), "sfx_perfect#0"))
    ev(pygame.MOUSEBUTTONUP, button=3)
    # 4) UI 버튼 (일시정지 → '계속하기')
    from src.platform.input import Action
    from src.scene.pause import PauseScene
    ps = PauseScene(g, sc)
    g.scenes.push(ps)
    t0 = tick[0]
    btn = next(x for x in ps.buttons if "계속" in x.label)
    ps.handle_action(Action("primary", pos=btn.rect.center))
    results.append(("UI 버튼 → ui_click", first("ui_click", t0), "ui_click"))
    if g.scenes.current is ps:
        g.scenes.pop()

    cfg = load_json("audio_config.json")
    tick_ms = g.tick_dt * 1000
    print(f"틱 {tick_ms:.1f}ms · PC 버퍼 {cfg['buffer_pc']} · 모바일 버퍼 {cfg['buffer_mobile']} (출력 지연 ≈ 버퍼 2개)")
    print(f"{'동작':28s} {'코드(틱)':>8s} {'어택':>6s} {'PC 합계':>8s} {'모바일 합계':>10s}")
    for label, ticks, snd in results:
        if ticks is None:
            print(f"{label:28s} {'(측정 못 함)':>8s}")
            continue
        att = g.sfx.attack_of(snd) * 1000 if snd in g.sfx.sounds else 0.0
        code = ticks * tick_ms
        pc = code + 2 * cfg["buffer_pc"] / 44.1 + att
        mob = code + 2 * cfg["buffer_mobile"] / 44.1 + att
        print(f"{label:28s} {ticks:8d} {att:5.0f}ms {pc:6.0f}ms {mob:8.0f}ms")
    print("※ 모바일 실제 기기는 출력 장치 지연(수십 ms)이 더해진다 → 설정 '오디오 지연 보정'으로 맞춤.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
