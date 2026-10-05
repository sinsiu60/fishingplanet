"""청새치 '일섬' 파이팅 연출 (ILSEOM.md 5장, DESIGN.md 43-15) — 이 물고기(fish.json "theme": "ilseom")에만.

  blade_ripple(y)  등장: 수면에 칼날 같은 물결 한 줄이 가로로 지나감 (1.1초)
  rush_line(a, b)  돌진 예고: 수면에 물고기 방향 얇은 흰 선 (0.35초) — 기존 신호에 덧붙이기만
  slash()          퍼펙트: 화면 위쪽 절반을 가로지르는 하얀 사선 베기 선, 가장자리 금빛 (0.15초 + 0.1초 사라짐)
                   — 신호 슬롯(화면 아래·물고기 주변)을 가리지 않게 위쪽 45%에만. 화면 효과 줄이기면 장면이 부르지 않음
  vignette()       3페이즈 진입: 화면 가장자리가 0.3초 살짝 어두워짐
"""
import pygame

from src.core.mathutil import clamp, lerp

WHITE = (255, 255, 255)
GOLD = (255, 214, 120)


class IlseomFX:
    SLASH_SEC = 0.15
    SLASH_FADE = 0.1

    def __init__(self):
        self.items: list[list] = []   # [종류, 남은 시간, 전체 시간, 자료]

    def blade_ripple(self, y: float) -> None:
        self.items.append(["ripple", 1.1, 1.1, y])

    def rush_line(self, a, b) -> None:
        self.items.append(["rush", 0.35, 0.35, (a, b)])

    def slash(self) -> None:
        t = self.SLASH_SEC + self.SLASH_FADE
        self.items.append(["slash", t, t, None])

    def vignette(self) -> None:
        self.items.append(["vignette", 0.3, 0.3, None])

    def update(self, dt: float) -> None:
        for it in self.items:
            it[1] -= dt
        self.items = [it for it in self.items if it[1] > 0]

    def active(self) -> bool:
        return bool(self.items)

    def draw(self, canvas: pygame.Surface, layer: str = "world") -> None:
        """layer: world = 수면 위 (물결·돌진 선) / screen = 화면 위 (베기 선·가장자리)."""
        w, h = canvas.get_size()
        for kind, left, total, data in self.items:
            u = 1 - left / total
            if layer == "world" and kind == "ripple":
                # 칼날 같은 물결: 얇고 밝은 선이 왼쪽에서 오른쪽으로 베고 지나감 (앞끝이 가장 밝음)
                x = lerp(-0.1 * w, 1.1 * w, u)
                y = int(data)
                a = 1 - clamp((u - 0.75) / 0.25, 0, 1)
                tail = w * 0.45
                for j in range(6):
                    k = j / 6
                    c = tuple(int(v * a * (0.25 + 0.75 * (1 - k))) for v in (220, 235, 255))
                    pygame.draw.line(canvas, c, (x - tail * (k + 1 / 6), y), (x - tail * k, y), 1)
                pygame.draw.line(canvas, tuple(int(v * a) for v in WHITE), (x - 18, y), (x + 2, y), 2)
            elif layer == "world" and kind == "rush":
                (ax, ay), (bx, by) = data
                a = 1 - u
                ex, ey = lerp(ax, bx, min(1.0, u * 3)), lerp(ay, by, min(1.0, u * 3))
                pygame.draw.line(canvas, tuple(int(v * a) for v in (235, 245, 255)), (ax, ay), (ex, ey), 1)
            elif layer == "screen" and kind == "slash":
                el = total - left
                grow = clamp(el / 0.05, 0, 1)
                a = 1.0 if el < self.SLASH_SEC else 1 - (el - self.SLASH_SEC) / self.SLASH_FADE
                x0, y0 = w * 0.22, h * 0.13   # 왼쪽 게이지·위쪽 보스 막대를 피해서
                x1, y1 = w * 0.96, h * 0.44
                xe, ye = lerp(x0, x1, grow), lerp(y0, y1, grow)
                glow = pygame.Surface((w, h))
                glow.fill((0, 0, 0))
                pygame.draw.line(glow, tuple(int(v * a * 0.55) for v in GOLD), (x0, y0), (xe, ye), 7)
                pygame.draw.line(glow, tuple(int(v * a) for v in GOLD), (x0, y0), (xe, ye), 4)
                canvas.blit(glow, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
                pygame.draw.line(canvas, tuple(int(lerp(150, 255, a)) for _ in range(3)), (x0, y0), (xe, ye), 2)
            elif layer == "screen" and kind == "vignette":
                a = 1 - abs(u * 2 - 1)   # 0.15초에 가장 어둡고 다시 밝아짐
                band = max(8, int(min(w, h) * 0.12))
                s = pygame.Surface((w, h), pygame.SRCALPHA)
                for i in range(band):
                    al = int(110 * a * (1 - i / band) ** 1.6)
                    if al <= 0:
                        continue
                    pygame.draw.rect(s, (0, 0, 0, al), (i, i, w - 2 * i, h - 2 * i), 1)
                canvas.blit(s, (0, 0))
