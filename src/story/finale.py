"""C5-05 선택 (오르시엘 포획 연출 직후, 기존 최종 엔딩 직전) · E-01 에필로그 (기존 최종 엔딩 직후 1회).

STORY.md 원문 그대로: 자막·말풍선·제목은 data/story/scenes.json(STORY.md 에서 읽은 것)에서만 가져온다.
선택은 건너뛰기 없음. 어느 쪽이든 도감·포획 기록·업적은 이미 같게 처리돼 있다 (포획 때 기록됨).
"""
import math
import random
import time

import pygame

from src.render.fish_draw import draw_fish_fit
from src.scene.base import Scene
from src.story import story
from src.story import ui as sui
from src.ui import widgets as ui
from src.ui.hud import draw_cursor, text


def _c(h: str) -> tuple:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


class ChoiceScene(Scene):
    """C5-05: 세계수 뿌리 샘 배경 + 뜰채 안 오르시엘 → 자막 → [ 놓아준다 ] [ 어탁으로 남긴다 ]."""

    def __init__(self, game, fish: dict, size: float, world=None, on_done=None):
        super().__init__(game)
        self.fish, self.size, self.world, self.on_done = fish, size, world, on_done
        self.sc = story.scene("C5-05")
        self.t = 0.0
        self.mouse = (0, 0)
        self.choice = None
        self.ct = 0.0
        game.adaptive.stop()          # 음악 없음
        game.sfx.loop("st_spring", True, 0.35)   # 샘물 소리
        w = game.screen.canvas.get_width()
        h = game.screen.canvas.get_height()
        self.btns = [ui.Button((w // 2 - 128, h - 70, 120, 20), f"[ {self.sc['choices'][0]} ]", lambda: self._pick("release")),
                     ui.Button((w // 2 + 8, h - 70, 120, 20), f"[ {self.sc['choices'][1]} ]", lambda: self._pick("record"))]

    def _pick(self, which: str) -> None:
        if self.choice:
            return
        self.game.sfx.play("ui_click")
        self.choice = which
        self.ct = 0.0
        if which == "record":
            self.game.sfx.play("st_paper", 0.6)

    def _finish(self) -> None:
        if getattr(self, "replay", False):   # 추억: 기록은 그대로
            self.game.sfx.loop("st_spring", False)
            if self in self.game.scenes.stack:
                self.game.scenes.stack.remove(self)
            return
        save = self.game.save
        st = story.state(save)
        if self.choice == "release":
            story.add_journal(save, "J13A")
        else:
            story.add_journal(save, "J13B")
            from src.render.fish_print import print_kind
            save.data.setdefault("prints", {})[self.fish["id"]] = {
                "size": round(self.size, 1), "date": time.strftime("%Y.%m.%d"), "spot": "세계수 뿌리 샘",
                "season": None, "kind": print_kind(self.fish, 5)}   # 금색 먹 어탁 자동 생성 (비용 없음)
        st["true_end_choice"] = self.choice
        story.complete(self.game, "C5-05")
        self.game.sfx.loop("st_spring", False)
        if self in self.game.scenes.stack:
            self.game.scenes.stack.remove(self)
        if self.on_done:
            self.on_done()

    def handle_action(self, a) -> None:
        if a.name == "primary" and self.t >= 3.0 and not self.choice:
            for b in self.btns:
                if b.click(a.pos):
                    return

    def update(self, dt: float) -> None:
        self.t += dt
        self.mouse = self.game.input.pointer
        if self.choice:
            self.ct += dt
            end = 6.5 if self.choice == "release" else 5.5
            if self.ct >= end:
                self._finish()

    def draw(self, canvas) -> None:
        w, h = canvas.get_size()
        if self.world is not None:
            canvas.blit(self.world, (0, 0))
        else:
            canvas.fill((20, 40, 44))
        cx, cy = w // 2, h // 2 + 10
        subs = self.sc["subs"]
        if self.choice == "release":
            k = min(1.0, self.ct / 4.0)
            if k < 1.0:   # 뜰채를 물에 담그자 천천히 헤엄쳐 깊은 곳으로
                fw = int(120 * (1 - 0.6 * k))
                surf = pygame.Surface((fw + 4, fw // 2 + 4), pygame.SRCALPHA)
                draw_fish_fit(surf, (2, 2, fw, fw // 2), self.fish, 150)
                surf.set_alpha(int(255 * (1 - k)))
                canvas.blit(surf, (cx - fw // 2 + int(k * 40), cy - fw // 4 + int(k * 60)))
            r = int(10 + 60 * k)   # 수면에 금빛 물결 하나
            pygame.draw.ellipse(canvas, (255, 214, 110), (cx - r, cy + 40 - r // 4, r * 2, r // 2), 1)
            if self.ct >= 4.0:
                sui.subtitle(canvas, subs[1], min(1.0, (self.ct - 4.0) / 0.3, (6.5 - self.ct) / 0.3))
            return
        if self.choice == "record":   # 종이 위에 금색 먹 어탁이 찍히는 연출
            from src.render.fish_print import make
            pr = make(self.fish, {"size": round(self.size, 1), "date": time.strftime("%Y.%m.%d"), "spot": "세계수 뿌리 샘",
                                  "kind": "legend"}, 260, 140)
            k = min(1.0, self.ct / 3.0)
            img = pr.copy()
            img.set_alpha(int(255 * k))
            canvas.fill((10, 12, 14), (cx - 134, cy - 84, 268, 148))
            canvas.blit(img, (cx - 130, cy - 80))
            if self.ct >= 3.0:
                sui.subtitle(canvas, subs[2], min(1.0, (self.ct - 3.0) / 0.3, (5.5 - self.ct) / 0.3))
            return
        # 뜰채 안의 오르시엘 (전설 포획 카드가 닫힌 직후)
        pygame.draw.arc(canvas, (210, 200, 180), (cx - 80, cy - 40, 160, 90), math.pi, math.tau, 2)
        for i in range(-70, 71, 12):
            pygame.draw.line(canvas, (190, 180, 160), (cx + i, cy + 4), (cx + i * 0.6, cy + 46), 1)
        pygame.draw.line(canvas, (150, 120, 80), (cx + 80, cy + 4), (cx + 170, cy - 60), 3)
        draw_fish_fit(canvas, (cx - 70, cy - 30, 140, 56), self.fish, 150)
        if self.t >= 1.0:
            sui.subtitle(canvas, subs[0], min(1.0, (self.t - 1.0) / 0.3))
        if self.t >= 3.0:
            for b in self.btns:
                b.draw(canvas, self.mouse)
        draw_cursor(canvas, self.mouse)


def draw_sunset_thumb(w: int = 60, h: int = 40) -> pygame.Surface:
    """동네 저수지 노을 풍경 썸네일 (코드로 그림, 60x40)."""
    s = pygame.Surface((w, h))
    for y in range(h // 2):
        k = y / (h // 2)
        s.fill((int(250 - 60 * k), int(150 + 30 * k), int(110 + 40 * k)), (0, y, w, 1))
    pygame.draw.circle(s, (255, 220, 150), (w * 2 // 3, h // 2 - 2), 5)
    pygame.draw.polygon(s, (80, 70, 90), [(0, h // 2), (12, h // 2 - 7), (26, h // 2 - 2), (40, h // 2 - 8), (w, h // 2)])
    s.fill((180, 120, 110), (0, h // 2, w, h - h // 2))
    for i in range(4):
        s.fill((255, 210, 160), (w * 2 // 3 - 6 + i, h // 2 + 3 + i * 3, 12 - i * 2, 1))
    return s


class EpilogueScene(Scene):
    """E-01: (마을 위) 자막 → 휴대폰 M7(탭 대기) → 사진 전송 → 서연 답장 → 페이드 → 동네 저수지 노을 (백 노인 실루엣, 찌 2개)
    → 말풍선 2개 → 자막 → 검은 화면 제목 4초 → 마을 자유 플레이."""

    def __init__(self, game, village, replay: bool = False):
        super().__init__(game)
        self.village = village
        self.replay = replay
        self.sc = story.scene("E-01")
        self.msg = story.load_json("story/phone.json")["messages"]["M7"]
        q = self.sc["all_quoted"]
        self.reply = next(x for x in q if x.startswith("…부럽다"))
        self.title, self.title_sub = q[-2], q[-1]
        self.subs = self.sc["subs"]   # [돌아왔다, 말풍선1, 말풍선2, 오늘도 물은 반짝였다]
        self.step = 0
        self.t = 0.0
        self.st = 0.0
        self.mouse = (0, 0)
        self.thumb = draw_sunset_thumb()
        game.adaptive.set_context("sharmion", None)
        game.adaptive.set("menu")

    # 단계: 0 자막(3초) · 1 휴대폰(탭 대기) · 2 사진 보냄(1.6초) · 3 답장(2.5초) · 4 페이드(0.8) · 5 노을+말풍선1(3.5)
    #       6 말풍선2(3.5) · 7 자막(3.0) · 8 제목(4.0) · 9 끝
    DUR = {0: 3.0, 2: 1.6, 3: 2.5, 4: 0.8, 5: 3.5, 6: 3.5, 7: 3.0, 8: 4.0}

    def _go(self, step: int) -> None:
        self.step, self.st = step, 0.0
        sfx = self.game.sfx
        if step == 1:
            sfx.play("st_vibrate", 0.5)
            self.game.haptics.vibrate("phone")
        elif step == 2:
            sfx.play("st_photo", 0.5)
        elif step == 5:
            sfx.loop("amb_bed_ocean", False)
            sfx.loop("st_spring", True, 0.25)   # 잔잔한 물소리
        elif step == 8:
            sfx.loop("st_spring", False)
            self.game.adaptive.set_context("sharmion", None)
        elif step == 9:
            if not self.replay:
                story.complete(self.game, "E-01")
            if self in self.game.scenes.stack:
                self.game.scenes.stack.remove(self)
            self.game.fade_in(0.8)

    def handle_action(self, a) -> None:
        if a.name != "primary":
            return
        if self.step == 1:   # 휴대폰 M7 은 탭할 때까지
            self._go(2)
        elif sui.skip_rect(self.game.screen.canvas).collidepoint(a.pos):
            self._go(9)

    def update(self, dt: float) -> None:
        self.t += dt
        self.st += dt
        self.mouse = self.game.input.pointer
        if self.village is not None:
            self.village.t += dt
        d = self.DUR.get(self.step)
        if d is not None and self.st >= d:
            self._go(self.step + 1 if self.step != 0 else 1)

    def _draw_sunset(self, canvas) -> None:
        w, h = canvas.get_size()
        hz = int(h * 0.48)
        for y in range(0, hz, 2):
            k = y / hz
            canvas.fill((int(240 - 70 * k), int(130 + 40 * k), int(100 + 50 * k)), (0, y, w, 2))
        pygame.draw.circle(canvas, (255, 214, 150), (w * 2 // 3, hz - 10), 18)
        pygame.draw.polygon(canvas, (86, 70, 92), [(0, hz), (w * 0.2, hz - 26), (w * 0.45, hz - 8), (w * 0.7, hz - 30), (w, hz)])
        for y in range(hz, h, 2):
            k = (y - hz) / (h - hz)
            canvas.fill((int(176 - 90 * k), int(110 - 50 * k), int(110 - 30 * k)), (0, y, w, 2))
        rnd = random.Random(4)
        for i in range(40):   # 윤슬
            x, y = w * 2 // 3 - 50 + rnd.randrange(100), hz + 4 + rnd.randrange(h - hz - 10)
            if math.sin(self.t * 3 + i) > 0.3:
                canvas.fill((255, 220, 170), (x, y, 3, 1))
        for bx in (w // 2 - 20, w // 2 + 40):   # 두 개의 찌
            by = hz + 40 + int(math.sin(self.t * 2 + bx) * 1.5)
            pygame.draw.ellipse(canvas, (230, 70, 60), (bx - 2, by - 5, 5, 6))
            canvas.fill((245, 245, 240), (bx - 2, by, 5, 2))
        sil = _c("#2A1E1A")   # 왼쪽에 나란히 앉은 백 노인의 실루엣 (삿갓)
        x0, y0 = 70, h - 30
        pygame.draw.polygon(canvas, sil, [(x0 - 38, y0 - 70), (x0, y0 - 98), (x0 + 38, y0 - 70)])
        pygame.draw.ellipse(canvas, sil, (x0 - 14, y0 - 76, 28, 26))
        pygame.draw.polygon(canvas, sil, [(x0 - 34, h), (x0 - 26, y0 - 50), (x0 + 26, y0 - 50), (x0 + 40, h)])
        pygame.draw.line(canvas, sil, (x0 + 20, y0 - 40), (x0 + 120, y0 - 110), 2)   # 낚싯대

    def _bubble(self, canvas, s: str) -> None:
        """백 노인 말풍선 (초상화 없음)."""
        w, h = canvas.get_size()
        r = pygame.Rect(40, h - 186, 236, 28)
        canvas.fill((250, 246, 236), r)
        pygame.draw.rect(canvas, (60, 50, 40), r, 1)
        pygame.draw.polygon(canvas, (250, 246, 236), [(64, r.bottom - 1), (76, r.bottom - 1), (68, r.bottom + 8)])
        text(canvas, s, (r.x + 8, r.centery), (40, 36, 30), 11, "midleft")

    def draw(self, canvas) -> None:
        w, h = canvas.get_size()
        st = self.step
        if st <= 4:
            if self.village is not None:
                self.village.draw_world(canvas)
            else:
                canvas.fill((40, 60, 80))
            if st == 0:
                sui.subtitle(canvas, self.subs[0], min(1.0, self.st / 0.3, (3.0 - self.st) / 0.3))
            if st >= 1:
                big = st >= 2
                r = sui.draw_phone(canvas, self.msg["from"], self.msg["text"], 1.0)
                if big:   # 휴대폰 창이 커지며 '사진을 보냈습니다' + 작은 사진
                    k = min(1.0, self.st / 0.3) if st == 2 else 1.0
                    R = pygame.Rect(0, 0, int(140 + 80 * k), int(60 + 70 * k))
                    R.bottomright = r.bottomright
                    pygame.draw.rect(canvas, sui.PHONE_BG, R, border_radius=8)
                    pygame.draw.rect(canvas, (70, 70, 80), R, 1, border_radius=8)
                    text(canvas, self.msg["from"], (R.x + 10, R.y + 12), sui.PHONE_FROM, 11, "midleft")
                    text(canvas, self.msg["text"], (R.x + 10, R.y + 28), (255, 255, 255), 11, "midleft")
                    text(canvas, "사진을 보냈습니다", (R.right - 10, R.y + 46), (170, 170, 180), 11, "midright")
                    canvas.blit(self.thumb, (R.right - 70, R.y + 56))
                    if st >= 3:
                        text(canvas, self.msg["from"], (R.x + 10, R.bottom - 14), sui.PHONE_FROM, 11, "midleft")
                        text(canvas, self.reply, (R.x + 40, R.bottom - 14), (255, 255, 255), 11, "midleft")
            if st == 4:
                s = pygame.Surface((w, h))
                s.set_alpha(int(255 * min(1.0, self.st / 0.8)))
                canvas.blit(s, (0, 0))
        elif st <= 7:
            self._draw_sunset(canvas)
            if st == 5 and self.st < 0.6:
                s = pygame.Surface((w, h))
                s.set_alpha(int(255 * (1 - self.st / 0.6)))
                canvas.blit(s, (0, 0))
            if st == 5:
                self._bubble(canvas, self.subs[1])
            elif st == 6:
                self._bubble(canvas, self.subs[2])
            else:
                sui.subtitle(canvas, self.subs[3], min(1.0, self.st / 0.3, (3.0 - self.st) / 0.3))
        else:
            canvas.fill((0, 0, 0))
            k = min(1.0, self.st / 0.6, (4.0 - self.st) / 0.6)
            col = tuple(int(240 * k) for _ in range(3))
            text(canvas, self.title, (w // 2, h // 2 - 8), col, 16, "center")
            text(canvas, self.title_sub, (w // 2, h // 2 + 14), tuple(int(170 * k) for _ in range(3)), 11, "center")
        if st != 1:
            sui.draw_skip(canvas, self.mouse)
        draw_cursor(canvas, self.mouse)
