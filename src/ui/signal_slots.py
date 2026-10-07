"""신호 슬롯 (DESIGN.md 31장 C3): 모든 대응 신호는 화면의 두 칸(왼손 / 오른손)에만 뜬다.

- 신호 사전 = 대응 6계열 (data/signals.json): 풀기 ▼▼ 파랑 / 감기 ▲ 초록 / 타이밍 링 노랑 / 방향 화살표 흰색 /
  참기 손바닥 회색 / 제스처 ⟳ 보라. 같은 계열이면 같은 색·모양 (모양만으로도 구분).
- 칸 자리: PC = 화면 가운데 조준점 좌우, 모바일 = 왼손 칸은 숙이기·드랙 버튼 쪽, 오른손 칸은 릴 패드 쪽 (왼손잡이 모드면 반대).
- 물고기 몸짓(물보라·그림자·기포·줄 나선·천장 반사광)은 원래 자리 그대로 — 여기선 그리지 않는다.
- 가짜(등불 가짜 예고, 가짜 지침)는 몸짓만: 칸에 신호가 뜨지 않는다.
- 연쇄 콤보: 예고 동안 칸 위에 행동 아이콘 줄(미리보기), 진행할 때마다 하나씩 꺼진다.
- 이중 패턴: 왼손 1 + 오른손 1, 두 번째 예고는 dual_stagger_sec 뒤에 뜬다.
- 칸 사이 아래: 작은 장력 줄 (신호가 떠 있을 때만, 숨기 목표 구간 표시).
"""
import math

import pygame

from src.core.config import load_json
from src.ui import fight_fx, icons
from src.ui.hud import SHADOW

GOOD = (130, 255, 180)
DIM = (120, 128, 150)
BAD = (255, 110, 95)


# 접근성 (31장 C6): 낚시 화면이 설정을 넣어 준다 — 색약 팔레트, 칸 크기 배율, 소리 신호 끔 → 그림 강조
OPTS = {"colorblind": False, "scale": 1.0, "strong": False, "phantom": False}
PHANTOM_GESTURE = (215, 170, 255)  # 환상 분위기(보라) 중 제스처(보라) 신호: 더 밝은 보라 + 흰 테두리


def configure(settings) -> None:
    OPTS["colorblind"] = bool(settings.get("colorblind"))
    OPTS["scale"] = cfg()["slots"]["size_mult"][settings.get("slot_size")]
    OPTS["strong"] = not settings.get("signal_sound")


def cfg() -> dict:
    return load_json("signals.json")


def family_of(action: str) -> str | None:
    return cfg()["actions"].get(action, {}).get("family")


def hand_of(action: str, family: str | None = None) -> str:
    c = cfg()
    a = c["actions"].get(action, {})
    fam = family or a.get("family")
    return a.get("hand") or c["families"].get(fam, {}).get("hand", "R")


def color_of(family: str):
    f = cfg()["families"][family]
    if OPTS["phantom"] and family == "gesture" and not OPTS["colorblind"]:
        return PHANTOM_GESTURE
    return tuple(f["cb_color"] if OPTS["colorblind"] else f["color"])


def white_edge(col) -> bool:
    """환상 분위기 중 제스처 신호면 흰 테두리를 한 겹 더 (보라 배경에 묻히지 않게)."""
    return OPTS["phantom"] and tuple(col) == PHANTOM_GESTURE


def slot_positions(w: int, h: int, touch: bool, left_handed: bool) -> tuple:
    s = cfg()["slots"]
    if touch:
        y = int(h * s["touch_y"])
        left, right = (int(w * s["touch_x"][0]), y), (int(w * s["touch_x"][1]), y)
        if left_handed:
            left, right = right, left
    else:
        y = int(h * s["pc_y"])
        left, right = (w // 2 - s["pc_dx"], y), (w // 2 + s["pc_dx"], y)
    return left, right


# ───────────────────────── 어떤 신호가 떠 있나 ─────────────────────────

def collect(fight, hide_tele: bool, inked: bool, dark: bool) -> list[dict]:
    """지금 칸에 띄울 신호들. hide_tele = 소리 전용 물고기(예고는 소리로만), inked = 먹물/어둠(점프 원 예고 숨김),
    dark = 동굴(행동 아이콘 대신 천장 반사광 — 꺾기 타이밍은 유지)."""
    b = fight.brain
    out: list[dict] = []
    tele = b.state == "telegraph"
    pend = b.pending if tele else None
    stagger = cfg()["dual_stagger_sec"]

    def add(action, kind, family=None, hand=None, **kw):
        fam = family or family_of(action)
        if fam is None or fam in ("combo", "fake"):
            return
        out.append(dict(action=action, kind=kind, family=fam, hand=hand or hand_of(action, fam), **kw))

    # 판정이 있는 신규 패턴 (예고 중이면 active=False)
    for i, p in enumerate(fight.pats):
        if not p.active and (hide_tele or dark):
            continue
        if not p.active and pend == "dual" and i == 1 and b.state_t < stagger:
            continue  # 이중 패턴: 두 번째 예고는 시차를 두고
        if p.id == "hide":
            peek = p.active and getattr(p, "peeking", False)
            add("hide", "act" if p.active else "tele", "reel" if peek else "release", "R" if peek else "L", pat=p)
        else:
            add(p.id, "act" if p.active else "tele", pat=p)
    # 기존 행동·점프형
    if tele and pend == "rush" and not (hide_tele or dark):
        add("rush", "tele")
    elif b.state == "rush":
        add("rush", "act")
    turn_on = fight.turn_flick is not None and not fight.turn_flick["done"] and b.turn_offset() is not None
    if (tele and pend == "turn" and not hide_tele) or b.state == "turn":
        if turn_on or not dark:
            add("turn", "tele" if tele else "act", flick=turn_on)
    jumping = b.state == "jump" and not b.jump_judged
    if (tele and pend in ("jump", "thrash", "leap") and not inked and not hide_tele and not fight.pre_judged) or jumping:
        kind = b.jump_kind if jumping else {"jump": "dip", "thrash": "thrash", "leap": "swipe"}[pend]
        action = {"dip": "jump", "thrash": "thrash", "swipe": "leap"}[kind]
        add(action, "act" if jumping else "tele")
    if b.state == "charge" and not hide_tele:
        add("charge", "act")
    if b.state in ("tired", "exhausted"):  # 가짜 지침(fake_tired)은 몸짓만 — 칸에 안 뜬다
        add("tired", "act")
    # 꼬임 잔여 (비틀기 판정이 끝난 뒤 남은 게이지)
    if fight.twist.value > 0.5 and not any(s["action"] == "twist" for s in out):
        add("twist", "residue")
    return out


# ───────────────────────── 그리기 ─────────────────────────

_BOX_BACK: dict = {}


def _box(canvas, pos, col, lit: bool, ok: bool, size: int) -> pygame.Rect:
    r = pygame.Rect(0, 0, size, size)
    r.center = pos
    back = _BOX_BACK.get(size)   # 크기별 한 번만 (O4)
    if back is None:
        back = _BOX_BACK[size] = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.rect(back, (12, 16, 30, 175), back.get_rect(), border_radius=8)
    canvas.blit(back, r.topleft)
    pygame.draw.rect(canvas, col if lit else tuple(int(c * 0.55) for c in col), r, 3 if OPTS["strong"] else 2,
                     border_radius=8)
    if white_edge(col):
        pygame.draw.rect(canvas, (255, 255, 255), r.inflate(4, 4), 1, border_radius=9)
    if ok:
        pygame.draw.rect(canvas, GOOD, r.inflate(-6, -6), 1, border_radius=6)
    return r


def _bar(canvas, x, y, w, frac, col, need=None) -> None:
    canvas.fill(SHADOW, (x - 1, y - 1, w + 2, 5))
    canvas.fill((40, 44, 62), (x, y, w, 3))
    canvas.fill(col, (x, y, int(w * max(0.0, min(1.0, frac))), 3))
    if need is not None:
        canvas.fill((255, 255, 255), (x + int(w * need), y - 2, 1, 7))


def _tri(canvas, x, y, d: int, s: int, col) -> None:
    """d = -1 위(▲) / +1 아래(▼)."""
    pts = [(x - s, y - d * s // 2), (x + s, y - d * s // 2), (x, y + d * (s // 2 + 2))]
    pygame.draw.polygon(canvas, SHADOW, [(px + 1, py + 1) for px, py in pts])
    pygame.draw.polygon(canvas, col, pts)


def _arrow(canvas, x, y, dx: int, dy: int, col) -> None:
    """방향 화살표 (dx, dy 중 하나만 ±1)."""
    L = 11
    x0, y0, x1, y1 = x - dx * L, y - dy * L, x + dx * L, y + dy * L
    for c, o in ((SHADOW, 1), (col, 0)):
        pygame.draw.line(canvas, c, (x0 + o, y0 + o), (x1 + o, y1 + o), 4)
        px, py = -dy, dx
        pygame.draw.polygon(canvas, c, [(x1 + dx * 5 + o, y1 + dy * 5 + o), (x1 - dx * 3 + px * 7 + o, y1 - dy * 3 + py * 7 + o),
                                        (x1 - dx * 3 - px * 7 + o, y1 - dy * 3 - py * 7 + o)])


def _palm(canvas, x, y, col) -> None:
    """참기: 손바닥 ✋."""
    canvas.fill(SHADOW, (x - 6, y - 2, 13, 11))
    canvas.fill(col, (x - 7, y - 3, 13, 11))
    for i in range(4):
        canvas.fill(col, (x - 7 + i * 3 + 1, y - 10 + (1 if i in (0, 3) else 0), 2, 7))
    canvas.fill(col, (x + 6, y - 1, 3, 5))  # 엄지


def family_icon(canvas, fam: str, x: int, y: int, col, t: float, small: bool = False, **kw) -> None:
    """계열 아이콘 (작게 = 콤보 미리보기 줄)."""
    if fam == "release":
        icons.release(canvas, x, y, col, 3 if small else 6)
    elif fam == "reel":
        _tri(canvas, x, y - (0 if small else 2), -1, 4 if small else 8, col)
    elif fam == "timing":
        pygame.draw.circle(canvas, col, (x, y), 5 if small else 9, 2)
        pygame.draw.circle(canvas, col, (x, y), 1 if small else 2)
    elif fam == "direction":
        dx, dy = kw.get("dir", (1, 0))
        if small:
            pygame.draw.line(canvas, col, (x - dx * 4 - dy * 0, y - dy * 4), (x + dx * 4, y + dy * 4), 2)
            pygame.draw.circle(canvas, col, (x + dx * 4, y + dy * 4), 2)
        else:
            _arrow(canvas, x, y, dx, dy, col)
    elif fam == "endure":
        if small:
            canvas.fill(col, (x - 3, y - 3, 6, 6))
        else:
            _palm(canvas, x, y, col)
    elif fam == "gesture":
        from src.ui.pattern_guide import _ring_arrow
        _ring_arrow(canvas, x, y, 4 if small else 9, t, col, 1 if small else 2)


def draw(canvas, fight, signals: list[dict], touch: bool, left_handed: bool, t: float) -> None:
    w, h = canvas.get_size()
    L, R = slot_positions(w, h, touch, left_handed)
    size = cfg()["slots"]["size"]
    spread = cfg()["slots"]["ring_spread"]
    k = OPTS["scale"]
    ks = int(size * k)
    fc = getattr(fight, "cfg", None) or load_json("fishing_config.json")["fight"]   # 비늘석 퍼펙트 판정 구간이 반영된 값 (46장 S4)
    used = {"L": 0, "R": 0}
    for s in signals:
        base = L if s["hand"] == "L" else R
        n = used[s["hand"]]
        used[s["hand"]] += 1
        out = -1 if (base[0] < w // 2) else 1   # 같은 손 두 번째 신호는 바깥쪽으로 비켜서
        pos = (base[0] + out * n * (ks + 6), base[1])
        if k == 1.0:
            _draw_one(canvas, fight, s, pos, size, spread, fc, t)
        else:
            # 칸 크기 설정: 기본 크기로 그린 칸(링 포함)을 통째로 키우거나 줄인다
            side = size + 2 * spread + 28
            tmp = pygame.Surface((side, side), pygame.SRCALPHA)
            _draw_one(tmp, fight, s, (side // 2, side // 2), size, spread, fc, t)
            img = pygame.transform.smoothscale(tmp, (int(side * k), int(side * k)))
            canvas.blit(img, img.get_rect(center=pos))
        if OPTS["strong"] and s["kind"] == "tele" and int(t * 6) % 2 == 0:
            # 소리 신호 끔: 예고 동안 바깥 테두리를 하나 더 (그림 강조)
            col = color_of(s["family"]) if s["family"] in cfg()["families"] else DIM
            pygame.draw.rect(canvas, col, pygame.Rect(0, 0, ks + 10, ks + 10).move(pos[0] - ks // 2 - 5,
                                                                                   pos[1] - ks // 2 - 5), 2,
                             border_radius=11)
    if signals:
        _tension_strip(canvas, fight, (w // 2, L[1] + ks // 2 + 12), t)
    _combo_preview(canvas, fight, (w // 2, L[1] - ks // 2 - 16), t)


def _draw_one(canvas, fight, s: dict, pos, size: int, spread: float, fc: dict, t: float) -> None:
    b = fight.brain
    fam, act, kind = s["family"], s["action"], s["kind"]
    col = color_of(fam)
    pat = s.get("pat")
    tele = kind == "tele"
    blink_on = not tele or int(t * 6) % 2 == 0
    ok = bool(pat is not None and pat.active and pat.last_ok)
    x, y = pos
    # 타이밍(링)은 링 자체가 남은 시간 — 칸 테두리 없이 링만
    if act in ("jump", "thrash"):
        second = act == "thrash" and b.state == "jump" and b.thrash_judged[0]
        tt = b.time_to_second() if second else b.time_to_apex()
        total = (b.jump_air / 2 - b.pcfg["thrash"]["land_before"] + b.jump_air / 2) if second \
            else b.cur_telegraph + b.jump_air / 2
        _box(canvas, pos, col, True, False, size)
        fight_fx.draw_jump_ring(canvas, pos, tt, max(0.3, total), fc["perfect_window_sec"], fc["good_window_sec"], t,
                                spread=spread)
        if act == "thrash":
            icons.pips(canvas, x, y + size // 2 + 6, 2, col, 6)
        return
    if act == "leap":
        _box(canvas, pos, col, True, False, size)
        total = b.cur_telegraph + b.jump_air / 2
        fight_fx.draw_swipe_ring(canvas, pos, b.time_to_apex(), total, fc["perfect_window_sec"], fc["good_window_sec"],
                                 -b.leap_dir, t, spread=spread)
        return
    _box(canvas, pos, col, blink_on, ok, size)
    by = y + size // 2 + 4
    bx, bw = x - size // 2 + 3, size - 6
    if act == "turn":
        tf = fight.turn_flick
        need = tf["need"] if tf else -(b.turn_dir or 1)
        family_icon(canvas, fam, x, y - 4, col, t, dir=(need, 0))
        off = b.turn_offset()
        if s.get("flick") and off is not None:
            cf = load_json("fishing_config.json")["flick"]
            before, after, perf = cf["turn_before_sec"], cf["turn_after_sec"], cf["turn_perfect_sec"]
            span = before + after
            canvas.fill((40, 44, 62), (bx, by, bw, 3))
            zero = bx + int(bw * before / span)
            canvas.fill((255, 214, 90), (zero - max(1, int(bw * perf / span)), by, max(2, int(bw * perf * 2 / span)), 3))
            k = max(-0.2, min(1.0, (off + before) / span))
            canvas.fill((255, 255, 255), (bx + int(bw * k), by - 2, 2, 7))
        return
    if act in ("dive", "surface"):
        family_icon(canvas, fam, x, y - 3, col, t, dir=(0, -1 if act == "dive" else 1))
    elif act == "pump" and pat is not None and pat.active:
        # 펌핑: 박마다 줄어드는 링이 '박 사이(감기)'에 맞는다 + 박 점
        iv = pat.interval
        k = (pat.t / iv) % 1.0
        ttg = (0.5 - k) * iv
        if ttg < -0.2 * iv:
            ttg += iv
        fight_fx.draw_jump_ring(canvas, pos, ttg, iv, 0.12, 0.2 * iv, t, spread=spread * 0.6)
        nb = max(1, b.pump_beats)
        icons.pips(canvas, x, by + 2, min(nb, 8), col, 5)
        if pat.beat > 0:
            icons.pips(canvas, x - (min(nb, 8) - 1) * 5 // 2 + (min(pat.beat, nb) - 1) * 5, by + 2, 1, (255, 255, 255))
        return
    else:
        family_icon(canvas, fam, x, y - 3, col, t)
    if kind == "residue":
        _bar(canvas, bx, by, bw, fight.twist.value / 100, BAD if fight.twist.value >= 75 else col)
        return
    if tele:
        if act == "bite":
            remain = b.timer if b.state == "telegraph" else 0.0
            _bar(canvas, bx, by, bw, 1 - remain / max(0.01, b.cur_telegraph), col)
            canvas.fill((255, 255, 255), (bx + bw - 1, by - 2, 2, 7))
        else:
            _bar(canvas, bx, by, bw, 1 - b.signal_progress(), DIM)   # 예고 남은 시간
        return
    # 행동 중 진행
    if act == "rush":
        if math.sin(t * 14) > 0:  # 돌진 중: 바깥 테두리 맥동
            pygame.draw.rect(canvas, col, pygame.Rect(x - size // 2 - 3, y - size // 2 - 3, size + 6, size + 6), 1,
                             border_radius=10)
    elif act == "charge":
        _bar(canvas, bx, by, bw, b.state_t / max(0.01, b.state_t + b.timer), col)
    elif act == "tired":
        pass
    elif pat is not None:
        if act == "reverse":
            _bar(canvas, bx, by, bw, pat.gauge / 100, GOOD if pat.gauge >= pat.c["keep_level"] else BAD,
                 pat.c["keep_level"] / 100)
            if int(t * 10) % 2 == 0:
                _tri(canvas, x, y - 5, -1, 8, (255, 255, 255))  # 연타: ▲ 깜빡
        elif act == "twist":
            _bar(canvas, bx, by, bw, min(1.0, pat.t / pat.dur), col)
        elif act == "hide":
            peek = getattr(pat, "peeking", False)
            _bar(canvas, bx, by, bw, pat.ratio, (255, 214, 90) if peek else (GOOD if pat.hold_t > 0 else BAD))
            if peek and int(t * 10) % 2 == 0:
                pygame.draw.rect(canvas, (255, 214, 90), pygame.Rect(x - size // 2 - 3, y - size // 2 - 3, size + 6,
                                                                     size + 6), 2, border_radius=10)
        elif act == "bite":
            _bar(canvas, bx, by, bw, 1.0, GOOD if pat.passed() else BAD)
        else:  # shake·dive·surface: 유지율
            r = pat.ratio
            _bar(canvas, bx, by, bw, r, GOOD if r >= pat.need and pat.last_ok else (255, 214, 90) if r >= pat.need else BAD,
                 pat.need)


def _tension_strip(canvas, fight, center, t: float) -> None:
    """칸 사이 아래 작은 장력 줄: 신호에 대응하며 장력을 같이 본다 (숨기 목표 구간 금색)."""
    w = 96
    x, y = center[0] - w // 2, center[1]

    def tx(v):
        return x + int(max(0.0, min(100.0, v)) / 100 * w)

    gl, gh = fight.green_low, fight.green_high
    canvas.fill(SHADOW, (x - 1, y - 1, w + 2, 5))
    canvas.fill((52, 64, 86), (x, y, tx(gl) - x, 3))
    canvas.fill((40, 100, 52), (tx(gl), y, tx(gh) - tx(gl), 3))
    canvas.fill((120, 38, 36), (tx(gh), y, tx(100) - tx(gh), 3))
    hide = next((p for p in fight.pats if p.id == "hide" and p.active and not p.success), None)
    if hide is not None:
        lo, hi = tx(gl + hide.c["low_min"]), tx(gl + hide.c["low_max"])
        pygame.draw.rect(canvas, (255, 214, 90), (lo - 1, y - 2, max(2, hi - lo) + 2, 7), 1)
    zone = fight.zone()
    blink = zone != "green" and int(t * 8) % 2 == 0
    col = {"green": (70, 180, 95), "red": (205, 62, 58), "slack": (140, 160, 200)}[zone]
    canvas.fill((255, 255, 255) if not blink else col, (tx(fight.tension) - 1, y - 3, 2, 9))


def _combo_preview(canvas, fight, center, t: float) -> None:
    """연쇄 콤보: 예고 동안 행동 아이콘 줄, 진행하면서 하나씩 꺼진다."""
    b = fight.brain
    if b.signal == "chain" and not b.sound_only:
        seq, cur = b.chain_seq, -1
    elif fight.combo is not None:
        seq, cur = fight.combo.seq, fight.combo.index
    else:
        return
    if not seq:
        return
    n = len(seq)
    step = 22
    x0 = center[0] - (n - 1) * step // 2
    y = center[1]
    back = pygame.Surface(((n - 1) * step + 24, 18), pygame.SRCALPHA)
    pygame.draw.rect(back, (12, 16, 30, 160), back.get_rect(), border_radius=6)
    canvas.blit(back, (x0 - 12, y - 9))
    failed = fight.combo is not None and fight.combo.failed
    for i, a in enumerate(seq):
        cx = x0 + i * step
        fam = family_of(a) or "direction"
        if i < cur:
            pygame.draw.circle(canvas, (60, 66, 90), (cx, y), 3)  # 끝난 단계: 꺼짐
            continue
        col = color_of(fam) if fam in cfg()["families"] else DIM
        if i == cur:
            pygame.draw.circle(canvas, BAD if failed else (255, 255, 255), (cx, y), 8, 1)
        dirv = (0, -1) if a == "dive" else (0, 1) if a == "surface" else (1, 0)
        family_icon(canvas, fam, cx, y, col, t, small=True, dir=dirv)


# ───────────────────────── 결과 화면 (31장 C5) ─────────────────────────

def _mini_box(canvas, action: str, x: int, y: int, t: float) -> None:
    fam = family_of(action) or "direction"
    if fam not in cfg()["families"]:
        fam = "direction"
    col = color_of(fam)
    r = pygame.Rect(0, 0, 24, 24)
    r.center = (x, y)
    canvas.fill((12, 16, 30), r)
    pygame.draw.rect(canvas, col, r, 2, border_radius=5)
    dirv = (0, -1) if action == "dive" else (0, 1) if action == "surface" else (1, 0)
    family_icon(canvas, fam, x, y, col, t, small=True, dir=dirv)


def draw_result_icons_column(canvas, missed: list, ups: list, pos, t: float, per_row: int = 5) -> int:
    """포획 결과 화면용: 왼쪽 위 기록 배지 아래에 세로로 — '놓친 신호' 줄, 그 아래 '숙련' 줄 (한 줄 최대 per_row 개,
    가운데 글자(가치·랭크 보너스)를 가리지 않게). 그린 높이를 돌려준다."""
    from src.ui.hud import text
    x, y = pos
    y0 = y
    for label, col, lst, up in (("놓친 신호", (255, 150, 130), missed, False), ("숙련 상승", GOOD, ups, True)):
        if not lst:
            continue
        text(canvas, label, (x, y), col, 11, "midleft")
        y += 22
        for i, a in enumerate(lst[:per_row * 2]):
            cx, cy = x + 12 + (i % per_row) * 28, y + (i // per_row) * 28
            _mini_box(canvas, a, cx, cy, t)
            if up:
                _tri(canvas, cx + 10, cy - 9, -1, 4, GOOD)
            else:
                pygame.draw.line(canvas, BAD, (cx + 6, cy + 4), (cx + 12, cy + 10), 2)
                pygame.draw.line(canvas, BAD, (cx + 12, cy + 4), (cx + 6, cy + 10), 2)
        y += 28 * ((min(len(lst), per_row * 2) - 1) // per_row + 1) - 2
    return y - y0


def draw_result_icons(canvas, missed: list, ups: list, pos, t: float) -> int:
    """놓친 신호(빨간 X) · 숙련도 상승(초록 ▲)을 아이콘으로. 그린 너비를 돌려준다."""
    from src.ui.hud import text
    x, y = pos
    x0 = x
    if missed:
        text(canvas, "놓친 신호", (x, y), (255, 150, 130), 11, "midleft")
        x += 52
        for a in missed[:6]:
            _mini_box(canvas, a, x + 12, y, t)
            pygame.draw.line(canvas, BAD, (x + 18, y + 4), (x + 26, y + 12), 2)
            pygame.draw.line(canvas, BAD, (x + 26, y + 4), (x + 18, y + 12), 2)
            x += 28
        x += 10
    if ups:
        text(canvas, "숙련", (x, y), GOOD, 11, "midleft")
        x += 28
        for a in ups[:6]:
            _mini_box(canvas, a, x + 12, y, t)
            _tri(canvas, x + 22, y - 9, -1, 4, GOOD)
            x += 28
    return x - x0
