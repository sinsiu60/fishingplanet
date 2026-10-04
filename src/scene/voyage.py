"""'등용' 엔딩 뒤: 엘드라시온의 소문(편지) → 원양 범선 출항 → 새 대륙 도착. 끝나면 대륙 해금 + 습지로 이동."""
import math
import random

import pygame

from src.render.screen import opaque as _opaque

from src.core.config import load_json
from src.core.mathutil import clamp, lerp, lerp_color
from src.scene.base import Scene
from src.ui.fight_fx import big_text
from src.ui.hud import draw_cursor, text

LETTER = [
    "낚시꾼에게.",
    "용문 폭포의 전설을 낚았다는 소문이 바다 건너까지 닿았소.",
    "동쪽 바다 끝에는 고대의 마력이 흐르는 대륙이 있다오.",
    "은빛 갈대, 수정 동굴, 하늘에 뜬 섬, 불의 바다, 오로라의 얼음...",
    "그리고 세계수 뿌리 샘에는 하늘과 바다의 왕이 산다지.",
    "범선 한 척을 항구에 대 두었소. 그대를 기다리겠소.",
]
T_LETTER, T_SAIL, T_ARRIVE, T_END = 0.0, 7.0, 13.0, 17.0


class VoyageScene(Scene):
    UI_FRAME = True

    def __init__(self, game, fishing, skip_letter: bool = False):
        """skip_letter: 스토리 C3-04(할아버지의 편지)가 '엘드라시온의 소문' 편지를 대신함 → 출항 컷신부터."""
        super().__init__(game)
        self.fishing = fishing
        self.t = T_SAIL if skip_letter else 0.0
        self.mouse = (0, 0)
        self.done = False
        self.cont = next(c["name"] for c in load_json("continents.json")["continents"] if c["id"] == "eldrasion")
        rnd = random.Random(5)
        self.gulls = [(rnd.uniform(0, 480), rnd.uniform(30, 90), rnd.uniform(0, 6)) for _ in range(5)]
        self.stars = [(rnd.uniform(0, 480), rnd.uniform(0, 120)) for _ in range(60)]
        game.sfx.stop_all()
        game.sfx.loop("amb_bed_ocean", True, 0.5)

    def handle_action(self, a) -> None:
        if a.name == "primary" and self.t > 0.8:
            # 다음 장면으로 건너뛰기
            for at in (T_SAIL, T_ARRIVE, T_END):
                if self.t < at:
                    self.t = at
                    return
            self._finish()

    def update(self, dt: float) -> None:
        prev = self.t
        self.t += dt
        self.mouse = self.ui_pointer()
        self.game.adaptive.set_context("eldrasion", None)  # 새 대륙 테마
        self.game.adaptive.set("menu")
        if prev < T_SAIL <= self.t:
            self.game.sfx.play("sfx_cast_swing", 0.8)  # 돛이 바람을 받는 휙 (예전 'whoosh'는 없는 소리였음)
            self.game.sfx.play("amb_wave_crash", 0.6)
        if prev < T_ARRIVE <= self.t:
            self.game.sfx.play("sfx_chord_legend", 0.8)
        if self.t >= T_END + 3.0:
            self._finish()

    def _finish(self) -> None:
        if self.done:
            return
        self.done = True
        save = self.game.save
        save.unlock_continent("eldrasion")
        self.game.sfx.loop("amb_bed_ocean", False)
        if self in self.game.scenes.stack:
            self.game.scenes.stack.remove(self)
        self.fishing.travel("marsh")
        self.fishing.toasts.show(f"{self.cont}에 도착했다! (부적 칸 +1, 새 상점 장비)", (220, 200, 255), 4.0, 11)
        from src.story import story
        if story.active(save):   # 스토리: 아스테라 항구 첫 도착 (C4-01) — 파노라마 → 자막 → 휴대폰 '전파 없음'
            from src.scene.village import VillageScene
            self.game.scenes.push(VillageScene(self.game, self.fishing, "eldrasion"))
        self.game.fade_in(1.0)
        self.game.save_now()

    # ── 그리기 ──
    def draw(self, canvas) -> None:
        if self.game.screen.ui_rect.size != canvas.get_size():
            canvas.fill((0, 0, 0))  # 모바일: 컷신은 가운데 16:9 (남는 곳은 검게)
        canvas = self.ui_canvas(canvas)
        t = self.t
        if t < T_SAIL:
            self._draw_letter(canvas, t)
        elif t < T_ARRIVE:
            self._draw_sail(canvas, t - T_SAIL)
        else:
            self._draw_arrive(canvas, t - T_ARRIVE)
        # 장면 사이 페이드
        for at in (T_SAIL, T_ARRIVE):
            d = abs(t - at)
            if d < 0.5:
                fl = _opaque(canvas.get_size())
                fl.fill((0, 0, 0))
                fl.set_alpha(int(255 * (1 - d / 0.5)))
                canvas.blit(fl, (0, 0))
        if int(t * 2) % 2 == 0 and t > 1.0:
            text(canvas, "클릭: 넘기기", (470, 262), (150, 150, 170), 11, "midright")
        draw_cursor(canvas, self.mouse)

    def _draw_letter(self, canvas, t: float) -> None:
        w, h = canvas.get_size()
        canvas.fill((20, 16, 14))
        paper = pygame.Rect(70, 24, 340, 222)
        canvas.fill((60, 46, 30), paper.move(3, 3))
        canvas.fill((232, 214, 176), paper)
        pygame.draw.rect(canvas, (170, 140, 100), paper, 2)
        text(canvas, f"{self.cont}의 소문", (w // 2, paper.y + 18), (110, 60, 40), 16, "center")
        for i, line in enumerate(LETTER):
            a = clamp((t - 0.6 - i * 0.9) / 0.6, 0, 1)
            if a > 0:
                col = lerp_color((232, 214, 176), (60, 40, 30), a)
                text(canvas, line, (paper.x + 16, paper.y + 46 + i * 24), col, 11, "midleft")
        # 밀랍 봉인
        pygame.draw.circle(canvas, (150, 40, 40), (paper.right - 30, paper.bottom - 26), 12)
        pygame.draw.circle(canvas, (190, 70, 60), (paper.right - 30, paper.bottom - 26), 8, 1)

    def _draw_sail(self, canvas, t: float) -> None:
        """새벽 바다 위로 범선이 오른쪽(동쪽)으로 떠난다."""
        w, h = canvas.get_size()
        hz = 150
        k = clamp(t / 6.0, 0, 1)
        for y in range(0, hz, 3):
            canvas.fill(lerp_color((40, 50, 100), (250, 180, 140), y / hz), (0, y, w, 3))
        pygame.draw.circle(canvas, (255, 230, 170), (380, hz), 26)
        canvas.fill((40, 70, 120), (0, hz, w, h - hz))
        for i in range(24):
            yy = hz + 4 + i * 5
            off = (t * (20 + i * 3) + i * 37) % 60
            canvas.fill((90, 130, 180), (int(off + (i * 53) % 400), yy, 18, 1))
        pygame.draw.polygon(canvas, (30, 40, 60), [(0, hz), (0, hz - 40), (40, hz - 30), (90, hz)])  # 떠나는 항구
        # 범선
        sx = lerp(110, 520, k * k)
        sy = hz + 14 + math.sin(t * 2) * 2
        sc = lerp(1.0, 0.5, k)
        hull = [(sx - 40 * sc, sy), (sx + 44 * sc, sy), (sx + 30 * sc, sy + 14 * sc), (sx - 30 * sc, sy + 14 * sc)]
        pygame.draw.polygon(canvas, (70, 44, 30), hull)
        for mx, mh in ((-14, 62), (14, 52)):
            x = sx + mx * sc
            pygame.draw.line(canvas, (60, 40, 30), (x, sy), (x, sy - mh * sc), 2)
            pygame.draw.polygon(canvas, (240, 236, 220), [(x + 2, sy - mh * sc + 4), (x + 24 * sc, sy - mh * sc * 0.55),
                                                         (x + 2, sy - 8 * sc)])
        pygame.draw.polygon(canvas, (200, 60, 60), [(sx - 14 * sc, sy - 62 * sc), (sx - 4 * sc, sy - 58 * sc),
                                                   (sx - 14 * sc, sy - 54 * sc)])
        for gx, gy, ph in self.gulls:
            x = (gx + t * 30) % w
            wing = math.sin(t * 6 + ph) * 3
            pygame.draw.lines(canvas, (240, 240, 250), False, [(x - 5, gy + wing), (x, gy), (x + 5, gy + wing)], 1)
        a = clamp((t - 1.0) / 1.0, 0, 1)
        text(canvas, "바다 건너, 마력이 흐르는 대륙으로...", (w // 2, 236),
             lerp_color((40, 70, 120), (240, 236, 250), a), 11, "center")

    def _draw_arrive(self, canvas, t: float) -> None:
        """밤하늘의 오로라 아래 새 대륙의 실루엣과 이름."""
        w, h = canvas.get_size()
        for y in range(0, h, 3):
            canvas.fill(lerp_color((8, 10, 30), (40, 30, 70), y / h), (0, y, w, 3))
        for x, y in self.stars:
            canvas.fill((220, 220, 255), (int(x), int(y), 1, 1))
        for band, col in enumerate(((90, 255, 180), (150, 120, 255))):
            for x in range(0, w, 2):
                y = 40 + band * 22 + 10 * math.sin(x * 0.02 + t * 0.5 + band)
                c = lerp_color((8, 10, 30), col, 0.3 + 0.15 * math.sin(x * 0.06 + t))
                canvas.fill(c, (x, int(y), 2, 14))
        land = [(0, 190), (60, 160), (120, 172), (170, 130), (210, 150), (260, 110), (300, 150), (360, 140),
                (420, 170), (480, 160), (480, 270), (0, 270)]
        pygame.draw.polygon(canvas, (30, 26, 50), land)
        pygame.draw.circle(canvas, (40, 70, 60), (260, 100), 28)  # 멀리 세계수
        canvas.fill((26, 30, 60), (0, 210, w, h - 210))
        pop = 1.0 + 0.5 * math.exp(-t * 4) * math.cos(t * 14)
        big_text(canvas, self.cont, (w // 2, 120), (230, 210, 255), 2.8 * pop, outline=True)
        if t > 0.8:
            text(canvas, "새 대륙이 열렸습니다", (w // 2, 150), (240, 236, 250), 11, "center")
        if t > 1.6:
            text(canvas, "지도(M) 위쪽 화살표로 두 대륙을 오갈 수 있어요", (w // 2, 168), (190, 180, 220), 11, "center")
