"""환상 포획 연출 테스트 룸 (DESIGN.md 33-11 V5): 실제로 낚지 않고 연출·음악만 골라 다시 보기.

종(12) × 버전(full·short·extended) × 대륙 곡(샤르미온·엘드라시온) 을 고르고 '재생'.
도감·보상·저장에는 아무것도 남지 않는다 (보상 아이콘은 보기용 가짜).
설정 → 접근성 → 테스트: 환상 포획 연출.
"""
import random

import pygame

from src.core.config import load_json
from src.core.mathutil import lerp_color
from src.fishing import phantom
from src.scene.base import Scene
from src.ui import widgets as ui
from src.ui.hud import draw_cursor, text

VARIANTS = (("full", "첫 포획 (8초)"), ("short", "다시 잡음 (4초)"), ("extended", "12종 완성 (11초)"))
CONTS = (("sharmion", "샤르미온 곡"), ("eldrasion", "엘드라시온 곡"))
FAKE_NEWS = {
    "full": {"phantom_new": True, "chest": "rare", "phantom_scales": 3, "blessing": True},
    "short": {"phantom_scales": 1},
    "extended": {"phantom_new": True, "chest": "legend", "phantom_scales": 5, "blessing": True, "phantom_gold": 500,
                 "phantom_rewards": ["환상을 낚은 자"]},
}


class PhantomShowTestScene(Scene):
    UI_FRAME = True

    def __init__(self, game):
        super().__init__(game)
        self.mouse = (0, 0)
        self.fish_list = phantom.all_phantoms()
        self.fi, self.vi = 0, 0
        spots = {s["id"]: s for s in load_json("spots.json")["spots"]}
        self.ci = 0
        self._spots = spots
        self._pick_cont()
        self.show = None
        self.song_ch = None
        self.loop_ch = None
        self.btn_prev = ui.Button((120, 40, 18, 16), "◀", lambda: self._fish(-1))
        self.btn_next = ui.Button((342, 40, 18, 16), "▶", lambda: self._fish(1))
        self.btn_var = ui.Button((140, 64, 200, 16), "", self._variant)
        self.btn_cont = ui.Button((140, 86, 200, 16), "", self._cont)
        self.btn_play = ui.Button((180, 120, 120, 22), "재생", self._play)
        self.btn_back = ui.Button((404, 250, 64, 15), "뒤로", self._back)

    # ── 고르기 ──
    def _pick_cont(self) -> None:
        sp = self._spots.get(self.fish_list[self.fi]["spot"], {})
        self.ci = 1 if sp.get("continent") == "eldrasion" else 0

    def _fish(self, d: int) -> None:
        self.fi = (self.fi + d) % len(self.fish_list)
        self._pick_cont()

    def _variant(self) -> None:
        self.vi = (self.vi + 1) % len(VARIANTS)

    def _cont(self) -> None:
        self.ci = (self.ci + 1) % len(CONTS)

    # ── 재생 ──
    def _play(self) -> None:
        from src.audio import phantom_song
        from src.render.phantom_show import PhantomShow
        self._stop_audio(0)
        f = self.fish_list[self.fi]
        variant, cont = VARIANTS[self.vi][0], CONTS[self.ci][0]
        sfx = self.game.sfx
        w, h = self.game.screen.canvas.get_size()
        lo, hi = f.get("size_cm", [50, 80])
        delay = getattr(sfx, "latency", 0.0) + getattr(sfx, "offset_s", 0.0)
        self.show = PhantomShow(f, {"size": round(random.uniform(lo, hi), 1)}, dict(FAKE_NEWS[variant]), variant, w, h,
                                mobile=self.game.input.kind == "touch",
                                reduce=self.game.settings.get("reduce_fx"), delay=delay)
        sfx.duck_levels({"mus": -60, "amb": -40, "sfx": -18}, hold=0.5, release=0.15)
        name = phantom_song.preload(sfx, variant, cont)
        self.song_ch = sfx.play(name, 1.0) if name else None
        self.loop_ch = None

    def _stop_audio(self, ms: int = 400) -> None:
        for ch in (self.song_ch, self.loop_ch):
            if ch is not None:
                ch.fadeout(ms) if ms else ch.stop()
        self.song_ch = self.loop_ch = None

    def _close_show(self) -> None:
        self._stop_audio()
        self.show = None

    def _back(self) -> None:
        self._stop_audio(0)
        self.game.scenes.pop()

    # ── 입력·시간 ──
    def handle_action(self, a) -> None:
        if a.name == "back":
            if self.show is not None:
                self._close_show()
            else:
                self._back()
        elif a.name == "primary":
            if self.show is not None:
                if self.show.waiting():
                    self._close_show()
                elif self.show.can_skip():
                    self.show.skip()
                return
            for b in (self.btn_prev, self.btn_next, self.btn_var, self.btn_cont, self.btn_play, self.btn_back):
                if b.click(a.pos):
                    self.game.sfx.play("ui_click")
                    break

    def update(self, dt: float) -> None:
        self.mouse = self.ui_pointer()
        sh = self.show
        if sh is None:
            return
        sfx = self.game.sfx
        for ev in sh.update(dt):
            if ev.startswith("icon:"):
                sfx.play(f"sfx_phantom_icon{min(3, int(ev.split(':')[1]))}", 0.6)
            elif ev in ("wait", "skip"):
                if ev == "skip" and self.song_ch is not None:
                    self.song_ch.fadeout(300)
                if self.loop_ch is None:
                    from src.audio import phantom_song
                    name = phantom_song.preload(sfx, "loop", CONTS[self.ci][0])
                    if name:
                        self.loop_ch = sfx.play(name, 0.55)
                        if self.loop_ch is not None:
                            self.loop_ch.play(sfx.sounds[name], loops=-1, fade_ms=600)
        sfx.duck_levels({"mus": -60, "amb": -40, "sfx": -18}, hold=0.3, release=0.15)

    # ── 그리기 ──
    def _backdrop(self, canvas) -> None:
        w, h = canvas.get_size()
        hz = int(h * 0.62)
        for y in range(0, h, 2):
            if y < hz:
                c = lerp_color((60, 34, 120), (150, 96, 200), y / hz)
            else:
                c = lerp_color((60, 44, 130), (22, 14, 56), (y - hz) / max(1, h - hz))
            canvas.fill(c, (0, y, w, 2))
        pygame.draw.line(canvas, (190, 160, 240), (0, hz), (w, hz))

    def draw(self, canvas) -> None:
        self._backdrop(canvas)
        if self.show is not None:
            self.show.draw(canvas, {})
            return
        ui_c = self.ui_canvas(canvas)
        w = ui_c.get_width()
        box = pygame.Rect(100, 14, 280, 156)
        ui_c.fill((14, 8, 28), box)
        pygame.draw.rect(ui_c, phantom.COLOR, box, 1)
        text(ui_c, "환상 포획 연출 테스트", (w // 2, 22), phantom.COLOR_LIGHT, 11, "center")
        f = self.fish_list[self.fi]
        text(ui_c, f"{self.fi + 1}/{len(self.fish_list)}  {f['name']}", (w // 2, 43), (235, 225, 255), 11, "center")
        self.btn_var.label = VARIANTS[self.vi][1]
        self.btn_cont.label = CONTS[self.ci][1]
        for b in (self.btn_prev, self.btn_next, self.btn_var, self.btn_cont, self.btn_play, self.btn_back):
            b.draw(ui_c, self.mouse)
        text(ui_c, "재생 중 클릭: 건너뛰기·닫기 (기록 안 남음)", (w // 2, 156), (170, 160, 200), 11, "center")
        draw_cursor(ui_c, self.mouse)
