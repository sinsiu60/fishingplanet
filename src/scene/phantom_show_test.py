"""포획 연출 테스트 룸 (DESIGN.md 33-11 V5 · 34장 L3): 실제로 낚지 않고 환상·전설 포획 연출과 음악만 골라 다시 보기.

[환상] 12종 × full·short·extended, [전설] 12종 × full·short·final(최종 보스) × 대륙 곡 을 고르고 '재생'.
'비교 (환상→전설→환상)' = 두 연출을 연달아 (희귀함 차이 확인용).
도감·보상·저장·엔딩에는 아무것도 남지 않는다 (보상 아이콘은 보기용 가짜).
설정 → 접근성 → 테스트: 포획 연출.
"""
import random

import pygame

from src.core.config import load_json
from src.core.mathutil import lerp_color
from src.fishing import phantom
from src.scene.base import Scene
from src.ui import widgets as ui
from src.ui.hud import draw_cursor, text

KINDS = ("phantom", "legend")
VARIANTS = {
    "phantom": (("full", "첫 포획 (8초)"), ("short", "다시 잡음 (4초)"), ("extended", "12종 완성 (11초)")),
    "legend": (("full", "첫 포획 (5초)"), ("short", "다시 잡음 (2.5초)"), ("final", "최종 보스 (5초 → 엔딩)")),
}
CONTS = (("sharmion", "샤르미온 곡"), ("eldrasion", "엘드라시온 곡"))
FAKE_NEWS = {
    "phantom": {
        "full": {"phantom_new": True, "chest": "rare", "phantom_scales": 3, "blessing": True},
        "short": {"phantom_scales": 1},
        "extended": {"phantom_new": True, "chest": "legend", "phantom_scales": 5, "blessing": True, "phantom_gold": 500,
                     "phantom_rewards": ["환상을 낚은 자"]},
    },
    "legend": {
        "full": {"new": True, "chest": "special", "trophy": 12000, "legend_scales": 5},
        "short": {"chest": "rare", "legend_scales": 2},
        "final": {"new": True, "chest": "legend", "trophy": 30000, "legend_scales": 5},
    },
}


class PhantomShowTestScene(Scene):
    UI_FRAME = True

    def __init__(self, game):
        super().__init__(game)
        self.mouse = (0, 0)
        self.lists = {"phantom": phantom.all_phantoms(),
                      "legend": [f for f in load_json("fish.json")["fish"] if f.get("rarity") == "legend"]}
        self.final_fish = load_json("legend_catch_timeline.json")["final_fish"]
        self.kind = "phantom"
        self.idx = {"phantom": 0, "legend": 0}
        self.vi = 0
        self._spots = {s["id"]: s for s in load_json("spots.json")["spots"]}
        self.ci = 0
        self._pick_cont()
        self.show = None
        self.song_ch = None
        self.loop_ch = None
        self.queue: list[tuple[str, int, str]] = []
        self.wait_t = 0.0
        self.btn_kind = ui.Button((140, 30, 200, 15), "", self._toggle_kind)
        self.btn_prev = ui.Button((120, 50, 18, 16), "◀", lambda: self._fish(-1))
        self.btn_next = ui.Button((342, 50, 18, 16), "▶", lambda: self._fish(1))
        self.btn_var = ui.Button((140, 72, 200, 16), "", self._variant)
        self.btn_cont = ui.Button((140, 92, 200, 16), "", self._cont)
        self.btn_play = ui.Button((150, 116, 80, 20), "재생", self._play)
        self.btn_cmp = ui.Button((236, 116, 104, 20), "비교 환→전→환", self._compare)
        self.btn_back = ui.Button((404, 250, 64, 15), "뒤로", self._back)
        self.buttons = (self.btn_kind, self.btn_prev, self.btn_next, self.btn_var, self.btn_cont, self.btn_play,
                        self.btn_cmp, self.btn_back)

    # ── 고르기 ──
    @property
    def fish(self) -> dict:
        return self.lists[self.kind][self.idx[self.kind]]

    def _variants(self) -> tuple:
        v = VARIANTS[self.kind]
        if self.kind == "legend" and self.fish["id"] not in self.final_fish:
            v = v[:2]
        return v

    def _pick_cont(self) -> None:
        sp = self._spots.get(self.fish["spot"], {})
        self.ci = 1 if sp.get("continent") == "eldrasion" else 0

    def _toggle_kind(self) -> None:
        self.kind = KINDS[(KINDS.index(self.kind) + 1) % len(KINDS)]
        self.vi = 0
        self._pick_cont()

    def _fish(self, d: int) -> None:
        self.idx[self.kind] = (self.idx[self.kind] + d) % len(self.lists[self.kind])
        self.vi = min(self.vi, len(self._variants()) - 1)
        self._pick_cont()

    def _variant(self) -> None:
        self.vi = (self.vi + 1) % len(self._variants())

    def _cont(self) -> None:
        self.ci = (self.ci + 1) % len(CONTS)

    # ── 재생 ──
    def _play(self) -> None:
        self._start(self.kind, self.fish, self._variants()[self.vi][0], CONTS[self.ci][0])

    def _compare(self) -> None:
        """환상 → 전설 → 환상 (첫 포획 버전) 연달아."""
        ph, lg = self.lists["phantom"][self.idx["phantom"]], self.lists["legend"][self.idx["legend"]]
        self.queue = [("legend", lg, "full"), ("phantom", ph, "full")]
        self._start("phantom", ph, "full", self._cont_of(ph))

    def _cont_of(self, f: dict) -> str:
        return "eldrasion" if self._spots.get(f["spot"], {}).get("continent") == "eldrasion" else "sharmion"

    def _start(self, kind: str, f: dict, variant: str, cont: str) -> None:
        self._stop_audio(0)
        sfx = self.game.sfx
        w, h = self.game.screen.canvas.get_size()
        lo, hi = f.get("size_cm", [50, 80])
        kw = dict(mobile=self.game.input.kind == "touch", reduce=self.game.settings.get("reduce_fx"),
                  delay=getattr(sfx, "latency", 0.0) + getattr(sfx, "offset_s", 0.0),
                  low=getattr(self.game, "slow_device", False) or self.game.settings.get("fps") == 30)
        result = {"size": round(random.uniform(lo, hi), 1), "rank": "S"}
        if kind == "phantom":
            from src.audio import phantom_song as song
            from src.render.phantom_show import PhantomShow as Show
        else:
            from src.audio import legend_song as song
            from src.render.legend_show import LegendShow as Show
        self.show = Show(f, result, dict(FAKE_NEWS[kind][variant]), variant, w, h, **kw)
        self.song_mod, self.cont_now = song, cont
        sfx.duck_levels({"mus": -60, "amb": -40, "sfx": -18}, hold=0.5, release=0.15)
        name = song.preload(sfx, variant, cont)
        self.song_ch = sfx.play(name, 1.0) if name else None
        self.loop_ch = None
        self.wait_t = 0.0

    def _stop_audio(self, ms: int = 400) -> None:
        for ch in (self.song_ch, self.loop_ch):
            if ch is not None:
                ch.fadeout(ms) if ms else ch.stop()
        self.song_ch = self.loop_ch = None

    def _close_show(self) -> None:
        self._stop_audio()
        self.show = None
        if self.queue:
            kind, f, variant = self.queue.pop(0)
            self._start(kind, f, variant, self._cont_of(f))

    def _back(self) -> None:
        self._stop_audio(0)
        self.game.scenes.pop()

    # ── 입력·시간 ──
    def handle_action(self, a) -> None:
        if a.name == "back":
            if self.show is not None:
                self.queue.clear()
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
            for b in self.buttons:
                if b.click(a.pos):
                    self.game.sfx.play("ui_click")
                    break

    def update(self, dt: float) -> None:
        self.mouse = self.ui_pointer()
        sh = self.show
        if sh is None:
            return
        sfx = self.game.sfx
        icon = "sfx_legend_icon" if sh.kind == "legend" else "sfx_phantom_icon"
        for ev in sh.update(dt):
            if ev.startswith("icon:"):
                sfx.play(f"{icon}{min(3, int(ev.split(':')[1]))}", 0.6)
            elif ev in ("wait", "skip"):
                if ev == "skip" and self.song_ch is not None:
                    self.song_ch.fadeout(300)
                if self.loop_ch is None:
                    name = self.song_mod.preload(sfx, "loop", self.cont_now)
                    if name:
                        self.loop_ch = sfx.play(name, 0.55)
                        if self.loop_ch is not None:
                            self.loop_ch.play(sfx.sounds[name], loops=-1, fade_ms=600)
        if sh.waiting() and self.queue:   # 비교 재생: 카드 대기 1.2초 뒤 다음 연출
            self.wait_t += dt
            if self.wait_t > 1.2:
                self._close_show()
        sfx.duck_levels({"mus": -60, "amb": -40, "sfx": -18}, hold=0.3, release=0.15)

    # ── 그리기 ──
    def _backdrop(self, canvas) -> None:
        w, h = canvas.get_size()
        hz = int(h * 0.62)
        legend = self.show is not None and self.show.kind == "legend"
        sky = ((70, 100, 160), (170, 160, 170)) if legend else ((60, 34, 120), (150, 96, 200))
        sea = ((50, 80, 120), (20, 30, 56)) if legend else ((60, 44, 130), (22, 14, 56))
        for y in range(0, h, 2):
            if y < hz:
                c = lerp_color(sky[0], sky[1], y / hz)
            else:
                c = lerp_color(sea[0], sea[1], (y - hz) / max(1, h - hz))
            canvas.fill(c, (0, y, w, 2))
        pygame.draw.line(canvas, (200, 190, 220), (0, hz), (w, hz))

    def draw(self, canvas) -> None:
        self._backdrop(canvas)
        if self.show is not None:
            self.show.draw(canvas, {})
            return
        ui_c = self.ui_canvas(canvas)
        w = ui_c.get_width()
        box = pygame.Rect(100, 8, 280, 162)
        ui_c.fill((14, 8, 28), box)
        legend = self.kind == "legend"
        accent = (255, 205, 90) if legend else phantom.COLOR
        pygame.draw.rect(ui_c, accent, box, 1)
        text(ui_c, "포획 연출 테스트", (w // 2, 15), (255, 236, 170) if legend else phantom.COLOR_LIGHT, 11, "center")
        self.btn_kind.label = "종류: 전설 (금)" if legend else "종류: 환상 (보라)"
        n = len(self.lists[self.kind])
        text(ui_c, f"{self.idx[self.kind] + 1}/{n}  {self.fish['name']}", (w // 2, 53), (235, 225, 255), 11, "center")
        self.vi = min(self.vi, len(self._variants()) - 1)
        self.btn_var.label = self._variants()[self.vi][1]
        self.btn_cont.label = CONTS[self.ci][1]
        for b in self.buttons:
            b.draw(ui_c, self.mouse)
        text(ui_c, "재생 중 클릭: 건너뛰기·닫기 (기록 안 남음)", (w // 2, 150), (170, 160, 200), 11, "center")
        draw_cursor(ui_c, self.mouse)
