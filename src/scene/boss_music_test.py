"""전설·환상 전용 BGM 테스트 (DESIGN.md 43, BOSS_BGM.md B5 디버그).

설정 → 접근성 → 테스트: 전설·환상 음악. 곡(L01~L12 · P01~P12)과 페이즈를 골라 바로 재생하고
위기·지침·실패·성공(전설 → 전설의 노래 / 환상 → 정적 0.35초 → 환상의 노래)을 눌러서 일으킨다. 기록은 안 남음.
"""
from src.core.config import load_json
from src.scene.base import Scene
from src.ui import widgets as ui
from src.ui.hud import draw_cursor, text

HUSH = 0.35   # 환상: 숨 멎음 정적 (PHANTOM_CATCH_SHOW)


def _names() -> dict:
    out = {}
    fl = load_json("fish.json")
    for f in (fl["fish"] if isinstance(fl, dict) else fl):
        out[f["id"]] = (f["name"], None)
    for f in load_json("phantom.json")["fish"]:
        out[f["id"]] = (f["name"], f.get("spot"))
    for f in (fl["fish"] if isinstance(fl, dict) else fl):
        if f.get("rarity") == "legend":
            sp = f.get("spot") or (f.get("spots") or [None])[0]
            out[f["id"]] = (f["name"], sp)
    return out


class BossMusicTestScene(Scene):
    UI_FRAME = True

    def __init__(self, game):
        super().__init__(game)
        self.boss = game.boss
        songs = self.boss.cfg.get("boss", {}).get("songs", {})
        self.ids = [k for k, v in songs.items() if not v.get("test")]
        self.names = _names()
        self.si = 0
        self.phase = 0
        self.crisis = False
        self.after = None      # (남은 초, 소리 이름) — 환상 성공: 정적 뒤 노래
        self.msg = ""
        self.mouse = (0, 0)
        y = 82
        self.btns = [ui.Button((110, 46, 18, 16), "◀", lambda: self._song(-1)),
                     ui.Button((352, 46, 18, 16), "▶", lambda: self._song(1)),
                     ui.Button((110, y, 84, 18), "재생 (인트로)", self._play),
                     ui.Button((198, y, 84, 18), "다음 페이즈", self._next_phase),
                     ui.Button((286, y, 84, 18), "위기", self._crisis),
                     ui.Button((110, y + 22, 84, 18), "지침 (2마디)", self._tired),
                     ui.Button((198, y + 22, 84, 18), "실패", self._fail),
                     ui.Button((286, y + 22, 84, 18), "성공", self._win),
                     ui.Button((198, y + 44, 84, 18), "정지", self._stop),
                     ui.Button((404, 250, 64, 15), "뒤로", self._back)]

    # ── 곡 ──
    def _sid(self) -> str:
        return self.ids[self.si] if self.ids else ""

    def _spec(self) -> dict:
        return self.boss.spec(self._sid()) or {}

    def _cont(self) -> str:
        fid = self._spec().get("fish")
        spot = self.names.get(fid, ("", None))[1]
        from src.audio.music_synth import spot_continent
        return spot_continent(spot) if spot else "sharmion"

    def _song(self, d) -> None:
        self._stop()
        self.si = (self.si + d) % max(1, len(self.ids))

    def _play(self) -> None:
        self.after = None
        self.phase = 0
        self.crisis = False
        if not self.boss.start(self._sid()):
            self.msg = "구운 파일이 없어요 (python tools/bake_boss.py)"
        else:
            self.msg = ""

    def _next_phase(self) -> None:
        if self.boss.active:
            self.phase = min(self.phase + 1, len(self._spec().get("phases", [1])) - 1)
            self.boss.set_phase(self.phase)

    def _crisis(self) -> None:
        self.crisis = not self.crisis
        self.boss.set_crisis(self.crisis)

    def _tired(self) -> None:
        self.boss.tired()

    def _fail(self) -> None:
        self.boss.fail()

    def _win(self) -> None:
        sfx = self.game.sfx
        sid, cont = self._sid(), self._cont()
        if self._spec().get("kind") == "phantom":
            from src.audio import phantom_song
            self.boss.stop()                       # 즉시 완전히 멈춤 → 정적
            name = phantom_song.preload(sfx, "full", cont)
            self.after = (HUSH, name) if name else None
        else:
            from src.audio import legend_song
            name = legend_song.preload(sfx, "full", cont, sid)
            self.boss.stop(fade_ms=150)            # 같은 조성 첫 타격음이 이어받음
            if name:
                sfx.play(name, 1.0)

    def _stop(self) -> None:
        self.after = None
        self.boss.stop(300)

    def _back(self) -> None:
        self._stop()
        self.game.scenes.pop()

    # ── 화면 ──
    def handle_action(self, a):
        if a.name == "back":
            self._back()
        elif a.name == "primary":
            for b in self.btns:
                if b.click(a.pos):
                    self.game.sfx.play("ui_click")
                    break

    def update(self, dt):
        self.mouse = self.ui_pointer()
        if self.after is not None:
            t, name = self.after
            t -= dt
            if t <= 0:
                self.game.sfx.play(name, 1.0)
                self.after = None
            else:
                self.after = (t, name)

    def draw(self, canvas):
        below = self.scene_below()
        if below is not None:
            below.draw(canvas)
        ui.dim(canvas, 170)
        c = self.ui_canvas(canvas)
        ui.panel(c, (100, 20, 280, 160))
        text(c, "전설·환상 음악 테스트", (240, 30), ui.ACCENT, 11, "center")
        sp = self._spec()
        name = self.names.get(sp.get("fish"), ("?", None))[0]
        kind = "전설" if sp.get("kind") == "legend" else "환상"
        text(c, f"{self._sid()}  {kind} · {name}", (240, 54), ui.TEXT, 11, "center")
        num, den = sp.get("meter", [4, 4])
        text(c, f"{sp.get('bpm', '?')} BPM · {num}/{den} · 페이즈 {len(sp.get('phases', []))}개", (240, 68), ui.DIM, 9, "center")
        self.btns[4].label = "위기 끄기" if self.crisis else "위기"
        for b in self.btns:
            b.draw(c, self.mouse)
        d = self.boss.debug()
        if self.boss.active:
            st = f"재생 중 · 페이즈 {d['phase']} · 마디 {d['bar'] if d['bar'] is not None else '-'}" + \
                 (" · 위기" if d["crisis"] else "") + (" · 지침(옥타브)" if d["tired"] else "")
        else:
            st = self.msg or ("정적…" if self.after else "멈춤")
        text(c, st, (240, 156), ui.ACCENT if self.boss.active else ui.DIM, 10, "center")
        draw_cursor(c, self.mouse)
