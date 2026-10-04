"""엔딩.

- sharmion: 용문잉어 '등용' 포획 후. 용이 하늘로 오르고 → 통계 → (처음이면) 엘드라시온의 소문 · 범선 출항
- final:    천해왕 오르시엘 포획 후. 세계수 위로 천해왕이 오르고 → 두 대륙 합산 통계 → 계속 플레이
"""
import math
import random

import pygame

from src.render.screen import opaque as _opaque

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
FINAL_LINES = [
    (1.5, "세계수의 뿌리에서 솟아오른 천해왕은"),
    (4.0, "하늘과 바다를 잇는 별의 강이 되었다."),
    (6.5, "두 대륙의 물가에는 오늘도 찌가 흔들린다."),
]
STATS_T = 9.5


class EndingScene(Scene):
    UI_FRAME = True

    def __init__(self, game, fishing, kind: str = "sharmion"):
        super().__init__(game)
        self.fishing = fishing
        self.kind = kind
        self.lines = FINAL_LINES if kind == "final" else LINES
        self.t = 0.0
        self.mouse = (0, 0)
        self.stars = [(random.uniform(0, 480), random.uniform(0, 200), random.random()) for _ in range(120)]
        game.sfx.stop_all()
        game.music.stop()
        game.adaptive.stop()
        self.track = "ending_final" if kind == "final" and game.music.has("ending_final") else "ending"
        if game.music.has(self.track):
            game.music.play(self.track)
        else:
            game.adaptive.set_context("ending", None)  # 합성 엔딩 곡 mus_ending (32장 S8)
            game.adaptive.set("menu")

    def handle_action(self, a) -> None:
        if a.name == "primary":
            if self.t < STATS_T and self.t > 1.0:
                self.t = STATS_T  # 건너뛰기
            elif self.t > STATS_T + 1.5:
                self.game.scenes.pop()
                if self.kind == "sharmion" and "eldrasion" not in self.game.save.data["unlocked_continents"]:
                    from src.scene.voyage import VoyageScene
                    self.game.scenes.push(VoyageScene(self.game, self.fishing))
                else:
                    self.game.fade_in(0.8)

    def update(self, dt: float) -> None:
        self.t += dt
        if self.game.music.has(self.track):
            self.game.music.play(self.track)
        self.mouse = self.ui_pointer()

    # ── 그리기 ──
    def draw(self, canvas) -> None:
        if self.game.screen.ui_rect.size != canvas.get_size():
            canvas.fill((0, 0, 0))  # 모바일: 컷신은 가운데 16:9 (남는 곳은 검게)
        canvas = self.ui_canvas(canvas)
        w, h = canvas.get_size()
        t = self.t
        # 밤하늘
        top, bottom = ((4, 10, 30), (30, 60, 80)) if self.kind == "final" else ((6, 8, 26), (40, 30, 70))
        for y in range(0, h, 3):
            canvas.fill(lerp_color(top, bottom, y / h), (0, y, w, 3))
        for x, y, b in self.stars:
            tw = 0.5 + 0.5 * math.sin(t * 2 + b * 10)
            canvas.fill(lerp_color((20, 20, 50), (255, 255, 240), b * tw), (int(x), int(y), 1, 1))
        if self.kind == "final":
            self._draw_final_scene(canvas, t)
        else:
            self._draw_waterfall_scene(canvas, t)
        # 이야기 문장
        if t < STATS_T:
            for i, (start, line) in enumerate(self.lines):
                if t > start:
                    a = clamp((t - start) / 0.8, 0, 1)
                    y = 222 + i * 14 - 28
                    text(canvas, line, (w // 2, y + int((1 - a) * 6)), lerp_color((26, 30, 60), (240, 236, 250), a),
                         11, "center", shadow=True)
        else:
            self._draw_stats(canvas, t - STATS_T)
        # 처음 페이드 인
        if t < 1.2:
            fl = _opaque((w, h))
            fl.fill((255, 250, 240))
            fl.set_alpha(int(255 * (1 - t / 1.2)))
            canvas.blit(fl, (0, 0))
        draw_cursor(canvas, self.mouse)

    def _draw_final_scene(self, canvas, t: float) -> None:
        """세계수 + 오로라 + 별의 강이 되어 오르는 천해왕."""
        w, h = canvas.get_size()
        for band, (col, y0) in enumerate((((90, 255, 180), 40), ((150, 120, 255), 64))):
            for x in range(0, w, 2):
                y = y0 + 10 * math.sin(x * 0.02 + t * 0.4 + band)
                c = lerp_color((4, 10, 30), col, 0.35 + 0.15 * math.sin(x * 0.07 + t))
                canvas.fill(c, (x, int(y), 2, 16))
        canvas.fill((14, 30, 40), (0, 200, w, h - 200))
        bark, leaf = (40, 30, 26), (20, 50, 40)
        for i in range(9):
            a = i / 9 * math.pi
            pygame.draw.circle(canvas, leaf, (int(240 + math.cos(a) * 190), int(30 - math.sin(a) * 6)), 50)
        pygame.draw.polygon(canvas, bark, [(196, 200), (220, 30), (260, 30), (284, 200)])
        for s in (-1, 1):
            pygame.draw.lines(canvas, bark, False, [(240 + s * 40, 190), (240 + s * 110, 186), (240 + s * 200, 204)], 12)
        pygame.draw.ellipse(canvas, (120, 220, 170), (180, 196, 120, 12))
        self._draw_dragon(canvas, t, body=((80, 120, 255), (40, 60, 160)), belly=(255, 230, 140), mane=(200, 230, 255),
                          head=(110, 150, 255))

    def _draw_waterfall_scene(self, canvas, t: float) -> None:
        w, h = canvas.get_size()
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

    def _draw_dragon(self, canvas, t: float, body=((210, 40, 40), (150, 20, 30)), belly=(255, 210, 110),
                     mane=(255, 170, 40), head=(230, 50, 40)) -> None:
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
            col = lerp_color(body[0], body[1], i / segs)
            pygame.draw.circle(canvas, col, (int(x), int(y)), r)
            if i % 2 == 0:
                pygame.draw.circle(canvas, belly, (int(x), int(y) + r // 2), max(1, r // 2))
            if i % 6 == 3:
                # 지느러미 갈기
                pygame.draw.line(canvas, mane, (x, y - r), (x - 4, y - r - 6), 2)
        if pts:
            hx, hy = pts[0]
            pygame.draw.circle(canvas, head, (int(hx), int(hy)), 11)
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
        if self.kind == "final":
            self._draw_final_stats(canvas, t)
            return
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

    def _draw_final_stats(self, canvas, t: float) -> None:
        """두 대륙 합산 통계."""
        w = canvas.get_width()
        save = self.game.save
        d, st = save.data, save.data["stats"]
        from src.save.save_game import all_fish, spot_continent
        caught = {"sharmion": 0, "eldrasion": 0}
        for f in all_fish():
            e = d["dex"].get(f["id"])
            if e:
                caught[spot_continent(f["spot"])] += e.get("count", 0)
        sh_got, sh_tot = save.continent_dex("sharmion")
        el_got, el_tot = save.continent_dex("eldrasion")
        panel = pygame.Rect(w // 2 - 160, 66, 320, 132)
        ui.panel(canvas, panel)
        text(canvas, "샤르미온", (panel.x + 170, panel.y + 12), (160, 220, 150), 11, "center")
        text(canvas, "엘드라시온", (panel.x + 260, panel.y + 12), (200, 180, 255), 11, "center")
        rows = [("포획", f"{caught['sharmion']}마리", f"{caught['eldrasion']}마리"),
                ("도감", f"{sh_got}/{sh_tot}", f"{el_got}/{el_tot}"),
                ("S랭크", f"{st['s_ranks'] - st.get('s_ranks_eldra', 0)}번", f"{st.get('s_ranks_eldra', 0)}번")]
        for i, (k, a, b) in enumerate(rows):
            if t > 0.3 + i * 0.25:
                y = panel.y + 30 + i * 16
                text(canvas, k, (panel.x + 14, y), ui.DIM, 11, "midleft")
                text(canvas, a, (panel.x + 170, y), ui.ACCENT, 11, "center")
                text(canvas, b, (panel.x + 260, y), ui.ACCENT, 11, "center")
        total = [("플레이 시간", ui.time_text(d["playtime"])), ("퍼펙트", f"{st['perfects']}번"),
                 ("번 돈", ui.money_text(st["earned"])), ("보물 도감", f"{len(d['treasure_dex'])}/16")]
        for i, (k, v) in enumerate(total):
            if t > 1.1 + i * 0.2:
                y = panel.y + 84 + (i // 2) * 16
                x = panel.x + 14 + (i % 2) * 160
                text(canvas, k, (x, y), ui.DIM, 11, "midleft")
                text(canvas, v, (x + 146, y), ui.ACCENT, 11, "midright")
        if t > 2.0:
            text(canvas, "두 대륙의 모든 전설을 낚았습니다. 고마워요!", (w // 2, 212), (240, 236, 250), 11, "center")
            text(canvas, "엔딩 후에도 계속 낚시를 즐길 수 있어요.", (w // 2, 228), ui.DIM, 11, "center")
        if t > 1.5 and int(t * 2) % 2 == 0:
            text(canvas, "클릭해서 계속", (w // 2, 250), (170, 180, 200), 11, "center")
