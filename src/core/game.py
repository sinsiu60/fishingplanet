"""메인 루프. 게임 로직은 초당 60틱 고정, 렌더링은 그와 분리된다."""
import time

import pygame

from src.render.screen import opaque as _opaque

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
    def __init__(self, max_frames: int | None = None, start_scene=None, audio: bool = True):
        cfg = game_config()
        from src.platform.detect import IS_MOBILE as _mob
        from src.core.config import load_json as _lj
        from src.core import bootlog
        _ac = _lj("audio_config.json")
        pygame.mixer.pre_init(44100, -16, 2, _ac["buffer_mobile"] if _mob else _ac["buffer_pc"])
        pygame.init()
        bootlog.mark(f"pygame {pygame.version.ver} init · mixer {pygame.mixer.get_init()}")
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
        bootlog.mark(f"화면 {self.screen.canvas.get_size()} · {self.screen.fmt_note} · 입력 {self.input.kind}")
        if self.screen.mobile:
            self._loading_frame()
            from src.platform.detect import IS_ANDROID
            if IS_ANDROID:
                from src.platform import android
                android.keep_screen_on()
        bootlog.mark("효과음 불러오기")
        self.sfx = Sfx(audio=audio)
        bootlog.mark(f"효과음 {len(self.sfx.sounds)}개 (실행 중 합성 {len(getattr(self.sfx, 'missing_baked', []))})")
        self.sfx.haptics = self.haptics  # play(..., haptic=종류) → 소리 어택 순간에 진동
        self.apply_audio_settings()
        self.music = Music(self.sfx)  # data/music/ 의 파일 (없으면 무음)
        from src.audio.adaptive_music import AdaptiveMusic
        self.adaptive = AdaptiveMusic(self.sfx)  # 적응형 음악 층 (32장 S6)
        bootlog.mark("음악 준비")
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
        from src.core import gcwatch
        gcwatch.install()
        gcwatch.settle(collect=True)  # 시작 때 만든 객체는 GC 가 다시 훑지 않게 (v0.8.10)
        bootlog.mark("첫 장면")

    def _perf_profile_draw(self) -> None:
        """성능 표시 켜짐: 10초마다 30프레임 동안 그리기를 cProfile 로 재서 오래 걸린 함수 8개를 화면에 (기기에서 원인 찾기)."""
        now = time.perf_counter()
        st = getattr(self, "_prof_state", None)
        if st is None:
            st = self._prof_state = {"next": now + 2.0, "prof": None, "n": 0, "lines": []}
        if st["prof"] is None and now >= st["next"]:
            import cProfile
            st["prof"], st["n"] = cProfile.Profile(), 0
        if st["prof"] is None:
            self.scenes.current.draw(self.screen.canvas)
            return
        st["prof"].enable()
        try:
            self.scenes.current.draw(self.screen.canvas)
        finally:
            st["prof"].disable()
        st["n"] += 1
        if st["n"] >= 30:
            import pstats
            stats = pstats.Stats(st["prof"]).stats
            rows = sorted(stats.items(), key=lambda kv: -kv[1][2])[:8]
            tot = sum(v[2] for v in stats.values()) / st["n"] * 1000
            st["lines"] = [f"프로파일 합계 {tot:6.2f}ms/프레임 (그리기 시간과 차이 = 파이썬 함수 밖)"] + [f"{v[2] / st['n'] * 1000:6.2f}ms {v[1] // st['n']:5d}회 "
                           f"{k[0].replace(chr(92), '/').split('/')[-1]}:{k[1]} {k[2]}" for k, v in rows]
            # 가장 오래 걸린 것이 blit 같은 C 함수면 어디서 불렀는지 (위 3곳)
            top = rows[0][1][4] if rows and rows[0][0][0] == "~" else {}
            for ck, cv in sorted(top.items(), key=lambda kv: -kv[1][3])[:3]:
                st["lines"].insert(2, f"   └ {cv[3] / st['n'] * 1000:6.2f}ms {cv[0] / st['n']:4.1f}회 "
                                      f"{ck[0].replace(chr(92), '/').split('/')[-1]}:{ck[1]} {ck[2]}")
            st["prof"], st["next"] = None, now + 10.0

    @staticmethod
    def _rss_mb() -> float:
        try:
            with open("/proc/self/statm") as f:
                import os
                return int(f.read().split()[1]) * os.sysconf("SC_PAGE_SIZE") / 1e6
        except Exception:
            return 0.0

    def _perf_draw(self, frame_time: float, ticks: int, upd: float, audio: float, draw: float) -> None:
        """설정 '성능 표시': 화면 왼쪽 위에 FPS 와 단계별 처리 시간(ms, 평균) — 폰 렉 원인 찾기 (v0.8.8)."""
        p = getattr(self, "_perf", None)
        cur = [1.0 / max(frame_time, 1e-4), upd * 1000, audio * 1000, draw * 1000, ticks]
        self._perf = cur if p is None else [a * 0.9 + b * 0.1 for a, b in zip(p, cur)]
        fps, u, a, d, tk = self._perf
        from src.ui.hud import text
        c = self.screen.canvas
        line = (f"FPS {fps:4.1f}  갱신 {u:4.1f}(×{tk:.1f})  소리 {a:4.1f}  그리기 {d:4.1f}  "
                f"출력 {getattr(self, '_perf_present', 0.0):4.1f}ms  일 {getattr(self, '_work_ms', 0):4.1f}")
        import gc
        self._perf_tick = getattr(self, "_perf_tick", 0) + 1
        if self._perf_tick % 60 == 1:
            self._perf_objs = len(gc.get_objects())  # 파이썬 객체 수 (1초에 한 번) — 계속 늘면 무언가 쌓이는 중
        from src.core import gcwatch
        now = time.perf_counter()
        g = getattr(self, "_gc_win", None)
        if g is None or now - g[0] >= 1.0:  # 1초 창: GC 에 쓴 시간·횟수·가장 긴 한 번
            if g is not None:
                span = now - g[0]
                self._gc_line = (f"GC {(gcwatch.total - g[1]) / span * 1000:5.1f}ms/초 {(gcwatch.count - g[2]) / span:4.1f}회/초 "
                                 f"최장 {gcwatch.take_longest() * 1000:4.1f}ms")
            self._gc_win = (now, gcwatch.total, gcwatch.count)
        extra = [f"메모리 {self._rss_mb():5.0f}MB  객체 {getattr(self, '_perf_objs', 0)}  얼림 {gc.get_freeze_count()}  "
                 f"{getattr(self, '_gc_line', 'GC -')}", self.screen.fmt_note]
        lines = [line] + extra + list(getattr(self, "_prof_state", {}).get("lines", []))
        from src.core.fonts import get_font
        font = get_font(11)
        for i, ln in enumerate(lines):
            w = font.size(ln)[0] + 6
            c.fill((0, 0, 0), (0, i * 12, min(c.get_width(), w), 12))
            text(c, ln, (3, 6 + i * 12), (140, 255, 160) if i < len(extra) + 1 else (255, 220, 120), 11, "midleft")

    def _loading_frame(self) -> None:
        """모바일 첫 실행은 효과음을 만드느라 몇 초 걸려서 안내 화면을 먼저 보여 준다."""
        from src.ui.hud import text
        c = self.screen.canvas
        c.fill((12, 16, 30))
        text(c, "준비 중...", (c.get_width() // 2, c.get_height() // 2), (220, 226, 240), 16, "center")
        try:  # 가끔 환상의 물고기 소문 한 줄 (33장 P6)
            from src.fishing.phantom import rumor
            line = rumor()
            if line:
                text(c, line, (c.get_width() // 2, c.get_height() // 2 + 26), (190, 160, 235), 11, "center")
        except Exception:
            pass
        self.screen.present()

    def frame_cap(self) -> int:
        """PC = 설정 파일 값 그대로. 모바일 = 설정 30/60, 메뉴 화면은 늘 30 (배터리). 로직은 언제나 초당 60틱."""
        if not self.screen.mobile:
            return self.fps_cap
        from src.scene.fishing_scene import FishingScene
        if not isinstance(self.scenes.current, FishingScene):
            return 30
        fps = self.settings.get("fps")
        if fps >= 60 and getattr(self, "slow_device", False):
            return 30  # 60을 못 버티는 폰: 들쭉날쭉한 40fps 보다 고른 30fps 가 덜 끊겨 보인다 (v0.8.7)
        return fps

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
            if self.screen.mobile:
                # 한 프레임 일한 시간(대기 제외) 평균: 20ms 넘으면 60fps 무리 → 30fps, 12ms 아래면 다시 60
                work = getattr(self, "_work_ms", 10.0) * 0.95 + self.clock.get_rawtime() * 0.05
                self._work_ms = work
                if work > 20.0:
                    self.slow_device = True
                elif work < 12.0:
                    self.slow_device = False
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

            perf = self.settings.get("perf_overlay")
            t0 = time.perf_counter() if perf else 0.0
            ticks = 0
            while accumulator >= self.tick_dt:
                if self.scenes.current:
                    self.scenes.current.update(self.tick_dt)
                accumulator -= self.tick_dt
                ticks += 1
            t1 = time.perf_counter() if perf else 0.0
            self.music.update()
            self.adaptive.update(frame_time, quiet=self.music.target is not None or self.music.current is not None)
            self.sfx.update(frame_time, slow=self.time_scale < 0.99)  # 믹서: 덕킹·리미터·버스 볼륨
            self.haptics.update(frame_time)  # 소리 어택에 맞춘 진동 (32장 S5)
            t2 = time.perf_counter() if perf else 0.0

            if self.scenes.current:
                if perf:
                    self._perf_profile_draw()
                else:
                    self.scenes.current.draw(self.screen.canvas)
            if self.fade > 0:
                self.fade = max(0.0, self.fade - frame_time)
                veil = _opaque(self.screen.canvas.get_size())
                veil.set_alpha(int(255 * self.fade / self.fade_total))
                self.screen.canvas.blit(veil, (0, 0))
            if perf:
                t3 = time.perf_counter()
                self._perf_draw(frame_time, ticks, t1 - t0, t2 - t1, t3 - t2)
            self.screen.present()
            if perf:
                self._perf_present = (self._perf_present * 0.9 + (time.perf_counter() - t3) * 100) \
                    if hasattr(self, "_perf_present") else 0.0

            frames += 1
            if frames in (1, 30):
                from src.core import bootlog
                bootlog.mark(f"프레임 {frames}")
            elif frames == 90:
                from src.core import bootlog
                bootlog.done()  # 여기까지 오면 시작 성공
            if self.max_frames is not None and frames >= self.max_frames:
                self.running = False

        pygame.quit()
