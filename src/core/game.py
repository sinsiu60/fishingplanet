"""메인 루프. 게임 로직은 초당 60틱 고정, 렌더링은 그와 분리된다."""
import pygame

from src.audio.music import Music
from src.audio.sfx import Sfx
from src.core.config import game_config
from src.platform.input import create_input
from src.render.screen import PixelScreen
from src.save.settings import Settings
from src.scene.base import SceneManager

MAX_FRAME_TIME = 0.25  # 창 드래그 등으로 멈췄을 때 틱이 폭주하지 않게
AUTOSAVE_SEC = 60.0


class Game:
    def __init__(self, max_frames: int | None = None, start_scene=None):
        cfg = game_config()
        from src.platform.detect import IS_MOBILE as _mob
        from src.core.config import load_json as _lj
        _ac = _lj("audio_config.json")
        pygame.mixer.pre_init(44100, -16, 2, _ac["buffer_mobile"] if _mob else _ac["buffer_pc"])
        pygame.init()
        self.settings = Settings()
        self.tick_rate = cfg["tick_rate"]
        self.tick_dt = 1.0 / self.tick_rate
        self.fps_cap = cfg.get("fps_cap", 144)
        from src.platform.detect import mobile_window
        self.screen = PixelScreen(cfg["width"], cfg["height"], self.settings.get("scale") or cfg.get("scale"),
                                  cfg["title"], mobile_window())
        pygame.mouse.set_visible(False)  # 커서는 캔버스에 직접 그린다
        self.input = create_input(self)  # 마우스·키보드·터치 → 행동 (src/platform/input.py)
        if self.input.kind == "touch":
            from src.ui import hud
            hud.SHOW_CURSOR = False
        from src.platform.haptics import Haptics
        self.haptics = Haptics(self.settings)  # 진동 (PC는 아무것도 안 함)
        from src.platform.lifecycle import Lifecycle
        self.lifecycle = Lifecycle(self)  # 모바일: 백그라운드 → 일시정지·저장
        self.preview = None
        from src.platform.detect import PREVIEW
        if PREVIEW:
            from src.platform.preview import Preview
            self.preview = Preview(self)
            self.screen.overlay = self.preview.draw
            pygame.display.set_caption(self.preview.caption())
        self.clock = pygame.time.Clock()
        if self.screen.mobile:
            self._loading_frame()
            from src.platform.detect import IS_ANDROID
            if IS_ANDROID:
                from src.platform import android
                android.keep_screen_on()
        self.sfx = Sfx()
        self.sfx.haptics = self.haptics  # play(..., haptic=종류) → 소리 어택 순간에 진동
        self.apply_audio_settings()
        self.music = Music(self.sfx)  # data/music/ 의 파일 (없으면 무음)
        from src.audio.adaptive_music import AdaptiveMusic
        self.adaptive = AdaptiveMusic(self.sfx)  # 적응형 음악 층 (32장 S6)
        self.save = None            # 현재 SaveGame (메뉴에선 None)
        self.autosave_t = 0.0
        self.scenes = SceneManager()
        # 슬로우모션용 (퍼펙트 0.3초 슬로우 등). 틱 간격은 그대로, 쌓이는 시간만 줄인다.
        self.time_scale = 1.0
        self.slow_timer = 0.0  # 실제 시간 기준 남은 슬로우모션
        self.fade = 0.0        # 화면 전환 페이드 인 (남은 시간)
        self.fade_total = 1.0
        self.running = True
        self.max_frames = max_frames  # 자동 테스트용
        if start_scene is None:
            from src.scene.menu import TitleScene
            start_scene = TitleScene
        self.scenes.push(start_scene(self))

    def _loading_frame(self) -> None:
        """모바일 첫 실행은 효과음을 만드느라 몇 초 걸려서 안내 화면을 먼저 보여 준다."""
        from src.ui.hud import text
        c = self.screen.canvas
        c.fill((12, 16, 30))
        text(c, "준비 중...", (c.get_width() // 2, c.get_height() // 2), (220, 226, 240), 16, "center")
        self.screen.present()

    def frame_cap(self) -> int:
        """PC = 설정 파일 값 그대로. 모바일 = 설정 30/60, 메뉴 화면은 늘 30 (배터리). 로직은 언제나 초당 60틱."""
        if not self.screen.mobile:
            return self.fps_cap
        from src.scene.fishing_scene import FishingScene
        if not isinstance(self.scenes.current, FishingScene):
            return 30
        return self.settings.get("fps")

    def switch_preset(self, name: str) -> None:
        """미리보기: 화면 프리셋을 바꾸고 지금 화면을 새 크기로 다시 연다 (낚시 중이면 낚시터 처음 상태로)."""
        from src.platform import detect
        from src.platform.input import create_input
        self.save_now()
        self.sfx.stop_all()
        detect.set_preset(name)
        cfg = game_config()
        self.screen = PixelScreen(cfg["width"], cfg["height"], None, cfg["title"], detect.mobile_window())
        self.screen.overlay = self.preview.draw
        pygame.display.set_caption(self.preview.caption())
        self.input = create_input(self)
        self.scenes.stack.clear()
        if self.save is not None:
            from src.scene.menu import start_game
            start_game(self, self.save)
        else:
            from src.scene.menu import TitleScene
            self.scenes.push(TitleScene(self))

    def apply_audio_settings(self) -> None:
        """설정 → 믹서 버스 볼륨·신호 강조 (32장 S3)."""
        s = self.settings
        self.sfx.set_volumes(s.get("volume"), s.get("vol_music"), s.get("vol_sfx"), s.get("vol_amb"),
                             bool(s.get("signal_boost")))
        self.sfx.offset_s = s.get("audio_offset_ms") / 1000  # 진동·신호 소리 시각 보정 (S5)

    def slowmo(self, real_sec: float, scale: float) -> None:
        self.slow_timer = real_sec
        self.time_scale = scale

    def fade_in(self, sec: float = 0.5) -> None:
        """검은 화면에서 서서히 밝아지는 전환."""
        self.fade = self.fade_total = sec

    def to_canvas(self, pos) -> tuple[int, int]:
        x, y = self.screen.to_canvas(pos)
        return max(0, min(self.screen.width - 1, x)), max(0, min(self.screen.height - 1, y))

    def save_now(self) -> None:
        """현재 진행을 저장 (게임 씬의 상태를 먼저 기록)."""
        if self.save is None:
            return
        for scene in self.scenes.stack:
            if hasattr(scene, "write_save"):
                scene.write_save()
        self.save.save()
        self.autosave_t = 0.0

    def quit(self) -> None:
        self.save_now()
        self.running = False

    def run(self) -> None:
        accumulator = 0.0
        frames = 0
        while self.running:
            frame_time = min(self.clock.tick(self.frame_cap()) / 1000.0, MAX_FRAME_TIME)
            if self.slow_timer > 0:
                self.slow_timer -= frame_time
                if self.slow_timer <= 0:
                    self.time_scale = 1.0
            accumulator += frame_time * self.time_scale
            if self.save is not None:
                self.save.data["playtime"] += frame_time
                self.autosave_t += frame_time
                if self.autosave_t >= AUTOSAVE_SEC:
                    self.save_now()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.quit()
                elif self.preview is not None and self.preview.handle_event(event):
                    pass
                elif self.lifecycle.handle_event(event):
                    pass
                elif self.scenes.current:
                    self.scenes.current.handle_event(event)

            while accumulator >= self.tick_dt:
                if self.scenes.current:
                    self.scenes.current.update(self.tick_dt)
                accumulator -= self.tick_dt
            self.music.update()
            self.adaptive.update(frame_time, quiet=self.music.target is not None or self.music.current is not None)
            self.sfx.update(frame_time, slow=self.time_scale < 0.99)  # 믹서: 덕킹·리미터·버스 볼륨
            self.haptics.update(frame_time)  # 소리 어택에 맞춘 진동 (32장 S5)

            if self.scenes.current:
                self.scenes.current.draw(self.screen.canvas)
            if self.fade > 0:
                self.fade = max(0.0, self.fade - frame_time)
                veil = pygame.Surface(self.screen.canvas.get_size())
                veil.set_alpha(int(255 * self.fade / self.fade_total))
                self.screen.canvas.blit(veil, (0, 0))
            self.screen.present()

            frames += 1
            if self.max_frames is not None and frames >= self.max_frames:
                self.running = False

        pygame.quit()
