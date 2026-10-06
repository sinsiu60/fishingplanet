"""마을 생활감 (DETAILS.md F, DESIGN.md 45장 DT9). 수치 · 문구는 data/details/village_life.json.

- 고양이 '나비' (윤슬 마을만): 살림망에 물고기가 있으면 화면 가운데(주인공 자리)로 졸졸 따라옴 · 탭 → [작은 물고기 주기]
  (일반 등급 중 가장 싼 1마리, 실제 날짜 하루 1번) · 친밀도 0~5 · 3 이상 = 들어올 때 마중 · 5 = 주인공의 집에서 잠 + 칭호.
- 비: NPC 우산 (두 마을) · 물웅덩이 (윤슬 마을만, 하늘색 반사 + 빗방울 파문).
- 밤: 간판 불 (두 마을) — draw_place 가 night 로 그림. 굴뚝 연기: 게임 시간 17~19시.
- 의뢰 게시판 쪽지: 8장 중 2장, 실제 ISO 주차마다 바뀜 (윤슬 마을만).
게임플레이 영향: 고양이 먹이(살림망에서 1마리 빠짐) · 칭호만 (DETAILS 원칙의 명시 예외).
"""
import datetime
import math
import random

import pygame

from src.core.config import load_json
from src.core.mathutil import clamp, lerp_color


def cfg() -> dict:
    return load_json("details/village_life.json")


def details(save) -> dict:
    return save.data.setdefault("details", {})


def affection(save) -> int:
    return int(details(save).get("cat_affection", 0))


# ───────────────────────── 쪽지 ─────────────────────────
def notes_this_week(cont: str, today: datetime.date | None = None) -> list[str]:
    """이번 주(ISO 주차) 쪽지 2장. 주마다 2장씩 다음으로 (8장 = 4주 순환)."""
    c = cfg()["notes"]
    if cont not in c["villages"]:
        return []
    d = today or datetime.date.today()
    y, wk, _ = d.isocalendar()
    lst = c["list"]
    n = c["per_week"]
    i = ((y * 53 + wk) * n) % len(lst)
    return [lst[(i + k) % len(lst)] for k in range(n)]


# ───────────────────────── 고양이 먹이 ─────────────────────────
def feed_candidate(save):
    """살림망의 일반 등급(잠금 제외) 중 가장 싼 1마리 (index, item) 또는 None."""
    from src.save.save_game import fish_by_id
    rar = cfg()["cat"]["feed_rarity"]
    best = None
    for i, it in enumerate(save.data.get("keepnet", [])):
        if it.get("lock"):
            continue
        try:
            f = fish_by_id(it["id"])
        except (KeyError, StopIteration):
            continue
        if f.get("rarity") != rar:
            continue
        p = it.get("price", 0)
        if best is None or p < best[2]:
            best = (i, it, p)
    return None if best is None else best[:2]


def feed_cat(save, today: str | None = None) -> dict:
    """{"result": "fed" | "full" | "none", "n": 친밀도, "title": 새 칭호 id | None, "fish": 준 물고기 id}."""
    c = cfg()["cat"]
    det = details(save)
    today = today or datetime.date.today().isoformat()
    n = int(det.get("cat_affection", 0))
    if det.get("cat_fed_date") == today:
        return {"result": "full", "n": n, "title": None, "fish": None}
    cand = feed_candidate(save)
    if cand is None:
        return {"result": "none", "n": n, "title": None, "fish": None}
    i, it = cand
    save.data["keepnet"].pop(i)
    n = min(c["affection_max"], n + 1)
    det["cat_affection"] = n
    det["cat_fed_date"] = today
    title = None
    if n >= c["sleep_home_at"]:
        cos = save.data.setdefault("cosmetics", {"titles": [], "float_skins": [], "rod_skins": []})
        if c["title_id"] not in cos.setdefault("titles", []):
            cos["titles"].append(c["title_id"])
            title = c["title_id"]
    return {"result": "fed", "n": n, "title": title, "fish": it["id"]}


# ───────────────────────── 고양이 그림 ─────────────────────────
def draw_cat(canvas, x: float, y: float, pose: str, face: int, t: float, step: float = 0.0, dim: float = 0.0) -> None:
    """작은 줄무늬 고양이 (몸 길이 약 16px). pose = walk | sit | eat | sleep. (x, y) = 발 밑 가운데."""
    c = cfg()["cat"]
    night = (24, 24, 44)
    col = lambda v: lerp_color(tuple(v), night, dim)  # noqa: E731
    body, stripe, belly = col(c["body"]), col(c["stripe"]), col(c["belly"])
    x, y = int(x), int(y)
    f = 1 if face >= 0 else -1
    if pose == "sleep":   # 동그랗게 말려 잠: 몸 + 꼬리가 감싸고, 귀 두 개, 숨쉬기
        br = 1 if math.sin(t * 1.6) > 0 else 0
        pygame.draw.ellipse(canvas, body, (x - 10, y - 8 - br, 20, 8 + br))
        for k in (-4, 0, 4):
            canvas.fill(stripe, (x + k, y - 8 - br, 2, 3))
        pygame.draw.circle(canvas, body, (x + 7 * f, y - 4), 4)
        pygame.draw.polygon(canvas, body, [(x + 4 * f, y - 7), (x + 5 * f, y - 10), (x + 7 * f, y - 7)])
        pygame.draw.polygon(canvas, body, [(x + 8 * f, y - 7), (x + 10 * f, y - 10), (x + 10 * f, y - 6)])
        canvas.fill((40, 30, 30), (x + 6 * f, y - 4, 2, 1))   # 감은 눈
        pygame.draw.arc(canvas, stripe, (x - 12, y - 6, 18, 8), math.pi * 0.9, math.pi * 1.9, 2)   # 감싼 꼬리
        return
    if pose == "sit":
        pygame.draw.ellipse(canvas, body, (x - 5, y - 11, 10, 11))
        pygame.draw.ellipse(canvas, belly, (x - 2 + f, y - 8, 5, 7))
        canvas.fill(stripe, (x - 4 * f - 1, y - 9, 2, 1))
        canvas.fill(stripe, (x - 4 * f - 1, y - 6, 2, 1))
        hx, hy = x + 2 * f, y - 13
        sw = math.sin(t * 2.2) * 3                              # 꼬리 살랑
        pygame.draw.lines(canvas, body, False, [(x - 4 * f, y - 1), (x - 9 * f, y - 3), (x - 10 * f + sw * f, y - 9)], 2)
    else:   # walk · eat: 네 발, 몸 가로
        bob = 1 if pose == "walk" and math.sin(step * 2) > 0 else 0
        pygame.draw.ellipse(canvas, body, (x - 8, y - 9 - bob, 16, 7))
        for k in (-4, 0, 4):
            canvas.fill(stripe, (x + k, y - 9 - bob, 2, 2))
        canvas.fill(belly, (x - 4, y - 4 - bob, 8, 1))
        for i, lx in enumerate((-6, -3, 3, 6)):
            lift = 1 if pose == "walk" and (math.sin(step + i * math.pi / 2) > 0.3) else 0
            canvas.fill(body, (x + lx * f, y - 3 - lift - bob, 2, 3))
        sw = math.sin(t * 3) * 2
        pygame.draw.lines(canvas, body, False, [(x - 7 * f, y - 8 - bob), (x - 11 * f, y - 11 - bob), (x - 12 * f, y - 15 - bob + sw)], 2)
        hx, hy = x + 9 * f, (y - 6 if pose == "eat" else y - 10 - bob)
    pygame.draw.circle(canvas, body, (hx, hy), 4)
    pygame.draw.polygon(canvas, body, [(hx - 4, hy - 2), (hx - 3, hy - 7), (hx - 1, hy - 3)])
    pygame.draw.polygon(canvas, body, [(hx + 4, hy - 2), (hx + 3, hy - 7), (hx + 1, hy - 3)])
    canvas.fill((240, 150, 150), (hx - 3, hy - 4, 1, 1))
    canvas.fill((240, 150, 150), (hx + 3, hy - 4, 1, 1))
    blink = (t * 0.6) % 3.5 < 0.12
    eye = (40, 60, 30) if dim < 0.5 else (200, 220, 120)   # 밤엔 눈이 반짝
    if blink or pose == "eat":
        canvas.fill(eye, (hx - 2, hy - 1, 2, 1))
        canvas.fill(eye, (hx + 1, hy - 1, 2, 1))
    else:
        canvas.fill(eye, (hx - 2, hy - 1, 1, 2))
        canvas.fill(eye, (hx + 2, hy - 1, 1, 2))
    canvas.fill((200, 110, 110), (hx + f, hy + 1, 1, 1))


def draw_heart(canvas, x: float, y: float, a: float) -> None:
    col = (int(240 * a), int(90 * a), int(110 * a))
    x, y = int(x), int(y)
    pygame.draw.circle(canvas, col, (x - 2, y), 2)
    pygame.draw.circle(canvas, col, (x + 2, y), 2)
    pygame.draw.polygon(canvas, col, [(x - 4, y + 1), (x + 4, y + 1), (x, y + 5)])


class VillageCat:
    """파노라마 위의 나비. x = 파노라마 좌표."""

    def __init__(self, save, width: int, view_c: float, rnd=None):
        c = cfg()["cat"]
        self.save, self.width = save, width
        self.rnd = rnd or random.Random()
        self.t = 0.0
        self.step = 0.0
        self.face = 1
        self.pose = "sit"
        self.eat = 0.0
        self.hearts: list = []       # [x, y, age]
        self.greet = 0.0             # 마중 남은 시간
        self.wander_t = self.rnd.uniform(2, 5)
        self.x = c["home_x"] + self.rnd.uniform(-c["wander"], c["wander"])
        self.goal = self.x
        self.meowed = False
        if affection(save) >= c["greet_at"]:   # 친밀도 3: 마을에 올 때마다 마중 (화면 가장자리에서 달려옴)
            self.x = clamp(view_c + 90, 20, width - 20)
            self.greet = 8.0

    def has_fish(self) -> bool:
        return bool(self.save.data.get("keepnet"))

    def update(self, dt: float, view_c: float, sfx=None) -> None:
        c = cfg()["cat"]
        self.t += dt
        for h in self.hearts:
            h[2] += dt
            h[1] -= 10 * dt
        self.hearts = [h for h in self.hearts if h[2] < 1.4]
        if self.eat > 0:
            self.eat -= dt
            self.pose = "eat"
            return
        self.greet = max(0.0, self.greet - dt)
        follow = self.has_fish() or self.greet > 0
        if follow:
            self.goal = view_c + c["follow_offset"]
            speed = c["follow_speed"] * (1.6 if self.greet > 0 else 1.0)
        else:
            self.wander_t -= dt
            if self.wander_t <= 0:
                self.wander_t = self.rnd.uniform(4, 9)
                self.goal = c["home_x"] + self.rnd.uniform(-c["wander"], c["wander"])
            speed = c["walk_speed"]
        self.goal = clamp(self.goal, 20, self.width - 20)
        d = self.goal - self.x
        if abs(d) > c["stop_dist"]:
            self.face = 1 if d > 0 else -1
            mv = min(abs(d), speed * dt)
            self.x += mv * self.face
            self.step += mv * 0.5
            self.pose = "walk"
        else:
            if self.pose == "walk" and self.greet > 0 and not self.meowed:   # 마중 도착: 야옹 + 하트
                self.meowed = True
                if sfx is not None:
                    sfx.play("sfx_cat_meow", 0.5)
                self.hearts.append([self.x, -16, 0.0])
            self.pose = "sit"

    def fed(self, sfx=None) -> None:
        self.eat = 1.8
        self.hearts.append([self.x, -16, 0.0])
        self.hearts.append([self.x + 6, -12, -0.3])
        if sfx is not None:
            sfx.play("sfx_cat_purr", 0.5)

    def rect(self, ox: float, feet: int) -> pygame.Rect:
        return pygame.Rect(int(self.x - ox) - 14, feet - 20, 28, 24)

    def draw(self, canvas, ox: float, feet: int, night: float) -> pygame.Rect:
        sx = self.x - ox
        draw_cat(canvas, sx, feet, self.pose, self.face, self.t, self.step, dim=0.45 * night)
        for hx, hy, age in self.hearts:
            if age >= 0:
                draw_heart(canvas, hx - ox, feet + hy - age * 6, max(0.0, 1 - age / 1.4))
        return self.rect(ox, feet)


# ───────────────────────── 비 · 굴뚝 ─────────────────────────
def umbrella_color(name: str) -> tuple:
    cols = cfg()["rain"]["umbrella_colors"]
    return tuple(cols[sum(map(ord, name)) % len(cols)])


def draw_umbrella(canvas, hx: int, hy: int, col, dim, hand: tuple | None = None) -> None:
    """머리(hx, hy) 위 우산: 반원 덮개 + 살 끝 + 손잡이 막대 (손 쪽으로)."""
    c = dim(col)
    top = hy - 16
    pygame.draw.ellipse(canvas, c, (hx - 13, top, 26, 14))
    edge = lerp_color(c, (0, 0, 0), 0.3)
    pygame.draw.line(canvas, edge, (hx - 13, top + 7), (hx + 13, top + 7), 1)
    for k in (-13, -6, 0, 6, 13):   # 살 끝 물결
        canvas.fill(edge, (hx + k - 1, top + 6, 2, 2))
    hl = lerp_color(c, (255, 255, 255), 0.35)
    pygame.draw.arc(canvas, hl, (hx - 11, top + 1, 22, 12), math.pi * 0.55, math.pi * 0.9, 1)
    pygame.draw.line(canvas, dim((60, 50, 40)), (hx, top + 7), hand or (hx + 7, hy + 14), 1)   # 손잡이


def draw_puddles(canvas, pal, ox: float, w: int, t: float, weather: str, ripples: list) -> None:
    """물웅덩이: 하늘색(지금 하늘) 반사 + 빗방울 파문. ripples = [[x, y, age]] (장면이 만들고 키움)."""
    c = cfg()["rain"]
    sky = lerp_color(tuple(pal["sky_bottom"]), (170, 210, 240), 0.45)
    for px, py, pw in c["puddles"]:
        sx = px - ox
        if not -pw < sx < w + pw:
            continue
        r = pygame.Rect(int(sx - pw / 2), py - 3, pw, 7)
        pygame.draw.ellipse(canvas, lerp_color(sky, (40, 50, 70), 0.35), r.inflate(2, 2))
        pygame.draw.ellipse(canvas, sky, r)
        canvas.fill(lerp_color(sky, (255, 255, 255), 0.5), (r.x + pw // 4, r.y + 2, pw // 3, 1))   # 하늘 반사 빛줄
    for rx, ry, age in ripples:
        k = age / 0.6
        rr = 1 + 5 * k
        col = lerp_color((235, 245, 255), sky, k)
        pygame.draw.ellipse(canvas, col, (int(rx - ox - rr), int(ry - rr * 0.35), int(rr * 2), max(1, int(rr * 0.7))), 1)


def tick_ripples(ripples: list, dt: float, weather: str, rnd) -> list:
    c = cfg()["rain"]
    rate = c["ripples_per_sec"].get(weather, 0.0) * len(c["puddles"])
    for r in ripples:
        r[2] += dt
    ripples = [r for r in ripples if r[2] < 0.6]
    if rate > 0:
        n = int(rate * dt) + (1 if rnd.random() < (rate * dt) % 1 else 0)
        for _ in range(n):
            px, py, pw = rnd.choice(c["puddles"])
            ripples.append([px + rnd.uniform(-pw * 0.38, pw * 0.38), py + rnd.uniform(-1.5, 1.5), 0.0])
    return ripples


def smoke_on(hour: float) -> float:
    """굴뚝 연기 세기 0~1: 17~19시 (처음 · 끝 15분은 서서히)."""
    c = cfg()["chimney"]
    a, b = c["from_hour"], c["to_hour"]
    if not a <= hour < b:
        return 0.0
    return clamp(min(hour - a, b - hour) / 0.25, 0, 1)


def chimney_pos(p: dict, sx: float, ground: int) -> tuple[int, int] | None:
    """굴뚝 꼭대기 (화면 좌표). 집 · 오두막: 지붕 오른쪽 경사 위 / 돌집(arch): 지붕 왼쪽 위."""
    kind, w = p["kind"], p["w"]
    x0 = int(sx - w / 2)
    if kind in ("house", "hut"):
        hh = (46 if p.get("low") else 62) if kind == "house" else 44
        cx = x0 + int(w * 0.74)
        slope = (cx - (x0 + w // 2)) / (w / 2 + 8)
        roof_y = ground - hh - int(30 * (1 - slope))
        return cx, roof_y - 8
    if kind == "arch":
        return x0 + 14, ground - 66 - 10 - 8
    return None


def draw_chimney(canvas, top: tuple[int, int], col, night: float) -> None:
    x, y = top
    canvas.fill(col, (x - 3, y, 7, 14))
    canvas.fill(lerp_color(col, (0, 0, 0), 0.35), (x - 4, y - 2, 9, 3))


def draw_smoke(canvas, top: tuple[int, int], t: float, k: float, seed: int, wind: float = 0.6) -> None:
    """천천히 오르며 커지고 옅어지는 연기 덩어리."""
    c = cfg()["chimney"]
    if k <= 0:
        return
    x, y = top
    n, rise = c["puffs"], c["rise_sec"]
    for i in range(n):
        u = ((t / rise) + i / n + seed * 0.137) % 1.0
        r = 2 + u * 6
        dx = u * 18 * wind + math.sin(t * 0.8 + i * 1.7 + seed) * 2 * u
        a = (1 - u) * 0.55 * k
        if a < 0.03:
            continue
        s = _puff(int(r), int(a * 20))
        canvas.blit(s, (int(x + dx - r - 1), int(y - 3 - u * 34 - r - 1)))


_PUFFS: dict = {}


def _puff(r: int, a20: int) -> pygame.Surface:
    """연기 덩어리 그림 (반지름 · 투명도 20단계로 구워 둠)."""
    key = (r, a20)
    s = _PUFFS.get(key)
    if s is None:
        s = _PUFFS[key] = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
        pygame.draw.circle(s, (210, 210, 214, int(255 * a20 / 20)), (r + 1, r + 1), r)
    return s
