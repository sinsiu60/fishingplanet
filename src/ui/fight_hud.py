"""파이팅 HUD: 장력·줄·바늘 게이지, 물고기 체력 바, 드랙, 판정 팝업, 결과 패널, F1 디버그."""
import math

import pygame

from src.core.fonts import get_font
from src.core.mathutil import clamp, lerp, lerp_color
from src.render.fish_draw import RANK_COLORS
from src.ui.hud import SHADOW, text

RARITY_COLOR = {"common": (230, 230, 230), "uncommon": (130, 230, 150), "rare": (130, 190, 255),
                "legend": (255, 214, 90)}
STATE_COLOR = {"지침": (130, 230, 255), "완전 지침": (130, 230, 255), "멈춤": (255, 240, 140),
               "회복 중": (200, 200, 200)}
GREEN, RED, SLACK = (70, 180, 95), (205, 62, 58), (80, 98, 130)
PANEL = (24, 30, 50)


def _vbar(canvas, x, y, w, h, frac, color, bg=(36, 40, 56)):
    canvas.fill(SHADOW, (x - 1, y - 1, w + 2, h + 2))
    canvas.fill(bg, (x, y, w, h))
    fh = int(h * clamp(frac, 0, 1))
    canvas.fill(color, (x, y + h - fh, w, fh))


def draw_gauges(canvas, pal, fight, t: float) -> None:
    x, y, w, h = 8, 44, 12, 140

    def ty(v):
        return y + h - clamp(v, 0, 100) / 100 * h

    gl, gh = fight.green_low, fight.green_high
    canvas.fill(SHADOW, (x - 1, y - 1, w + 2, h + 2))
    canvas.fill(lerp_color(SLACK, (0, 0, 0), 0.35), (x, ty(gl), w, ty(0) - ty(gl)))
    canvas.fill(lerp_color(GREEN, (0, 0, 0), 0.45), (x, ty(gh), w, ty(gl) - ty(gh)))
    canvas.fill(lerp_color(RED, (0, 0, 0), 0.4), (x, ty(100), w, ty(gh) - ty(100)))
    zone = fight.zone()
    col = {"green": GREEN, "red": RED, "slack": (140, 160, 200)}[zone]
    top = ty(fight.tension)
    canvas.fill(col, (x + 2, top, w - 4, ty(0) - top))
    # 초록 구간 경계선
    canvas.fill((230, 255, 230), (x - 2, int(ty(gl)), w + 4, 1))
    canvas.fill((230, 255, 230), (x - 2, int(ty(gh)), w + 4, 1))
    # 현재 장력 표시
    blink = zone != "green" and int(t * 8) % 2 == 0
    mc = (255, 255, 255) if not blink else col
    canvas.fill(mc, (x - 3, int(top), w + 6, 2))
    pygame.draw.polygon(canvas, mc, [(x + w + 3, top), (x + w + 8, top - 4), (x + w + 8, top + 4)])
    text(canvas, "장력", (x + w // 2, y + h + 12), pal["text"], 11, "center")

    # 줄 내구도
    lf = fight.line_frac
    lc = lerp_color((255, 80, 60), (235, 240, 250), clamp((lf - 0.15) / 0.5, 0, 1))
    if lf < 0.25 and int(t * 6) % 2 == 0:
        lc = (255, 40, 40)
    _vbar(canvas, 36, y, 5, h, lf, lc)
    text(canvas, "줄", (38, y + h + 12), pal["text"], 11, "center")
    # 바늘 빠짐
    hf = fight.hook / 100
    hc = (255, 170, 60) if hf < 0.6 or int(t * 6) % 2 else (255, 60, 40)
    _vbar(canvas, 60, y, 5, h, hf, hc)
    # 실수로 쌓인 몫 (줄어들지 않음): 어두운 빨강 + 1/3 눈금
    floor = getattr(fight, "hook_floor", 0.0)
    if floor > 0:
        fh = int(h * min(1.0, floor / 100))
        canvas.fill((150, 30, 40), (60, y + h - fh, 5, fh))
    for k in (1, 2):
        canvas.fill((14, 16, 26), (59, y + h - h * k // 3, 7, 1))
    text(canvas, "바늘", (61, y + h + 12), pal["text"], 11, "center")
    # 줄 걸림 (위협 구역이 있는 낚시터만)
    if fight.hazards:
        sf = fight.snag / 100
        sc = (200, 150, 255) if not fight.in_hazard or int(t * 6) % 2 else (255, 80, 200)
        _vbar(canvas, 88, y, 5, h, sf, sc)
        text(canvas, "걸림", (90, y + h + 12), pal["text"], 11, "center")
    # 엘드라시온 기믹
    gim = getattr(fight, "gim", None)
    if gim is None:
        return
    kinds = gim.kinds(fight.brain)
    gx = 116 if fight.hazards else 88
    if "tangle" in kinds:
        tf = gim.tangle / 100
        tc = (190, 210, 230) if tf < 0.7 or int(t * 6) % 2 else (255, 120, 120)
        if gim.reel_lock_t > 0:
            tc = (255, 80, 80)
        _vbar(canvas, gx, y, 5, h, tf, tc)
        text(canvas, "엉킴", (gx + 2, y + h + 12), pal["text"], 11, "center")
        gx += 28
    if "heat" in kinds:
        # 열: 파이팅 시간이 45초에 가까워질수록 차오르고, 넘으면 붉게 맥동
        start = gim.heat_start(fight)
        hf = min(1.0, fight.elapsed / start)
        hot = gim.heat_dmg > 0
        hc = (255, 150, 60) if not hot else lerp_color((255, 80, 40), (255, 220, 120), 0.5 + 0.5 * math.sin(t * 10))
        _vbar(canvas, gx, y, 5, h, hf, hc)
        text(canvas, "열", (gx + 2, y + h + 12), pal["text"], 11, "center")
        if hot:
            text(canvas, f"-{gim.heat_dmg:.1f}%/s", (gx + 2, y - 8), (255, 140, 90), 11, "center")
        gx += 28
    if "current" in kinds:
        # 물살: 장력 게이지 바로 옆 작은 파도 + 다음 마루까지
        wx, wy = 104, y + h - 10
        left = gim.next_crest(fight)
        for i in range(24):
            ph = (fight.elapsed + i * 0.1) / gim.cfg["current_period"] * math.tau
            yy = wy - math.sin(ph) * 4
            canvas.fill(SHADOW, (wx + i * 2 + 1, int(yy) + 1, 2, 2))
            canvas.fill((255, 240, 170) if i == 0 else (230, 245, 255), (wx + i * 2, int(yy), 2, 2))
        col = (255, 220, 120) if left < 0.8 else (180, 220, 255)
        text(canvas, f"물살 마루 {left:.1f}초", (wx, wy + 10), col, 11, "midleft")
    if "ice" in kinds and gim.ice_out and int(t * 6) % 2 == 0:
        text(canvas, "얼음에 쓸린다!", (x, y - 10), (150, 220, 255), 11, "midleft")


def draw_boss_bar(canvas, pal, fight) -> None:
    w = canvas.get_width()
    bw, bh = 150, 6
    x = (w - bw) // 2
    y = 20
    fish = fight.fish
    name = fish["name"]
    if fight.brain.dragon:
        name = "용 '등용'"
    text(canvas, name, (x - 6, y + 3), RARITY_COLOR.get(fish["rarity"], (255, 255, 255)), 11, "midright")
    phases = fight.brain.phases
    if phases:
        # 페이즈 표시: ◆◆◇
        for i in range(len(phases)):
            cx = x + bw // 2 - (len(phases) - 1) * 6 + i * 12
            cy = y + 13
            col = (255, 214, 90) if i <= fight.brain.phase else (80, 70, 50)
            pygame.draw.polygon(canvas, col, [(cx, cy - 3), (cx + 3, cy), (cx, cy + 3), (cx - 3, cy)])
    canvas.fill(SHADOW, (x - 1, y - 1, bw + 2, bh + 2))
    canvas.fill((50, 30, 36), (x, y, bw, bh))
    canvas.fill((235, 90, 80), (x, y, int(bw * fight.stamina_frac), bh))
    canvas.fill((255, 170, 150), (x, y, int(bw * fight.stamina_frac), 1))
    name = fight.brain.display_name()
    text(canvas, name, (x + bw + 6, y + 3), STATE_COLOR.get(name, (255, 200, 170)), 11, "midleft")


def draw_drag(canvas, pal, fight) -> None:
    x, y = 8, 226
    r = text(canvas, "드랙", (x, y), pal["text"], 11, "midleft")
    bx = r.right + 4
    for i in range(fight.drag_steps):
        filled = i < fight.drag
        rect = (bx + i * 7, y - 3, 5, 7)
        canvas.fill(SHADOW, (rect[0] - 1, rect[1] - 1, 7, 9))
        canvas.fill((255, 220, 120) if filled else (60, 64, 80), rect)
    text(canvas, "Q- E+", (bx + fight.drag_steps * 7 + 4, y), (190, 195, 210), 11, "midleft")


def draw_distance(canvas, pal, fight, inset: int = 0) -> None:
    text(canvas, f"거리 {fight.distance:.1f}m", (canvas.get_width() - 6 - inset, 4), pal["text"], 11, "topright")


STAMP_T = 0.6       # 랭크 도장이 찍히는 시각 (획득 컷 기준)
CATCH_READY_T = 1.0  # 이후 클릭하면 계속


def draw_catch_info(canvas, result: dict, t: float, news: dict | None = None) -> None:
    """획득 컷 정보: 이름·크기 → 랭크 도장 쾅 → 기록 → 가치 숫자 올라감 (순서대로)."""
    w = canvas.get_width()
    fish = result["fish"]
    rc = RANK_COLORS[result["rank"]]
    if t > 0.3:
        k = clamp((t - 0.3) / 0.15, 0, 1)
        dy = int((1 - k) * -10)
        text(canvas, fish["name"], (w // 2, 24 + dy), RARITY_COLOR.get(fish["rarity"], (255, 255, 255)), 16, "center")
        text(canvas, f"{result['size']:.1f}cm", (w // 2, 44 + dy), (255, 255, 255), 16, "center")
        # 희귀 이상: 희귀도 리본
        if fish["rarity"] in ("rare", "legend"):
            label = {"rare": "희귀", "legend": "★ 전설 ★"}[fish["rarity"]]
            col = RARITY_COLOR[fish["rarity"]]
            rw = 44 if fish["rarity"] == "rare" else 70
            rect = pygame.Rect(0, 0, rw, 13)
            rect.center = (w // 2, 62 + dy)
            canvas.fill(lerp_color((20, 20, 30), col, 0.35), rect)
            pygame.draw.rect(canvas, col, rect, 1)
            text(canvas, label, rect.center, col, 11, "center")
    # 랭크 도장: 크게 날아와 쾅
    if t > STAMP_T:
        k = clamp((t - STAMP_T) / 0.14, 0, 1)
        scale = lerp(3.2, 1.0, k * k)
        rx, ry = w - 70, 54
        side = int(36 * scale)
        box = pygame.Rect(0, 0, side, side)
        box.center = (rx, ry)
        canvas.fill(SHADOW, box.move(2, 2))
        canvas.fill(PANEL, box)
        pygame.draw.rect(canvas, rc, box, max(2, int(2 * scale)))
        img = get_font(16).render(result["rank"], False, rc)
        img = pygame.transform.scale(img, (int(img.get_width() * scale * 1.3), int(img.get_height() * scale * 1.3)))
        canvas.blit(img, img.get_rect(center=box.center))
        if k >= 1:
            # 찍힌 뒤 퍼지는 고리
            ring = clamp((t - STAMP_T - 0.14) / 0.3, 0, 1)
            if ring < 1:
                pygame.draw.rect(canvas, rc, box.inflate(int(ring * 40), int(ring * 40)), 1)
            text(canvas, "랭크", (rx, ry + 26), (200, 205, 220), 11, "center")
    y = 192
    if t > 0.85:
        stats = (f"퍼펙트 {result['perfects']}   실수 {result['misses']}   줄 손상 {result['line_damage'] * 100:.0f}%   "
                 f"시간 {result['elapsed']:.0f}초 (기준 {result['par']:.0f}초)")
        text(canvas, stats, (w // 2, y), (220, 225, 240), 11, "center")
    if t > 0.95:
        k = clamp((t - 0.95) / 0.5, 0, 1)
        shown = int(result["price"] * (1 - (1 - k) ** 2))
        text(canvas, f"가치 {shown}원", (w // 2, y + 16), (255, 230, 140), 11, "center")
    if result["rank"] == "S" and t > 1.5:
        text(canvas, "S랭크 보너스: 크기 +10%, 판매가 ×2", (w // 2, y + 32), RANK_COLORS["S"], 11, "center")
    # 새 기록 배지 (왼쪽 위에 차례로)
    if news and t > 1.0:
        badges = []
        if news.get("new"):
            badges.append(("NEW! 도감 등록", (255, 230, 120)))
        if news.get("record"):
            badges.append(("최대 크기 경신!", (140, 240, 150)))
        if news.get("gold"):
            badges.append(("도감 금테 획득!", RANK_COLORS["S"]))
        if news.get("hint"):
            badges.append((f"힌트 해금 ({news['hint']}회) - 도감 확인", (150, 220, 255)))
        for i, (label, col) in enumerate(badges):
            if t > 1.0 + i * 0.15:
                text(canvas, label, (12, 24 + i * 15), col, 11, "midleft")
    if t > 1.2:
        text(canvas, "살림망에 보관했어요 (B: 상점에서 판매)", (w // 2, 240), (170, 180, 200), 11, "center")
    if t > CATCH_READY_T + 0.5 and int(t * 2) % 2 == 0:
        text(canvas, "클릭해서 계속", (w // 2, 256), (170, 180, 200), 11, "center")


def draw_lose_panel(canvas, fight, title_reason: tuple[str, str], t: float) -> None:
    w = canvas.get_width()
    title, advice = title_reason
    pw, ph = 300, 92
    x, y = (w - pw) // 2, 70
    canvas.fill(SHADOW, (x + 2, y + 2, pw, ph))
    canvas.fill(PANEL, (x, y, pw, ph))
    pygame.draw.rect(canvas, (220, 90, 80), (x, y, pw, ph), 1)
    text(canvas, f"놓쳤다! — {title}", (w // 2, y + 14), (255, 140, 120), 16, "center")
    # 조언 줄바꿈
    lines = _wrap(advice, 30)
    for i, ln in enumerate(lines[:2]):
        text(canvas, ln, (w // 2, y + 38 + i * 14), (230, 232, 240), 11, "center")
    text(canvas, f"{fight.fish['name']} · 남은 체력 {fight.stamina_frac * 100:.0f}% · {fight.elapsed:.0f}초",
         (w // 2, y + 72), (170, 178, 196), 11, "center")
    if t > 0.8 and int(t * 2) % 2 == 0:
        text(canvas, "클릭해서 계속", (w // 2, y + ph + 12), (170, 180, 200), 11, "center")


def _wrap(s: str, width: int) -> list[str]:
    from src.platform.hints import localize
    words = localize(s).split(" ")  # 모바일: 조작 문구를 터치 문구로 바꾼 뒤 줄바꿈
    lines, cur = [], ""
    for wd in words:
        if len(cur) + len(wd) + 1 > width and cur:
            lines.append(cur)
            cur = wd
        else:
            cur = f"{cur} {wd}".strip()
    if cur:
        lines.append(cur)
    return lines


def draw_debug(canvas, fight, extra: list[str] | None = None, right: int = 4) -> None:
    b = fight.brain
    tta = b.time_to_apex()
    lines = [
        f"장력 {fight.tension:.0f}→{fight.target:.0f} [{fight.green_low}-{fight.green_high}]",
        f"드랙 {fight.drag}/{fight.drag_steps} 한계{fight.drag_limit:.0f}",
        f"거리 {fight.distance:.1f} 감{fight.reel_speed_now:.1f} 풀{fight.payout_now:.1f}",
        f"줄 {fight.line:.0f} 바늘 {fight.hook:.0f} 걸림 {fight.snag:.0f}",
        f"체력 {fight.stamina:.0f} burst {b.burst:.2f}",
        f"{b.state} {b.pending or ''} {b.timer:.2f}s",
        f"정렬 {fight.align:+.2f} 측 {fight.fish_side():+.2f}",
        f"정점 {tta:+.2f}s" if tta < 50 else "정점 -",
        f"P{fight.perfects} G{fight.goods} M{fight.misses} {fight.elapsed:.0f}/{fight.par:.0f}s",
    ] + (extra or [])
    draw_debug_lines(canvas, lines, right)


def draw_debug_lines(canvas, lines: list[str], right: int = 4) -> None:
    """F1 수치 상자 (화면 오른쪽, right = 오른쪽 여백 — 터치는 릴 패드를 피한다)."""
    bw = 132
    x, y = canvas.get_width() - right - bw, 70
    box = pygame.Surface((bw, len(lines) * 12 + 6), pygame.SRCALPHA)
    box.fill((0, 0, 0, 160))
    canvas.blit(box, (x, y))
    for i, ln in enumerate(lines):
        text(canvas, ln, (x + 4, y + 3 + i * 12), (200, 255, 200), 11)
