"""안드로이드와 같은 pygame(2.6.x, pygame-ce 아님)에서 소리·장면이 도는지 빠른 확인 (CI, 32-14).

PC는 pygame-ce, APK는 pygame 2.6 이라 한쪽에만 있는 API(예: Channel.id)를 쓰면 폰에서만 바로 꺼진다.
  python tools/compat_smoke.py      (SDL_VIDEODRIVER/SDL_AUDIODRIVER=dummy 로)
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("FISHING_SAVE_DIR", os.path.join(ROOT, "build", "smoke_save"))


def main() -> int:
    import pygame
    os.makedirs(os.environ["FISHING_SAVE_DIR"], exist_ok=True)
    print("pygame", pygame.version.ver, "ce" if getattr(pygame, "IS_CE", False) else "")
    from src.core.game import Game
    from src.save.save_game import SaveGame
    from src.scene.fishing_scene import FishingScene
    from src.scene.training import TrainingTank
    from src.ui import tutorial as tut
    g = Game()
    sfx = g.sfx
    # 모든 소리: 한 번씩 재생 (패닝·진동 포함), 반복음 켜고 끄기
    for i, name in enumerate(sorted(sfx.sounds)):
        sfx.play(name, 0.5, pan=(-1) ** i * 0.5, haptic="nibble")
        if i % 8 == 0:
            sfx.update(1 / 60, slow=i % 16 == 0)
    sfx.muffle = True
    for name in ("amb_bed_lake", "amb_rain_bed"):
        sfx.loop(name, True, 0.5)
        sfx.loop(name, True, 0.3)
    sfx.muffle = False
    sfx.stop_all()
    # 낚시 장면: 훈련 수조 파이팅 몇 초 + 음악 층
    g.save = SaveGame(1)
    g.scenes.stack.clear()
    sc = FishingScene(g)
    g.scenes.push(sc)
    for k in list(tut.CARDS) + list(tut.GUIDES):
        sc.tutorial.seen.add(k)
    for entry in (("pat", "rush"), ("pat", "jump"), ("pat", "turn")):
        sc.training = TrainingTank(sc)
        sc.training.entries = [entry]
        sc.training.index = 0
        sc.training.start()
        for _ in range(60 * 4):
            sc.card = None
            sc.update(1 / 60)
            sfx.update(1 / 60)
            g.adaptive.update(1 / 60)
            g.haptics.update(1 / 60)
    sc.training = None
    print("ok: 소리", len(sfx.sounds), "· 음악 층", len(g.adaptive.sounds))
    return 0


if __name__ == "__main__":
    sys.exit(main())
