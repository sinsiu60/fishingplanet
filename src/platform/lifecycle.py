"""앱 생명주기 (MOBILE.md 4번): 홈 버튼·앱 전환·전화·알림창.

  백그라운드로 갈 때  → 낚시 중이면 일시정지 화면을 띄우고 즉시 저장, 소리 멈춤
  돌아올 때           → 소리 다시 (일시정지 화면 그대로 → 파이팅 중이었어도 멈춘 상태로 복귀)
  알림창 내림(포커스 잃음) → 일시정지만
안드로이드에서 SDL은 백그라운드 동안 메인 루프를 알아서 멈춘다(SDL_ANDROID_BLOCK_ON_PAUSE 기본값).
PC에선 아무것도 하지 않는다 (창을 내려도 지금처럼 계속 돈다).
"""
import pygame

from src.platform.detect import IS_MOBILE

BACKGROUND = {getattr(pygame, n) for n in ("APP_WILLENTERBACKGROUND", "APP_DIDENTERBACKGROUND", "WINDOWMINIMIZED")
              if hasattr(pygame, n)}
FOREGROUND = {getattr(pygame, n) for n in ("APP_DIDENTERFOREGROUND", "WINDOWRESTORED") if hasattr(pygame, n)}
DANGER = {getattr(pygame, n) for n in ("APP_TERMINATING", "APP_LOWMEMORY") if hasattr(pygame, n)}
FOCUS_LOST = getattr(pygame, "WINDOWFOCUSLOST", None)


class Lifecycle:
    def __init__(self, game):
        self.game = game
        self.in_background = False

    def handle_event(self, event) -> bool:
        """처리했으면 True (씬으로 넘기지 않음)."""
        if not IS_MOBILE:
            return False
        t = event.type
        if t in BACKGROUND:
            if not self.in_background:
                self.in_background = True
                self.pause_game()
                self.game.save_now()
                if pygame.mixer.get_init():
                    pygame.mixer.pause()
            return True
        if t in FOREGROUND:
            self.game.screen._bars_dirty = True  # 돌아오면 화면 버퍼가 비었을 수 있다 → 검은 띠 다시
            if self.in_background:
                self.in_background = False
                if pygame.mixer.get_init():
                    pygame.mixer.unpause()
            return True
        if t in DANGER:
            self.game.save_now()
            return True
        if FOCUS_LOST is not None and t == FOCUS_LOST:
            self.pause_game()
            return True
        return False

    def pause_game(self) -> None:
        """낚시 화면이 맨 위면 일시정지 화면을 띄운다 (메뉴 화면은 원래 멈춰 있음)."""
        from src.scene.fishing_scene import FishingScene
        cur = self.game.scenes.current
        if isinstance(cur, FishingScene) and cur.landing is None:
            from src.scene.pause import PauseScene
            self.game.scenes.push(PauseScene(self.game, cur))
