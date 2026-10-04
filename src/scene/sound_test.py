"""사운드 테스트 룸 (DESIGN.md 32장 S3): 게임 안 하고 소리만 들어 보며 다듬기.

- 왼쪽: 모든 소리 목록 (버스 탭으로 거르기, 휠·▲▼로 넘김). 누르면 재생, '×5'는 0.35초 간격 5번(변주 확인).
- 오른쪽 위: 지금 믹서 상태 (버스별 재생 중 수, 리미터, 덕킹).
- 오른쪽 아래 (페이지 버튼으로 바꿈):
  연속음  상태 연동 소리 (src/audio/fight_audio.py) — 감기 속도·장력 슬라이더로 릴 루프 구간(slow/normal/fast, 장력 높으면 한 단계 느리게)
          전환 확인, '돌진' = 돌진 시뮬레이션 (zing_rise → loop_fast → 정점 drag_fast → reel_stop).
  성공음  등급(small·mid·big·퍼펙트)·연속 단계(0~2)별 재생, 퍼펙트·더블 퍼펙트는 노란 빛과 같이 (impact_ms 싱크 확인).
- 맨 아래: 적응형 음악 상황 바꿔 듣기 (S6) — 장력 슬라이더 = 파이팅 타악 세기.
설정 → 소리 → 사운드 테스트 룸.
"""
from src.scene.base import Scene
from src.ui import widgets as ui
from src.ui.hud import draw_cursor, text

BUSES = ("전체", "sig", "자연", "sfx", "reward", "mus", "amb", "ui")  # 자연 = 자연음 신호·보조음 (SOUND_CLEANUP N2)
ROWS = 12
SPACES = (("breakwater", "바다"), ("reservoir", "야외"), ("crystal_cave", "동굴"), ("deep", "심해"))  # 릴 시뮬레이터 공간 (N5)
MUS_STATES = ("끔", "idle", "bite", "fight", "fight+위기", "fight_big", "tired", "fight_calm", "legend", "legend_tired",
              "win", "fail", "menu")


class SoundTestScene(Scene):
    UI_FRAME = True

    def __init__(self, game):
        super().__init__(game)
        self.mouse = (0, 0)
        self.sfx = game.sfx
        self.tabs = ui.Tabs(14, 34, list(BUSES), width=27)
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
        self._space0 = getattr(self.sfx, "space_spot", None)
        self.btn_back = ui.Button((404, 250, 64, 15), "뒤로", self._back)
        self.btn_up = ui.Button((212, 54, 18, 14), "▲", lambda: self._scroll(-ROWS))
        self.btn_dn = ui.Button((212, 236, 18, 14), "▼", lambda: self._scroll(ROWS))
        self.btn_fa = ui.Button((246, 120, 222, 15), "", self._toggle_fa)
        self.mus_i = 0
        self.btn_mus = ui.Button((246, 250, 150, 15), "", self._next_mus)
        self.page = 0   # 0 연속음 / 1 성공음
        self.btn_page = ui.Button((380, 102, 88, 13), "", self._next_page)
        # 소리 구역 (DESIGN.md 39): 장소(바깥 마을 ↔ 실내 5곳) · 날씨 · 천둥
        zc = game.zones.cfg["zones"]
        self.zone_ids = [z for z in zc if zc[z].get("name")]
        self.zone_i = 0
        self.weathers = [("clear", "맑음"), ("rain", "비"), ("storm", "폭풍"), ("fog", "안개")]
        self.weather_i = 0
        self.btn_zone = ui.Button((246, 124, 222, 15), "", self._next_zone)
        self.btn_weather = ui.Button((246, 144, 110, 15), "", self._next_weather)
        self.btn_thunder = ui.Button((360, 144, 108, 15), "천둥 (폭풍)", lambda: game.zones.force_thunder())
        self.btn_zone_off = ui.Button((246, 164, 222, 15), "구역 시험 끄기", self._zone_off)
        self.btn_rush = ui.Button((404, 222, 64, 13), "돌진", self._rush_sim)
        self.rush_t = -1.0
        self.glow: list[float] = []      # 노란 빛 미리보기 시작 시각 (self.t)
        self.succ_btns = []
        grades = (("small", "작은"), ("mid", "중간"), ("big", "큰"), ("big_pop", "퍼펙트"))
        for r, (g, lab) in enumerate(grades):
            for k in range(3):
                self.succ_btns.append(ui.Button((300 + k * 42, 124 + r * 17, 40, 14), f"{k}", lambda g=g, k=k: self._succ(g, k)))
        self.succ_btns.append(ui.Button((246, 196, 108, 14), "퍼펙트 + 노란 빛", lambda: self._succ("big_pop", 0)))
        self.succ_btns.append(ui.Button((358, 196, 110, 14), "더블 퍼펙트 + 빛", lambda: self._succ("double_pop", 0)))
        self.succ_labels = [lab for _, lab in grades]

    def names(self) -> list[str]:
        bus = BUSES[self.tabs.index]
        out = sorted(self.sfx.sounds) if self.sfx.enabled else []
        if bus == "자연":
            out = [n for n in out if n.startswith(("sig_nat_", "sig_aux_"))]
        elif bus != "전체":
            out = [n for n in out if self.sfx.bus_of(n) == bus]
        return out

    def _scroll(self, d: int) -> None:
        self.top = max(0, min(max(0, len(self.names()) - ROWS), self.top + d))

    def _back(self) -> None:
        self._zone_off()
        self._back2()

    def _back2(self) -> None:
        if self.fa is not None:
            self.fa.stop()
        if getattr(self, "_space", None) is not None and self._space != self._space0:
            self.sfx.set_space(self._space0)  # 릴 시뮬레이터에서 바꾼 공간을 낚시터 것으로 되돌림
        self.game.scenes.pop()

    def _next_mus(self) -> None:
        self.mus_i = (self.mus_i + 1) % len(MUS_STATES)
        self.phase = 0

    def _mus(self) -> None:
        """음악 상황 강제 (끔이면 원래 장면이 정한 대로)."""
        if self.mus_i == 0:
            return
        am = self.game.adaptive
        st = MUS_STATES[self.mus_i]
        crisis = st.endswith("+위기")
        st = st.split("+")[0]
        cont, spot = (am.ctx or am.ctx_next or ("sharmion", "reservoir", False))[:2]
        am.set_context(cont, None if st == "menu" else (spot or "reservoir"), st.startswith("legend"))
        ten = next((v["v"] for v in self.sliders if v["key"] == "tension"), 50.0)
        am.set(st, (ten - 30) / 45, 2, 1.0, crisis=crisis)

    def _rush_sim(self) -> None:
        """돌진 시뮬레이션: 줄 풀림 0 → 1 (0.8초) → 유지 0.5초 → 0 (1초), 시작 zing_rise · 정점 drag_fast · 끝 reel_stop."""
        if self.fa is None:
            return
        self.fa_on = True
        self.rush_t = 0.0
        self.fa.reel.rush_begin()

    def _succ(self, grade: str, k: int) -> None:
        """성공음 재생 + 퍼펙트·더블이면 노란 빛을 impact_ms(+ 오디오 지연 보정) 에 (게임과 같은 계산)."""
        from src.audio import reel_audio
        self.sfx.play(reel_audio.success_name(grade, k))
        self.last = reel_audio.success_name(grade, k)
        info = reel_audio.success_info(grade, k)
        off = self.game.settings.get("audio_offset_ms") / 1000.0
        if grade in ("big_pop", "double_pop"):
            self.glow_sec = reel_audio.manifest().get("perfect_effect", {}).get("glow_duration_ms", 300) / 1000
            self.glow.append(self.t + max(0.0, info["impact_ms"] / 1000 + off))
            if grade == "double_pop":
                self.glow.append(self.t + max(0.0, (info["second_impact_ms"] or 460) / 1000 + off))
            self.game.haptics.vibrate("perfect", 1.0, delay=max(0.0, info["impact_ms"] / 1000 + off))

    def _next_page(self) -> None:
        self.page = (self.page + 1) % 3
        if self.page != 2:
            self._zone_off()

    def _zone_test(self) -> None:
        self.game.zones.test = {"zone": self.zone_ids[self.zone_i], "weather": self.weathers[self.weather_i][0]}

    def _next_zone(self) -> None:
        self.zone_i = (self.zone_i + 1) % len(self.zone_ids)
        self._zone_test()

    def _next_weather(self) -> None:
        self.weather_i = (self.weather_i + 1) % len(self.weathers)
        self._zone_test()

    def _zone_off(self) -> None:
        self.game.zones.test = None

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
            for b in (self.btn_back, self.btn_up, self.btn_dn, self.btn_mus, self.btn_page):
                if b.click(m):
                    return
            zb = [self.btn_zone, self.btn_weather, self.btn_thunder, self.btn_zone_off]
            for b in ([self.btn_fa, self.btn_rush] if self.page == 0 else self.succ_btns if self.page == 1 else zb):
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
            for s in (self.sliders if self.page == 0 else []):
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
            vals = {s["key"]: s["v"] for s in self.sliders}
            if self.rush_t >= 0:   # 돌진 시뮬레이션: 줄 풀림 곡선, 감기 멈춤
                self.rush_t += dt
                rt = self.rush_t
                vals["payout"] = min(1.0, rt / 0.8) if rt < 1.3 else max(0.0, 1 - (rt - 1.3) / 1.0)
                vals["reel"] = 0.0
                if rt >= 2.3:
                    self.rush_t = -1.0
                    self.fa.reel.rush_end()
            sp = SPACES[int(round(vals.get("space", 0)))][0]
            if sp != getattr(self, "_space", None):  # 공간 바꾸면 그 공간 버전으로 다시 읽음
                self._space = sp
                self.sfx.set_space(sp)
            self.fa.update(dt, vals)
        self._mus()

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
        self.btn_mus.label = f"음악: {MUS_STATES[self.mus_i]}"
        for b in (self.btn_back, self.btn_up, self.btn_dn, self.btn_mus):
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
        # 노란 빛 미리보기 (퍼펙트·더블 퍼펙트 — 게임과 같은 impact_ms·glow 시간)
        for g0 in list(self.glow):
            u = (self.t - g0) / getattr(self, "glow_sec", 0.3)
            if u >= 1:
                self.glow.remove(g0)
            elif u >= 0:
                a = 0.8 * (u / 0.2 if u < 0.2 else (1 - u) / 0.8)
                import pygame
                gl = pygame.Surface((222, 30), pygame.SRCALPHA)
                gl.fill((255, 226, 110, int(220 * a)))
                canvas.blit(gl, (246, 216))
        self.btn_page.label = ("▶ 성공음", "▶ 소리 구역", "▶ 연속음")[self.page]
        self.btn_page.draw(canvas, self.mouse)
        if self.page == 2:
            z = self.game.zones
            text(canvas, "소리 구역 (실내/바깥 전환)", (246, 108), ui.ACCENT, 11, "midleft")
            zid = self.zone_ids[self.zone_i]
            zc = z.cfg["zones"][zid]
            kind = "실내" if zc.get("type") == "indoor" else "바깥"
            self.btn_zone.label = f"장소: {zc['name']} ({kind}) ▶"
            self.btn_weather.label = f"날씨: {self.weathers[self.weather_i][1]} ▶"
            for b in (self.btn_zone, self.btn_weather, self.btn_thunder, self.btn_zone_off):
                b.draw(canvas, self.mouse)
            on = "시험 중" if z.test else "꺼짐 (게임 장면 그대로)"
            text(canvas, f"{on} · 실내 섞임 {self.sfx.indoor:.2f} · 바깥 음악 ×{self.game.adaptive.zone_gain:.2f}",
                 (246, 186), ui.TEXT, 11, "midleft")
            loops = ", ".join(sorted(n.replace("amb_", "").replace("room_", "") for n in self.sfx.loops))
            from src.ui.hud import wrap_text
            for i, ln in enumerate(wrap_text("반복: " + (loops or "-"), 220)[:3]):
                text(canvas, ln, (246, 200 + i * 12), ui.DIM, 11, "midleft")
        if self.page == 1:
            text(canvas, "성공음 (등급 × 연속 단계)", (246, 108), ui.ACCENT, 11, "midleft")
            for r, lab in enumerate(self.succ_labels):
                text(canvas, lab, (250, 131 + r * 17), ui.TEXT, 11, "midleft")
            for b in self.succ_btns:
                b.draw(canvas, self.mouse)
            text(canvas, "노란 빛 = 소리의 '팡'과 같은 순간이어야 함", (246, 228), ui.DIM, 11, "midleft")
        # 상태 연동 소리
        if self.sliders and self.page == 0:
            text(canvas, "상태 연동 (파이팅 연속음)", (246, 108), ui.ACCENT, 11, "midleft")
            self.btn_fa.label = "끄기" if self.fa_on else "켜고 슬라이더로 조절"
            self.btn_fa.draw(canvas, self.mouse)
            self.btn_rush.draw(canvas, self.mouse)
            for i, s in enumerate(self.sliders):
                y = 143 + i * 13
                x, w = 330, 110
                s["rect"] = (x, y, w)
                text(canvas, s["label"], (246, y), ui.TEXT, 11, "midleft")
                k = (s["v"] - s["min"]) / (s["max"] - s["min"])
                ui.bar(canvas, (x, y - 3, w, 6), k, (140, 200, 255))
                text(canvas, f"{s['v']:.1f}", (x + w + 4, y), ui.DIM, 11, "midleft")
            if self.fa is not None and self.fa_on:  # 연속음 주인공 (N3) — 장력·줄 풀림 슬라이더로 바뀌는 것 확인
                names = {"reel": "감기", "payout": "줄 풀림", "thrash": "첨벙", "yellow": "노란 구간", "red": "빨강"}
                y = 143 + len(self.sliders) * 13
                sv = {x["key"]: x["v"] for x in self.sliders}
                space = SPACES[int(round(sv.get("space", 0)))][1]
                r = self.fa.reel
                band = {"slow": "느림", "normal": "보통", "fast": "빠름", "run": "줄 풀림", "tease": "예고"}.get(r.band, "-")
                if r.band == "normal":
                    band += " A" if r.ab == 0 else " B"
                text(canvas, f"주인공 {names.get(self.fa.focus, self.fa.focus)} · 릴 {band}{' 무겁게' if r.heavy else ''} · {space}",
                     (246, y), ui.ACCENT, 11, "midleft")
        draw_cursor(canvas, self.mouse)
