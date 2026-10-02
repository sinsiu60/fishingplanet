"""모바일 터치 버튼 배치와 그리기 (DESIGN.md 26-10, MOBILE.md 1번 그림).

    [일시정지]                                   [가방] / 파이팅 중 [도구]
    ...
    (숙이기)  [▲]▮                                         ( 릴 패드 )
              [▼]▮                                         감기·방향·꺾기
왼손잡이 모드면 좌우를 뒤집는다. 크기·투명도는 설정 3단계. 태블릿(캔버스 높이 > 300)은 조금 작게.
버튼 판정은 실제 모양보다 button_slop_px 만큼 넉넉하다.
"""
import math

import pygame

from src.core.config import load_json
from src.ui.hud import SHADOW, text

TEXT = (236, 240, 248)


def cfg() -> dict:
    return load_json("mobile_config.json")


class Control:
    def __init__(self, cid: str, rect: pygame.Rect, shape: str = "rect", label: str = ""):
        self.id = cid
        self.rect = rect
        self.shape = shape
        self.label = label

    @property
    def center(self) -> tuple[int, int]:
        return self.rect.center

    @property
    def r(self) -> int:
        return self.rect.w // 2

    def hit(self, p) -> bool:
        slop = cfg()["button_slop_px"]
        if self.shape == "circle":
            return math.hypot(p[0] - self.center[0], p[1] - self.center[1]) <= self.r + slop
        return self.rect.inflate(slop * 2, slop * 2).collidepoint(p)


def ui_scale(h: int, settings) -> float:
    c = cfg()
    s = c["button_sizes"][settings.get("touch_size")]
    return s * (c["tablet_scale"] if h > 300 else 1.0)


def layout(w: int, h: int, ctx: dict, settings, items_open: bool = False) -> list[Control]:
    """지금 상황(ctx: FishingScene.touch_context)에 보여 줄 버튼들. 앞쪽이 먼저 판정된다."""
    s = ui_scale(h, settings)
    left_handed = settings.get("touch_left")
    sx = ctx.get("safe_x", 0)  # 폰 가장자리 카메라 구멍·둥근 모서리
    m = 8 + sx
    out: list[Control] = []

    def add(cid, x, y, cw, ch, shape="rect", label=""):
        x, y, cw, ch = int(x), int(y), int(round(cw)), int(round(ch))
        if left_handed:
            x = w - x - cw
        out.append(Control(cid, pygame.Rect(x, y, cw, ch), shape, label))

    if ctx.get("overlay"):
        return out  # 튜토리얼 카드·도움말: 화면 아무 곳이나 탭하면 닫힘
    top = 22
    if ctx.get("show_pause"):
        add("pause", 4 + sx, 4, top, top)
    if ctx.get("fight"):
        items = ctx.get("items") or []
        if items:
            add("item", w - 4 - sx - top, 4, top, top, label="도구")
            if items_open:
                # 도구 버튼 아래로 펼침 (옆으로 펼치면 물고기 이름·체력 바를 가린다)
                bw = 70
                for n, (slot, name, count) in enumerate(items):
                    add(f"item{slot}", w - 4 - sx - bw, 4 + top + 6 + n * (top + 4), bw, top, label=f"{name} ×{count}")
        r = 20 * s
        add("dip", m, h - m - 2 * r, 2 * r, 2 * r, "circle", "숙이기")
        bw, bh = 28 * s, 22 * s
        bx = m + 2 * r + 8
        add("drag_up", bx, h - m - 2 * bh - 6, bw, bh, label="▲")
        add("drag_down", bx, h - m - bh, bw, bh, label="▼")
        pr = 40 * s
        add("pad", w - m - 2 * pr, h - m - 2 * pr, 2 * pr, 2 * pr, "circle", "감기")
    else:
        if ctx.get("show_bag"):
            add("bag", w - 4 - sx - top, 4, top, top)
        if ctx.get("can_retrieve"):
            add("retrieve", m, h - m - 24 * s, 52 * s, 24 * s, label="회수")
        if ctx.get("lure"):
            # 대기 중 루어: 패드를 가볍게 누르고 있으면 리트리브 (짧게 탭 = 저킹)
            pr = 32 * s
            add("pad", w - m - 2 * pr, h - m - 2 * pr, 2 * pr, 2 * pr, "circle", "리트리브")
    return out


def _icon(surf, c: Control, col) -> None:
    x, y = c.center
    if c.id == "pause":
        surf.fill(col, (x - 4, y - 5, 3, 10))
        surf.fill(col, (x + 2, y - 5, 3, 10))
    elif c.id == "bag":
        pygame.draw.rect(surf, col, (x - 6, y - 3, 12, 9), 1)
        pygame.draw.arc(surf, col, (x - 4, y - 8, 8, 9), 0, math.pi, 1)
    elif c.id == "dip":  # 숙이기 (파이팅 중 글자 대신 그림, 31장)
        from src.ui import icons
        icons.dip(surf, x, y, col)
    elif c.id == "item":
        from src.ui import icons
        icons.bag(surf, x, y, col)
    elif c.id in ("drag_up", "drag_down"):
        d = -1 if c.id == "drag_up" else 1
        k = max(4, c.rect.h // 4)
        pygame.draw.polygon(surf, col, [(x - k, y - d * k // 2), (x + k, y - d * k // 2), (x, y + d * k // 2)])
    else:
        text(surf, c.label, (x, y), col, 11, "center")


def draw(canvas, controls: list[Control], pressed: set, settings, aim: float = 0.0, drag=None,
         pitch: float = 0.0) -> None:
    """버튼을 반투명으로 그린다. pressed = 지금 눌린 버튼 id."""
    a = cfg()["button_alpha"][settings.get("touch_alpha")]
    layer = pygame.Surface(canvas.get_size(), pygame.SRCALPHA)
    for c in controls:
        on = c.id in pressed
        fill = (60, 80, 120, min(255, a + 40)) if on else (16, 22, 40, a)
        edge = (255, 220, 120, 230) if on else (220, 228, 245, min(255, a + 60))
        if c.shape == "circle":
            pygame.draw.circle(layer, fill, c.center, c.r)
            pygame.draw.circle(layer, edge, c.center, c.r, 1)
        else:
            pygame.draw.rect(layer, fill, c.rect, border_radius=4)
            pygame.draw.rect(layer, edge, c.rect, 1, border_radius=4)
        if c.id == "pad":
            # 노브: 누른 채 좌우로 밀면 낚싯대 방향, 위아래로 밀면 낚싯대 상하 (손 떼면 상하만 가운데로)
            kx = c.center[0] + int(aim * c.r * 0.55)
            ky = c.center[1] - int((pitch if on else 0.0) * c.r * 0.4)
            kr = int(c.r * 0.42)
            pygame.draw.line(layer, (220, 228, 245, a), (c.rect.x + 6, c.center[1]), (c.rect.right - 6, c.center[1]))
            pygame.draw.line(layer, (220, 228, 245, a // 2), (c.center[0], c.rect.y + 16), (c.center[0], c.rect.bottom - 16))
            pygame.draw.circle(layer, (255, 220, 120, 200) if on else (200, 210, 230, min(255, a + 30)),
                               (kx, ky), kr)
    canvas.blit(layer, (0, 0))
    for c in controls:
        col = (255, 228, 140) if c.id in pressed else TEXT
        if c.id == "pad":
            if c.label == "감기":
                # 파이팅: 글자 대신 릴 그림 + 좌우 삼각형 (방향)
                from src.ui import icons
                icons.reel(canvas, c.center[0], c.rect.bottom - 11, col)
                for d in (-1, 1):
                    tx = c.center[0] + d * (c.r - 10)
                    pygame.draw.polygon(canvas, (200, 208, 225), [(tx + d * 4, c.center[1]), (tx - d * 2, c.center[1] - 5),
                                                                  (tx - d * 2, c.center[1] + 5)])
            else:
                text(canvas, c.label, (c.center[0], c.rect.bottom - 9), col, 11, "center")
        else:
            _icon(canvas, c, col)
    if drag is not None:
        up = next((c for c in controls if c.id == "drag_up"), None)
        down = next((c for c in controls if c.id == "drag_down"), None)
        if up and down:
            cur, steps = drag
            x = max(up.rect.right, down.rect.right) + 4 if up.rect.x < canvas.get_width() // 2 \
                else min(up.rect.x, down.rect.x) - 10
            y0, y1 = up.rect.y, down.rect.bottom
            ch = (y1 - y0 - (steps - 1) * 2) / steps
            for i in range(steps):
                yy = int(y1 - (i + 1) * ch - i * 2)
                canvas.fill(SHADOW, (x - 1, yy - 1, 8, int(ch) + 2))
                canvas.fill((255, 220, 120) if i < cur else (60, 64, 80), (x, yy, 6, int(ch)))
            right = x > up.rect.x
            from src.ui import icons
            icons.reel(canvas, x + 15 if right else x - 9, (y0 + y1) // 2, TEXT)  # 드랙 = 릴 그림
