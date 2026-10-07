"""비늘석 화면 부품 (SCALESTONE.md, DESIGN.md 46장 S3): 그림 · 상세 카드 · 새 옵션 공개 연출 · 일괄 분해 확인 창.

새 옵션 공개 연출 (문서 표 그대로):
  0.0      강화 버튼 → 비늘석 그림이 살짝 떠오르며 빛남 + 작은 '띵' (ui_ss_rise)
  0.0~0.8  다음 부옵션 칸에서 옵션 이름이 빠르게 돌아감, 점점 느려짐 + 똑딱 (ui_ss_tick, 점점 느리게)
  0.8      옵션이 멈추며 등급 색으로 반짝, 수치가 0 → 뽑힌 값까지 0.3초 + 맑은 확정음 (ui_ss_lock)
  1.1      비늘석이 원래 자리로, +n 갱신
  +4 완성  테두리가 한 바퀴 빛나고 '완성' 도장 + 도장 '쾅' (ui_stamp, UI 손맛 규칙)
  0.3초 이후 탭하면 바로 결과 · 화면 효과 줄이기 = 돌아가는 연출 없이 0.3초 페이드로 결과.
그림은 정수배 확대만 (부드러운 보간 금지).
"""
import math

import pygame

from src.core.fonts import get_font
from src.core.paths import asset_path
from src.save import scalestone as ss
from src.ui import widgets as ui
from src.ui.hud import text

_IMG: dict = {}

LIFT_PX = 6
SPIN_END = 0.8
COUNT_SEC = 0.3
SETTLE = 1.1
SWEEP_SEC = 0.5          # +4 완성: 테두리 한 바퀴
STAMP_AT = SETTLE + SWEEP_SEC
DONE_END = STAMP_AT + 0.45
SKIP_AFTER = 0.3
REDUCE_SEC = 0.3
EMPTY_COL = (96, 102, 122)


def icon(grade: str | None, small: bool = False, scale: int = 1) -> pygame.Surface:
    """비늘석 그림 32x32 (small = 16x16), grade None = 빈 칸. scale = 정수배."""
    key = (grade, small, scale)
    img = _IMG.get(key)
    if img is None:
        if grade is None:
            name = "scalestone_slot_empty"
        else:
            name = ss.grade_info(grade)["icon"] + ("_16" if small else "")
        raw = pygame.image.load(str(asset_path("items", "scalestone", name + ".png")))
        try:
            raw = raw.convert_alpha()
        except pygame.error:
            pass
        if small and grade is None:
            raw = pygame.transform.scale(raw, (16, 16)) if raw.get_width() == 32 else raw
        img = _IMG[key] = pygame.transform.scale(raw, (raw.get_width() * scale, raw.get_height() * scale)) if scale != 1 else raw
    return img


def dots(stone: dict) -> str:
    """옵션 개수 점 ●●●○○."""
    n = len(stone["opts"])
    return "●" * n + "○" * (5 - n)


def draw_dots(canvas, x: int, cy: int, stone: dict, col) -> int:
    """옵션 개수 점 5개 (붙은 칸 = 등급 색 채움, 빈 칸 = 테두리) — 글꼴 ●○ 는 폭이 커서 직접 그림. 오른쪽 끝 x 를 돌려줌."""
    n = len(stone["opts"])
    for i in range(5):
        c = (x + 3 + i * 7, cy)
        if i < n:
            pygame.draw.circle(canvas, col, c, 3)
        else:
            pygame.draw.circle(canvas, EMPTY_COL, c, 3, 1)
    return x + 5 * 7


class EnhanceReveal:
    """강화 결과(scalestone.enhance 의 반환값)를 받아 공개 연출을 진행. 끝나면 active = False."""

    def __init__(self, res: dict, reduce: bool = False, sfx=None, rnd=None):
        self.res = res
        self.stone = res["stone"]
        self.grade = self.stone["grade"]
        self.col = tuple(ss.grade_info(self.grade)["color"])
        self.reduce = bool(reduce)
        self.sfx = sfx
        self.t = 0.0
        self.done_stone = bool(res.get("done"))
        self.end = (REDUCE_SEC if self.reduce else (DONE_END if self.done_stone else SETTLE + 0.15))
        self._played: set = set()
        # 돌아가는 이름: 이미 붙은 옵션을 뺀 후보를 돌림. 간격이 점점 길어짐 (0.035초 × 1.22^k), 마지막은 뽑힌 옵션
        o = ss.options()
        have = {x["id"] for x in self.stone["opts"][:res["index"]]}
        pool = [oid for oid in o["order"] if oid not in have] or [res["opt"]["id"]]
        import random as _r
        r = rnd or _r.Random(self.stone["uid"] * 31 + res["index"])
        self.ticks: list[tuple[float, str]] = []
        tt, gap, last = 0.0, 0.035, None
        while tt < SPIN_END - 0.02:
            cand = [p for p in pool if p != last] or pool
            last = r.choice(cand)
            self.ticks.append((tt, last))
            tt += gap
            gap *= 1.22
        self._tick_i = -1
        self._sound("ui_ss_rise" if not self.reduce else "ui_ss_lock")

    @property
    def active(self) -> bool:
        return self.t < self.end

    def _sound(self, name: str, vol: float = 0.7) -> None:
        if self.sfx is not None:
            self.sfx.play(name, vol)

    def update(self, dt: float) -> None:
        if not self.active:
            return
        self.t = min(self.end, self.t + dt)
        if self.reduce:
            if self.t >= REDUCE_SEC and self.done_stone and "stamp" not in self._played:
                self._played.add("stamp")
                self._sound("ui_stamp", 0.6)
            return
        # 똑딱: 이름이 바뀔 때마다
        while self._tick_i + 1 < len(self.ticks) and self.ticks[self._tick_i + 1][0] <= self.t and self.t < SPIN_END:
            self._tick_i += 1
            self._sound("ui_ss_tick", 0.5)
        if self.t >= SPIN_END and "lock" not in self._played:
            self._played.add("lock")
            self._sound("ui_ss_lock")
        if self.done_stone and self.t >= STAMP_AT and "stamp" not in self._played:
            self._played.add("stamp")
            self._sound("ui_stamp", 0.6)

    def tap(self) -> bool:
        """0.3초 이후 탭 → 바로 결과 (놓친 확정음 · 도장 소리는 한 번만). 받아들였으면 True."""
        if not self.active or self.reduce or self.t < SKIP_AFTER:
            return False
        if "lock" not in self._played:
            self._played.add("lock")
            self._sound("ui_ss_lock")
        if self.done_stone and "stamp" not in self._played:
            self._played.add("stamp")
            self._sound("ui_stamp", 0.6)
        self.t = self.end
        return True

    # ── 그릴 때 쓰는 값 ──
    def level_shown(self) -> int:
        if self.reduce:
            return self.res["level"] if self.t >= REDUCE_SEC * 0.5 else self.res["level"] - 1
        return self.res["level"] if self.t >= SETTLE else self.res["level"] - 1

    def lift(self) -> float:
        """돌이 떠오른 정도 0..1 (0.15초 올라감, 1.1에서 0.15초 내려옴)."""
        if self.reduce:
            return 0.0
        up = min(1.0, self.t / 0.15)
        down = max(0.0, min(1.0, (self.t - SETTLE) / 0.15))
        return max(0.0, up - down)

    def row(self) -> tuple[str | None, str | None, tuple, float]:
        """새 옵션 칸 내용 (이름, 수치 글자, 색, 반짝 0..1). 이름 None = 아직 빈 칸."""
        opt = self.res["opt"]
        if self.reduce:
            a = min(1.0, self.t / REDUCE_SEC)
            return ss.option_text(opt, False), ss.value_text(opt["id"], opt["v"]), self.col, 0.0 if a >= 1 else -a
        if self.t < SPIN_END:
            name = self.ticks[max(0, self._tick_i)][1] if self.ticks else opt["id"]
            return ss.options()["options"][name]["name"], "", ui.TEXT, 0.0
        k = min(1.0, (self.t - SPIN_END) / COUNT_SEC)
        k = 1 - (1 - k) ** 2
        v = opt["v"] * k
        spec = ss.options()["options"][opt["id"]]
        v = round(v, 1 if spec["unit"] == "pct" else 2)
        flash = max(0.0, 1.0 - (self.t - SPIN_END) / 0.35)
        return spec["name"], ss.value_text(opt["id"], v), self.col, flash

    def sweep(self) -> float | None:
        """+4 완성 테두리 빛 위치 0..1 (한 바퀴), 없으면 None."""
        if not self.done_stone or self.reduce or not (SETTLE <= self.t < STAMP_AT):
            return None
        return (self.t - SETTLE) / SWEEP_SEC

    def stamp_scale(self) -> float | None:
        """'완성' 도장 크기 (1.3 → 1.0, 0.14초), 아직이면 None."""
        if not self.done_stone:
            return None
        at = REDUCE_SEC if self.reduce else STAMP_AT
        if self.t < at:
            return None
        if self.reduce:
            return 1.0
        k = min(1.0, (self.t - at) / 0.14)
        return 1.3 - 0.3 * k


# ───────────────────────── 상세 카드 ─────────────────────────

def _stamp(canvas, center, scale: float, col) -> None:
    f = get_font(16)
    t = f.render("완성", False, col)
    s = pygame.Surface((t.get_width() + 12, t.get_height() + 6), pygame.SRCALPHA)
    s.blit(t, (6, 3))
    pygame.draw.rect(s, col, s.get_rect(), 2, border_radius=3)
    s = pygame.transform.rotate(s, -8)
    if abs(scale - 1.0) > 1e-3:
        s = pygame.transform.scale(s, (max(1, int(s.get_width() * scale)), max(1, int(s.get_height() * scale))))
    canvas.blit(s, s.get_rect(center=center))


def _perimeter_point(r: pygame.Rect, u: float) -> tuple[int, int]:
    per = 2 * (r.w + r.h)
    d = (u % 1.0) * per
    if d < r.w:
        return r.x + int(d), r.y
    d -= r.w
    if d < r.h:
        return r.right - 1, r.y + int(d)
    d -= r.h
    if d < r.w:
        return r.right - 1 - int(d), r.bottom - 1
    d -= r.w
    return r.x, r.bottom - 1 - int(d)


def draw_detail(canvas, rect, stone: dict, reveal: EnhanceReveal | None = None) -> dict:
    """오른쪽 상세: 그림 3배(96x96) · 등급 이름 · +n · 부옵션 5줄 (빈 칸 회색 '강화하면 열림').
    돌려주는 값: {"stone": 그림 rect, "rows": [줄 rect × 5]} — 화면이 버튼 · 튜토리얼 강조 위치로 씀."""
    rect = pygame.Rect(rect)
    g = ss.grade_info(stone["grade"])
    col = tuple(g["color"])
    if reveal is not None and reveal.stone is not stone:
        reveal = None
    big = icon(stone["grade"], scale=3)
    lift = reveal.lift() if reveal else 0.0
    sr = big.get_rect(topleft=(rect.x + 4, rect.y + 4 - int(round(LIFT_PX * lift))))
    if lift > 0:   # 빛남: 등급 색 둥근 빛 (더하기)
        glow = pygame.Surface((sr.w + 24, sr.h + 24))   # 검은 바탕 + 미리 곱한 색 → 더하기 (가장자리는 0)
        for i in range(6):
            k = 0.07 * lift * (i + 1)
            pygame.draw.ellipse(glow, tuple(int(v * k) for v in col), glow.get_rect().inflate(-i * 8, -i * 8))
        canvas.blit(glow, glow.get_rect(center=sr.center), special_flags=pygame.BLEND_ADD)
    canvas.blit(big, sr)
    sw = reveal.sweep() if reveal else None
    if sw is not None:   # 테두리 한 바퀴: 앞쪽 밝은 점 + 꼬리
        br = sr.inflate(4, 4)
        for j in range(14):
            u = sw - j * 0.012
            if u < 0:
                continue
            p = _perimeter_point(br, u)
            c = tuple(min(255, int(v * (1 - j / 16) + 255 * (1 - j / 14) * 0.4)) for v in col)
            pygame.draw.rect(canvas, c, (p[0] - 1, p[1] - 1, 3, 3))
    lvl = reveal.level_shown() if reveal else stone["level"]
    x = sr.right + 8
    text(canvas, f"{g['name']} 비늘석", (x, rect.y + 8), col, 13)
    text(canvas, f"+{lvl}", (x, rect.y + 26), ui.ACCENT if lvl >= 4 else ui.TEXT, 16)
    if stone.get("locked"):
        text(canvas, "잠김", (x, rect.y + 48), ui.DIM, 11)
    rows = []
    ry = rect.y + 4 + 96 + 8
    rh = 15
    rev_i = reveal.res["index"] if reveal else None
    for i in range(5):
        rr = pygame.Rect(rect.x + 4, ry + i * rh, rect.w - 8, rh - 1)
        rows.append(rr)
        if i == rev_i and reveal is not None:
            name, val, c, flash = reveal.row()
            if flash < 0:      # 줄이기: 페이드 인
                a = -flash
                pygame.draw.rect(canvas, ui.PANEL_LIGHT, rr, border_radius=2)
                s = pygame.Surface(rr.size, pygame.SRCALPHA)
                text(s, name, (4, 1), c, 11)
                text(s, val, (rr.w - 4, 1), c, 11, "topright")
                s.set_alpha(int(255 * a))
                canvas.blit(s, rr)
                continue
            pygame.draw.rect(canvas, ui.PANEL_LIGHT, rr, border_radius=2)
            if flash > 0:
                hl = pygame.Surface(rr.size)
                hl.fill(tuple(int(v * 0.45 * flash) for v in c))
                canvas.blit(hl, rr, special_flags=pygame.BLEND_ADD)
            text(canvas, name, (rr.x + 4, rr.y + 1), c, 11)
            if val:
                text(canvas, val, (rr.right - 4, rr.y + 1), c, 11, "topright")
            continue
        if i < len(stone["opts"]) and (rev_i is None or i < rev_i):
            o = stone["opts"][i]
            text(canvas, ss.option_text(o, False), (rr.x + 4, rr.y + 1), ui.TEXT, 11)
            text(canvas, ss.value_text(o["id"], o["v"]), (rr.right - 4, rr.y + 1), col, 11, "topright")
        else:
            pygame.draw.rect(canvas, (40, 46, 66), rr, 1, border_radius=2)
            text(canvas, "강화하면 열림", (rr.x + 4, rr.y + 1), EMPTY_COL, 11)
    sc = reveal.stamp_scale() if reveal else None
    if sc is not None:
        _stamp(canvas, (sr.right - 6, sr.bottom - 10), sc, ui.ACCENT)
    return {"stone": sr, "rows": rows}


def cost_text(stone: dict) -> str:
    """강화 버튼 글자: '강화 1,200원 · 소재 10' (최대면 '최대 강화')."""
    c = ss.enhance_cost(stone)
    if c is None:
        return "최대 강화"
    return f"강화 {ui.money_text(c['gold'])} · 소재 {c['mat']}"
