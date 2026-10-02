"""돌진 예고 = 낚싯줄 펄스 (DESIGN.md 31-14). 수치는 data/signals.json "rush_pulse".

  1단계 웅크림 : 그림자가 짧게 압축 + 꼬리 S자, 바깥에서 안쪽으로 줄어드는 점선 타원, 줄이 살짝 느슨
  2단계 줄 펄스 : 빛 펄스가 줄을 따라 물고기 → 손 (이동 시간 = 남은 예고), 배지가 아래부터 차오름,
                 울림 음이 점점 높아지다 돌진 silence_sec 전 무음, 모바일은 약한 진동이 점점 세게
  3단계 돌진   : 펄스가 손에 닿는 순간 돌진 — 그림자 길게 늘어나며 멀어짐, V자 물살·물보라, 줄이 팽팽히 튕김,
                 배지 꽉 차며 번쩍, '쉬익', 모바일 '툭'
  변주: 대형(big_fish_cm 이상) 펄스 2개(두 번째에 돌진) / 광폭 = 더 밝고 웅크림 짧게 / 교활 가짜 돌진 = 웅크림·물결만
"""
import math

import pygame

from src.core.config import load_json
from src.core.mathutil import clamp, lerp_color

PULSE = (255, 236, 160)


def cfg() -> dict:
    return load_json("signals.json")["rush_pulse"]


def phase(fight) -> dict | None:
    """지금 돌진 예고·시작 단계. None = 돌진과 상관없음."""
    b = fight.brain
    c = cfg()
    frenzy = "frenzy" in fight.mutations
    if b.state == "telegraph" and b.pending in ("rush", "fake_rush"):
        p = b.signal_progress()
        fake = b.pending == "fake_rush"
        cf = c["crouch_frac"] * (c["frenzy_crouch_mult"] if frenzy else 1.0)
        if fake:
            return {"stage": "crouch", "k": clamp(p / max(0.05, cf), 0, 1), "fake": True, "frenzy": frenzy}
        if p < cf:
            return {"stage": "crouch", "k": p / cf, "fake": False, "frenzy": frenzy}
        q = (p - cf) / max(1e-6, 1 - cf)
        n = c["big_fish_pulses"] if fight.size_cm >= c["big_fish_cm"] else 1
        idx = min(n - 1, int(q * n))
        return {"stage": "pulse", "q": q, "pk": q * n - idx, "idx": idx, "n": n, "frenzy": frenzy, "fake": False,
                "left": (1 - p) * b.cur_telegraph, "k": 1.0}
    if b.state == "rush" and b.state_t < c["rush_flash_sec"] * 2:
        return {"stage": "rush", "k": clamp(b.state_t / c["rush_flash_sec"], 0, 1), "frenzy": frenzy, "fake": False}
    return None


def shadow_mods(ph: dict | None) -> dict:
    """그림자 모양: 웅크림 = 짧게 압축 + 꼬리 S자, 돌진 = 길게 늘어남."""
    if ph is None:
        return {}
    if ph["stage"] in ("crouch", "pulse"):
        k = ph["k"]
        return {"squash": 1 - 0.38 * k, "curl": k}
    k = ph["k"]
    return {"stretch": 0.7 * (1 - abs(k - 0.4))}


def line_sag(ph: dict | None) -> float:
    """줄 처짐 추가량: 웅크리면 살짝 느슨, 돌진 순간엔 팽팽 (음수)."""
    if ph is None:
        return 0.0
    if ph["stage"] == "crouch":
        return 7 * ph["k"]
    if ph["stage"] == "pulse":
        return 6 * (1 - ph["q"])
    return -20 if ph["k"] < 1 else 0.0


def draw_ripples(canvas, pos, scale: float, ph: dict | None, t: float) -> None:
    """웅크림: 바깥에서 중심으로 줄어드는 점선 타원 (물이 빨려 든다)."""
    if ph is None or ph["stage"] not in ("crouch", "pulse") or pos is None:
        return
    c = cfg()
    n = c["ripples"]
    per = c["ripple_period_sec"] * (0.7 if ph.get("frenzy") else 1.0)
    fade = 1.0 if ph["stage"] == "crouch" else max(0.0, 1 - ph["q"] * 1.5)
    if fade <= 0.02:
        return
    x, y = pos
    base = 30 * max(0.6, min(1.6, scale))
    layer = pygame.Surface(canvas.get_size(), pygame.SRCALPHA)
    for i in range(n):
        k = 1 - ((t / per + i / n) % 1.0)          # 1 → 0: 바깥에서 안으로
        rx, ry = base * (0.3 + 0.9 * k), base * (0.3 + 0.9 * k) * 0.32
        a = int(200 * fade * (1 - k * 0.6) * min(1.0, (1 - k) * 4 + 0.3))
        segs = 14
        for j in range(segs):
            if j % 2:
                continue  # 점선
            a0, a1 = j / segs * math.tau, (j + 1) / segs * math.tau
            p0 = (x + math.cos(a0) * rx, y + math.sin(a0) * ry)
            p1 = (x + math.cos(a1) * rx, y + math.sin(a1) * ry)
            pygame.draw.line(layer, (225, 240, 255, a), p0, p1, 1)
    canvas.blit(layer, (0, 0))


def draw_pulse(canvas, pts: list, ph: dict | None, t: float) -> None:
    """줄 위 빛 펄스: pts = 손(낚싯대 끝) → 물고기. 펄스는 물고기 쪽에서 손 쪽으로."""
    if ph is None or ph["stage"] != "pulse" or not pts or len(pts) < 2:
        return
    bright = cfg()["frenzy_brightness"] if ph.get("frenzy") else 1.0
    u = 1 - ph["pk"]                                 # 1 = 물고기 끝, 0 = 손
    n = len(pts) - 1
    layer = pygame.Surface(canvas.get_size(), pygame.SRCALPHA)
    for tail in range(6, -1, -1):                    # 꼬리 잔상 (물고기 쪽)
        uu = min(1.0, u + tail * 0.025)
        f = uu * n
        i = min(n - 1, int(f))
        fx = pts[i][0] + (pts[i + 1][0] - pts[i][0]) * (f - i)
        fy = pts[i][1] + (pts[i + 1][1] - pts[i][1]) * (f - i)
        a = int(clamp(255 * (1 - tail / 7) * min(1.0, bright), 0, 255))
        r = (3.5 if tail == 0 else 2.4 - tail * 0.25) * (1.35 if bright > 1 else 1.0)
        if tail == 0:
            pulse = 0.85 + 0.15 * math.sin(t * 40)
            pygame.draw.circle(layer, (*PULSE, int(min(255, 70 * bright))), (int(fx), int(fy)), int(r * 3.4 * pulse))
            pygame.draw.circle(layer, (*PULSE, int(min(255, 150 * bright))), (int(fx), int(fy)), int(r * 2))
            pygame.draw.circle(layer, (255, 255, 255, 255), (int(fx), int(fy)), max(1, int(r)))
        else:
            pygame.draw.circle(layer, (*PULSE, a), (int(fx), int(fy)), max(1, int(r)))
    # 지나온 줄(물고기~펄스)은 살짝 빛남
    k = int(u * n)
    if k < n:
        seg = pts[k:]
        if len(seg) >= 2:
            pygame.draw.lines(layer, (*PULSE, int(120 * min(1.0, bright))), False, seg, 1)
    canvas.blit(layer, (0, 0))


def draw_taut(canvas, pts: list, ph: dict | None, t: float) -> None:
    """돌진 순간: 줄이 팽팽하게 튕김 (하얀 줄 + 떨림)."""
    if ph is None or ph["stage"] != "rush" or ph["k"] >= 1 or not pts:
        return
    k = ph["k"]
    amp = 3 * (1 - k)
    out = []
    for i, (x, y) in enumerate(pts):
        u = i / max(1, len(pts) - 1)
        out.append((x, y + math.sin(u * math.pi) * math.sin(t * 90) * amp))
    col = lerp_color((255, 255, 255), PULSE, k)
    pygame.draw.lines(canvas, col, False, out, 2 if k < 0.5 else 1)


def draw_wake(canvas, pos, heading_side: float, scale: float, ph: dict | None, t: float) -> None:
    """돌진: 물고기 뒤로 벌어지는 V자 물살."""
    if ph is None or ph["stage"] != "rush" or pos is None:
        return
    k = min(1.0, ph["k"] / 2 + 0.5 * (ph["k"] >= 1))
    x, y = pos
    d = 1 if heading_side >= 0 else -1
    ln = 26 * max(0.6, min(1.6, scale)) * (0.5 + k)
    a = int(220 * (1 - k * 0.6))
    layer = pygame.Surface(canvas.get_size(), pygame.SRCALPHA)
    for s in (-1, 1):
        for w in range(3):
            off = w * 4
            pygame.draw.line(layer, (235, 245, 255, max(0, a - w * 60)), (x - d * off, y),
                             (x - d * (ln + off), y + s * ln * 0.32), 1)
    canvas.blit(layer, (0, 0))
