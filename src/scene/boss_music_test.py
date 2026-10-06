"""전설·환상 전용 BGM 테스트 (DESIGN.md 43, BOSS_BGM.md B5 디버그 · BOSS_BGM_SUNO.md 보스 곡 테스트).

설정 → 접근성 → 테스트: 전설·환상 음악. 전설 12종(SUNO 곡 — 없으면 합성 곡) · 환상 12곡을 골라 바로 재생하고
페이즈 전환·위기·실패·포획 성공(전설 SUNO → 다음 박 타격 + 카드 시각 표시 / 합성 전설 → 전설의 노래 / 환상 → 정적 → 환상의 노래)을
버튼으로 일으킨다. 기록은 안 남음.
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
        # 전설은 물고기마다 하나(SUNO 가 있으면 그 곡, 없으면 합성 곡), 환상은 합성 곡 그대로
        legends, seen = [], set()
        for sid, v in songs.items():
            if v.get("test") or v.get("kind") != "legend" or v.get("fish") in seen:
                continue
            seen.add(v["fish"])
            legends.append(self.boss.song_for(v["fish"]) or sid)
        self.ids = legends + [k for k, v in songs.items() if not v.get("test") and v.get("kind") != "legend"]
        self.card_t = None     # SUNO 포획: (타격까지 남은 초, impact, card) 표시용
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
        self.card_t = None
        sid = self._sid()
        if not self.boss.available(sid):
            self.msg = "구운 파일이 없어요 (python tools/bake_boss.py)"
            self.pending = None
            return
        self.boss.prepare(sid)
        if self.boss.start(sid):
            self.msg = ""
            self.pending = None
        else:   # 파일을 읽는 중 (기다리지 않음, O5) — update 가 다 읽히면 시작
            self.msg = "불러오는 중…"
            self.pending = sid

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
        if self.boss.is_suno(sid):
            if not self.boss.suno.active:
                return
            info = self.boss.catch_info(sid)
            wait = self.boss.catch()
            self.card_t = [wait + info.get("impact_sec", 0.0), info.get("card_sec", 0.0) - info.get("impact_sec", 0.0), 0.0]
            self.msg = f"타격까지 {wait:.2f}초 ({'즉시' if info.get('start') == 'immediate' else '다음 박'})"
            return
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
        pend = getattr(self, "pending", None)
        if pend is not None and pend == self._sid():
            if self.boss.start(pend):
                self.msg = ""
                self.pending = None
        if self.card_t is not None:
            self.card_t[2] += dt
            if self.card_t[2] >= self.card_t[0] + self.card_t[1] + 2.0:
                self.card_t = None
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
        suno = self.boss.is_suno(self._sid())
        text(c, f"{self._sid()}  {kind} · {name}" + ("  [SUNO]" if suno else ""), (240, 54), ui.TEXT, 11, "center")
        num, den = sp.get("meter", [4, 4])
        text(c, f"{sp.get('bpm', '?')} BPM · {num}/{den} · 페이즈 {len(sp.get('phases', []))}개", (240, 68), ui.DIM, 9, "center")
        self.btns[4].label = "위기 끄기" if self.crisis else "위기"
        for b in self.btns:
            b.draw(c, self.mouse)
        d = self.boss.debug()
        if self.boss.active:
            st = f"재생 중 · 페이즈 {d['phase']} · 마디 {d['bar'] if d['bar'] is not None else '-'}" + \
                 (f" · {d['file']}" if d.get("file") else "") + (" · 위기" if d["crisis"] else "") + (" · 지침(옥타브)" if d["tired"] else "")
        else:
            st = self.msg or ("정적…" if self.after else "멈춤")
        if self.card_t is not None:
            el, hit, card = self.card_t[2], self.card_t[0], self.card_t[0] + self.card_t[1]
            stage = "쾅!" if hit <= el < card else ("포획 카드" if el >= card else "…")
            text(c, f"포획: 타격 {hit:.2f}s · 카드 {card:.2f}s · 지금 {el:.2f}s  {stage}", (240, 142), ui.ACCENT, 9, "center")
        text(c, st, (240, 156), ui.ACCENT if self.boss.active else ui.DIM, 10, "center")
        draw_cursor(c, self.mouse)
