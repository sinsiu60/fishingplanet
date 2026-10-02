"""신규 패턴(U3·U4) 화면 표시: 대응 안내 패널, 꼬임 게이지, 연쇄 콤보 순서, 줄 나선.

안내 패널은 화면 위쪽 가운데 (알림 줄 아래, 수평선 위). 예고 중엔 '준비'와 남은 시간, 행동 중엔 지금 잘하고 있는지(유지율 막대).
소리 전용 물고기(안개잉어)는 예고 중엔 패널을 숨긴다 (예고는 소리로만 — 행동이 시작되면 보임).
"""
import math

import pygame

from src.core.config import load_json
from src.ui import icons
from src.ui.fight_fx import ICON_COL, draw_behavior_icon
from src.ui.hud import SHADOW, text

PANEL = (16, 20, 36)
GOOD = (130, 255, 180)
BAD = (255, 110, 95)
TEXT = (236, 240, 248)
DIM = (150, 160, 185)

# (PC 안내, 터치 안내)
PROMPT = {
    "shake": ("감기 멈추고 마우스 가만히", "패드에서 손 떼고 가만히"),
    "dive": ("마우스를 위로 — 낚싯대 세우기", "패드를 위로 밀기"),
    "surface": ("마우스를 아래로 — 낚싯대 눕히기", "패드를 아래로 밀기"),
    "reverse": ("좌클릭 연타로 감기!", "패드 연타로 감기!"),
    "twist": ("마우스로 원을 그려 풀기", "패드 위에서 원 그리기"),
    "hide": ("감기 멈추고 풀어 주기", "패드에서 손 떼고 풀어 주기"),
    "pump": ("북소리 사이에만 좌클릭 감기", "북소리 사이에만 패드 누르기"),
    "bite": ("번쩍이는 순간 Shift!", "번쩍이는 순간 ▼ 길게!"),
}
ACTION_KO = {"rush": "돌진", "jump": "점프", "leap": "몸털기", "turn": "방향 전환", "charge": "멈춤"}


def names() -> dict:
    return load_json("patterns.json")["names"]


def action_name(a: str) -> str:
    return names().get(a) or ACTION_KO.get(a, a)


def _bar(canvas, x, y, w, frac, need, col) -> None:
    canvas.fill(SHADOW, (x - 1, y - 1, w + 2, 6))
    canvas.fill((40, 44, 62), (x, y, w, 4))
    canvas.fill(col, (x, y, int(w * max(0.0, min(1.0, frac))), 4))
    if need is not None:
        nx = x + int(w * need)
        canvas.fill((255, 255, 255), (nx, y - 2, 1, 8))


def draw_pattern_panel(canvas, fight, touch: bool, t: float) -> None:
    y0 = 76  # 알림(58) 아래, 수평선 위
    y = _draw_panel_rows(canvas, fight, touch, t, y0)
    draw_mini_tension(canvas, fight, t, y if y > y0 else None)


def _draw_panel_rows(canvas, fight, touch: bool, t: float, y: int) -> int:
    """안내 줄들을 위에서부터 그리고, 다음 줄이 올 y를 돌려준다 (아무것도 없으면 그대로)."""
    b = fight.brain
    w = canvas.get_width()
    # 연쇄 콤보: 순서 줄
    combo_seq = None
    if b.signal == "chain" and not b.sound_only:
        combo_seq, cur = b.chain_seq, -1
    elif fight.combo is not None:
        combo_seq, cur = fight.combo.seq, fight.combo.index
    if combo_seq:
        # 콤보: 행동 아이콘을 한 줄로 (글자 없음, 31장) — 지난 것은 흐리게, 지금 것은 금색 고리
        n = len(combo_seq)
        step = 24
        x0 = w // 2 - (n - 1) * step // 2
        bg = pygame.Rect(x0 - 16, y - 9, (n - 1) * step + 32, 19)
        canvas.fill(PANEL, bg)
        pygame.draw.rect(canvas, ICON_COL["chain"], bg, 1)
        failed = fight.combo is not None and fight.combo.failed
        for i, a in enumerate(combo_seq):
            cx = x0 + i * step
            kind = a if a in ICON_COL else "rush"
            if i < cur:
                pygame.draw.circle(canvas, (60, 66, 90), (cx, y), 6)
                continue
            draw_behavior_icon(canvas, (cx, y + 20), kind, 1.0, 1, t)
            if i == cur:
                pygame.draw.circle(canvas, BAD if failed else (255, 240, 160), (cx, y), 11, 1)
            if i < n - 1:
                canvas.fill(DIM, (cx + 11, y, 3, 1))
        y += 22
    # 패턴 대응 (이중 패턴이면 두 줄): 아이콘 + 막대, 글자 없음
    for pat in list(fight.pats):
        if b.sound_only and not pat.active:
            continue
        _judge_row(canvas, fight, pat, touch, t, w, y)
        y += 20
    # 공중 몸부림: 아이콘 + 숙이기 두 번 자리(점 2개)
    thrash = b.telegraphing("thrash") or (b.state == "jump" and b.jump_kind == "thrash" and not b.jump_judged)
    if thrash and not b.sound_only:
        pw = 120
        x = w // 2 - pw // 2
        col = ICON_COL["thrash"]
        bg = pygame.Rect(x, y - 8, pw, 17)
        canvas.fill(PANEL, bg)
        pygame.draw.rect(canvas, col, bg, 1)
        draw_behavior_icon(canvas, (x + 12, y + 20), "thrash", 1.0, 1, t)
        n = 1 + (1 if b.state == "jump" and b.thrash_judged[0] else 0)
        for i in range(2):
            c = (x + 60 + i * 22, y)
            pygame.draw.circle(canvas, col, c, 5, 0 if i < n - 1 else 1)
        y += 20
    # 꼬임 게이지 (행동이 끝나도 남는다): 나선 아이콘 + 막대
    tw = fight.twist.value
    if tw > 0.5:
        gw = 120
        x = w // 2 - gw // 2
        danger = tw >= 75 and int(t * 8) % 2 == 0
        col = (255, 90, 70) if tw >= 75 else (255, 200, 90) if tw >= 40 else ICON_COL["twist"]
        icons.twist(canvas, x - 10, y + 1, BAD if danger else col)
        _bar(canvas, x, y, gw, tw / 100, None, col)
        y += 17
    return y


# ── 가운데 미니 장력 바 ──
# 패턴 안내가 떠 있는 동안만 그 바로 아래에 얇게 (왼쪽 장력 게이지와 같은 색·같은 눈금, 가로로).
# 장력으로 판정하는 패턴은 목표 구간을 겹쳐 그린다: 숨기 = 풀어 줄 구간(금색), 콤보 돌진 = 빨간 구간 경계 강조.
_T_GREEN, _T_RED, _T_SLACK = (70, 180, 95), (205, 62, 58), (80, 98, 130)
_TARGET = (255, 214, 90)


def _dark(c, k):
    return tuple(int(v * (1 - k)) for v in c)


def draw_mini_tension(canvas, fight, t: float, y: int | None) -> None:
    """y = 안내 패널 다음 줄 위치 (패널이 없으면 None → 서서히 사라짐). 패널 아래에 붙은 얇은 줄로 그린다."""
    st = fight.__dict__.setdefault("_mini_tension", {"a": 0.0, "y": 0, "t": t})
    dt = max(0.0, min(0.1, t - st["t"]))
    st["t"] = t
    if y is not None:
        st["y"] = y
        st["a"] = min(1.0, st["a"] + dt * 6)  # 약 0.17초에 걸쳐 나타남
    else:
        st["a"] = max(0.0, st["a"] - dt * 4)
    if st["a"] <= 0:
        return
    pw, ph = 250, 12
    surf = pygame.Surface((pw, ph + 4), pygame.SRCALPHA)
    surf.fill(PANEL, (0, 0, pw, ph))
    pygame.draw.rect(surf, (52, 60, 88), (0, 0, pw, ph), 1)
    icons.tension(surf, 14, ph // 2, DIM)
    bx, bw, by = 30, pw - 36, ph // 2 - 2

    def tx(v):
        return bx + int(max(0.0, min(100.0, v)) / 100 * bw)

    gl, gh = fight.green_low, fight.green_high
    surf.fill(SHADOW, (bx - 1, by - 1, bw + 2, 6))
    surf.fill(_dark(_T_SLACK, 0.35), (bx, by, tx(gl) - bx, 4))
    surf.fill(_dark(_T_GREEN, 0.45), (tx(gl), by, tx(gh) - tx(gl), 4))
    surf.fill(_dark(_T_RED, 0.4), (tx(gh), by, tx(100) - tx(gh), 4))
    # 목표 구간 (장력으로 판정하는 패턴): 숨기 = 풀어 줄 구간, 그 위 초록 가운데부터는 줄이 쓸림
    hide = next((p for p in fight.pats if p.id == "hide" and p.active and not p.success), None)
    if hide is not None:
        lo, hi = tx(gl + hide.c["low_min"]), tx(gl + hide.c["low_max"])
        on = hide.hold_t > 0 or hide.peeking
        surf.fill((*_TARGET, 150 if on else 110), (lo, by, max(2, hi - lo), 4))
        pygame.draw.rect(surf, _TARGET, (lo - 1, by - 2, max(2, hi - lo) + 2, 8), 1)
        surf.fill(_T_RED, (tx((gl + gh) / 2), by - 2, 1, 8))
    rush_combo = fight.combo is not None and fight.brain.state == "rush"
    surf.fill((255, 120, 110) if rush_combo else (230, 255, 230), (tx(gh), by - 1, 1, 6))
    surf.fill((230, 255, 230), (tx(gl), by - 1, 1, 6))
    # 현재 장력 (왼쪽 게이지와 같은 색·깜빡임)
    zone = fight.zone()
    blink = zone != "green" and int(t * 8) % 2 == 0
    col = {"green": _T_GREEN, "red": _T_RED, "slack": (140, 160, 200)}[zone]
    mc = (255, 255, 255) if not blink else col
    surf.fill(mc, (tx(fight.tension) - 1, by - 2, 2, 8))
    surf.set_alpha(int(255 * st["a"]))
    canvas.blit(surf, (canvas.get_width() // 2 - pw // 2, st["y"] - 9))


def _judge_row(canvas, fight, pat, touch: bool, t: float, w: int, y: int) -> None:
    b = fight.brain
    pid = pat.id
    col = ICON_COL[pid]
    pw = 250
    x = w // 2 - pw // 2
    bg = pygame.Rect(x, y - 8, pw, 17)
    canvas.fill(PANEL, bg)
    pygame.draw.rect(canvas, col, bg, 1)
    # 이름·대응 문장 대신 아이콘 (예고 중엔 깜빡, 31장 C2 — C3에서 신호 슬롯으로 옮김)
    if pat.active or int(t * 6) % 2 == 0:
        draw_behavior_icon(canvas, (x + 12, y + 20), pid, 1.0, 1, t)
    by, bx, bw = y - 2, x + 26, pw - 32
    if pid == "pump":
        _pump_dots(canvas, fight, pat, bx, by, bw, t)
    elif pid == "bite":
        # 예고가 끝나는 순간(세로선)에 드랙 최저 — 남은 예고 시간이 줄어든다
        remain = b.timer if b.state == "telegraph" else 0.0
        total = max(0.01, b.cur_telegraph)
        _bar(canvas, bx, by, bw, 1 - remain / total, None, BAD if pat.active and not pat.passed() else col)
        canvas.fill((255, 255, 255), (bx + bw - 1, by - 3, 2, 10))
    elif not pat.active:
        _bar(canvas, bx, by, bw, 1 - b.signal_progress(), None, (120, 130, 160))  # 예고 남은 시간
    elif pid == "reverse":
        c = pat.c
        _bar(canvas, bx, by, bw, pat.gauge / 100, c["keep_level"] / 100, GOOD if pat.gauge >= c["keep_level"] else BAD)
    elif pid == "twist":
        _bar(canvas, bx, by, bw, min(1.0, pat.t / pat.dur), None, (120, 130, 160))
    elif pid == "hide":
        flash = pat.peeking and int(t * 10) % 2 == 0
        _bar(canvas, bx, by, bw, pat.ratio, None, (255, 214, 90) if pat.peeking else GOOD if pat.hold_t > 0 else BAD)
        if flash:
            pygame.draw.rect(canvas, (255, 214, 90), bg, 2)
    else:
        ok = pat.ratio >= pat.need
        _bar(canvas, bx, by, bw, pat.ratio, pat.need, GOOD if ok and pat.last_ok else (255, 214, 90) if ok else BAD)


def _pump_dots(canvas, fight, pat, x: int, y: int, w: int, t: float) -> None:
    """펌핑: 박마다 칸 — 당김(빨강 띠) / 감을 자리(초록 띠), 지난 박은 성공·실패 색."""
    b = fight.brain
    n = max(1, b.pump_beats if pat.active else pat.c["beats"][0])
    cw = w / n
    for i in range(n):
        cx = int(x + i * cw)
        canvas.fill((40, 44, 62), (cx + 1, y - 1, int(cw) - 2, 6))
        canvas.fill((200, 90, 80), (cx + 1, y - 1, max(1, int(cw * 0.25)), 6))          # 당김
        canvas.fill((70, 140, 90), (cx + int(cw * 0.3), y - 1, max(1, int(cw * 0.4)), 6))  # 감을 자리
        if i < len(pat.hits) and i < pat.beat:
            good = pat.hits[i] and not pat.bad[i]
            canvas.fill(GOOD if good else BAD, (cx + 1, y - 1, int(cw) - 2, 2))
    if pat.active:
        k = pat.t / pat.interval
        mx = int(x + min(n, k) * cw)
        canvas.fill((255, 255, 255), (mx, y - 3, 1, 10))


def draw_line_twist(canvas, p0, p1, amount: float, t: float) -> None:
    """줄 비틀기: 줄을 따라 감기는 나선 무늬 (amount 0~1)."""
    if amount <= 0.02:
        return
    x0, y0 = p0
    x1, y1 = p1
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy)
    if length < 4:
        return
    nx, ny = -dy / length, dx / length
    n = max(6, int(length / 6))
    col = ICON_COL["twist"]
    amp = 1.5 + 2.5 * amount
    prev = None
    for i in range(n + 1):
        k = i / n
        if k < 0.15:
            continue  # 낚싯대 끝 근처는 비운다
        off = math.sin(k * 26 - t * 16) * amp * min(1.0, k * 2)
        pt = (x0 + dx * k + nx * off, y0 + dy * k + ny * off)
        if prev is not None:
            pygame.draw.line(canvas, col, prev, pt, 1)
        prev = pt
