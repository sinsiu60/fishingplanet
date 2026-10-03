"""환상의 물고기 등장 연출 (DESIGN.md 33-5·33-6): 보랏빛 파장 + 환상 팔레트 + 대사.

세계(하늘·산·물)를 환상 팔레트로 한 번 더 그려서 파장 마스크(수면 납작한 타원 → 하늘 둥근 막)로 합성한다.
UI·HUD·신호 슬롯은 팔레트를 쓰지 않으므로 그대로.

상태 (mode):
  bloom   착수 → 파장이 퍼짐 (0.2~2.2초) → 화면 전체 보라 → 대사 (2.4~4.4초) → 입질까지 유지
  fight   파이팅 중 강도 fight_k(0.6), 2페이즈 진입 때 1.0 으로 맥박
  restore 포획 컷이 끝난 뒤 restore_sec 에 걸쳐 원래 색
  retreat 실패·직접 회수: 사라진 지점으로 보라가 빨려 들어감 (retreat_sec)
"""
import math

import pygame

from src.core.mathutil import clamp, lerp, lerp_color, smoothstep

# 팔레트 키 → (목표 색, 섞는 비율)
TARGET = {
    "sky_top": ((96, 52, 170), 0.75), "sky_bottom": ((176, 110, 220), 0.75),
    "water_top": ((70, 52, 150), 0.7), "water_bottom": ((34, 22, 84), 0.7), "wave_dark": ((40, 26, 92), 0.7),
    "wave_light": ((215, 180, 255), 0.6), "reflection": ((215, 180, 255), 0.6),
    "mountain_far": ((70, 40, 110), 0.75), "mountain_near": ((44, 24, 74), 0.75), "reed": ((40, 22, 66), 0.6),
    "sun": ((235, 210, 255), 0.6), "cloud": ((170, 130, 220), 0.6),
}
BOBBER = {"bobber": (240, 60, 200), "bobber_base": (240, 225, 255)}
RING = (226, 170, 255)


def _lum(c) -> float:
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2] + 1.0


def phantom_palette(pal: dict, k: float) -> dict:
    """시간대 팔레트에 환상 팔레트를 k(0~1)만큼 덧입힌다. 밝기는 원래 시간대를 따라감 (낮 = 밝은 보라, 밤 = 깊은 보라)."""
    if k <= 0.001:
        return pal
    out = dict(pal)
    for key, (tgt, amt) in TARGET.items():
        v = pal.get(key)
        if not isinstance(v, tuple):
            continue
        s = max(0.5, (_lum(v) / _lum(tgt)) ** 0.6)  # 아주 어두운 곳(동굴·밤)에서도 보라가 보이게 최소 밝기
        t2 = tuple(int(clamp(c * s, 0, 255)) for c in tgt)
        out[key] = lerp_color(v, t2, amt * k)
    for key, tgt in BOBBER.items():
        if isinstance(pal.get(key), tuple):
            out[key] = lerp_color(pal[key], tgt, k)
    return out


class PhantomFx:
    def __init__(self, cfg: dict):
        self.cfg = cfg               # phantom.json "spawn"
        self.mode: str | None = None
        self.t = 0.0
        self.k = 0.0                 # 화면 전체에 입히는 강도
        self.center = (0.0, 0.0)     # 파장 중심 (화면 좌표)
        self.k_from = 0.0
        self.reduce = False          # 화면 효과 줄이기: 파장 대신 페이드
        self.pulse_t = -1.0
        self.events: list[str] = []
        self.fired: set = set()

    @property
    def active(self) -> bool:
        return self.mode is not None

    # ── 시작·전환 ──
    def bloom(self, center, reduce: bool = False) -> None:
        self.mode, self.t, self.center, self.reduce = "bloom", 0.0, center, reduce
        self.k = 0.0
        self.fired = set()

    def to_fight(self) -> None:
        if self.mode is None:
            return
        self.mode, self.t = "fight", 0.0
        self.k_from = self.k

    def pulse(self) -> None:
        self.pulse_t = 0.0

    def restore(self) -> None:
        if self.mode is None:
            return
        self.mode, self.t, self.k_from = "restore", 0.0, self.k

    def retreat(self, center) -> None:
        if self.mode is None or self.mode == "retreat":
            return
        self.mode, self.t, self.k_from, self.center = "retreat", 0.0, max(self.k, 0.3), center

    def clear(self) -> None:
        self.mode = None
        self.k = 0.0

    def locked(self) -> bool:
        """파장이 퍼지는 동안 (0~full초) 릴 감기·재캐스팅·회수 입력 무시."""
        return self.mode == "bloom" and self.t < self.cfg["bloom"]["full"]

    # ── 시간 ──
    def update(self, dt: float) -> None:
        if self.mode is None:
            return
        self.t += dt
        b = self.cfg["bloom"]
        if self.mode == "bloom":
            if self.reduce:
                self.k = smoothstep(clamp((self.t - b["start"]) / self.cfg["reduce_fx_fade_sec"], 0, 1))
            else:
                self.k = 1.0 if self.t >= b["full"] else 0.0  # 그 전엔 마스크로만
            for name, at in (("start", b["start"]), ("full", b["full"]), ("line", b["line_in"])):
                if self.t >= at and name not in self.fired:
                    self.fired.add(name)
                    self.events.append(f"bloom_{name}")
        elif self.mode == "fight":
            fk = self.cfg["fight_k"]
            self.k = lerp(self.k_from, fk, smoothstep(clamp(self.t / 0.8, 0, 1)))
            if self.pulse_t >= 0:
                self.pulse_t += dt
                p = self.pulse_t / self.cfg["phase_pulse_sec"]
                if p >= 1:
                    self.pulse_t = -1.0
                else:
                    self.k = max(self.k, lerp(fk, 1.0, math.sin(math.pi * p)))
        elif self.mode == "restore":
            u = clamp(self.t / self.cfg["restore_sec"], 0, 1)
            self.k = self.k_from * (1 - smoothstep(u))
            if u >= 1:
                self.clear()
        elif self.mode == "retreat":
            u = clamp(self.t / self.cfg["retreat_sec"], 0, 1)
            self.k = 0.0
            if u >= 1:
                self.clear()

    # ── 대사 ──
    def line_alpha(self) -> float:
        if self.mode != "bloom":
            return 0.0
        b = self.cfg["bloom"]
        if self.t < b["line_in"] or self.t > b["line_out"] + 0.4:
            return 0.0
        return min(1.0, (self.t - b["line_in"]) / 0.4, (b["line_out"] + 0.4 - self.t) / 0.4)

    def calm(self) -> float:
        """물결 멈춤 정도 0~1 (파도 진폭을 줄인다)."""
        if self.mode == "bloom":
            return smoothstep(clamp((self.t - self.cfg["bloom"]["start"]) / 2.0, 0, 1))
        if self.mode == "fight":
            return 0.3
        return 0.0

    # ── 마스크 ──
    def mask_front(self) -> float | None:
        """지금 파장 앞쪽이 있는 '파장 시간'(0.2~2.2초 기준). None = 마스크 없음."""
        b = self.cfg["bloom"]
        if self.reduce:
            return None
        if self.mode == "bloom" and b["start"] <= self.t < b["full"] + b["fade"]:
            return self.t
        if self.mode == "retreat":
            u = clamp(self.t / self.cfg["retreat_sec"], 0, 1)
            return lerp(b["full"] + b["fade"], b["start"], smoothstep(u))
        return None

    def inner_k(self) -> float:
        """마스크 안쪽 강도."""
        return self.k_from if self.mode == "retreat" else 1.0

    def _shapes(self, w: int, h: int, hz: int, ft: float):
        """파장 시간 ft 의 (수면 타원 반지름 rx·위·아래, 하늘 막 반지름)."""
        b = self.cfg["bloom"]
        cx, cy = self.center
        u = clamp((ft - b["start"]) / (b["horizon"] - b["start"]), 0, 1.4)
        e = u ** 0.85
        rx = max(1.0, w * 1.15) * e
        ry_down = max(1.0, (h - cy) * 1.25) * e ** 0.8      # 가까운 쪽 빠르게
        ry_up = max(1.0, (cy - hz) + 2) * clamp((ft - b["start"]) / (b["sky_start"] - b["start"]), 0, 1.5)  # 먼 쪽 느리게
        sky = 0.0
        if ft > b["sky_start"]:
            far = max(math.hypot(cx, hz), math.hypot(w - cx, hz)) * 1.05
            sky = far * smoothstep(clamp((ft - b["sky_start"]) / (b["full"] - b["sky_start"]), 0, 1))
        return rx, ry_up, ry_down, sky

    def _draw_region(self, surf, w, h, hz, ft, color, width=0) -> None:
        cx, cy = self.center
        rx, ry_up, ry_down, sky = self._shapes(w, h, hz, ft)
        if rx < 1:
            return
        old = surf.get_clip()
        # 수면: 아래 반 (가까운 쪽) + 위 반 (먼 쪽), 수평선 아래만
        surf.set_clip(pygame.Rect(0, max(hz, int(cy)), w, h))
        pygame.draw.ellipse(surf, color, (cx - rx, cy - ry_down, rx * 2, ry_down * 2), width)
        surf.set_clip(pygame.Rect(0, hz, w, max(0, int(cy) - hz + 1)))
        pygame.draw.ellipse(surf, color, (cx - rx, cy - ry_up, rx * 2, ry_up * 2), width)
        if sky > 1:
            surf.set_clip(pygame.Rect(0, 0, w, hz))
            pygame.draw.circle(surf, color, (int(cx), hz), int(sky), width)
        surf.set_clip(old)

    def mask(self, w: int, h: int, hz: int) -> pygame.Surface | None:
        """알파 마스크 (흰색, 지나간 자리 255 · 앞쪽 0.3초 띠는 점점 옅게)."""
        ft = self.mask_front()
        if ft is None:
            return None
        m = pygame.Surface((w, h), pygame.SRCALPHA)
        m.fill((255, 255, 255, 0))
        fade = self.cfg["bloom"]["fade"]
        for i, a in enumerate((70, 130, 190, 255)):
            self._draw_region(m, w, h, hz, ft - fade * i / 3, (255, 255, 255, a))
        return m

    def draw_ring(self, canvas, hz: int) -> None:
        """파장 테두리: 밝은 보라 얇은 선 + 바깥 옅은 잔물결."""
        ft = self.mask_front()
        if ft is None:
            return
        w, h = canvas.get_size()
        self._draw_region(canvas, w, h, hz, ft + 0.08, lerp_color(RING, (40, 20, 70), 0.55), 1)
        self._draw_region(canvas, w, h, hz, ft, RING, 1)
