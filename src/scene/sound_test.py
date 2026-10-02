"""사운드 테스트 룸 (DESIGN.md 32장 S3): 게임 안 하고 소리만 들어 보며 다듬기.

- 왼쪽: 모든 소리 목록 (버스 탭으로 거르기, 휠·▲▼로 넘김). 누르면 재생, '×5'는 0.35초 간격 5번(변주 확인).
- 오른쪽 위: 지금 믹서 상태 (버스별 재생 중 수, 리미터, 덕킹).
- 오른쪽 아래: 상태 연동 소리 (src/audio/fight_audio.py) — 슬라이더로 값을 바꾸며 연속음 듣기.
설정 → 소리 → 사운드 테스트 룸.
"""
from src.scene.base import Scene
from src.ui import widgets as ui
from src.ui.hud import draw_cursor, text

BUSES = ("전체", "sig", "sfx", "reward", "mus", "amb", "ui")
ROWS = 12


class SoundTestScene(Scene):
    UI_FRAME = True

    def __init__(self, game):
        super().__init__(game)
        self.mouse = (0, 0)
        self.sfx = game.sfx
        self.tabs = ui.Tabs(14, 34, list(BUSES), width=30)
        self.top = 0
        self.queue: list[tuple[float, str]] = []
        self.t = 0.0
        self.last = ""
        try:
            from src.audio.fight_audio import FightAudio, SLIDERS
            self.fa = FightAudio(self.sfx)
            self.sliders = [dict(s, v=s["default"]) for s in SLIDERS]
        except ImportError:
            self.fa, self.sliders = None, []
        self.fa_on = False
        self.btn_back = ui.Button((404, 250, 64, 15), "뒤로", self._back)
        self.btn_up = ui.Button((212, 54, 18, 14), "▲", lambda: self._scroll(-ROWS))
        self.btn_dn = ui.Button((212, 236, 18, 14), "▼", lambda: self._scroll(ROWS))
        self.btn_fa = ui.Button((246, 120, 222, 15), "", self._toggle_fa)

    def names(self) -> list[str]:
        bus = BUSES[self.tabs.index]
        out = sorted(self.sfx.sounds) if self.sfx.enabled else []
        if bus != "전체":
            out = [n for n in out if self.sfx.bus_of(n) == bus]
        return out

    def _scroll(self, d: int) -> None:
        self.top = max(0, min(max(0, len(self.names()) - ROWS), self.top + d))

    def _back(self) -> None:
        if self.fa is not None:
            self.fa.stop()
        self.game.scenes.pop()

    def _toggle_fa(self) -> None:
        self.fa_on = not self.fa_on
        if not self.fa_on and self.fa is not None:
            self.fa.stop()

    def handle_action(self, a) -> None:
        if a.name == "back":
            self._back()
        elif a.name == "scroll":
            self._scroll(-int(a.value) * 3)
        elif a.name == "primary":
            m = a.pos
            if self.tabs.click(m):
                self.top = 0
                return
            for b in (self.btn_back, self.btn_up, self.btn_dn, self.btn_fa):
                if b.click(m):
                    return
            names = self.names()
            for i in range(ROWS):
                n = self.top + i
                if n >= len(names):
                    break
                y = 58 + i * 15
                if 14 <= m[0] <= 182 and y - 7 <= m[1] <= y + 7:
                    self.sfx.play(names[n])
                    self.last = names[n]
                    return
                if 186 <= m[0] <= 208 and y - 7 <= m[1] <= y + 7:
                    self.queue = [(self.t + k * 0.35, names[n]) for k in range(5)]
                    self.last = names[n]
                    return
            for s in self.sliders:
                x, y, w = s["rect"]
                if x <= m[0] <= x + w and y - 5 <= m[1] <= y + 5:
                    s["v"] = s["min"] + (s["max"] - s["min"]) * (m[0] - x) / w
                    return

    def update(self, dt: float) -> None:
        self.t += dt
        self.mouse = self.ui_pointer()
        due = [q for q in self.queue if q[0] <= self.t]
        self.queue = [q for q in self.queue if q[0] > self.t]
        for _, n in due:
            self.sfx.play(n)
        if self.fa is not None and self.fa_on:
            self.fa.update(dt, {s["key"]: s["v"] for s in self.sliders})

    def draw(self, canvas) -> None:
        under = self.scene_below()
        if under is not None:
            under.draw(canvas)
        ui.dim(canvas, 200)
        canvas = self.ui_canvas(canvas)
        ui.panel(canvas, (6, 6, 468, 260))
        text(canvas, "사운드 테스트 룸", (14, 18), ui.ACCENT, 16, "midleft")
        text(canvas, "누르면 재생 · ×5 = 변주 확인", (240, 18), ui.DIM, 11, "midleft")
        self.tabs.draw(canvas, self.mouse)
        names = self.names()
        for i in range(ROWS):
            n = self.top + i
            if n >= len(names):
                break
            name = names[n]
            y = 58 + i * 15
            hov = 14 <= self.mouse[0] <= 182 and y - 7 <= self.mouse[1] <= y + 7
            col = ui.ACCENT if name == self.last else (ui.TEXT if hov else (200, 206, 222))
            snd = self.sfx.sounds[name]
            text(canvas, name, (16, y), col, 11, "midleft")
            text(canvas, f"{snd.get_length():.1f}s", (180, y), ui.DIM, 11, "midright")
            text(canvas, "×5", (197, y), ui.GOOD, 11, "center")
        text(canvas, f"{self.top + 1}-{min(len(names), self.top + ROWS)} / {len(names)}", (120, 248), ui.DIM, 11,
             "center")
        for b in (self.btn_back, self.btn_up, self.btn_dn):
            b.draw(canvas, self.mouse)
        # 믹서 상태
        if self.sfx.enabled:
            st = self.sfx.stats()
            text(canvas, "믹서", (246, 44), ui.ACCENT, 11, "midleft")
            busy = " ".join(f"{k}:{v}" for k, v in st["busy"].items())
            text(canvas, busy, (246, 58), ui.TEXT, 11, "midleft")
            text(canvas, f"리미터 ×{st['limiter']}  덕킹 {st['duck'] or '-'}", (246, 72), ui.TEXT, 11, "midleft")
            if self.last:
                text(canvas, f"{self.last} → 버스 {self.sfx.bus_of(self.last)}", (246, 86), ui.DIM, 11, "midleft")
        # 상태 연동 소리
        if self.sliders:
            text(canvas, "상태 연동 (파이팅 연속음)", (246, 108), ui.ACCENT, 11, "midleft")
            self.btn_fa.label = "끄기" if self.fa_on else "켜고 슬라이더로 조절"
            self.btn_fa.draw(canvas, self.mouse)
            for i, s in enumerate(self.sliders):
                y = 148 + i * 18
                x, w = 330, 110
                s["rect"] = (x, y, w)
                text(canvas, s["label"], (246, y), ui.TEXT, 11, "midleft")
                k = (s["v"] - s["min"]) / (s["max"] - s["min"])
                ui.bar(canvas, (x, y - 3, w, 6), k, (140, 200, 255))
                text(canvas, f"{s['v']:.1f}", (x + w + 4, y), ui.DIM, 11, "midleft")
        draw_cursor(canvas, self.mouse)
