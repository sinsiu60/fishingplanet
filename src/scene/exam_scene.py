"""백 노인의 시험 화면 (BAEK_EXAM.md 🅱-3 · 🅱-6, DESIGN.md 49-3).

백 노인 오두막 메뉴 [시험] · 엘라 공방 [백 노인의 편지] (T6 부터) 에서 여는 패널 — 상점 패널처럼 건물 화면 위 (host = InteriorScene,
초상화는 왼쪽 창에 계속 보이고 그 아래 한 줄 대사).
왼쪽 = 다음 시험 티어 · 시험 물고기 실루엣 (도감에 있으면 이름, 아니면 '???') · 합격 조건 · 빌려주는 장비 · 시험 장소.
오른쪽 = 응시 자격 ①②③ 막대 (n / 필요, 다 차면 초록 체크). 아래 = [시험 보기] / [시험 찌 반납] · [훈련 수조에서 연습] (3번 불합격 뒤).
"""
import math

import pygame

from src.save import exam
from src.scene.base import Scene
from src.ui import shop_ui as su
from src.ui import widgets as ui
from src.ui.hud import draw_cursor, text, wrap_text

GREEN = (110, 220, 130)


class ExamScene(Scene):
    UI_FRAME = True

    def __init__(self, game, fishing, host, letter: bool = False):
        super().__init__(game)
        self.fishing = fishing
        self.host = host
        self.letter = letter            # 엘라 공방: 백 노인의 편지
        self.save = game.save
        self.mouse = (0, 0)
        self.age = 0.0
        self.frame = pygame.Rect(130, 6, 342, 258)
        fr = self.frame
        self.L = pygame.Rect(fr.x + 6, fr.y + 22, 150, 172)
        self.R = pygame.Rect(fr.x + 160, fr.y + 22, fr.w - 166, 172)
        self.action_btn = ui.Button((fr.x + 6, fr.bottom - 42, 150, 17), "", self._action)
        self.train_btn = ui.Button((fr.x + 160, fr.bottom - 42, fr.w - 166, 17), "훈련 수조에서 연습", self._train)
        self.close_btn = ui.Button((fr.right - 66, fr.bottom - 21, 58, 16), "닫기", self._close)
        self.msg, self.msg_col, self.msg_t = "", ui.TEXT, 0.0
        self._open_line()

    # ── 대사 (host 왼쪽 창) ──
    def _speak(self, key: str, **kw) -> None:
        expr, s = exam.line(key, **kw)
        self.host.expr = expr or "neutral"
        self.host.react_line = (self.host.expr, s, self.host.t)
        self.host._voice_burst(len(s))

    def _open_line(self) -> None:
        st = exam.state(self.save)
        t = exam.next_tier(self.save)
        if self.letter:
            self._speak("letter_open")
            return
        if t is None:
            self._speak("done")
        elif st["active"]:
            self._speak("give")
        elif exam.show_hint(self.save) and not self._waiting():
            self._speak("hint", pattern=exam.pattern_name(exam.show_hint(self.save)))
        elif self._waiting():
            self._speak("wait")
        elif exam.eligible(self.save):
            if exam.ready_first(self.save, t):   # 자격 충족 (처음) — sharp, 그 뒤로는 말없이 패널만
                self._speak("ready")
        else:
            self._speak("short")

    def _waiting(self) -> bool:
        return exam.retry_wait(self.save, self.fishing.clock.day)

    # ── 버튼 ──
    def _state(self) -> tuple[str, bool]:
        t = exam.next_tier(self.save)
        if t is None:
            return "모든 시험 합격", False
        if exam.active(self.save):
            return "시험 찌 반납 (미루기)", True
        if self._waiting():
            return "내일 다시 볼 수 있어요", False
        if not exam.eligible(self.save):
            return "자격이 모자라요", False
        return "시험 보기", True

    def _action(self) -> None:
        label, ok = self._state()
        if not ok:
            return
        if exam.active(self.save):
            exam.postpone(self.save)
            self.game.sfx.play("ui_click")
            self._say("시험 찌를 돌려줬어요 (불합격 아님)", ui.TEXT)
        else:
            exam.give_float(self.save)
            self.game.sfx.play("ui_equip")
            self._speak("give_ella" if self.letter else "give")
            self._say("시험 찌를 받았어요 · 자동으로 끼워져요", ui.GOOD)
            self.game.guide.event("exam_given")
        self.game.save_now()

    def _train(self) -> None:
        pid = exam.show_hint(self.save)
        if pid is None:
            return
        self.game.save_now()
        self.game.scenes.pop()
        self.fishing.start_training(pattern=pid)   # 그 패턴을 골라 둔 채로 (위에 열린 화면은 닫힘)

    def _close(self) -> None:
        self.game.save_now()
        self.game.scenes.pop()
        self.host.shop_closed()

    def _say(self, msg: str, col) -> None:
        self.msg, self.msg_col, self.msg_t = msg, col, 3.0

    # ── 입력 ──
    def handle_action(self, a) -> None:
        if a.name == "back":
            self._close()
            return
        if a.name == "confirm":
            self._action()
            return
        if a.name != "primary":
            return
        for b in self._buttons():
            if b.click(a.pos):
                return

    def _buttons(self) -> list:
        out = [self.action_btn, self.close_btn]
        if exam.show_hint(self.save) and not exam.active(self.save):
            out.append(self.train_btn)
        return out

    def update(self, dt: float) -> None:
        self.age += dt
        self.mouse = self.ui_pointer()
        self.msg_t = max(0.0, self.msg_t - dt)
        self.host.t += dt   # 왼쪽 초상화 깜빡임 · 숨쉬기 (host.update 는 위 화면이 있으면 멈춤)
        self.host.blink_left = max(0.0, self.host.blink_left - dt)
        self.host.blink_t -= dt
        if self.host.blink_t <= 0:
            self.host.blink_left = self.host.c["blink_sec"]
            self.host.blink_t = self.host.rnd.uniform(*self.host.c["blink_every"])

    # ── 그리기 ──
    def draw(self, canvas) -> None:
        self.host.draw_shop_backdrop(canvas)
        canvas = self.ui_canvas(canvas)
        fr = self.frame
        canvas.fill(ui.SHADOW, fr.move(2, 2))
        canvas.fill(su.WIN_BG, fr)
        pygame.draw.rect(canvas, su.BORDER, fr, 1)
        title = "백 노인의 편지" if self.letter else "백 노인의 시험"
        text(canvas, title, (fr.x + 8, fr.y + 10), ui.ACCENT, 16, "midleft")
        p = exam.passed(self.save)
        su.badge(canvas, f"합격 T{p}", (fr.right - 8, fr.y + 10), GREEN if p > 1 else su.GRAY)
        t = exam.next_tier(self.save)
        for r in (self.L, self.R):
            canvas.fill(su.CELL_BG, r)
            pygame.draw.rect(canvas, su.BORDER, r, 1)
        if t is None:
            text(canvas, "모든 시험에 합격했어요", self.L.union(self.R).center, GREEN, 11, "center")
        else:
            self._draw_left(canvas, t)
            self._draw_right(canvas, t)
        self._draw_status(canvas, t)
        label, ok = self._state()
        self.action_btn.label, self.action_btn.enabled = label, ok
        self.action_btn.draw(canvas, self.mouse)
        if self.train_btn in self._buttons():
            self.train_btn.draw(canvas, self.mouse)
        self.close_btn.draw(canvas, self.mouse)
        from src.tutorial import targets as T
        r0 = self.game.screen.ui_rect
        T.mark("exam.quals", self.R.move(r0.x, r0.y))
        T.mark("exam.fish", self.L.move(r0.x, r0.y))
        T.mark("exam.btn", self.action_btn.rect.move(r0.x, r0.y))
        draw_cursor(canvas, self.mouse)

    def _draw_left(self, canvas, t: int) -> None:
        L = self.L
        x = L.x + 6
        su.btext(canvas, f"다음 시험  T{t}", (x, L.y + 9), su.YELLOW, 11, "midleft")
        box = pygame.Rect(L.x + 6, L.y + 18, L.w - 12, 44)
        su.pic_box(canvas, box)
        f = exam.exam_fish(t)
        known = exam.fish_known(self.save, t)
        from src.render.fish_draw import draw_fish_fit
        draw_fish_fit(canvas, box.inflate(-8, -8), f, 70, silhouette=None if known else (8, 8, 14),
                      tail_wag=0.25 * math.sin(self.age * 3))
        name = f["name"] if known else "???"
        if exam.cfg().get("stamina_mult", {}).get(str(t), 1.0) > 1.0:
            name += " (큰 놈)"
        text(canvas, su.fit(name, L.w - 12), (x, L.y + 72), su.RARITY["rare"], 11, "midleft")
        rows = [("합격", exam.pass_text(t), su.WHITE),
                ("장비", f"T{t} 기본 4종 빌려줌", su.WHITE),
                ("장소", ", ".join(self._spot_names(t - 1)), su.WHITE)]
        y = L.y + 88
        for lab, val, col in rows:
            text(canvas, lab, (x, y), su.GRAY, 11, "midleft")
            for ln in wrap_text(val, L.w - 44)[:2]:
                text(canvas, ln, (x + 30, y), col, 11, "midleft")
                y += 13
            y += 2
        text(canvas, "비늘석 · 부적 · 소모품 효과 없음", (x, L.bottom - 9), su.SUB, 11, "midleft")

    def _spot_names(self, tier: int) -> list[str]:
        return exam.spot_names(tier)

    def _draw_right(self, canvas, t: int) -> None:
        R = self.R
        x = R.x + 6
        su.btext(canvas, "응시 자격", (x, R.y + 9), su.YELLOW, 11, "midleft")
        text(canvas, f"T{t - 1} 낚시터 기준", (R.right - 6, R.y + 9), su.GRAY, 11, "midright")
        marks = ("①", "②", "③")
        y = R.y + 26
        for i, q in enumerate(exam.quals(self.save)):
            text(canvas, f"{marks[i]} {q['label']}", (x, y), su.WHITE, 11, "midleft")
            num = f"{min(q['have'], q['need'])} / {q['need']}" if not q.get("legend") else "전설 포획"
            text(canvas, num, (R.right - 18, y), GREEN if q["ok"] else su.WHITE, 11, "midright")
            if q["ok"]:
                su.check(canvas, R.right - 14, y, GREEN)
            bar = pygame.Rect(x, y + 8, R.w - 12, 6)
            canvas.fill((24, 28, 44), bar)
            frac = 1.0 if q["ok"] else min(1.0, q["have"] / max(1, q["need"]))
            k = min(1.0, self.age / 0.35)
            canvas.fill(GREEN if q["ok"] else (230, 180, 80), (bar.x + 1, bar.y + 1, int((bar.w - 2) * frac * k), bar.h - 2))
            pygame.draw.rect(canvas, (70, 76, 100), bar, 1)
            sub = {"dex": "전설 빼고 그 물 고기 등록",
                   "stars": "S 랭크 · 대물 · 변이 · 숙련으로 별",
                   "owner": q.get("alt", "")}[q["key"]]
            text(canvas, sub, (x, y + 22), su.GRAY, 11, "midleft")
            y += 42
        if len(exam.quals(self.save)) < 3:
            text(canvas, "③ 그 물의 주인 — T3 시험부터", (x, y), su.SUB, 11, "midleft")

    def _draw_status(self, canvas, t) -> None:
        fr = self.frame
        y = self.L.bottom + 10
        if self.msg_t > 0:
            s, col = self.msg, self.msg_col
        elif t is None:
            s, col = "백 노인: 더 가르칠 게 없네.", su.SUB
        elif exam.active(self.save):
            s, col = f"시험 찌를 낀 채 {', '.join(self._spot_names(t - 1))}에서 던지면 3초 뒤 시험 물고기", su.YELLOW
        elif self._waiting():
            s, col = "불합격 — 게임 하루가 지나면 다시 (모닥불에서 쉬어도 돼요)", su.SUB
        elif exam.fails(self.save):
            s, col = f"불합격 {exam.fails(self.save)}번 · 비용은 없어요", su.SUB
        elif exam.eligible(self.save):
            s, col = "자격을 다 채웠어요 — [시험 보기]로 시험 찌를 받아요", GREEN
        else:
            s, col = "자격을 다 채우면 시험을 볼 수 있어요", su.SUB
        text(canvas, su.fit(s, fr.w - 12), (fr.x + 6, y), col, 11, "midleft")


class ExamNoticeScene(Scene):
    """옛 세이브 안내 (🅱-5): 가진 장비 최고 티어까지 자동 합격 — 백 노인 초상화 (smile) + 한 줄, 한 번만."""
    UI_FRAME = True

    def __init__(self, game):
        super().__init__(game)
        self.mouse = (-100, -100)
        self.t = 0.0
        self.tier = exam.passed(game.save)
        self.expr, self.line = exam.line("legacy", tier=self.tier)
        self.button = ui.Button((240 - 50, 206, 100, 22), "확인", self._close, size=13)

    def _close(self) -> None:
        exam.mark_notice(self.game.save)
        self.game.save.save()
        self.game.scenes.pop()

    def handle_action(self, a) -> None:
        if a.name in ("back", "confirm"):
            self._close()
        elif a.name == "primary" and self.button.click(a.pos):
            self.game.sfx.play("ui_click")

    def update(self, dt: float) -> None:
        self.t += dt
        self.mouse = self.ui_pointer()

    def draw(self, canvas) -> None:
        under = self.scene_below()
        if under is not None:
            under.draw(canvas)
        ui.dim(canvas, 170)
        canvas = self.ui_canvas(canvas)
        ui.panel(canvas, (240 - 170, 40, 340, 196))
        from src.scene.interior import portrait
        blink = (self.t % 4.0) < 0.13
        talk = self.t < 1.6 and int(self.t / 0.09) % 2 == 0
        img = pygame.transform.scale(portrait("baek", self.expr or "smile", blink, talk), (96, 96))
        canvas.blit(img, (240 - 160, 52))
        text(canvas, "백 노인", (240 - 54, 62), (242, 196, 107), 11, "midleft")
        y = 82
        for ln in wrap_text(self.line, 210):
            text(canvas, ln, (240 - 54, y), ui.TEXT, 11, "midleft")
            y += 16
        text(canvas, "장비 구매 · 장착은 합격한 티어까지 — 다음 티어는 백 노인의 시험", (240, 162), ui.DIM, 11, "center")
        tiers = " ".join(exam.ROMAN[i] for i in range(2, self.tier + 1))
        su.btext(canvas, f"합격  {tiers}", (240, 177), GREEN, 11, "center")
        names = [n for t, n in ((4, "물을 아는 자"), (8, "해강의 뒤를 이은 자")) if self.tier >= t]
        if names:
            text(canvas, "  ".join(f"칭호 「{n}」" for n in names), (240, 192), (255, 214, 90), 11, "center")
        self.button.draw(canvas, self.mouse)


class ExamResultScene(Scene):
    """시험 판이 끝난 뒤 (결과 카드를 닫으면): T2 ~ T5 = 백 노인 초상화 + 한 줄 / T6 ~ T8 = 백 노인의 편지 (🅱-4 · 🅱-7).
    합격하면 다음 티어 장비를 살 수 있다는 줄 · 불합격이면 게임 하루 뒤 (3번째부터 놓친 패턴 힌트)."""
    UI_FRAME = True

    def __init__(self, game, fishing, res: dict):
        super().__init__(game)
        self.fishing = fishing
        self.res = res
        self.mouse = (-100, -100)
        self.t = 0.0
        t = res["tier"]
        self.letter = t >= exam.cfg()["letter_from"]
        if res["pass"]:
            key = "pass_2" if t == 2 else "pass_mid"
            game.sfx.play("sfx_rank_s", 0.7)
        else:
            key = "fail"
        hint = exam.show_hint(game.save) if not res["pass"] else None
        self.expr, self.line = exam.line(key)
        self.sub = (f"T{t} 장비 4종을 이제 살 수 있어요" if res["pass"] else
                    f"불합격 {res['fails']}번 — 게임 하루 뒤 다시 (비용 없음)")
        self.titles = res.get("titles") or []
        self.hint = exam.line("hint", pattern=exam.pattern_name(hint))[1] if hint else None
        if self.letter:
            body = exam.line("letter_pass_8" if (res["pass"] and t == 8) else
                             "letter_pass" if res["pass"] else "letter_fail")[1]
            from src.story.story import player_name
            paras = [f"{player_name(game.save)}에게.", "", *wrap_text(body, 250), "", *wrap_text(self.sub, 250),
                     *[f"칭호 「{n}」" for n in self.titles], "", "— 백"]
            self.body = "\n".join(paras)
            game.sfx.play("st_paper", 0.6)
        self.button = ui.Button((240 - 50, 214, 100, 22), "확인", self._close, size=13)

    def _close(self) -> None:
        if self in self.game.scenes.stack:
            self.game.scenes.stack.remove(self)
        self.game.save_now()

    def handle_action(self, a) -> None:
        if self.t < 0.5:
            return
        if a.name in ("back", "confirm") or (self.letter and a.name == "primary"):
            self._close()
        elif a.name == "primary" and self.button.click(a.pos):
            self.game.sfx.play("ui_click")

    def update(self, dt: float) -> None:
        self.t += dt
        self.mouse = self.ui_pointer()

    def draw(self, canvas) -> None:
        under = self.scene_below()
        if under is not None:
            under.draw(canvas)
        if self.letter:
            from src.story.ui import draw_paper
            dim = pygame.Surface(canvas.get_size(), pygame.SRCALPHA)
            dim.fill((0, 0, 0, 150))
            canvas.blit(dim, (0, 0))
            r = draw_paper(canvas, self.body, min(1.0, self.t / 0.3))
            if self.t > 1.0 and int(self.t * 2) % 2:
                text(canvas, "탭하면 닫기" if self.game.input.kind == "touch" else "클릭하면 닫기", (r.centerx, r.bottom + 10),
                     (200, 200, 200), 11, "center")
            return
        ui.dim(canvas, 170)
        canvas = self.ui_canvas(canvas)
        ui.panel(canvas, (240 - 170, 40, 340, 204))
        from src.scene.interior import portrait
        blink = (self.t % 4.0) < 0.13
        talk = self.t < 1.6 and int(self.t / 0.09) % 2 == 0
        img = pygame.transform.scale(portrait("baek", self.expr or "neutral", blink, talk), (96, 96))
        canvas.blit(img, (240 - 160, 52))
        text(canvas, "백 노인", (240 - 54, 62), (242, 196, 107), 11, "midleft")
        y = 82
        for ln in wrap_text(self.line, 210):
            text(canvas, ln, (240 - 54, y), ui.TEXT, 11, "midleft")
            y += 16
        if self.hint:
            for ln in wrap_text(self.hint, 210):
                text(canvas, ln, (240 - 54, y + 4), (255, 214, 140), 11, "midleft")
                y += 16
        col = GREEN if self.res["pass"] else (255, 150, 130)
        su.btext(canvas, ("합격!  " if self.res["pass"] else "불합격  ") + exam.ROMAN[self.res["tier"]], (240, 166), col, 16,
                 "center")
        text(canvas, self.sub, (240, 186), ui.DIM, 11, "center")
        if self.titles:
            text(canvas, "  ".join(f"칭호 「{n}」" for n in self.titles), (240, 200), (255, 214, 90), 11, "center")
        self.button.draw(canvas, self.mouse)
