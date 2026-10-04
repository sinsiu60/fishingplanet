"""스토리 컷신 (STORY.md 표의 시간·좌표·색·자막·소리 그대로, 내부 해상도 480x270 · 넓은 화면은 가운데 + 배경색으로 채움).

CutsceneScene(sid): P-01~P-04 · C3-02 · C5-04 · 클로즈업(C1-06 손잡이) — 오른쪽 위 '건너뛰기' (이름 입력·선택은 없음).
ChoiceScene: C5-05 [ 놓아준다 ] [ 어탁으로 남긴다 ] (건너뛰기 없음). EpilogueScene: E-01.
"""
import math
import random

import pygame

from src.scene.base import Scene
from src.story import story
from src.story import ui as sui
from src.ui.hud import draw_cursor, text


def _c(h: str) -> tuple:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _black(canvas, a: float, col=(0, 0, 0)) -> None:
    if a <= 0:
        return
    s = pygame.Surface(canvas.get_size())
    s.fill(col)
    s.set_alpha(int(255 * min(1.0, a)))
    canvas.blit(s, (0, 0))


class Frame:
    """480x270 장면을 화면 가운데에 (화면비가 달라도 좌표 그대로)."""

    def __init__(self, canvas):
        w, h = canvas.get_size()
        self.ox, self.oy = (w - 480) // 2, (h - 270) // 2
        self.c = canvas

    def r(self, x0, y0, x1, y1) -> pygame.Rect:
        return pygame.Rect(self.ox + x0, self.oy + y0, x1 - x0, y1 - y0)

    def p(self, x, y) -> tuple[int, int]:
        return self.ox + int(x), self.oy + int(y)


# ───────────────────────── 장면별 그림 ─────────────────────────
def draw_p01(canvas, t: float, sc: dict) -> None:
    canvas.fill(_c("#1C2230"))
    f = Frame(canvas)
    canvas.fill(_c("#2A2F3A"), (0, f.oy + 199, canvas.get_width(), 3))          # 책상 가로선 y=200, 두께 3
    mon = f.r(140, 60, 340, 180)
    canvas.fill(_c("#C9D3E0"), mon)
    for x in range(mon.x, mon.right, 10):
        canvas.fill(_c("#9AA6B8"), (x, mon.y, 1, mon.h))
    for y in range(mon.y, mon.bottom, 10):
        canvas.fill(_c("#9AA6B8"), (mon.x, y, mon.w, 1))
    for i, (x0, x1) in enumerate(((100, 200), (280, 380))):                    # 형광등 2개
        on = True
        if i == 1 and 3.0 <= t < 3.8:                                           # 오른쪽 형광등 0.2초 간격 2번 깜빡
            on = int((t - 3.0) / 0.2) % 2 == 1
        if on:
            canvas.fill(_c("#E8F0FF"), f.r(x0, 12, x1, 16))
    text(canvas, sc["clock"], f.p(462, 34), (255, 255, 255), 11, "midright")   # 시계 (오른쪽 위, 건너뛰기 버튼 아래)
    for i, (at, msg) in enumerate(zip((1.0, 1.8, 2.6), sc["alerts"])):         # 알림 상자가 하나씩 쌓임
        if t >= at:
            from src.core.fonts import get_font
            r = pygame.Rect(0, 0, get_font(11).size(msg)[0] + 10, 16)   # 모니터 오른쪽 아래에 맞춰
            r.right = mon.right - 4
            r.bottom = f.oy + 176 - i * 19
            canvas.fill((255, 255, 255), r)
            pygame.draw.rect(canvas, (150, 150, 158), r, 1)
            text(canvas, msg, (r.x + 5, r.centery), (40, 40, 48), 11, "midleft")


def draw_p02(canvas, t: float, sc: dict) -> None:
    canvas.fill(_c("#10141C"))
    f = Frame(canvas)
    win = f.r(60, 60, 420, 180)
    canvas.fill(_c("#1E2633"), win)
    old = canvas.get_clip()
    canvas.set_clip(win)
    for k in range(4):                                                          # 0.4초마다 흰 빛줄기 (길이 80, 두께 2)
        ph = (t - k * 0.4) % 1.6
        x = win.right - ph / 1.6 * (win.w + 160)
        y = win.y + 20 + (k * 29) % (win.h - 30)
        canvas.fill((235, 240, 250), (int(x), y, 80, 2))
    cx, cy = win.centerx, win.centery
    pygame.draw.circle(canvas, _c("#2B3444"), (cx, cy - 10), 20)                # 유리에 비친 실루엣: 머리(지름 40)
    pygame.draw.ellipse(canvas, _c("#2B3444"), (cx - 46, cy + 12, 92, 70))      # 어깨 반원
    canvas.set_clip(old)


def draw_p03(canvas, t: float, sc: dict) -> None:
    canvas.fill(_c("#3A3026"))
    f = Frame(canvas)
    box = f.r(160, 90, 320, 220)
    canvas.fill(_c("#8A6A45"), box)
    pygame.draw.rect(canvas, _c("#6B5034"), box, 3)
    canvas.fill(_c("#6B5034"), (box.x, box.y - 14, box.w, 14))                  # 열린 뚜껑
    a, b = (box.x + 18, box.bottom - 18), (box.right - 50, box.y + 16)          # 대각선 대나무 낚싯대 (18px 마디)
    pygame.draw.line(canvas, _c("#C9A86A"), a, b, 4)
    ln = math.hypot(b[0] - a[0], b[1] - a[1])
    for d in range(9, int(ln), 18):
        u = d / ln
        x, y = a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u
        pygame.draw.line(canvas, _c("#A88849"), (x - 2, y - 2), (x + 2, y + 2), 3)
    note = pygame.Rect(box.right - 40, box.bottom - 46, 26, 20)                 # 오른쪽 접힌 흰 쪽지
    canvas.fill((245, 242, 232), note)
    pygame.draw.line(canvas, (210, 205, 190), note.topleft, note.bottomright, 1)
    if 3.0 <= t < 5.5:                                                          # 쪽지 클로즈업 2.5초
        k = min(1.0, (t - 3.0) / 0.25)
        paper = pygame.Surface(canvas.get_size())
        paper.fill(sui.PAPER)
        paper.set_alpha(int(255 * k))
        canvas.blit(paper, (0, 0))
        if k >= 1.0:
            for i, s in enumerate(sc["note"]):                                  # 손글씨 느낌 3줄 (살짝 기울어짐)
                x = f.ox + 150 + (i % 2) * 6 + (40 if i == 2 else 0)
                text(canvas, s, (x, f.oy + 100 + i * 30 + int(math.sin(i * 1.7) * 2)), sui.INK, 16, "midleft")


def draw_p04(canvas, t: float, sc: dict) -> None:
    f = Frame(canvas)
    w = canvas.get_width()
    if t < 1.5:                                                                 # 책상 위 흰 봉투 '사직서'
        canvas.fill(_c("#2A2F3A"))
        env = f.r(180, 100, 300, 170)
        canvas.fill((245, 245, 242), env)
        pygame.draw.lines(canvas, (200, 200, 205), False, [env.topleft, env.center, env.topright], 1)
        text(canvas, sc["envelope"], (env.centerx, env.centery + 14), (40, 40, 48), 16, "center")
        return
    sea = t >= 5.5
    canvas.fill(_c("#CDE8F6"))
    view = f.r(50, 40, 430, 200)
    if not sea:                                                                 # 산·논이 오른쪽에서 왼쪽으로
        sc_x = (t - 1.5) * 60
        for k in range(-1, 8):
            x = view.x + k * 90 - int(sc_x % 90)
            pygame.draw.polygon(canvas, _c("#5E7A5A"), [(x, view.y + 110), (x + 45, view.y + 60 + (k % 3) * 8), (x + 90, view.y + 110)])
        canvas.fill(_c("#A8C27A"), (0, view.y + 110, w, view.h))
        for k in range(-1, 14):
            x = view.x + k * 40 - int((t - 1.5) * 140 % 40)
            canvas.fill(lerp(_c("#A8C27A"), (120, 150, 80)), (x, view.y + 118, 22, 1))
    else:                                                                       # 바다: 수면 + 흰 1px 점 30개 깜빡 (윤슬)
        canvas.fill(_c("#6FB7D9"), (0, view.y + 90, w, canvas.get_height()))
        rnd = random.Random(7)
        for i in range(30):
            x, y = view.x + rnd.randrange(view.w), view.y + 95 + rnd.randrange(80)
            if math.sin(t * (3 + rnd.random() * 4) + i) > 0.2:
                canvas.fill((255, 255, 255), (x, y, 1, 1))
    frame = _c("#3A3A44")                                                       # 버스 창틀
    canvas.fill(frame, (0, 0, w, view.y))
    canvas.fill(frame, (0, view.bottom, w, canvas.get_height()))
    canvas.fill(frame, (0, 0, view.x, canvas.get_height()))
    canvas.fill(frame, (view.right, 0, w, canvas.get_height()))
    canvas.fill(frame, (view.centerx - 3, view.y, 6, view.h))


def lerp(a, b, k=0.4):
    return tuple(int(x + (y - x) * k) for x, y in zip(a, b))


def draw_closeup(canvas, t: float, sc: dict) -> None:
    """C1-06 클로즈업: 화면 가득 대나무 손잡이 #C9A86A + 칼로 새긴 '해강' #6B4A2B (2초)."""
    canvas.fill(_c("#C9A86A"))
    w, h = canvas.get_size()
    for y in range(0, h, 9):                                                    # 대나무 결
        canvas.fill(lerp(_c("#C9A86A"), _c("#A88849"), 0.35), (0, y, w, 1))
    canvas.fill(_c("#A88849"), (0, h // 2 + 50, w, 6))                          # 마디
    text(canvas, "해강", (w // 2 + 1, h // 2 + 1), lerp(_c("#6B4A2B"), (0, 0, 0), 0.3), 16, "center")
    text(canvas, "해강", (w // 2, h // 2), _c("#6B4A2B"), 16, "center")


def draw_c302(canvas, t: float, sc: dict, world=None) -> None:
    """비밀 장소 바위: 배경 그대로 시점 오른쪽 이동(2초) → 바위 #6E6E78 80x50 + 받침대 2개 #5A3D2A → 새긴 글자 클로즈업."""
    f = Frame(canvas)
    if t < 3.0:
        pan = int(min(1.0, t / 2.0) * 40)
        if world is not None:
            canvas.blit(world, (-pan, 0))
            canvas.blit(world, (canvas.get_width() - pan, 0), (0, 0, pan, canvas.get_height()))
        if t >= 2.0:
            rock = f.r(300, 170, 380, 220)
            pygame.draw.ellipse(canvas, _c("#6E6E78"), rock)
            pygame.draw.ellipse(canvas, lerp(_c("#6E6E78"), (255, 255, 255), 0.15), rock.inflate(-30, -30).move(-8, -8))
            for x in (290, 384):
                canvas.fill(_c("#5A3D2A"), f.r(x, 196, x + 4, 224))
        return
    canvas.fill(_c("#6E6E78"))                                                  # 바위 표면 클로즈업
    rnd = random.Random(3)
    w, h = canvas.get_size()
    for _ in range(140):
        canvas.fill(lerp(_c("#6E6E78"), (40, 40, 48), rnd.random() * 0.5), (rnd.randrange(w), rnd.randrange(h), 2, 1))
    cx, cy = w // 2 - 30, h // 2 - 20
    text(canvas, sc["carved"][0], (cx, cy), _c("#3A3A44"), 16, "center")
    fx = cx + 40                                                                # 선 3개로 된 물고기
    pygame.draw.line(canvas, _c("#3A3A44"), (fx, cy - 6), (fx + 16, cy), 1)
    pygame.draw.line(canvas, _c("#3A3A44"), (fx, cy + 6), (fx + 16, cy), 1)
    pygame.draw.line(canvas, _c("#3A3A44"), (fx - 6, cy - 6), (fx - 6, cy + 6), 1)


def draw_c504(canvas, t: float, sc: dict, world=None) -> None:
    """세계수 뿌리 샘: 거대한 뿌리 사이 평평한 돌 제단 #8A8A80 60x14 → 1.5초 제단 위 낡은 종이 + 돌멩이 #5E5E58."""
    f = Frame(canvas)
    canvas.fill((22, 34, 30))
    w, h = canvas.get_size()
    for k in range(7):                                                          # 거대한 뿌리
        x = f.ox + 20 + k * 70
        pygame.draw.polygon(canvas, (58, 46, 34), [(x - 30, h), (x - 6, f.oy + 40 + (k % 3) * 20), (x + 12, f.oy + 30), (x + 40, h)])
        pygame.draw.line(canvas, (80, 64, 46), (x - 2, f.oy + 50), (x + 6, h), 2)
    for i in range(18):                                                         # 샘물 빛
        x = f.ox + 60 + (i * 53) % 360
        y = f.oy + 200 + (i * 17) % 50
        if math.sin(t * 2 + i) > 0:
            canvas.fill((120, 220, 210), (x, y, 2, 1))
    alt = f.r(210, 176, 270, 190)
    canvas.fill(_c("#8A8A80"), alt)
    canvas.fill(lerp(_c("#8A8A80"), (0, 0, 0), 0.3), (alt.x, alt.bottom, alt.w, 6))
    if t >= 1.5:
        canvas.fill(sui.PAPER, f.r(224, 170, 256, 177))
        pygame.draw.ellipse(canvas, _c("#5E5E58"), f.r(236, 166, 246, 172))


SPECS = {
    # sid: (그림, 길이(초), [(시작, 끝, 자막 위치 index)], [(시각, 소리, 음량)], 끝 전환)
    "P-01": (draw_p01, 6.5, [(4.5, 6.0, 0)], [(0.0, "loop:st_keyboard", 0.25), (0.0, "loop:st_buzz", 0.12),
                                            (1.0, "st_ding", 0.45), (1.8, "st_ding", 0.45), (2.6, "st_ding", 0.45)], ("black", 6.0, 0.5)),
    "P-02": (draw_p02, 5.5, [(2.5, 5.0, 0)], [(0.0, "loop:st_train", 0.3)], ("black", 5.0, 0.5)),
    "P-03": (draw_p03, 7.0, [(0.0, 3.0, 0)], [(0.0, "st_box", 0.6), (3.0, "st_paper", 0.6)], ("black", 6.5, 0.5)),
    "P-04": (draw_p04, 8.5, [(6.0, 8.0, 0)], [(0.0, "st_envelope", 0.5), (1.5, "loop:st_bus", 0.3), (5.5, "loop:amb_bed_ocean", 0.4),
                                            (5.5, "music:sharmion", 0)], ("white", 8.0, 0.5)),
    "CLOSEUP": (draw_closeup, 2.0, [], [], None),
    "C3-02": (draw_c302, 6.5, [(4.0, 6.0, 0)], [(0.0, "loop:amb_bed_mist", 0.3)], ("black", 6.0, 0.5)),
    "C5-04": (draw_c504, 3.2, [], [(0.0, "loop:st_spring", 0.35), (3.0, "st_paper", 0.6)], None),
}


class CutsceneScene(Scene):
    """샷 하나 (SPECS) — 끝나면 on_done. 오른쪽 위 '건너뛰기'."""

    def __init__(self, game, sid: str, on_done=None, world=None, skippable: bool = True):
        super().__init__(game)
        self.sid = sid
        self.spec = SPECS[sid]
        self.sc = story.scenes().get(sid, {})
        self.on_done = on_done
        self.world = world            # 배경 스냅샷 (C3-02: 비밀 장소 그대로)
        self.skippable = skippable
        self.t = 0.0
        self.mouse = (0, 0)
        self.loops: list[str] = []
        self.done = False
        self.fired = set()

    def _sound(self, name: str, vol: float) -> None:
        sfx = self.game.sfx
        if name.startswith("loop:"):
            n = name[5:]
            sfx.loop(n, True, vol)
            self.loops.append(n)
        elif name.startswith("music:"):
            self.story_music = name[6:]   # 장면이 음악을 정함 → 장소 음악은 비켜 줌 (소리 구역, DESIGN.md 39)
            self.game.adaptive.set_context(name[6:], None)   # 샤르미온 대륙 테마
            self.game.adaptive.set("menu")
        else:
            sfx.play(name, vol)

    def _stop_loops(self) -> None:
        for n in self.loops:
            self.game.sfx.loop(n, False)
        self.loops = []

    def finish(self) -> None:
        if self.done:
            return
        self.done = True
        self._stop_loops()
        if self in self.game.scenes.stack:
            self.game.scenes.stack.remove(self)
        if self.on_done:
            self.on_done()

    def handle_action(self, a) -> None:
        if a.name == "primary" and self.skippable and sui.skip_rect(self.game.screen.canvas).collidepoint(a.pos):
            self.game.sfx.play("ui_click")
            self.finish()

    def update(self, dt: float) -> None:
        self.t += dt
        self.mouse = self.game.input.pointer
        for i, (at, name, vol) in enumerate(self.spec[3]):
            if i not in self.fired and self.t >= at:
                self.fired.add(i)
                self._sound(name, vol)
        if self.t >= self.spec[1]:
            self.finish()

    def draw(self, canvas) -> None:
        fn = self.spec[0]
        if fn in (draw_c302, draw_c504):
            fn(canvas, self.t, self.sc, self.world)
        else:
            fn(canvas, self.t, self.sc)
        for a, b, i in self.spec[2]:
            if a <= self.t < b:
                k = min(1.0, (self.t - a) / 0.3, (b - self.t) / 0.3)
                sui.subtitle(canvas, self.sc["subs"][i], k)
        tr = self.spec[4]
        if tr:
            kind, at, ln = tr
            if self.t >= at:
                _black(canvas, (self.t - at) / ln, (255, 255, 255) if kind == "white" else (0, 0, 0))
        if self.t < 0.3:
            _black(canvas, 1 - self.t / 0.3)
        if self.skippable:
            sui.draw_skip(canvas, self.mouse)
        draw_cursor(canvas, self.mouse)


class SubtitleScene(Scene):
    """배경(함수) 위에 자막 하나 (C5-04 끝 '할아버지는, 여기서 멈췄다.' 3초 등)."""

    def __init__(self, game, line: str, secs: float, backdrop=None, on_done=None):
        super().__init__(game)
        self.line, self.secs, self.backdrop, self.on_done = line, secs, backdrop, on_done
        self.t = 0.0

    def handle_action(self, a) -> None:
        if a.name == "primary" and sui.skip_rect(self.game.screen.canvas).collidepoint(a.pos):
            self.t = self.secs

    def update(self, dt: float) -> None:
        self.t += dt
        if self.t >= self.secs:
            if self in self.game.scenes.stack:
                self.game.scenes.stack.remove(self)
            if self.on_done:
                self.on_done()

    def draw(self, canvas) -> None:
        if self.backdrop:
            self.backdrop(canvas)
        else:
            canvas.fill((0, 0, 0))
        k = min(1.0, self.t / 0.3, (self.secs - self.t) / 0.3)
        sui.subtitle(canvas, self.line, k)
        sui.draw_skip(canvas, self.game.input.pointer)
