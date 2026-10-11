"""낚시터 사건 연출 (JOURNEY.md 🅰, DESIGN 54-4). 데이터 data/spot_events.json, 기록 src/save/spot_events.py.

낚시 화면 위에 겹쳐 그리는 30 ~ 40초 연출: 위아래 검은 띠 + 첫 3초 제목 + 자막(lines) + 건너뛰기.
draw_world = 물속 그림자 · 말뚝 · 결정처럼 낚싯대 · 전경보다 뒤 (FishingScene.draw 의 life.draw_world 다음),
draw_screen = 색 덮기 · 입자 · 번쩍 · 기울기 · 띠 · 자막 (HUD 위). 새 효과음 없음 — 기존 소리만 (cue).
다시 보기(집 '추억')는 처음 볼 때 남긴 낚시터 그림(save 폴더 events/) 위에 같은 연출.
"""
import math
import random

import pygame

from src.core.mathutil import lerp_color
from src.ui.hud import text, wrap_text

BAR = 22
GOLD = (255, 214, 90)


def _smooth(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


class EventPlayer:
    def __init__(self, spot_id: str, ev: dict, replay: bool = False):
        self.spot = spot_id
        self.ev = ev
        self.kind = ev["kind"]
        self.sec = float(ev["sec"])
        self.replay = replay
        self.t = 0.0
        self.done = False
        self.skipped = False
        self.cues: list[tuple[str, float]] = []   # (소리 이름, 볼륨) — 장면이 재생 (기존 소리)
        self._fired: set = set()
        rnd = random.Random(hash(spot_id) & 0xFFFF)
        self.pts = [(rnd.random(), rnd.random(), rnd.random(), rnd.random()) for _ in range(90)]
        self.skip_rect = pygame.Rect(0, 0, 0, 0)

    # ── 진행 ──
    @property
    def k(self) -> float:
        """들어가고 나오는 2초 페이드."""
        return min(_smooth(self.t / 2.0), _smooth((self.sec - self.t) / 2.0))

    def update(self, dt: float) -> None:
        self.t += dt
        for at, name, vol in CUES.get(self.kind, ()):
            if self.t >= at and (at, name) not in self._fired:
                self._fired.add((at, name))
                self.cues.append((name, vol))
        if self.t >= self.sec:
            self.done = True

    def skip(self) -> None:
        self.skipped = True
        self.done = True

    def shake(self) -> tuple[int, int]:
        amp = 0.0
        if self.kind == "ice_cracks" and 3.0 < self.t < 4.2 or self.kind == "ice_cracks" and 9.6 < self.t < 10.6:
            amp = 3.0
        elif self.kind == "storm_warning" and 11.0 < self.t < 12.0:
            amp = 3.5
        elif self.kind == "eruption" and 3.0 < self.t < 4.0:
            amp = 1.5
        if amp <= 0:
            return 0, 0
        return int(math.sin(self.t * 61) * amp), int(math.cos(self.t * 47) * amp)

    # ── 그리기 ──
    def draw_world(self, canvas, pal, cam) -> None:
        fn = getattr(self, "_w_" + self.kind, None)
        if fn:
            fn(canvas, pal, cam, canvas.get_width(), canvas.get_height(), cam.horizon if cam else canvas.get_height() * 0.42)

    def draw_screen(self, canvas, pal, cam=None) -> None:
        W, H = canvas.get_size()
        hz = cam.horizon if cam else H * 0.42
        fn = getattr(self, "_s_" + self.kind, None)
        if fn:
            fn(canvas, pal, cam, W, H, hz)
        self._bars(canvas, W, H)

    def _bars(self, canvas, W, H) -> None:
        b = int(BAR * _smooth(min(self.t / 0.8, (self.sec - self.t) / 0.8)))
        if b <= 0:
            return
        canvas.fill((0, 0, 0), (0, 0, W, b))
        canvas.fill((0, 0, 0), (0, H - b, W, b))
        if self.t < 4.0:   # 제목
            a = _smooth(min(self.t / 0.6, (4.0 - self.t) / 0.6))
            col = lerp_color((0, 0, 0), GOLD, a)
            from src.save.journey import spot_short
            text(canvas, f"{spot_short(self.spot)} · {self.ev['name']}", (W // 2, b // 2 + 1), col, 11, "center")
        line = None
        for at, who, s in self.ev["lines"]:
            if self.t >= at:
                line = (at, who, s)
        if line is not None:
            at, who, s = line
            a = _smooth((self.t - at) / 0.4)
            s2 = f"{who}: {s}" if who else s
            ln = wrap_text(s2, W - 40)[:1]
            if ln:
                text(canvas, ln[0], (W // 2, H - b // 2 - 1), lerp_color((0, 0, 0), (240, 236, 220), a), 11, "center")
        lab = "다시 보기 · 닫기 ▶" if self.replay else "건너뛰기 ▶"
        r = text(canvas, lab, (W - 8, b // 2 + 1), (150, 150, 160), 11, "midright")
        self.skip_rect = r.inflate(12, 8)

    def _tint(self, canvas, col, a: float) -> None:
        if a <= 0.01:
            return
        s = pygame.Surface(canvas.get_size(), pygame.SRCALPHA)
        s.fill((*col, int(255 * min(1.0, a))))
        canvas.blit(s, (0, 0))

    def _proj(self, cam, x, z, y=0.0):
        if cam is None:
            return None
        return cam.project(x, z, y)

    # ── 저수지: 할아버지의 첫 자리 — 말뚝 · 'ㅎ' 반짝 · 금빛 물결 ──
    def _w_first_seat(self, canvas, pal, cam, W, H, hz):
        p = self._proj(cam, -7.0, 11.0)
        if p is None:
            px, py, sc = W * 0.3, hz + (H - hz) * 0.45, 1.0
        else:
            px, py, sc = p[0], p[1], max(0.6, p[2] / 12)
        k = self.k
        h, w = int(26 * sc), max(3, int(4 * sc))
        wood = lerp_color(pal.get("water_top", (60, 90, 110)), (120, 92, 60), 0.85)
        pygame.draw.rect(canvas, wood, (int(px - w / 2), int(py - h), w, h))
        pygame.draw.rect(canvas, lerp_color(wood, (0, 0, 0), 0.3), (int(px - w / 2), int(py - h), w, h), 1)
        if self.t > 15.5:   # 'ㅎ' 새김이 반짝 (해강의 흔적 글자 모양 — 글꼴에 낱자가 없음)
            from src.render.grandpa_marks import GLYPH
            a = 0.5 + 0.5 * math.sin(self.t * 4)
            col = lerp_color(wood, GOLD, a * k)
            u = max(1, int(sc))
            gx, gy = int(px - 1.5 * u), int(py - h * 0.65)
            for cx, cy in GLYPH:
                canvas.fill(col, (gx + cx * u, gy + cy * u, u, u))
        for i in range(3):   # 말뚝 옆 금빛 물결
            ph = ((self.t * 0.45) + i / 3) % 1.0
            rw, rh = (6 + 28 * ph) * sc, (1.5 + 5 * ph) * sc
            col = lerp_color(pal.get("water_top", (60, 90, 110)), GOLD, (1 - ph) * k * (0.4 + 0.6 * _smooth((self.t - 20) / 3)))
            pygame.draw.ellipse(canvas, col, (px + 10 * sc - rw, py - rh, rw * 2, rh * 2), 1)

    # ── 계곡: 산군의 발자국 — 비가 그침 · 젖은 발자국 넷 · 안개 · 줄무늬 그림자 ──
    def _w_tracks(self, canvas, pal, cam, W, H, hz):
        k = self.k
        if 15.0 < self.t < 26.0:   # 상류로 지나가는 줄무늬 그림자
            u = (self.t - 15.0) / 11.0
            x = W * (0.15 + 0.7 * u)
            y = hz + (H - hz) * 0.18
            body = pygame.Surface((70, 14), pygame.SRCALPHA)
            pygame.draw.ellipse(body, (20, 24, 22, int(120 * k)), (0, 2, 70, 10))
            for i in range(5):
                pygame.draw.line(body, (60, 46, 22, int(110 * k)), (12 + i * 11, 3), (16 + i * 11, 11), 2)
            canvas.blit(body, (int(x - 35), int(y)))

    def _s_tracks(self, canvas, pal, cam, W, H, hz):
        k = self.k
        rain = max(0.0, 1.0 - self.t / 6.0)   # 비가 그침
        for i, (a, b, c, d) in enumerate(self.pts[:60]):
            if a > rain:
                continue
            x = (a * W + self.t * 40) % W
            y = (b * H + self.t * 300 * (0.7 + c)) % H
            pygame.draw.line(canvas, (170, 190, 210), (int(x), int(y)), (int(x - 2), int(y + 6)), 1)
        fog = pygame.Surface((W, 30), pygame.SRCALPHA)   # 안개 띠
        fog.fill((220, 228, 232, int(70 * k * _smooth((self.t - 12) / 4))))
        canvas.blit(fog, (0, int(hz)))
        for i in range(4):   # 발자국 넷 (전경 바위 → 물가)
            at = 7.0 + i * 1.6
            if self.t < at:
                continue
            a = _smooth((self.t - at) / 0.8) * k
            x, y = W * (0.12 + i * 0.07), H - BAR - 30 - i * 10
            col = lerp_color((90, 90, 86), (40, 44, 46), a)
            pygame.draw.ellipse(canvas, col, (x - 6, y - 3, 12, 8))
            for j in range(4):
                pygame.draw.circle(canvas, col, (int(x - 6 + j * 4), int(y - 6)), 2)

    # ── 방파제: 폭풍 경보 — 등대 빛 · 파도 · 번개 속 은빛 물고기 ──
    def _s_storm_warning(self, canvas, pal, cam, W, H, hz):
        k = self.k
        self._tint(canvas, (14, 18, 34), 0.45 * k)
        lx, ly = W * 0.86, hz - 18   # 등대 불빛이 바다를 훑음
        ang = self.t * 1.1
        beam = pygame.Surface((W, H), pygame.SRCALPHA)
        for s in (-1, 1):
            a0 = math.pi + math.sin(ang) * 0.9
            pts = [(lx, ly), (lx + math.cos(a0 - 0.06) * W, ly + math.sin(a0 - 0.06) * W * 0.2 * s),
                   (lx + math.cos(a0 + 0.06) * W, ly + math.sin(a0 + 0.06) * W * 0.2 * s)]
            pygame.draw.polygon(beam, (255, 240, 180, int(40 * k)), pts)
        canvas.blit(beam, (0, 0))
        pygame.draw.circle(canvas, (255, 240, 180), (int(lx), int(ly)), 3)
        if 11.0 < self.t < 12.2:   # 큰 파도: 화면 하얗게 한 번
            self._tint(canvas, (240, 246, 255), 1.0 - (self.t - 11.0) / 1.2)
        if 18.0 < self.t < 21.0:   # 번개 + 은빛 물고기
            f = 1.0 - (self.t - 18.0) / 3.0
            if self.t < 18.3:
                self._tint(canvas, (220, 228, 255), 0.6)
            x0 = W * 0.42
            pts = [(x0, 0), (x0 - 8, hz * 0.4), (x0 + 6, hz * 0.55), (x0 - 4, hz - 8)]
            pygame.draw.lines(canvas, (240, 240, 255), False, pts, 2)
            fx, fy = W * 0.55, hz - 14 - 18 * math.sin(min(1.0, (self.t - 18) / 1.5) * math.pi)
            pygame.draw.ellipse(canvas, lerp_color((40, 40, 60), (220, 230, 245), f), (fx - 14, fy - 3, 28, 7))
            pygame.draw.polygon(canvas, lerp_color((40, 40, 60), (220, 230, 245), f), [(fx + 12, fy), (fx + 20, fy - 5), (fx + 20, fy + 5)])

    # ── 먼바다: 첫 항해 — 고래 그림자 · 갈매기 떼 ──
    def _w_first_voyage(self, canvas, pal, cam, W, H, hz):
        if 6.0 < self.t < 22.0:
            u = (self.t - 6.0) / 16.0
            k = _smooth(min(u / 0.2, (1 - u) / 0.2))
            cx, cy = W * (1.15 - 1.3 * u), hz + (H - hz) * 0.72
            s = pygame.Surface((W, H), pygame.SRCALPHA)
            pygame.draw.ellipse(s, (6, 16, 30, int(150 * k)), (cx - 140, cy - 26, 280, 52))
            pygame.draw.polygon(s, (6, 16, 30, int(150 * k)), [(cx + 130, cy), (cx + 185, cy - 22), (cx + 175, cy), (cx + 185, cy + 22)])
            pygame.draw.ellipse(s, (6, 16, 30, int(120 * k)), (cx - 40, cy + 14, 50, 14))
            canvas.blit(s, (0, 0))

    def _s_first_voyage(self, canvas, pal, cam, W, H, hz):
        if 18.0 < self.t < 30.0:
            u = (self.t - 18.0) / 12.0
            for i, (a, b, c, d) in enumerate(self.pts[:14]):
                x = W * (-0.1 + 1.25 * u) - a * 90
                y = hz * (0.25 + 0.5 * b) + math.sin(self.t * 6 + i) * 2
                wing = 3 + int(2 * math.sin(self.t * 12 + i))
                pygame.draw.lines(canvas, (30, 34, 44), False, [(x - 4, y - wing + 3), (x, y), (x + 4, y - wing + 3)], 1)

    # ── 심해: 빛이 꺼진 곳 — 어둠 · 눈빛 · 아주 큰 눈 ──
    def _s_lights_out(self, canvas, pal, cam, W, H, hz):
        dark = _smooth((self.t - 1.0) / 2.0) * _smooth((self.sec - self.t) / 3.0)
        self._tint(canvas, (2, 4, 10), 0.9 * dark)
        n = int(min(1.0, max(0.0, (self.t - 7.0) / 8.0)) * 12)
        for i, (a, b, c, d) in enumerate(self.pts[:n]):
            x = W * a + math.sin(self.t * 0.4 + i) * 12
            y = hz + (H - hz - BAR) * (0.15 + 0.75 * b)
            blink = 0.0 if (self.t * 0.7 + c * 9) % 4.0 < 0.15 else 1.0
            col = lerp_color((2, 4, 10), (150, 230, 200) if d > 0.4 else (240, 200, 120), dark * blink)
            canvas.fill(col, (int(x), int(y), 2, 1))
            canvas.fill(col, (int(x + 5 + 3 * c), int(y), 2, 1))
        if 18.0 < self.t < 34.0:   # 아주 큰 눈 두 개가 천천히 감김
            u = (self.t - 18.0) / 16.0
            op = math.sin(min(1.0, u * 1.6) * math.pi / 2) * (1 - _smooth((u - 0.55) / 0.45))
            for ex in (W * 0.42, W * 0.58):
                ey = hz + 8
                pygame.draw.ellipse(canvas, lerp_color((2, 4, 10), (200, 220, 160), op * dark), (ex - 14, ey - 4 * op, 28, max(1, 8 * op)))
                if op > 0.3:
                    pygame.draw.ellipse(canvas, (10, 12, 8), (ex - 3, ey - 3 * op, 6, max(1, 6 * op)))

    # ── 용문 폭포: 잉어 떼의 등용 — 폭포를 거슬러 뛰는 잉어 ──
    def _s_carp_leap(self, canvas, pal, cam, W, H, hz):
        k = self.k
        top, bot = hz * 0.35, hz + 10
        for i, (a, b, c, d) in enumerate(self.pts[:26]):
            per = 2.2 + c * 1.6
            ph = (self.t + d * per * 3) % per / per
            x = W * (0.62 + 0.22 * a)
            reach = 0.25 + 0.35 * b
            y = bot - (bot - top) * reach * math.sin(ph * math.pi)
            col = lerp_color((60, 50, 40), (230, 160, 70), 0.6 * k)
            pygame.draw.ellipse(canvas, col, (x - 4, y - 2, 8, 4))
        if 15.0 < self.t < 22.0:   # 한 마리가 거의 끝까지 — 떨어짐
            u = (self.t - 15.0) / 7.0
            y = bot - (bot - top * 0.4) * math.sin(u * math.pi) * (0.98 if u < 0.5 else 1.0)
            x = W * 0.72 + math.sin(u * 7) * 2
            pygame.draw.ellipse(canvas, GOLD, (x - 5, y - 3, 11, 5))

    # ── 습지: 갈대의 노래 — 반딧불 · 한쪽으로 쓸리는 갈대 ──
    def _s_reed_song(self, canvas, pal, cam, W, H, hz):
        k = self.k
        self._tint(canvas, (10, 16, 40), 0.35 * k)
        for i, (a, b, c, d) in enumerate(self.pts[:40]):
            x = W * a + math.sin(self.t * 0.6 + i) * 8
            y = hz - 20 + (H - hz) * 0.8 * b + math.cos(self.t * 0.5 + c * 6) * 6
            on = 0.5 + 0.5 * math.sin(self.t * (1.5 + c) + d * 6)
            canvas.fill(lerp_color((20, 30, 30), (230, 250, 140), on * k), (int(x), int(y), 2, 2))
        sweep = _smooth((self.t - 9.0) / 4.0) * k   # 갈대가 한쪽으로
        for i in range(34):
            x = i * W / 33
            base = H - BAR
            lean = (10 + 6 * math.sin(self.t * 2.2 + i * 0.4)) * sweep
            pygame.draw.line(canvas, (40, 52, 46), (int(x), base), (int(x + lean), int(base - 34 - (i * 7) % 12)), 2)

    # ── 수정 동굴: 메아리 — '징' 고리 · 빛나는 결정 ──
    def _w_echo(self, canvas, pal, cam, W, H, hz):
        k = self.k
        p = self._proj(cam, -6.0, 14.0)
        px, py = (p[0], p[1]) if p else (W * 0.32, hz + 30)
        glow = _smooth((self.t - 9.0) / 2.0) * k
        col = lerp_color((120, 140, 190), (210, 240, 255), glow)
        pygame.draw.polygon(canvas, col, [(px, py - 30), (px + 7, py - 8), (px, py), (px - 7, py - 8)])
        pygame.draw.polygon(canvas, (60, 70, 110), [(px, py - 30), (px + 7, py - 8), (px, py), (px - 7, py - 8)], 1)
        if glow > 0.05:
            for i in range(3):
                ph = (self.t * 0.6 + i / 3) % 1.0
                pygame.draw.ellipse(canvas, lerp_color(pal.get("water_top", (60, 90, 110)), (200, 240, 255), (1 - ph) * glow),
                                    (px - 30 * ph - 4, py + 2 - 4 * ph, 60 * ph + 8, 8 * ph + 3), 1)

    def _s_echo(self, canvas, pal, cam, W, H, hz):
        for at in (3.0, 6.0, 9.0):   # 징 — 화면 고리
            if at < self.t < at + 2.0:
                u = (self.t - at) / 2.0
                pygame.draw.circle(canvas, lerp_color((40, 40, 60), (200, 230, 255), 1 - u), (W // 2, int(hz)), int(20 + 220 * u), 1)

    # ── 부유섬: 섬이 돈다 — 화면 10° 기울기 · 거꾸로 흐르는 물살 ──
    def _s_island_turns(self, canvas, pal, cam, W, H, hz):
        k = self.k
        tilt = 10.0 * _smooth((self.t - 2.0) / 6.0) * _smooth((self.sec - 3.0 - self.t) / 6.0)
        if tilt > 0.2:
            snap = canvas.copy()
            rot = pygame.transform.rotozoom(snap, tilt, 1.0 + tilt / 60)
            canvas.blit(rot, (W // 2 - rot.get_width() // 2, H // 2 - rot.get_height() // 2))
        flow = _smooth((self.t - 9.0) / 3.0) * k
        for i, (a, b, c, d) in enumerate(self.pts[:24]):   # 물살이 거꾸로 (오른쪽 → 왼쪽 위로)
            x = (W * a - self.t * 60 * (0.6 + c)) % W
            y = hz + (H - hz - BAR) * b
            pygame.draw.line(canvas, lerp_color((40, 60, 80), (200, 230, 250), 0.6 * flow), (int(x), int(y)), (int(x + 10), int(y + 2)), 1)

    # ── 화산: 작은 분화 — 붉은 번쩍 · 재 · 회색 수면 · 김 ──
    def _s_eruption(self, canvas, pal, cam, W, H, hz):
        k = self.k
        vx, vy = W * 0.2, hz - 6
        if self.t > 2.5:   # 분화 빛
            g = _smooth((self.t - 2.5) / 1.0) * (0.4 + 0.6 * _smooth((8.0 - self.t) / 4.0)) * k
            s = pygame.Surface((W, H), pygame.SRCALPHA)
            pygame.draw.circle(s, (255, 90, 40, int(110 * g)), (int(vx), int(vy)), 40)
            pygame.draw.circle(s, (255, 190, 90, int(150 * g)), (int(vx), int(vy)), 12)
            canvas.blit(s, (0, 0))
            for i, (a, b, c, d) in enumerate(self.pts[:12]):   # 터져 오르는 불씨
                u = ((self.t - 2.5) * (0.5 + c)) % 3.0 / 3.0
                x = vx + (a - 0.5) * 60 * u
                y = vy - 50 * math.sin(u * math.pi) * (0.6 + b)
                canvas.fill(lerp_color((80, 30, 20), (255, 160, 60), (1 - u) * k), (int(x), int(y), 2, 2))
        gray = _smooth((self.t - 9.0) / 4.0) * k   # 재 · 회색 수면
        s = pygame.Surface((W, int(H - hz)), pygame.SRCALPHA)
        s.fill((120, 118, 116, int(90 * gray)))
        canvas.blit(s, (0, int(hz)))
        for i, (a, b, c, d) in enumerate(self.pts[20:80]):
            x = (W * a + math.sin(self.t + i) * 10) % W
            y = (H * b + self.t * 14 * (0.5 + c)) % H
            canvas.fill(lerp_color((40, 40, 40), (170, 166, 160), gray), (int(x), int(y), 1, 1))
        if self.t > 16.0:   # 김
            st = _smooth((self.t - 16.0) / 3.0) * k
            for i in range(6):
                x = W * (0.2 + 0.12 * i) + math.sin(self.t * 0.8 + i) * 6
                y = hz + 10 - ((self.t * 6 + i * 13) % 30)
                pygame.draw.circle(canvas, lerp_color((90, 90, 96), (220, 220, 225), 0.4 * st), (int(x), int(y)), 4, 1)
        if self.t > 24.0:   # 불꽃 비늘 반짝
            a = 0.5 + 0.5 * math.sin(self.t * 6)
            pygame.draw.polygon(canvas, lerp_color((120, 50, 30), (255, 140, 60), a * k),
                                [(W * 0.5, H - BAR - 22), (W * 0.5 + 5, H - BAR - 17), (W * 0.5, H - BAR - 12), (W * 0.5 - 5, H - BAR - 17)])

    # ── 빙해: 얼음이 갈라진다 — 금 · 흔들림 · 하얗게 · 새 자리 (오로라 없음) ──
    def _s_ice_cracks(self, canvas, pal, cam, W, H, hz):
        k = self.k
        grow = _smooth((self.t - 3.0) / 6.0)
        x, y = W * 0.5, H - BAR - 4
        pts = [(x, y)]
        for i, (a, b, c, d) in enumerate(self.pts[:10]):
            x += (a - 0.5) * 50
            y -= 6 + 10 * b
            if (i + 1) / 10 > grow:
                break
            pts.append((x, y))
        if len(pts) > 1 and self.t < 10.0:
            pygame.draw.lines(canvas, (230, 245, 255), False, pts, 2)
            pygame.draw.lines(canvas, (90, 130, 160), False, [(px + 1, py + 1) for px, py in pts], 1)
        if 9.6 < self.t < 11.6:   # 건너뜀: 하얗게
            u = (self.t - 9.6) / 2.0
            self._tint(canvas, (240, 248, 255), math.sin(u * math.pi))
        if self.t > 11.6:   # 새 자리: 얼음 아래가 더 깊고 맑다
            self._tint(canvas, (20, 60, 90), 0.18 * k * _smooth((self.t - 11.6) / 3.0))

    # ── 세계수: 할아버지의 마지막 흔적 — 뿌리 · 샘 · 낡은 찌 ──
    def _s_last_trace(self, canvas, pal, cam, W, H, hz):
        k = self.k
        root = lerp_color((30, 26, 20), (70, 58, 40), 0.5)
        for side in (-1, 1):   # 양옆 뿌리
            x0 = W * (0.5 + side * 0.5)
            pts = [(x0, BAR), (x0 - side * 60, H * 0.35), (x0 - side * 30, H * 0.6), (x0 - side * 80, H - BAR)]
            pygame.draw.lines(canvas, root, False, pts, int(10 * k) + 1)
        g = _smooth((self.t - 2.0) / 3.0) * k   # 샘 빛
        s = pygame.Surface((W, H), pygame.SRCALPHA)
        pygame.draw.ellipse(s, (180, 240, 220, int(60 * g)), (W * 0.35, hz + 20, W * 0.3, 26))
        canvas.blit(s, (0, 0))
        if self.t > 9.0:   # 뿌리에 걸린 낡은 찌 (대나무색 띠 + 빨간 점)
            a = _smooth((self.t - 9.0) / 1.5) * k
            fx, fy = W * 0.68, H * 0.32 + math.sin(self.t * 1.2) * 2
            pygame.draw.line(canvas, lerp_color(root, (200, 200, 190), a), (fx, fy - 18), (fx, fy - 7), 1)
            pygame.draw.ellipse(canvas, lerp_color(root, (214, 206, 186), a), (fx - 3, fy - 7, 7, 14))
            canvas.fill(lerp_color(root, (168, 138, 86), a), (int(fx - 3), int(fy - 1), 7, 3))
            pygame.draw.circle(canvas, lerp_color(root, (190, 80, 70), a), (int(fx), int(fy - 6)), 1)
            if self.t > 16.0:
                r = 6 + 3 * math.sin(self.t * 3)
                pygame.draw.circle(canvas, lerp_color(root, GOLD, 0.5 * a), (int(fx), int(fy)), int(r), 1)


# 기존 소리만 (새 효과음 없음): (초, 소리, 볼륨)
CUES = {
    "first_seat": ((15.5, "st_paper", 0.4),),
    "storm_warning": ((11.0, "sfx_splash", 0.8), (18.0, "amb_thunder_near", 0.7)),
    "first_voyage": ((24.0, "sfx_splash", 0.4),),
    "lights_out": ((1.0, "ui_click", 0.3),),
    "echo": ((3.0, "sfx_chord_legend", 0.25), (6.0, "sfx_chord_legend", 0.18), (9.0, "sfx_chord_legend", 0.12)),
    "eruption": ((2.5, "sfx_splash", 0.5),),
    "ice_cracks": ((3.0, "sfx_splash", 0.5), (9.6, "sfx_splash", 0.6)),
    "last_trace": ((16.0, "st_paper", 0.4),),
}
