"""파이팅 HUD: 장력·줄·바늘 게이지, 물고기 체력 바, 드랙, 판정 팝업, 결과 패널, F1 디버그."""
import math

import pygame

from src.core.config import load_json
from src.core.fonts import get_font
from src.core.mathutil import clamp, lerp, lerp_color
from src.render.fish_draw import RANK_COLORS
from src.ui import icons
from src.ui.hud import SHADOW, text

RARITY_COLOR = {"common": (230, 230, 230), "uncommon": (130, 230, 150), "rare": (130, 190, 255),
                "phantom": (190, 120, 255), "legend": (255, 214, 90)}
GREEN, RED, SLACK = (70, 180, 95), (205, 62, 58), (80, 98, 130)
PANEL = (24, 30, 50)
TOP_PAD = 0   # 보스전 시네마 띠 높이 (51-2) — 위쪽 가장자리 HUD(거리 막대)를 띠 안쪽으로


_RANK: dict = {}   # 랭크 도장 글자 (크기별)

def _vbar(canvas, x, y, w, h, frac, color, bg=(36, 40, 56)):
    canvas.fill(SHADOW, (x - 1, y - 1, w + 2, h + 2))
    canvas.fill(bg, (x, y, w, h))
    fh = int(h * clamp(frac, 0, 1))
    canvas.fill(color, (x, y + h - fh, w, fh))


_GAUGE_BACK: dict = {}


def draw_gauges(canvas, pal, fight, t: float) -> None:
    x, y, w, h = 8, 44, 12, 140

    def ty(v):
        return y + h - clamp(v, 0, 100) / 100 * h

    # 장력·줄·바늘을 한 묶음으로 (31장 C6): 옅은 받침 하나 — 걸림·기믹 게이지는 그 오른쪽에 따로
    back = _GAUGE_BACK.get(h)
    if back is None:   # 매 프레임 새 반투명 표면을 만들지 않게 (폰, DESIGN.md 44) — 아래 10px = 팔 힘 막대 (CU5)
        back = _GAUGE_BACK[h] = pygame.Surface((72, h + 40), pygame.SRCALPHA)
        pygame.draw.rect(back, (10, 14, 28, 90), back.get_rect(), border_radius=6)
    canvas.blit(back, (x - 6, y - 6))

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
    if fight.manual_drag and fight.drag_limit < 100:   # '드랙 직접 조절' (CU3-3): 줄이 풀리기 시작하는 장력 = 흰 1px 선, 넘은 구간 하늘색 줄무늬
        ly = int(ty(fight.drag_limit))
        if fight.tension > fight.drag_limit:
            for yy in range(int(top), ly, 3):
                canvas.fill((150, 210, 255), (x + 2, yy, w - 4, 1))
        canvas.fill((255, 255, 255), (x - 1, ly, w + 2, 1))
    # 현재 장력 표시
    blink = zone != "green" and int(t * 8) % 2 == 0
    mc = (255, 255, 255) if not blink else col
    canvas.fill(mc, (x - 3, int(top), w + 6, 2))
    pygame.draw.polygon(canvas, mc, [(x + w + 3, top), (x + w + 8, top - 4), (x + w + 8, top + 4)])
    icons.tension(canvas, x + w // 2, y + h + 10, pal["text"])  # 파이팅 중엔 글자 대신 그림 (31장)

    # 줄 내구도
    lf = fight.line_frac
    lc = lerp_color((255, 80, 60), (235, 240, 250), clamp((lf - 0.15) / 0.5, 0, 1))
    if lf < 0.25 and int(t * 6) % 2 == 0:
        lc = (255, 40, 40)
    _vbar(canvas, 36, y, 5, h, lf, lc)
    icons.line(canvas, 38, y + h + 10, pal["text"])
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
    icons.hook(canvas, 62, y + h + 10, pal["text"])
    _draw_arm(canvas, fight, x, y + h + 19, t)
    # 줄 걸림 (위협 구역이 있는 낚시터만)
    if fight.hazards:
        sf = fight.snag / 100
        sc = (200, 150, 255) if not fight.in_hazard or int(t * 6) % 2 else (255, 80, 200)
        _vbar(canvas, 88, y, 5, h, sf, sc)
        icons.snag(canvas, 90, y + h + 10, pal["text"])
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
        icons.tangle(canvas, gx + 2, y + h + 10, pal["text"])
        gx += 28
    if "heat" in kinds:
        # 열: 파이팅 시간이 45초에 가까워질수록 차오르고, 넘으면 붉게 맥동
        start = gim.heat_start(fight)
        hf = min(1.0, fight.elapsed / start)
        hot = gim.heat_dmg > 0
        hc = (255, 150, 60) if not hot else lerp_color((255, 80, 40), (255, 220, 120), 0.5 + 0.5 * math.sin(t * 10))
        _vbar(canvas, gx, y, 5, h, hf, hc)
        icons.heat(canvas, gx + 2, y + h + 10, hc if hot else pal["text"])
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
        # 다음 마루까지: 숫자 대신 줄어드는 막대
        col = (255, 220, 120) if left < 0.8 else (180, 220, 255)
        k = max(0.0, min(1.0, left / gim.cfg["current_period"]))
        canvas.fill(SHADOW, (wx - 1, wy + 7, 50, 4))
        canvas.fill(col, (wx, wy + 8, int(48 * k), 2))
    if "ice" in kinds and gim.ice_out and int(t * 6) % 2 == 0:
        pygame.draw.rect(canvas, (150, 220, 255), (x - 3, y - 3, w + 6, h + 6), 1)  # 얼음에 쓸림: 장력 게이지 테두리 깜빡


STATE_COLOR = {"지침": (130, 230, 255), "완전 지침": (130, 230, 255), "멈춤": (255, 240, 140),
               "회복 중": (200, 200, 200)}


def draw_boss_bar(canvas, pal, fight) -> None:
    """체력 막대 + 왼쪽 물고기 이름(희귀도 색) + 오른쪽 지금 상태 (31-11: 상태 글자 복귀)."""
    w = canvas.get_width()
    bw, bh = 150, 6
    x = (w - bw) // 2
    y = 20
    fish = fight.fish
    name = fish["name"] if not fight.brain.dragon else "용 '등용'"
    rc = RARITY_COLOR.get(fish["rarity"], (255, 255, 255))
    if getattr(fight, "name_hidden", False):   # 정체 숨김 (CU6-1): 이름 · 희귀도 색 숨김
        name, rc = "???", (235, 235, 240)
    if fish.get("rarity") != "phantom":  # 환상어: 파이팅 중 이름·등급명 표시 안 함 (33장)
        text(canvas, name, (x - 6, y + 3), rc, 11, "midright")

    phases = fight.brain.phases
    if phases:
        # 페이즈 표시: ◆◆◇
        for i in range(len(phases)):
            cx = x + bw // 2 - (len(phases) - 1) * 6 + i * 12
            cy = y + 13
            on = (190, 120, 255) if fish.get("rarity") == "phantom" else (255, 214, 90)
            col = on if i <= fight.brain.phase else (80, 70, 50)
            pygame.draw.polygon(canvas, col, [(cx, cy - 3), (cx + 3, cy), (cx, cy + 3), (cx - 3, cy)])
    p2 = getattr(fight, "p2_bar", False)
    if p2:   # 환상 2페이즈 모습 (PHANTOM_PHASE2.md 6번): 보라 그라데이션 · 이중 테두리 · 마름모 · 반짝 · 점 2개
        import time
        from src.render.phantom_phase2 import draw_p2_bar
        draw_p2_bar(canvas, x, y, bw, bh, fight.stamina_frac, time.perf_counter())
    else:
        canvas.fill(SHADOW, (x - 1, y - 1, bw + 2, bh + 2))
        canvas.fill((50, 30, 36), (x, y, bw, bh))
        _stamina_fill(canvas, fight, x, y, bw, bh)
        border = rc
        if getattr(fight, "gap_t", 0) > 0 and int(fight.elapsed * 8) % 2 == 0:
            border = (255, 220, 90)   # 틈 (CU4-3): 테두리 노란 깜빡
        pygame.draw.rect(canvas, border, (x - 2, y - 2, bw + 4, bh + 4), 1)
        fx = getattr(fight, "stam_fx", None)
        if fx and fx["kind"] == "perfect" and fight.elapsed - fx["t"] < fight.atk["bar"]["flash_sec"]:
            pygame.draw.rect(canvas, (255, 255, 255), (x - 3, y - 3, bw + 6, bh + 6), 1)   # 퍼펙트: 흰 번쩍 테두리
    st = fight.brain.display_name()
    if fight.brain.state == "fake_tired":
        st = "지침"
    shift = p2 or getattr(fight, "p2_shift", False)   # 2페이즈 바의 마름모 · 점 2개 오른쪽으로 (컷신 폭발부터)
    text(canvas, st, (x + bw + (26 if shift else 6), y + 3), STATE_COLOR.get(st, (255, 200, 170)), 11, "midleft")


ARM_COL = (0xE8, 0xA0, 0x40)


def _draw_arm(canvas, fight, x: int, y: int, t: float) -> None:
    """팔 힘 (CU5-1): 장력 게이지 아래 주황 가로 막대 + 손 아이콘. 바닥나면 빨강 깜빡, 처음 무거우면 "무겁다…!"."""
    if not hasattr(fight, "arm"):
        return
    bx, bw, bh = x + 8, 50, 4
    out = fight.arm_out_t > 0
    col = (255, 60, 50) if out and int(t * 8) % 2 == 0 else ARM_COL
    _hand_icon(canvas, x + 1, y + 2, col)
    canvas.fill(SHADOW, (bx - 1, y - 1, bw + 2, bh + 2))
    canvas.fill((50, 36, 24), (bx, y, bw, bh))
    canvas.fill(col, (bx, y, int(bw * fight.arm / 100), bh))
    canvas.fill(lerp_color(col, (255, 255, 255), 0.4), (bx, y, int(bw * fight.arm / 100), 1))
    if getattr(fight, "heavy_text_t", 0) > 0:
        text(canvas, "무겁다…!", (bx + bw + 6, y + 2), (255, 200, 140), 11, "midleft")


def _hand_icon(canvas, x: int, y: int, col) -> None:
    """작은 주먹 (5×5): 손등 + 엄지."""
    canvas.fill(SHADOW, (x - 2, y - 1, 6, 5))
    canvas.fill(col, (x - 3, y - 2, 6, 4))
    canvas.fill(lerp_color(col, (0, 0, 0), 0.35), (x - 3, y - 1, 1, 3))
    canvas.fill(col, (x - 4, y - 1, 1, 2))


def _stamina_fill(canvas, fight, x: int, y: int, bw: int, bh: int) -> None:
    """체력 채움 + 연출 (CU4-2): 회복 = 초록으로 차오름(0.3초) · 퍼펙트 = 크게 뚝(흰 잔상) · 좋음 = 작게(옅은 잔상)."""
    frac = fight.stamina_frac
    ov = getattr(fight, "bar_override", None)
    if ov is not None:   # 전설 3페이즈 컷신 (CU11): 진입 전 값 → 마지막 0.3초에 50% 까지 차오름
        canvas.fill((235, 90, 80), (x, y, int(bw * ov), bh))
        canvas.fill((255, 170, 150), (x, y, int(bw * ov), 1))
        return
    fx = getattr(fight, "stam_fx", None)
    bar = fight.atk["bar"] if hasattr(fight, "atk") else None
    age = fight.elapsed - fx["t"] if fx else 99.0
    if fx and fx["kind"] == "miss" and age < bar["heal_sec"]:
        k = age / bar["heal_sec"]
        base = fx["from"]
        canvas.fill((235, 90, 80), (x, y, int(bw * base), bh))
        grow = int(bw * (base + (frac - base) * k)) - int(bw * base)
        canvas.fill((120, 220, 120), (x + int(bw * base), y, max(0, grow), bh))   # 회복: 초록으로 차오름
        canvas.fill((255, 170, 150), (x, y, int(bw * base), 1))
        return
    canvas.fill((235, 90, 80), (x, y, int(bw * frac), bh))
    canvas.fill((255, 170, 150), (x, y, int(bw * frac), 1))
    if fx and fx["kind"] in ("perfect", "good") and age < bar["hit_sec"]:
        lost = int(bw * fx["from"]) - int(bw * frac)
        if lost > 0:
            k = 1 - age / bar["hit_sec"]
            col = (255, 255, 255) if fx["kind"] == "perfect" else (255, 200, 190)
            g = pygame.Surface((lost, bh), pygame.SRCALPHA)
            g.fill((*col, int(220 * k)))
            canvas.blit(g, (x + int(bw * frac), y))   # 깎인 만큼 잔상이 사라짐


def draw_sweat(canvas, p, t: float) -> None:
    """틈 (CU4-3): 물고기 그림자 위 땀방울 2개 (하늘색 1px, 천천히 흘러내림)."""
    if not p:
        return
    sx, sy, s = p
    r = max(4, int(s * 0.25))
    for i, dx in enumerate((-r, r)):
        ph = (t * 1.6 + i * 0.5) % 1.0
        px, py = int(sx + dx), int(sy - r - 3 + ph * 3)
        canvas.fill((160, 220, 255), (px, py, 1, 2))
        canvas.fill((220, 245, 255), (px, py - 1, 1, 1))


def draw_side_wake(canvas, tip, side: int, t: float) -> None:
    """측면 압박 (CU4-4): 낚싯대 끝에 작은 흰 물살 — 당기는 쪽으로 흘러가는 짧은 줄 3개 (그림자 1px 아래)."""
    x, y = int(tip[0]), int(tip[1])
    for i in range(3):
        ph = (t * 2.5 + i / 3) % 1.0
        ln = 4 + int(ph * 5)
        yy = y + 1 + i * 2
        a = int(255 * (1 - ph) ** 0.7)
        x0 = x + 2 + int(ph * 4) if side > 0 else x - 2 - ln - int(ph * 4)
        for col, dy, aa in ((SHADOW, 1, a // 2), ((255, 255, 255), 0, a)):
            surf = pygame.Surface((ln, 1), pygame.SRCALPHA)
            surf.fill((*col, aa))
            canvas.blit(surf, (x0, yy + dy))


def draw_gap_flash(canvas, k: float) -> None:
    """틈 공략 성공: 화면 흰 금색 번쩍 (최대 10%)."""
    w, h = canvas.get_size()
    g = pygame.Surface((w, h), pygame.SRCALPHA)
    g.fill((255, 236, 170, int(26 * max(0.0, min(1.0, k)))))
    canvas.blit(g, (0, 0))


def release_ready(fight) -> bool:
    """돌진 예고 중 · 아직 안 풀린 돌진 중 — 'Q' · '풀기' 버튼 깜빡 (CU3). 늦게라도 누르면 그때부터 풀림."""
    b = fight.brain
    if fight.manual_drag:
        return False
    if b.state == "telegraph" and b.pending == "rush":
        return fight.rel_press is None   # 지난 돌진 판정과 상관없이, 이번 예고에서 아직 안 눌렀으면
    return b.state == "rush" and fight.rush_start_t is not None and (
        fight.rel_grade is None or (fight.rel_grade == "miss" and not fight.rel_late))


def draw_drag(canvas, pal, fight, need: bool = False, t: float = 0.0) -> None:
    """드랙 5칸. need = 지금 드랙이 중요할 때(돌진·힘 모으기·장력 빨강·방금 바꿈) — 금색 테두리로 강조 (31장 C6).
    자동 드랙 (CU3): 칸 대신 작은 릴 (풀릴수록 빠르게 돎) + 돌진 예고 동안 'Q' 깜빡."""
    x, y = 8, 226
    if not fight.manual_drag:
        spin = 3.0 + 16.0 * (1 - fight.drag_frac)        # 풀림(최저) = 빠르게
        col = (255, 220, 120) if need else pal["text"]
        cx, cy = x + 6, y
        for c, o in ((SHADOW, 1), (col, 0)):
            pygame.draw.circle(canvas, c, (cx + o, cy + o), 6, 2)
        for k in range(3):
            a = t * spin + k * math.tau / 3
            pygame.draw.line(canvas, col, (cx, cy), (cx + math.cos(a) * 5, cy + math.sin(a) * 5), 1)
        if release_ready(fight) and int(t * 6) % 2 == 0:
            r = text(canvas, "Q", (cx + 12, cy), (255, 220, 120), 11, "midleft")
            text(canvas, "풀기", (r.right + 3, cy), (255, 220, 120), 11, "midleft")
        return
    icons.reel(canvas, x + 6, y, (255, 220, 120) if need else pal["text"])
    bx = x + 18
    for i in range(fight.drag_steps):
        filled = i < fight.drag
        rect = (bx + i * 7, y - 3, 5, 7)
        canvas.fill(SHADOW, (rect[0] - 1, rect[1] - 1, 7, 9))
        canvas.fill((255, 220, 120) if filled else (60, 64, 80), rect)
    if need and int(t * 4) % 2 == 0:
        pygame.draw.rect(canvas, (255, 220, 120), (x - 2, y - 7, 18 + fight.drag_steps * 7 + 4, 15), 1, border_radius=3)


def draw_distance(canvas, pal, fight, inset: int = 0) -> None:
    """거리: 숫자 대신 작은 막대 (왼쪽 끝 = 내 쪽, 점 = 물고기)."""
    from src.core.config import load_json
    far = load_json("fishing_config.json")["cast"]["max_distance"]
    w = 46
    icons.distance(canvas, canvas.get_width() - 10 - inset - w, 8 + TOP_PAD, w, fight.distance / far, (150, 200, 255))


STAMP_T = 0.6       # 랭크 도장이 찍히는 시각 (획득 컷 기준)
CATCH_READY_T = 1.0  # 이후 클릭하면 계속


def catch_badges(news: dict | None) -> list:
    """획득 컷 왼쪽 위 기록 배지 [(글자, 색)] — 아래 숙련도 아이콘 줄이 이만큼 내려간다."""
    badges = []
    if not news:
        return badges
    if news.get("new"):
        badges.append(("NEW! 도감 등록", (255, 230, 120)))
    if news.get("record"):
        badges.append(("최대 크기 경신!", (140, 240, 150)))
    if news.get("gold"):
        badges.append(("도감 금테 획득!", RANK_COLORS["S"]))
    if news.get("heavy"):   # 대물 (크기 상위 10%, CU5-2) — 판매가 +30% (CU8-④)
        badges.append(("묵직한 손맛! 판매가 +30%", (255, 190, 120)))
    if news.get("excited"):   # 들뜬 물고기 (CU9) — 판매가 × core.json variety.excited_price
        k = load_json("core.json")["variety"]["excited_price"]
        badges.append((f"들뜬 녀석! 판매가 ×{k:g}", (255, 170, 120)))
    if news.get("oren"):      # 오렌의 도전장 (CU12)
        badges.append((f"오렌의 도전장 달성! {news['oren']['size']:g}cm", (190, 170, 255)))
    if news.get("weekly"):    # 주간 대회 (CU12)
        rk = news["weekly"].get("rank")
        badges.append((f"주간 대회 기록 {news['weekly']['size']:g}cm" + (f" · 지금 {rk}등" if rk else ""), (255, 214, 90)))
    if news.get("stray"):     # 길을 잃은 손님 (CU9) — 다른 낚시터 물고기
        badges.append(("길을 잃은 손님", (170, 210, 255)))
    if news.get("first_bonus"):   # 첫 만남 보너스 (CU8-④)
        badges.append((f"첫 만남 보너스 +{news['first_bonus']:,}원", (140, 240, 150)))
    if news.get("hint"):
        badges.append((f"힌트 해금 ({news['hint']}회) - 도감 확인", (150, 220, 255)))
    if news.get("phantom_new"):
        gold = f" +{news['phantom_gold']:,}원" if news.get("phantom_gold") else ""
        badges.append((f"환상 도감 등록!{gold}", (225, 180, 255)))
    if news.get("phantom_scales"):
        badges.append((f"비늘 +{news['phantom_scales']} · 축복 10분", (210, 150, 255)))
    for rw in news.get("phantom_rewards", []):
        badges.append((f"수집 보상: {rw}", (255, 214, 90)))
    if news.get("trophy"):
        badges.append((f"전설 첫 포획 트로피 +{news['trophy']:,}원!", RANK_COLORS["S"]))
    if news.get("resell"):
        badges.append((f"다시 잡은 전설: 판매가 ×{news['resell']:g}", (200, 200, 210)))
    if news.get("mutations"):   # 변이 (TG-17 강조 대상) — 파이팅 시작 알림과 같은 글자
        from src.fishing import mutation
        kinds = mutation.cfg()["kinds"]
        m = news["mutations"][0]
        badges.append((f"{kinds[m]['name']} 변이", tuple(kinds[m]["color"])))
    if news.get("chest"):       # 보물상자 (TG-10 강조 대상) — 획득 알림과 같은 이름
        from src.save import treasure
        info = treasure.grade_info(news["chest"])
        badges.append((f"{info['name']} 보물상자 획득!", tuple(info["color"])))
    if news.get("scalestone"):   # 비늘석 (46장) — 파이팅이 끝난 뒤 카드에만
        from src.save import scalestone
        badges.append(scalestone.news_line(news["scalestone"]))
    badges += dex_badges(news)
    return badges


def dex_badges(news: dict) -> list:
    """도감 별·숙련·도감 보상 (35-2) — 결과 화면에서만."""
    from src.save.dexbook import STAR_LABEL
    out = []
    for s in news.get("dex_stars", []):
        if s > 1:  # ★1(첫 포획)은 'NEW! 도감 등록'과 같음
            out.append((f"도감 ★{s} {STAR_LABEL[s]}! (★{news.get('dex_star_total', s)}/5)", (255, 220, 120)))
    if news.get("mastery_up"):
        out.append((f"숙련 {news['mastery_up']}단계!", (170, 255, 200)))
    for rw in news.get("dex_rewards", []):
        out.append((f"도감 보상: {rw}", (255, 214, 90)))
    return out


def badge_times(news: dict | None) -> list:
    """[(나타나는 시각, 종류 'stamp' | 'star')] — 도장 쾅(도감 새 칸) · 별 반짝(도감 별) 소리를 장면이 같은 순간에 낸다 (DT10)."""
    out = []
    for i, (label, _) in enumerate(catch_badges(news)):
        kind = _badge_kind(label)
        if kind:
            out.append((1.0 + i * 0.15, kind))
    return out


def _badge_kind(label: str):
    if label.startswith("NEW!") or label.startswith("환상 도감 등록"):
        return "stamp"
    if label.startswith("도감 ★"):
        return "star"
    return None


def _badge(canvas, label: str, col, pos, age: float) -> None:
    """기록 배지. 도감 새 칸 = 도장이 쾅 (1.3배 → 1배, 0.25초, 도장 테두리), 도감 별 = 반짝 튀어 오름 (1.2배 → 1배, 0.3초) (DT10)."""
    kind = _badge_kind(label)
    if kind is None and label.startswith("비늘석 "):   # 비늘석 획득 = 16x16 아이콘 + 등급 + 첫 옵션 (46장 S5)
        from src.save import scalestone
        from src.ui.scalestone_ui import icon
        g = next((g for g in scalestone.grades()["order"] if label.startswith(f"비늘석 {scalestone.grade_info(g)['name']}")), None)
        if g is not None:
            canvas.blit(icon(g, small=True), (pos[0], pos[1] - 8))
            pos = (pos[0] + 18, pos[1])
    if kind is None:
        text(canvas, label, pos, col, 11, "midleft")
        return
    dur, big = (0.25, 1.3) if kind == "stamp" else (0.3, 1.2)
    u = clamp(age / dur, 0, 1)
    sc = big + (1.0 - big) * (1 - (1 - u) ** 2)
    img = get_font(11).render(label, False, col)
    w0, h0 = img.get_size()
    if kind == "stamp":   # 도장 테두리 (잉크 빨강), 찍힌 뒤에도 남음
        box = pygame.Surface((w0 + 6, h0 + 2), pygame.SRCALPHA)
        pygame.draw.rect(box, (220, 70, 60, 220), box.get_rect(), 1)
        box.blit(img, (3, 1))
        img, w0, h0 = box, w0 + 6, h0 + 2
    if sc != 1.0:
        img = pygame.transform.scale(img, (max(1, int(w0 * sc)), max(1, int(h0 * sc))))
    x, y = pos
    x -= 3 if kind == "stamp" else 0
    dy = -int(4 * math.sin(math.pi * u)) if kind == "star" and u < 1 else 0   # 별: 살짝 튀어 오름
    r = img.get_rect(midleft=(x - (img.get_width() - w0) // 2, y + dy))
    canvas.blit(img, r)
    if kind == "star" and u < 1:   # 반짝 십자
        k = math.sin(math.pi * u)
        cx, cy = r.x + int((get_font(11).size("도감 ")[0] + 4) * sc), r.centery - 1   # ★ 자리
        c = (255, 250, 210)
        ln = int(2 + 4 * k)
        pygame.draw.line(canvas, c, (cx - ln, cy), (cx + ln, cy), 1)
        pygame.draw.line(canvas, c, (cx, cy - ln), (cx, cy + ln), 1)


# 랭크 막대 아이콘 5×5 (줄 · 시간 · 신호 · 실수)
_BAR_ICONS = {
    "line": ["....#", "...#.", "..#..", ".#...", "#...."],
    "time": [".###.", "#.#.#", "#.##.", "#...#", ".###."],
    "signal": ["..#..", "..#..", "..#..", ".....", "..#.."],
    "miss": ["#...#", ".#.#.", "..#..", ".#.#.", "#...#"],
}
BAR_KEYS = ("line", "time", "signal", "miss")


def rank_ratios(result: dict) -> dict:
    """결과 카드 막대 4개의 채움 비율 (BAEK_EXAM 🅰-6): 줄 · 시간 · 신호 = 항목 점수 / 최대, 실수 = 1 − 깎인 점수 / (실수 3번 몫)."""
    r = load_json("fishing_config.json")["rank"]
    sc = result.get("score") or {}
    return {"line": clamp(sc.get("line_pts", 0) / r["line_max"], 0, 1),
            "time": clamp(sc.get("time_pts", 0) / r["time_max"], 0, 1),
            "signal": clamp(sc.get("signal_pts", 0) / r["signal_max"], 0, 1),
            "miss": clamp(1 + sc.get("miss_pts", 0) / (3 * r["per_miss"]), 0, 1)}


def rank_bars_rect(rx: int, y: int) -> pygame.Rect:
    return pygame.Rect(rx - 32, y - 1, 64, 4 * 8 + 1)


def draw_rank_bars(canvas, result: dict, rx: int, y: int, t: float) -> None:
    """랭크 도장 아래 작은 막대 4개 (숫자 없음). S 가 아니면 가장 모자란 막대가 깜빡, 점수는 S 인데 퍼펙트가 모자라면 한 줄."""
    if "signal_pts" not in (result.get("score") or {}):
        return   # 옛 결과 (훈련 수조 등 점수 없는 판)
    ratios = rank_ratios(result)
    weakest = min(BAR_KEYS, key=lambda k: ratios[k]) if result["rank"] != "S" else None
    if weakest is not None and ratios[weakest] >= 0.999:
        weakest = None   # 다 찼는데 S 가 아님 = 퍼펙트가 모자란 것 (아래 한 줄로 알림)
    blink_off = weakest is not None and t > 0.4 and int(t * 4) % 2 == 1
    for i, k in enumerate(BAR_KEYS):
        yy = y + i * 8
        col = (210, 216, 236)
        for dy_, row in enumerate(_BAR_ICONS[k]):
            for dx_, ch in enumerate(row):
                if ch == "#":
                    canvas.set_at((rx - 30 + dx_, yy + dy_), col)
        bar = pygame.Rect(rx - 22, yy, 52, 5)
        canvas.fill((24, 28, 44), bar)
        fill = int(round((bar.w - 2) * ratios[k] * clamp(t / 0.35, 0, 1)))
        good = lerp_color((230, 90, 80), (110, 220, 130), ratios[k])
        if not (k == weakest and blink_off):
            canvas.fill(good, (bar.x + 1, bar.y + 1, fill, bar.h - 2))
        pygame.draw.rect(canvas, (255, 214, 90) if k == weakest and not blink_off else (70, 76, 100), bar, 1)
    sc = result["score"]
    if sc.get("s_blocked") and t > 0.4:
        need = load_json("fishing_config.json")["rank"]["S_min_perfects"]
        text(canvas, f"퍼펙트 {need}번", (rx, y + 4 * 8 + 6), RANK_COLORS["S"], 11, "center")


def draw_catch_info(canvas, result: dict, t: float, news: dict | None = None) -> None:
    """획득 컷 정보: 이름·크기 → 랭크 도장 쾅 → 기록 → 가치 숫자 올라감 (순서대로)."""
    w = canvas.get_width()
    fish = result["fish"]
    rc = RANK_COLORS[result["rank"]]
    if t > 0.3:
        k = clamp((t - 0.3) / 0.15, 0, 1)
        dy = int((1 - k) * -10)
        if fish["rarity"] == "phantom":
            # "환상의 물고기, ○○○" — 두 줄 (왼쪽 위 기록 배지와 겹치지 않게)
            text(canvas, "환상의 물고기,", (w // 2, 12 + dy), (225, 180, 255), 11, "center")
        text(canvas, fish["name"], (w // 2, 26 + dy) if fish["rarity"] == "phantom" else (w // 2, 24 + dy),
             RARITY_COLOR.get(fish["rarity"], (255, 255, 255)), 16, "center")
        sr = text(canvas, f"{result['size']:.1f}cm", (w // 2, 44 + dy), (255, 255, 255), 16, "center")
        if fish.get("rarity") in ("common", "uncommon", "rare") and "size_cm" in fish:
            lo, hi = fish["size_cm"]
            if result["size"] >= lo + 0.9 * (hi - lo):   # 대물 (크기 범위 상위 10%, 도감 ★3 와 같은 기준)
                text(canvas, "대물", (sr.right + 4, sr.centery + 1), (255, 214, 90), 11, "midleft")
        # 희귀 이상: 희귀도 리본
        if fish["rarity"] in ("rare", "legend", "phantom"):
            label = {"rare": "희귀", "legend": "★ 전설 ★", "phantom": "◆ 환상 ◆"}[fish["rarity"]]
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
        rk = (result["rank"], tuple(rc), round(scale, 4))
        img = _RANK.get(rk)   # 커지는 도장은 0.14초뿐, 찍힌 뒤(scale 1.0)는 매 프레임 같은 그림 (O2)
        if img is None:
            if len(_RANK) > 64:
                _RANK.clear()
            img = get_font(16).render(result["rank"], False, rc)
            img = _RANK[rk] = pygame.transform.scale(img, (int(img.get_width() * scale * 1.3), int(img.get_height() * scale * 1.3)))
        canvas.blit(img, img.get_rect(center=box.center))
        if k >= 1:
            # 찍힌 뒤 퍼지는 고리
            ring = clamp((t - STAMP_T - 0.14) / 0.3, 0, 1)
            if ring < 1:
                pygame.draw.rect(canvas, rc, box.inflate(int(ring * 40), int(ring * 40)), 1)
            text(canvas, "랭크", (rx, ry + 26), (200, 205, 220), 11, "center")
            draw_rank_bars(canvas, result, rx, ry + 36, t - STAMP_T)
    y = 192
    if t > 0.85:
        stats = (f"퍼펙트 {result['perfects']}   실수 {result['misses']}   줄 손상 {result['line_damage'] * 100:.0f}%   "
                 f"시간 {result['elapsed']:.0f}초 (기준 {result['par']:.0f}초)")
        text(canvas, stats, (w // 2, y), (220, 225, 240), 11, "center")
    ex = (news or {}).get("exam")
    if ex:   # 백 노인의 시험 판 (49-3): 가치 · 살림망 대신 합격 판정
        if t > 0.95:
            if ex["pass"]:
                text(canvas, f"T{ex['tier']} 시험 합격!", (w // 2, y + 18), (110, 220, 130), 16, "center")
            else:
                text(canvas, f"T{ex['tier']} 시험 불합격 — {ex['need']}", (w // 2, y + 18), (255, 140, 120), 11, "center")
        if t > 1.2:
            text(canvas, "시험용 물고기 — 살림망 · 도감에 넣지 않아요", (w // 2, 240), (170, 180, 200), 11, "center")
        if t > CATCH_READY_T + 0.5 and int(t * 2) % 2 == 0:
            text(canvas, "클릭해서 계속", (w // 2, 256), (170, 180, 200), 11, "center")
        return
    if t > 0.95:
        k = clamp((t - 0.95) / 0.5, 0, 1)
        shown = int(result["price"] * (1 - (1 - k) ** 2))
        text(canvas, f"가치 {shown}원", (w // 2, y + 16), (255, 230, 140), 11, "center")
    if result["rank"] == "S" and t > 1.5:
        rc_ = load_json("fishing_config.json")["rank"]
        text(canvas, f"S랭크 보너스: 크기 +{rc_['s_size_bonus'] * 100:.0f}%, 판매가 ×{rc_['price_mult']['S']:g}",
             (w // 2, y + 32), RANK_COLORS["S"], 11, "center")
    # 새 기록 배지 (왼쪽 위에 차례로)
    if news and t > 1.0:
        badges = catch_badges(news)
        for i, (label, col) in enumerate(badges):
            if t > 1.0 + i * 0.15:
                _badge(canvas, label, col, (12, 24 + i * 15), t - (1.0 + i * 0.15))
    if news and news.get("legend_line") and t > 1.6:
        # 전설 첫 포획: 환상의 물고기 암시 한 줄 (33장 P6)
        k = clamp((t - 1.6) / 0.8, 0, 1)
        col = lerp_color((40, 30, 60), (210, 170, 255), k)
        text(canvas, news["legend_line"], (w // 2, 160), col, 11, "center")
    if news and news.get("title") and t > 0.6:
        if news.get("title_frame"):  # 환상 비늘 교환: 칭호 보라 테두리
            tw = get_font(11).size(f"「{news['title']}」")[0] + 10
            pygame.draw.rect(canvas, (190, 120, 255), (w // 2 - tw // 2, 168, tw, 16), 1, border_radius=4)
            pygame.draw.rect(canvas, (90, 50, 140), (w // 2 - tw // 2 - 2, 166, tw + 4, 20), 1, border_radius=5)
        text(canvas, f"「{news['title']}」", (w // 2, 176), (255, 214, 90), 11, "center")  # 장착한 칭호
    if t > 1.2:
        text(canvas, "살림망에 보관했어요 (하루네 낚시점에서 판매)", (w // 2, 240), (170, 180, 200), 11, "center")
    if news and news.get("stamp") and t > 1.1:
        # 날씨 · 시간 · 장소 도장 (DETAILS D, 모든 등급) — 오른쪽 아래
        from src.ui.catch_stamp import draw_stamp
        draw_stamp(canvas, news["stamp"], (w - 10, canvas.get_height() - 30))
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
    if fight.fish.get("rarity") == "phantom":
        # 환상어: 이름 대신 한 줄 (놓친 환상어는 도감에도 남지 않는다)
        text(canvas, "보라빛 잔상이 깊은 곳으로 사라졌다", (w // 2, y + 72), (225, 180, 255), 11, "center")
    else:
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


def draw_quest_icon(canvas, lines: list, inset: int = 0) -> None:
    """파이팅 중 의뢰: 글자는 숨기고 조건이 깨졌을 때만 아이콘 1개 (31장). 상세는 결과 화면."""
    if any(state == "fail" for _, state in lines):
        icons.quest_fail(canvas, canvas.get_width() - 14 - inset, 22)


def draw_quests(canvas, lines: list, inset: int = 0) -> None:
    """결과 화면의 의뢰 진행 (오른쪽 위): 지키는 중 / 실패 / 완료. 파이팅 중엔 draw_quest_icon."""
    w = canvas.get_width()
    y = 44  # 물고기 이름·체력 바(20~36) 아래, 패턴 안내(69~) 위
    font = get_font(11)
    for label, state in lines:
        col = {"ok": (220, 225, 240), "fail": (255, 110, 95), "done": (130, 255, 180)}[state]
        if len(label) > 30:
            label = label[:29] + "…"
        tw, th = font.size(label)
        bg = pygame.Surface((tw + 6, th + 2), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 110))
        canvas.blit(bg, (w - 8 - inset - tw - 3, y - th // 2 - 1))
        text(canvas, label, (w - 8 - inset, y), col, 11, "midright")
        y += 13


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
