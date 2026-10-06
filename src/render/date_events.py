"""실제 날짜 이벤트 · 생일 (DETAILS.md H-1 · H-2, DESIGN.md 45장 DT11). 수치 · 문구는 data/details/date_events.json.

기기 날짜 기준. 풍경과 대사만 (확률 · 보상 변화 없음) — 생일 찌 외형만 예외.
- 새해(1/1): 아침 낚시터 해돋이가 크고 붉게 · 하루 아저씨 인사
- 설날(음력 1/1): 윤슬 마을 하늘에 연 3~4개 · 백 노인 인사
- 추석(음력 8/15): 밤 보름달 1.5배 · 소라 인사
- 크리스마스(12/24~25): 마을 처마 작은 전구 + 가볍게 눈 내리는 풍경 (실제 날씨와 별개) · 하루 아저씨 인사
- 생일(설정): 그날 마을 첫 입장 시 하루 아저씨 · 소라 대사, 그해 처음 한 번 '생일 축하 찌'
"""
import datetime
import math
import random

import pygame

from src.core.config import load_json
from src.core.mathutil import lerp_color

FORCE: dict = {"date": None}   # 테스트 · 디버그: datetime.date 로 오늘을 바꿈


def cfg() -> dict:
    return load_json("details/date_events.json")


def today() -> datetime.date:
    return FORCE["date"] or datetime.date.today()


def events(d: datetime.date | None = None) -> list[str]:
    d = d or today()
    c = cfg()
    md, iso = d.strftime("%m-%d"), d.isoformat()
    out = [eid for eid, e in c["fixed"].items() if md in e["dates"]]
    out += [eid for eid, dates in c["lunar"].items() if iso in dates]
    return out


def active(eid: str, d: datetime.date | None = None) -> bool:
    return eid in events(d)


# ── 생일 ──
def birthday(save) -> str | None:
    """'MM-DD' 또는 None (설정에서 비워 두면 기능 없음)."""
    return save.data.get("details", {}).get("birthday") or None


def is_birthday(save, d: datetime.date | None = None) -> bool:
    b = birthday(save)
    if not b:
        return False
    d = d or today()
    if b == "02-29" and not _leap(d.year):
        return d.strftime("%m-%d") == "02-28"   # 윤년이 아닌 해는 2월 28일에
    return d.strftime("%m-%d") == b


def _leap(y: int) -> bool:
    return y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)


def village_greetings(save, cont: str, d: datetime.date | None = None) -> dict:
    """마을 첫 입장(그날 한 번): {"lines": [(npc, 문장)], "gift": 새로 받은 외형 id | None}. 윤슬 마을만 (인사하는 NPC 가 거기 있음)."""
    d = d or today()
    det = save.data.setdefault("details", {})
    out = {"lines": [], "gift": None}
    if cont != "sharmion":
        return out
    seen = det.setdefault("date_greet_seen", [])
    c = cfg()
    from src.story.story import player_name
    for eid in events(d):
        key = f"{eid}:{d.isoformat()}"
        g = c["greet"].get(eid)
        if g and key not in seen:
            seen.append(key)
            out["lines"].append((g["npc"], g["line"]))
    if is_birthday(save, d):
        key = f"birthday:{d.isoformat()}"
        if key not in seen:
            seen.append(key)
            for ln in c["birthday"]["lines"]:
                out["lines"].append((ln["npc"], ln["line"].replace("{player}", player_name(save))))
            if det.get("birthday_gift_year") != d.year:
                det["birthday_gift_year"] = d.year
                cos = save.data.setdefault("cosmetics", {})
                lst = cos.setdefault("float_skins", [])
                gid = c["birthday"]["gift"]
                if gid not in lst:
                    lst.append(gid)
                out["gift"] = gid
    del seen[:-24]   # 오래된 기록은 버림
    return out


# ── 낚시터 하늘 (world.draw_celestial 이 읽는 값) ──
def sky_tweak(hour: float, d: datetime.date | None = None) -> dict:
    """{"sun_scale", "sun_color", "moon_scale", "full_moon"} — 새해 아침 해돋이 · 추석 보름달."""
    ev = events(d)
    sc = cfg()["scene"]
    out = {}
    if "newyear" in ev:
        a, b = sc["newyear"]["hours"]
        if a <= hour <= b:
            out.update(sun_scale=sc["newyear"]["sun_scale"], sun_color=tuple(sc["newyear"]["sun_color"]))
    if "chuseok" in ev:
        out.update(moon_scale=sc["chuseok"]["moon_scale"], full_moon=True)
    return out


# ── 마을 풍경 ──
_KITES = [(0.18, 34, (220, 70, 60)), (0.42, 22, (70, 120, 210)), (0.63, 40, (240, 200, 70)), (0.86, 28, (90, 170, 100))]


def draw_kites(canvas, ox: float, w: int, t: float, n: int) -> None:
    """설날 연: 방패연 · 가오리연 모양이 바람에 흔들림, 아래로 실이 늘어짐."""
    for i, (u, y, col) in enumerate(_KITES[:n]):
        x = (u * (w + 200) - ox * 0.15) % (w + 120) - 60
        sway = math.sin(t * 1.1 + i * 1.7) * 4
        bob = math.sin(t * 1.6 + i) * 3
        cx, cy = x + sway, y + bob
        if i % 2 == 0:   # 방패연: 네모 + 가운데 동그라미 구멍
            r = pygame.Rect(0, 0, 12, 15)
            r.center = (int(cx), int(cy))
            canvas.fill(col, r)
            canvas.fill((245, 240, 225), r.inflate(-4, -4))
            pygame.draw.circle(canvas, col, r.center, 2)
            pygame.draw.line(canvas, lerp_color(col, (0, 0, 0), 0.3), r.topleft, r.bottomright, 1)
            pygame.draw.line(canvas, lerp_color(col, (0, 0, 0), 0.3), r.topright, r.bottomleft, 1)
            tail0 = r.midbottom
        else:            # 가오리연: 마름모 + 긴 꼬리
            pts = [(cx, cy - 8), (cx + 7, cy), (cx, cy + 8), (cx - 7, cy)]
            pygame.draw.polygon(canvas, col, pts)
            pygame.draw.line(canvas, (245, 240, 225), pts[0], pts[2], 1)
            tail0 = (int(cx), int(cy + 8))
            for k in range(5):
                tx = tail0[0] + math.sin(t * 3 + k * 0.9 + i) * 3
                canvas.fill(col, (int(tx), tail0[1] + 3 + k * 4, 2, 3))
        # 실: 아래(마을 쪽)로 처지며
        sx, sy = tail0
        pts = [(sx, sy)] + [(sx - k * 6 + math.sin(t + k) * 1.5, sy + k * k * 1.6 + k * 6) for k in range(1, 7)]
        pygame.draw.lines(canvas, (235, 235, 235), False, pts, 1)


def draw_bulbs(canvas, places: list, ox: float, w: int, t: float, ground: int, night: float) -> None:
    """크리스마스: 집 처마(지붕 아래 끝)를 따라 작은 전구 — 번갈아 깜빡."""
    cols = [tuple(c) for c in cfg()["scene"]["christmas"]["bulb_colors"]]
    for p in places:
        if p["kind"] not in ("house", "hut", "arch"):
            continue
        sx = p["x"] - ox
        if not -120 < sx < w + 120:
            continue
        pw = p["w"]
        x0 = int(sx - pw / 2)
        if p["kind"] == "arch":
            y = ground - 66 - 1
            xs = range(x0 - 4, x0 + pw + 6, 6)
            ys = [y + 1 + (k % 2) for k in range(len(xs))]
        else:
            hh = (46 if p.get("low") else 62) if p["kind"] == "house" else 44
            xs = range(x0 - 6, x0 + pw + 8, 6)
            ys = [ground - hh + 2 + (k % 2) for k in range(len(xs))]
        pygame.draw.line(canvas, (40, 50, 40), (xs[0], ys[0] - 1), (xs[-1], ys[0] - 1), 1)
        for k, (x, y) in enumerate(zip(xs, ys)):
            on = (int(t * 2) + k) % 3 != 0
            c = cols[k % len(cols)]
            canvas.fill(c if on else lerp_color(c, (30, 30, 30), 0.6), (x, y, 2, 2))
            if on and night > 0.3:
                g = pygame.Surface((7, 7))
                pygame.draw.circle(g, tuple(int(v * 0.35 * night) for v in c), (3, 3), 3)
                canvas.blit(g, (x - 2, y - 2), special_flags=pygame.BLEND_RGB_ADD)


class LightSnow:
    """크리스마스 가볍게 눈 내리는 풍경 (화면 효과만, 실제 날씨와 별개)."""

    def __init__(self, n: int, seed: int = 25):
        r = random.Random(seed)
        self.flakes = [(r.uniform(0, 1), r.uniform(0, 1), r.uniform(8, 16), r.uniform(0, 6.3), r.choice((1, 1, 2))) for _ in range(n)]

    def draw(self, canvas, t: float) -> None:
        w, h = canvas.get_size()
        for u, v, sp, ph, sz in self.flakes:
            x = (u * w + math.sin(t * 0.7 + ph) * 8) % w
            y = (v * h + t * sp) % h
            canvas.fill((245, 248, 255), (int(x), int(y), sz, sz))
