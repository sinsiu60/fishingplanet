"""물고기 자리 행동 UI (DESIGN.md 31-11): 패턴이 오면 물고기 위치에 크게 떠서 '그 자리에서' 진행된다.

원래 점프 '우클릭' 판정 원·방향 전환 '확 꺾기!' 프롬프트처럼 — 패턴 이름만 알려 주는 고정 칸이 아니라,
물고기에 붙어 다니며 예고 카운트다운 → 행동 중 진행 게이지 → 판정까지 한자리에서 보여 준다.

  위   : 상태 글자 (돌진! / 머리 흔들기! / 지침 …) — 등장할 때 톡 튀어나오고, 거센 행동은 떨린다
  가운데: 배지 (계열 아이콘) + 줄어드는 접근 원(예고 남은 시간) / 행동 중엔 패턴별 진행 장치
  아래 : 작은 장력 줄 (할 일 문구는 띄우지 않음 — 지침의 '기회!'만, 31-13)

어떤 신호를 띄울지는 signal_slots.collect() 그대로 (소리 전용·먹물·동굴 어둠·이중 시차 규칙 유지).
가짜 지침은 진짜처럼 '지침 / 기회!'가 뜬다 — 꼬리 까딱·기포(몸짓)로 가려내는 게 이 패턴의 재미.
"""
import math

import pygame

from src.core.config import load_json
from src.core.mathutil import clamp
from src.ui import fight_fx, signal_slots as ss
from src.ui.fight_fx import GOLD, big_text
from src.ui.hud import SHADOW

GOOD = (130, 255, 180)
BAD = (255, 110, 95)
WHITE = (240, 244, 252)
TIRED = (110, 255, 140)

# 상태 글자 (예고·행동 공통). 신규 패턴 이름은 patterns.json names
BASE_NAMES = {"rush": "돌진!", "jump": "점프!", "leap": "몸털기!", "turn": "방향 전환!", "charge": "힘 모으기!",
              "thrash": "공중 몸부림!", "tired": "지침", "stiff": "경직!"}
# 할 일 칩: (PC, 터치)
HINTS = {
    "rush": ("드랙 Q↓", "드랙 ▼"), "rush_act": ("버텨!", "버텨!"), "rush_red": ("감기 멈춰!", "손 떼!"),
    "charge": ("지금 감아!", "지금 감아!"),
    "shake": ("손 떼!", "손 떼!"), "dive": ("위로!", "위로!"), "surface": ("아래로!", "아래로!"),
    "reverse": ("연타!", "연타!"), "twist": ("돌려!", "원 그리기!"), "hide": ("풀어 줘!", "손 떼!"),
    "hide_peek": ("지금 감아!", "지금 감아!"), "pump": ("사이에 감기", "사이에 탭"), "bite": ("Shift 준비", "▼ 준비"),
    "bite_now": ("Shift!", "▼ 길게!"), "jump": ("우클릭", "숙이기"), "thrash": ("우클릭 ×2", "숙이기 ×2"),
    "tired": ("기회!", "기회!"),
}


def _name(action: str) -> str:
    if action in BASE_NAMES:
        return BASE_NAMES[action]
    return load_json("patterns.json")["names"].get(action, action) + "!"


def _hint(key: str, touch: bool) -> str:
    h = HINTS.get(key)
    return (h[1] if touch else h[0]) if h else ""


# ───────────────────────── 작은 부품 ─────────────────────────

def state_label(canvas, x, y, s: str, col, age: float, t: float, heavy: bool = False, scale: float = 1.0) -> None:
    """상태 글자: 등장할 때 크게 튀어나왔다 자리잡음, 거센 행동은 좌우로 떨림."""
    pop = 1.0 + 0.7 * math.exp(-age * 12) * math.cos(age * 26)
    sx = math.sin(t * 40) * 1.5 if heavy else 0.0
    big_text(canvas, s, (x + sx, y), col, 1.5 * scale * max(0.7, pop), outline=True)


def hint_chip(canvas, x, y, s: str, col, t: float, urgent: bool = False) -> None:
    """할 일 칩: 어두운 알약 + 글자. 급하면 테두리 맥동."""
    if not s:
        return
    from src.core.fonts import get_font
    w = get_font(11).size(s)[0] + 12
    r = pygame.Rect(0, 0, w, 15)
    r.center = (int(x), int(y))
    back = pygame.Surface(r.size, pygame.SRCALPHA)
    pygame.draw.rect(back, (12, 16, 30, 200), back.get_rect(), border_radius=7)
    canvas.blit(back, r.topleft)
    on = not urgent or int(t * 8) % 2 == 0
    pygame.draw.rect(canvas, col if on else (90, 96, 120), r, 2 if urgent else 1, border_radius=7)
    big_text(canvas, s, r.center, col if on else WHITE, 1.0, outline=True)


def badge(canvas, x, y, fam: str, col, t: float, r: int = 14, lit: bool = True, dirv=(1, 0)) -> None:
    pygame.draw.circle(canvas, SHADOW, (x + 1, y + 1), r + 1)
    pygame.draw.circle(canvas, (16, 20, 36), (x, y), r)
    pygame.draw.circle(canvas, col if lit else tuple(int(c * 0.5) for c in col), (x, y), r, 2)
    if fam in ss.cfg()["families"]:
        ss.family_icon(canvas, fam, x, y, col, t, dir=dirv)


def countdown(canvas, x, y, left: float, col, r: int = 14, spread: int = 34) -> None:
    """예고 남은 시간: 바깥 접근 원이 줄어들어 배지에 닿는 순간 = 행동 시작 (+ 남은 시간 원호)."""
    left = clamp(left, 0.0, 1.0)
    ra = r + 2 + spread * left
    surf = pygame.Surface((int(ra * 2 + 8), int(ra * 2 + 8)), pygame.SRCALPHA)
    o = surf.get_width() // 2
    a = int(clamp(255 * (1.3 - left), 110, 255))
    pygame.draw.circle(surf, (*SHADOW, a // 2), (o + 1, o + 1), int(ra), 2)
    pygame.draw.circle(surf, (*col, a), (o, o), int(ra), 2)
    canvas.blit(surf, (x - o, y - o))
    rect = pygame.Rect(0, 0, (r + 4) * 2, (r + 4) * 2)
    rect.center = (x, y)
    if left > 0.02:
        pygame.draw.arc(canvas, WHITE, rect, math.pi / 2, math.pi / 2 + math.tau * left, 2)


def gauge_arc(canvas, x, y, r: int, frac: float, col, need: float | None = None, width: int = 3) -> None:
    """배지 둘레 진행 원호 (아래에서 시계 방향). need = 목표 눈금."""
    rect = pygame.Rect(0, 0, r * 2, r * 2)
    rect.center = (x, y)
    pygame.draw.circle(canvas, (40, 44, 62), (x, y), r, width)
    if frac > 0.01:
        start = -math.pi / 2 - math.tau * clamp(frac, 0, 1)
        pygame.draw.arc(canvas, col, rect, start, -math.pi / 2, width)
    if need is not None:
        a = -math.pi / 2 - math.tau * need
        p0 = (x + math.cos(a) * (r - 4), y - math.sin(a) * (r - 4))
        p1 = (x + math.cos(a) * (r + 4), y - math.sin(a) * (r + 4))
        pygame.draw.line(canvas, (255, 255, 255), p0, p1, 2)


def v_arrow(canvas, x, y, d: int, col, size: int = 12) -> None:
    """세로 큰 화살표 (d = -1 위 / +1 아래)."""
    tip = y + d * size
    for c, o in ((SHADOW, 1), (col, 0)):
        pygame.draw.line(canvas, c, (x + o, y - d * size * 0.4 + o), (x + o, tip - d * 4 + o), 4)
        pygame.draw.polygon(canvas, c, [(x + o, tip + o), (x - 7 + o, tip - d * 8 + o), (x + 7 + o, tip - d * 8 + o)])


def ring_arrow(canvas, x, y, r: int, t: float, col, width: int = 2) -> None:
    """회전하는 원 화살표 (비틀기)."""
    a0 = t * 6
    rect = pygame.Rect(0, 0, r * 2, r * 2)
    rect.center = (x, y)
    pygame.draw.arc(canvas, col, rect, a0, a0 + math.pi * 1.5, width)
    ex, ey = x + math.cos(a0 + math.pi * 1.5) * r, y - math.sin(a0 + math.pi * 1.5) * r
    tx, ty = -math.sin(a0 + math.pi * 1.5), -math.cos(a0 + math.pi * 1.5)
    pygame.draw.polygon(canvas, col, [(ex + tx * 6, ey + ty * 6), (ex - ty * 4, ey + tx * 4), (ex + ty * 4, ey - tx * 4)])


def mini_tension(canvas, fight, x, y, t: float, w: int = 70) -> None:
    """물고기 아래 작은 장력 줄 (초록 구간·숨기 목표 금색)."""
    x0 = int(x - w // 2)

    def tx(v):
        return x0 + int(clamp(v, 0.0, 100.0) / 100 * w)

    gl, gh = fight.green_low, fight.green_high
    canvas.fill(SHADOW, (x0 - 1, y - 1, w + 2, 5))
    canvas.fill((52, 64, 86), (x0, y, tx(gl) - x0, 3))
    canvas.fill((40, 120, 60), (tx(gl), y, tx(gh) - tx(gl), 3))
    canvas.fill((130, 40, 38), (tx(gh), y, tx(100) - tx(gh), 3))
    hide = next((p for p in fight.pats if p.id == "hide" and p.active and not p.success), None)
    if hide is not None:
        lo, hi = tx(gl + hide.c["low_min"]), tx(gl + hide.c["low_max"])
        pygame.draw.rect(canvas, GOLD, (lo - 1, y - 2, max(2, hi - lo) + 2, 7), 1)
    zone = fight.zone()
    col = {"green": (70, 220, 110), "red": (255, 70, 60), "slack": (150, 170, 210)}[zone]
    blink = zone != "green" and int(t * 8) % 2 == 0
    canvas.fill((255, 255, 255) if not blink else col, (tx(fight.tension) - 1, y - 3, 3, 9))


def combo_row(canvas, fight, x, y, t: float) -> None:
    """연쇄 콤보: 할 순서대로 아이콘 줄 (진행하면 하나씩 꺼지고, 지금 단계는 흰 테두리)."""
    b = fight.brain
    if b.signal == "chain" and not b.sound_only:
        seq, cur = b.chain_seq, -1
    elif fight.combo is not None:
        seq, cur = fight.combo.seq, fight.combo.index
    else:
        return
    if not seq:
        return
    n, step = len(seq), 24
    x0 = int(x - (n - 1) * step / 2)
    back = pygame.Surface(((n - 1) * step + 28, 22), pygame.SRCALPHA)
    pygame.draw.rect(back, (12, 16, 30, 190), back.get_rect(), border_radius=8)
    canvas.blit(back, (x0 - 14, int(y) - 11))
    failed = fight.combo is not None and fight.combo.failed
    for i, a in enumerate(seq):
        cx = x0 + i * step
        if i < cur:
            pygame.draw.circle(canvas, (70, 76, 100), (cx, int(y)), 3)
            continue
        fam = ss.family_of(a) or "direction"
        col = ss.color_of(fam) if fam in ss.cfg()["families"] else (150, 160, 185)
        if i == cur:
            pygame.draw.circle(canvas, BAD if failed else WHITE, (cx, int(y)), 10, 2)
        dirv = (0, -1) if a == "dive" else (0, 1) if a == "surface" else (1, 0)
        ss.family_icon(canvas, fam, cx, int(y), col, t, small=True, dir=dirv)


# ───────────────────────── 한 신호 ─────────────────────────

def _rush_badge(canvas, f, x, y, fam, col, t, R) -> None:
    """돌진 배지: 줄 펄스 진행률만큼 아래부터 차오르고, 돌진 순간 꽉 차며 번쩍 (31-14)."""
    from src.ui import rush_cue
    ph = rush_cue.phase(f)
    fill = 0.0
    flash = 0.0
    if ph is not None:
        if ph["stage"] == "pulse":
            fill = ph["q"]
        elif ph["stage"] == "rush":
            fill, flash = 1.0, max(0.0, 1 - ph["k"])
    elif f.brain.state == "rush":
        fill = 1.0
    pygame.draw.circle(canvas, SHADOW, (x + 1, y + 1), R + 1)
    pygame.draw.circle(canvas, (16, 20, 36), (x, y), R)
    if fill > 0:
        surf = pygame.Surface((R * 2 + 2, R * 2 + 2), pygame.SRCALPHA)
        pygame.draw.circle(surf, (*col, 150), (R + 1, R + 1), R)
        cut = int((R * 2 + 2) * (1 - fill))
        surf.fill((0, 0, 0, 0), (0, 0, R * 2 + 2, cut))
        canvas.blit(surf, (x - R - 1, y - R - 1))
    pygame.draw.circle(canvas, col, (x, y), R, 2)
    ss.family_icon(canvas, fam, x, y, WHITE if fill > 0.5 else col, t)
    if flash > 0:
        pygame.draw.circle(canvas, (255, 255, 255), (x, y), int(R + 2 + 10 * (1 - flash)), 2)
        if flash > 0.7:
            pygame.draw.circle(canvas, (255, 255, 255), (x, y), R)  # 꽉 차는 순간 번쩍


def _widget(canvas, ctx: dict, s: dict, x: int, y: int) -> tuple[str, object, bool]:
    """신호 하나를 물고기 자리에 그린다. 돌려줌: (할 일 칩 글자, 칩 색, 급함)."""
    f, b, t, touch = ctx["fight"], ctx["fight"].brain, ctx["t"], ctx["touch"]
    act, kind, fam = s["action"], s["kind"], s["family"]
    col = ss.color_of(fam) if fam in ss.cfg()["families"] else GOLD
    pat = s.get("pat")
    tele = kind == "tele"
    strong = ss.OPTS["strong"]
    R = int(14 * ss.OPTS["scale"])
    if act == "rush":
        _rush_badge(canvas, f, x, y, fam, col, t, R)
        if not tele:
            red = f.zone() == "red"
            pulse = int(R + 3 + 3 * abs(math.sin(t * 14)))
            pygame.draw.circle(canvas, BAD if red else col, (x, y), pulse, 1)
        return "", col, False
    if tele:
        left = 1 - b.signal_progress()
        if act == "bite":
            # 물어뜯기: 턱이 닫혀 온다 — 다 닫히는 순간 드랙 순간 최저
            gap = int(4 + 18 * left)
            for d in (-1, 1):
                pts = [(x - 12, y + d * gap), (x + 12, y + d * gap), (x, y + d * (gap - 9))]
                pygame.draw.polygon(canvas, SHADOW, [(px + 1, py + 1) for px, py in pts])
                pygame.draw.polygon(canvas, (255, 255, 255) if left < 0.25 else col, pts)
            now = left < 0.2
            return _hint("bite_now" if now else "bite", touch), GOLD if now else col, now
        dirv = (0, -1) if act == "dive" else (0, 1) if act == "surface" else (1, 0)
        badge(canvas, x, y, fam, col, t, R, lit=int(t * 6) % 2 == 0 or not strong, dirv=dirv)
        countdown(canvas, x, y, left, col, R, int(34 * ss.OPTS["scale"]))
        if act in ("dive", "surface"):
            v_arrow(canvas, x + R + 14, y, -1 if act == "dive" else 1, col)
        return _hint(act if act in HINTS else "", touch), col, left < 0.25
    # ── 행동 중 ──
    if act == "charge":
        prog = b.state_t / max(0.01, b.state_t + b.timer)
        badge(canvas, x, y, fam, col, t, R)
        gauge_arc(canvas, x, y, R + 6, prog, col)
        return _hint("charge", touch), GOLD, True
    if act == "tired":
        return "", col, False
    if pat is None and act != "twist":
        badge(canvas, x, y, fam, col, t, R)
        return "", col, False
    if act == "shake":
        jx = int(math.sin(t * 50) * 2)
        badge(canvas, x + jx, y, fam, col, t, R)
        r = pat.ratio
        ok = pat.last_ok
        gauge_arc(canvas, x, y, R + 6, r, GOOD if r >= pat.need and ok else (GOLD if r >= pat.need else BAD), pat.need)
        return _hint("shake", touch), GOOD if ok else BAD, not ok
    if act in ("dive", "surface"):
        d = -1 if act == "dive" else 1
        bob = int(math.sin(t * 10) * 3)
        ok = pat.last_ok
        badge(canvas, x, y, fam, col, t, R, dirv=(0, d))
        v_arrow(canvas, x, y + d * (R + 16) + d * bob, d, GOOD if ok else col, 14)
        r = pat.ratio
        gauge_arc(canvas, x, y, R + 6, r, GOOD if r >= pat.need else BAD, pat.need)
        return _hint(act, touch), GOOD if ok else BAD, not ok
    if act == "reverse":
        badge(canvas, x, y, fam, col, t, R)
        # 오른쪽 세로 회수 막대 + 기준 눈금, 연타할 때마다 위로 튐
        bx, by, bh = x + R + 10, y - 18, 36
        canvas.fill(SHADOW, (bx - 1, by - 1, 8, bh + 2))
        canvas.fill((40, 44, 62), (bx, by, 6, bh))
        fh = int(bh * pat.gauge / 100)
        keep = pat.c["keep_level"] / 100
        canvas.fill(GOOD if pat.gauge >= pat.c["keep_level"] else BAD, (bx, by + bh - fh, 6, fh))
        canvas.fill((255, 255, 255), (bx - 2, by + bh - int(bh * keep), 10, 1))
        if int(t * 10) % 2 == 0:
            ss._tri(canvas, x, y - R - 9, -1, 7, WHITE)
        return _hint("reverse", touch), GOLD, True
    if act == "twist":
        tv = f.twist.value / 100
        ring_arrow(canvas, x, y, R + 8, t, col, 3 if strong else 2)
        gauge_arc(canvas, x, y, R + 14, tv, BAD if tv >= 0.75 else (255, 170, 90), width=2)
        badge(canvas, x, y, fam, col, t, R)
        return _hint("twist", touch), BAD if tv >= 0.5 else col, tv >= 0.5
    if act == "hide":
        peek = getattr(pat, "peeking", False)
        if peek:
            big = int(R + 6 + 4 * abs(math.sin(t * 16)))
            badge(canvas, x, y, "reel", GOLD, t, R)
            pygame.draw.circle(canvas, GOLD, (x, y), big, 2)
            return _hint("hide_peek", touch), GOLD, True
        badge(canvas, x, y, fam, col, t, R)
        gauge_arc(canvas, x, y, R + 6, pat.ratio, GOOD if pat.hold_t > 0 else BAD)
        return _hint("hide", touch), col, False
    if act == "pump" and pat.active:
        iv = pat.interval
        k = (pat.t / iv) % 1.0
        ttg = (0.5 - k) * iv
        if ttg < -0.2 * iv:
            ttg += iv
        fight_fx.draw_jump_ring(canvas, (x, y), ttg, iv, 0.12, 0.2 * iv, t, spread=26)
        nb = max(1, b.pump_beats)
        from src.ui import icons
        icons.pips(canvas, x, y + R + 8, min(nb, 8), col, 5)
        if pat.beat > 0:
            icons.pips(canvas, x - (min(nb, 8) - 1) * 5 // 2 + (min(pat.beat, nb) - 1) * 5, y + R + 8, 1, WHITE)
        return _hint("pump", touch), col, abs(ttg) < 0.12
    if act == "bite":
        badge(canvas, x, y, fam, GOOD if pat.passed() else BAD, t, R)
        return "", col, False
    badge(canvas, x, y, fam, col, t, R)
    return "", col, False


# ───────────────────────── 전체 ─────────────────────────

def draw(canvas, ctx: dict) -> None:
    """ctx: fight, sigs(collect 결과), anchor(물고기 화면 위치, 카메라 연출 반영), apex(높이→화면 위치 함수),
    touch, t, flick_cfg, fight_cfg, sound_only, inked."""
    f, b, t = ctx["fight"], ctx["fight"].brain, ctx["t"]
    w, h = canvas.get_size()
    ax, ay = ctx["anchor"]
    x = int(clamp(ax, 70, w - 70))
    # 배지 묶음은 물고기 바로 위 — 그림자(웅크림·물결 같은 몸짓 신호)를 가리지 않게 (31-14)
    y = int(clamp(ay - 30, 62, h - 74))
    sigs = [s for s in ctx["sigs"] if s["action"] not in ("jump", "thrash", "leap", "turn")]
    label, lcol, heavy = None, WHITE, False
    chips = []
    # 지침 (가짜 지침도 똑같이 — 몸짓으로 가려낸다)
    if b.state in ("tired", "exhausted", "fake_tired") and not b.sound_only:
        fight_fx.draw_tired_ring(canvas, (ax, ay), 1.2, t)
        fight_fx.draw_tired_ring(canvas, (ax, ay), 1.2, t + 0.33)
        label, lcol = ("완전 지침" if b.state == "exhausted" else "지침"), TIRED
        chips.append(("기회!", GOLD, True))  # '기회!' 하나만 (테두리만 맥동)
    # 일반 신호들 (이중이면 좌우로 나란히)
    n = len(sigs)
    for i, s in enumerate(sigs):
        sx = x + int((i - (n - 1) / 2) * 52)
        _widget(canvas, ctx, s, sx, y)  # 패턴 중 할 일 문구(버텨!·감기 멈춰! 등)는 띄우지 않는다 — 그림 장치로만 (31-13)
        if label is None and s["kind"] != "residue":
            a = "dual" if b.state == "dual" or b.pending == "dual" else s["action"]
            if a == "hide" and s["kind"] == "act" and getattr(s.get("pat"), "peeking", False):
                label = "고개 내밈!"
            else:
                label = _name(a)
            lcol = ss.color_of(s["family"]) if s["family"] in ss.cfg()["families"] else GOLD
            heavy = s["kind"] == "act" and s["action"] in ("rush", "thrash", "twist", "pump", "reverse")
    if label is None and any(s["kind"] == "residue" for s in sigs):
        label, lcol = "꼬임!", ss.color_of("gesture")
    # 점프형: 원래 판정 원 (정점 위치), 방향 전환: 원래 꺾기 프롬프트
    jump_sig = next((s for s in ctx["sigs"] if s["action"] in ("jump", "thrash", "leap")), None)
    if jump_sig is not None:
        a = jump_sig["action"]
        if label is None:
            label, lcol, heavy = _name(a), fight_fx.ICON_COL.get(a, GOLD), jump_sig["kind"] == "act"
        _draw_jump(canvas, ctx, a)
    turn_sig = next((s for s in ctx["sigs"] if s["action"] == "turn"), None)
    if turn_sig is not None:
        if label is None:
            label, lcol = _name("turn"), fight_fx.ICON_COL["turn"]
        _draw_turn(canvas, ctx, turn_sig, x, y)
    # 콤보 순서 줄 (상태 글자 위)
    if b.signal == "chain" or f.combo is not None:
        combo_row(canvas, f, x, y - 52, t)
        if label is None or b.signal == "chain":
            label, lcol = _name("chain"), GOLD
    ly = y - 32
    if jump_sig is not None:
        p = ctx["apex"](b.jump_height)
        if p:
            ly = min(ly, int(p[1]) - 30)  # 판정 원 위로
    if turn_sig is not None and f.turn_flick and not f.turn_flick["done"]:
        ly = y - 48  # '확 꺾기!' 위로
    if label and not ctx.get("judge_busy"):  # 판정 글자가 막 떴으면 그쪽이 우선
        state_label(canvas, x, max(30, ly), label, lcol, b.state_t, t, heavy)
    cy = max(y + 26, int(ay) + 16)  # 칩·장력 줄은 물고기 아래
    for s, c, urgent in chips[:2]:
        hint_chip(canvas, x, cy, s, c, t, urgent)
        cy += 17
    if sigs or jump_sig or turn_sig or b.state in ("tired", "exhausted", "fake_tired"):
        mini_tension(canvas, f, x, cy + 2, t)


def _draw_jump(canvas, ctx: dict, a: str) -> None:
    b, t, touch = ctx["fight"].brain, ctx["t"], ctx["touch"]
    fc = ctx["fight_cfg"]
    if a == "leap":
        p = ctx["apex"](b.jump_height)
        if p:
            total = b.cur_telegraph + b.jump_air / 2
            fight_fx.draw_swipe_ring(canvas, p, b.time_to_apex(), total, fc["perfect_window_sec"],
                                     fc["good_window_sec"], -b.leap_dir, t)
        return
    if a == "thrash":
        second = b.state == "jump" and b.jump_kind == "thrash" and b.thrash_judged[0]
        hgt = b.pcfg["thrash"]["height_mult"] * b.jump_height * (0.35 if second else 1.0)
        p = ctx["apex"](hgt)
        if p:
            tt = b.time_to_second() if second else b.time_to_apex()
            total = (b.jump_air / 2 - b.pcfg["thrash"]["land_before"] + b.jump_air / 2) if second \
                else b.cur_telegraph + b.jump_air / 2
            fight_fx.draw_jump_ring(canvas, p, tt, max(0.3, total), fc["perfect_window_sec"], fc["good_window_sec"], t,
                                    label=_hint("thrash", touch))
        return
    p = ctx["apex"](b.jump_height)
    if p:
        total = b.cur_telegraph + b.jump_air / 2
        fight_fx.draw_jump_ring(canvas, p, b.time_to_apex(), total, fc["perfect_window_sec"], fc["good_window_sec"], t,
                                label=_hint("jump", touch))


def _draw_turn(canvas, ctx: dict, s: dict, x: int, y: int) -> None:
    f, b, t = ctx["fight"], ctx["fight"].brain, ctx["t"]
    fc = ctx["flick_cfg"]
    tf, off = f.turn_flick, b.turn_offset()
    amount = b.signal_progress() if b.state == "telegraph" else 1.0
    fight_fx.draw_turn_chevrons(canvas, ctx["anchor"], b.turn_dir, 0.4 + 0.6 * amount, t)
    if tf and not tf["done"] and off is not None and off >= -(fc["turn_before_sec"] + 0.35):
        fight_fx.draw_turn_prompt(canvas, (x, y), tf["need"], off, fc["turn_before_sec"], fc["turn_after_sec"],
                                  fc["turn_perfect_sec"], t)
    elif b.state == "telegraph":
        col = fight_fx.ICON_COL["turn"]
        need = tf["need"] if tf else -(b.turn_dir or 1)
        badge(canvas, x, y, "direction", col, t, int(14 * ss.OPTS["scale"]), dirv=(need, 0))
        countdown(canvas, x, y, 1 - b.signal_progress(), col, int(14 * ss.OPTS["scale"]))
