"""엔딩: 용문잉어(최종 전설) 포획 후. 용이 하늘로 오르고 → 통계 → 계속 플레이."""
import math
import random

import pygame

from src.core.config import load_json
from src.core.mathutil import clamp, lerp, lerp_color
from src.scene.base import Scene
from src.ui import widgets as ui
from src.ui.fight_fx import big_text
from src.ui.hud import draw_cursor, text

LINES = [
    (1.5, "폭포를 거슬러 오른 잉어는"),
    (4.0, "마침내 용이 되어 하늘로 올랐다."),
    (6.5, "물가에는 잔잔한 물결만이 남았다."),
]
STATS_T = 9.5


class EndingScene(Scene):
    def __init__(self, game, fishing):
        super().__init__(game)
        self.fishing = fishing
        self.t = 0.0
        self.mouse = (0, 0)
        self.stars = [(random.uniform(0, 480), random.uniform(0, 200), random.random()) for _ in range(120)]
        game.sfx.stop_all()
        game.music.stop()
        if game.music.has("ending"):
            game.music.play("ending")
        else:
            game.sfx.loop("bgm_ending", True, 0.6)

    def handle_event(self, event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.t < STATS_T and self.t > 1.0:
                self.t = STATS_T  # 건너뛰기
            elif self.t > STATS_T + 1.5:
                self.game.sfx.loop("bgm_ending", False)
                self.game.scenes.pop()
                self.game.fade_in(0.8)

    def update(self, dt: float) -> None:
        self.t += dt
        if self.game.music.has("ending"):
            self.game.music.play("ending")
        self.mouse = self.game.to_canvas(pygame.mouse.get_pos())

    # ── 그리기 ──
    def draw(self, canvas) -> None:
        w, h = canvas.get_size()
        t = self.t
        # 밤하늘
        for y in range(0, h, 3):
            canvas.fill(lerp_color((6, 8, 26), (40, 30, 70), y / h), (0, y, w, 3))
        for x, y, b in self.stars:
            tw = 0.5 + 0.5 * math.sin(t * 2 + b * 10)
            canvas.fill(lerp_color((20, 20, 50), (255, 255, 240), b * tw), (int(x), int(y), 1, 1))
        # 달
        pygame.draw.circle(canvas, (60, 60, 90), (360, 70), 34)
        pygame.draw.circle(canvas, (240, 236, 210), (360, 70), 26)
        # 폭포와 수면
        canvas.fill((26, 30, 60), (0, 200, w, h - 200))
        pygame.draw.polygon(canvas, (16, 18, 36), [(0, 200), (0, 60), (60, 90), (150, 120), (200, 200)])
        pygame.draw.polygon(canvas, (16, 18, 36), [(w, 200), (w, 70), (430, 100), (330, 130), (290, 200)])
        canvas.fill((150, 170, 220), (226, 110, 28, 92))
        for i in range(8):
            yy = 110 + (t * 140 + i * 23) % 90
            canvas.fill((220, 230, 255), (228 + (i * 5) % 24, int(yy), 2, 7))
        pygame.draw.ellipse(canvas, (120, 130, 180), (190, 195, 100, 14))
        self._draw_dragon(canvas, t)
        # 이야기 문장
        if t < STATS_T:
            for start, line in LINES:
                if t > start:
                    a = clamp((t - start) / 0.8, 0, 1)
                    y = 222 + LINES.index((start, line)) * 14 - 28
                    text(canvas, line, (w // 2, y + int((1 - a) * 6)), lerp_color((26, 30, 60), (240, 236, 250), a),
                         11, "center")
        else:
            self._draw_stats(canvas, t - STATS_T)
        # 처음 페이드 인
        if t < 1.2:
            fl = pygame.Surface((w, h))
            fl.fill((255, 250, 240))
            fl.set_alpha(int(255 * (1 - t / 1.2)))
            canvas.blit(fl, (0, 0))
        draw_cursor(canvas, self.mouse)

    def _draw_dragon(self, canvas, t: float) -> None:
        """용: 몸통 마디들이 S자로 따라 오르며 달을 지나 하늘로."""
        k = clamp((t - 0.8) / 8.0, 0, 1.2)
        head_s = k * 1.6
        segs = 34
        pts = []
        for i in range(segs):
            s = head_s - i * 0.035
            if s < 0:
                break
            x = 240 + math.sin(s * 5.0) * 70 + s * 60
            y = 200 - s * 190
            pts.append((x, y))
        for i, (x, y) in reversed(list(enumerate(pts))):
            r = max(2, int(9 - i * 0.2))
            body = lerp_color((210, 40, 40), (150, 20, 30), i / segs)
            pygame.draw.circle(canvas, body, (int(x), int(y)), r)
            if i % 2 == 0:
                pygame.draw.circle(canvas, (255, 210, 110), (int(x), int(y) + r // 2), max(1, r // 2))
            if i % 6 == 3:
                # 지느러미 갈기
                pygame.draw.line(canvas, (255, 170, 40), (x, y - r), (x - 4, y - r - 6), 2)
        if pts:
            hx, hy = pts[0]
            pygame.draw.circle(canvas, (230, 50, 40), (int(hx), int(hy)), 11)
            pygame.draw.line(canvas, (255, 214, 110), (hx - 4, hy - 9), (hx - 8, hy - 18), 2)
            pygame.draw.line(canvas, (255, 214, 110), (hx + 4, hy - 9), (hx + 8, hy - 18), 2)
            canvas.fill((255, 255, 200), (int(hx) - 4, int(hy) - 3, 3, 3))
            canvas.fill((255, 255, 200), (int(hx) + 2, int(hy) - 3, 3, 3))
            for side in (-1, 1):
                wh = [(hx + side * 6, hy + 4), (hx + side * 18, hy + 10 + math.sin(t * 4) * 3),
                      (hx + side * 26, hy + 4)]
                pygame.draw.lines(canvas, (255, 214, 110), False, wh, 1)
            # 반짝이는 꼬리 빛
            for i in range(10):
                a = t * 3 + i
                canvas.fill((255, 240, 180), (int(hx + math.cos(a) * 16), int(hy + math.sin(a) * 16), 1, 1))

    def _draw_stats(self, canvas, t: float) -> None:
        w = canvas.get_width()
        save = self.game.save
        d = save.data
        st = d["stats"]
        total = len(load_json("fish.json")["fish"])
        big_text(canvas, "THE END", (w // 2, 40), (255, 228, 150), 2.6 if t > 0.2 else 3.6, outline=True)
        panel = pygame.Rect(w // 2 - 120, 70, 240, 120)
        ui.panel(canvas, panel)
        rows = [("플레이 시간", ui.time_text(d["playtime"])),
                ("총 포획", f"{st['catches']}마리"),
                ("S랭크", f"{st['s_ranks']}번"),
                ("퍼펙트", f"{st['perfects']}번"),
                ("도감", f"{save.dex_count()}/{total}종 ({save.dex_count() * 100 // total}%)"),
                ("번 돈", ui.money_text(st["earned"]))]
        for i, (k, v) in enumerate(rows):
            if t > 0.3 + i * 0.25:
                y = panel.y + 14 + i * 17
                text(canvas, k, (panel.x + 14, y), ui.DIM, 11, "midleft")
                text(canvas, v, (panel.right - 14, y), ui.ACCENT, 11, "midright")
        if t > 2.0:
            text(canvas, "플레이해 주셔서 고마워요!", (w // 2, 206), (240, 236, 250), 11, "center")
            text(canvas, "엔딩 후에도 계속 낚시를 즐길 수 있어요. 남은 도감과 금테를 채워 보세요.", (w // 2, 222),
                 ui.DIM, 11, "center")
        if t > 1.5 and int(t * 2) % 2 == 0:
            text(canvas, "클릭해서 계속", (w // 2, 250), (170, 180, 200), 11, "center")
