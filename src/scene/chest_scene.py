"""보물상자 화면 (C): 상자 열기(등급별 연출) · 조각 교환소 · 보유 아이템(장착·사용) · 보물 도감."""
import math
import random

import pygame

from src.render.screen import opaque as _opaque

from src.core.mathutil import clamp, lerp, lerp_color
from src.render.chest import draw_chest, draw_glow, draw_item_icon
from src.render.landing import draw_star
from src.save import treasure as tr
from src.scene.base import Scene
from src.ui import widgets as ui
from src.ui.fight_fx import big_text
from src.ui.hud import draw_cursor, text, wrap_text

TABS = [("open", "상자"), ("exchange", "조각 교환소"), ("items", "보유 아이템"), ("dex", "보물 도감"), ("diary", "어부의 수첩")]
KIND_KO = {"consumable": "소모품", "charm": "부적", "cosmetic": "외형", "rod": "낚싯대", "reel": "릴", "net": "뜰채", "phantom_x": "환상 비늘"}
MAT_KO = {"sharmion": "샤르미온 소재", "eldrasion": "엘드라시온 소재"}
LIST = pygame.Rect(16, 52, 236, 186)
DETAIL = pygame.Rect(260, 52, 204, 186)
ROW_H = 17
# 등급별 연출 길이: (뚜껑이 열리는 시각, 보상 카드가 뜨는 시각)
OPEN_AT = {"common": 0.35, "rare": 0.75, "special": 1.15, "legend": 1.7}
CARD_AT = {"common": 0.65, "rare": 1.05, "special": 1.45, "legend": 2.15}


class ChestScene(Scene):
    UI_FRAME = True

    def open_sound(self):
        """메뉴 소리 (DT10): 어부의 수첩으로 바로 열면 종이 넘기는 소리."""
        return "ui_paper" if TABS[self.tabs.index][0] == "diary" else None

    def __init__(self, game, fishing):
        super().__init__(game)
        self.fishing = fishing
        self.save = game.save
        self.mouse = (0, 0)
        self.age = 0.0
        self.t = 0.0
        self.tabs = ui.Tabs(16, 30, [t[1] for t in TABS], width=80)
        self.sel = 0
        self.scroll = 0
        self.msg, self.msg_col, self.msg_t = "", ui.TEXT, 0.0
        self.close_btn = ui.Button((404, 244, 60, 16), "닫기 (C)", self._close)
        self.action_btn = ui.Button((DETAIL.x + 8, DETAIL.bottom - 22, DETAIL.w - 16, 17), "", self._action)
        self.chooser: dict | None = None  # 모래시계·소라: 시간대/날씨 고르기
        self.choice_btns: list[ui.Button] = []
        self.open_btns = [ui.Button((0, 0, 92, 17), "열기", lambda g=g: self._open(g)) for g in tr.GRADES]
        self.anim: dict | None = None   # 개봉 연출
        self.particles: list[list[float]] = []

    @property
    def kind(self) -> str:
        return TABS[self.tabs.index][0]

    def _say(self, msg: str, col=ui.TEXT) -> None:
        self.msg, self.msg_col, self.msg_t = msg, col, 2.2
        if col == ui.BAD:
            self.game.sfx.play("ui_error")

    def _close(self) -> None:
        if self.anim:
            return
        self.game.save_now()
        self.game.scenes.pop()

    # ── 상자 열기 ──
    def _open(self, grade: str) -> None:
        reward = tr.open_chest(self.save, grade, self.fishing.spot_id)
        if reward is None:
            return
        self.anim = {"grade": grade, "t": 0.0, "reward": reward, "fired": set()}
        d = reward.get("diary")
        if d is not None:  # 낡은 어부의 수첩 (33장 P6) — 중복은 환상 비늘 1개
            self._say("낡은 어부의 수첩 한 장이 끼어 있었다 (수첩 탭)" if not d["dup"] else
                      "또 같은 수첩 한 장… 보라빛 비늘 1개로", (210, 160, 255))
        self.particles.clear()
        # 등급 소리 하나가 처음부터 열리는 순간(OPEN_AT)까지 다 맡는다 (32장 S5):
        # 일반 삐걱→딸깍 / 희귀 상승→차임 / 특별 덜컹→폭발 / 전설 빌드업→0.1초 무음→웅장한 터짐
        self.game.sfx.play(f"sfx_chest_{grade}", 1.0)
        self.game.save_now()

    def _anim_event(self, key: str) -> None:
        a = self.anim
        grade = a["grade"]
        col = tr.grade_info(grade)["color"]
        cx, cy = 240, 150
        sfx = self.game.sfx
        if key == "open":
            n = {"common": 14, "rare": 30, "special": 60, "legend": 110}[grade]
            for i in range(n):
                ang = random.uniform(math.pi * 1.05, math.pi * 1.95) if grade == "common" else i / n * math.tau
                sp = random.uniform(40, 90) * (1 + {"common": 0, "rare": 0.4, "special": 0.9, "legend": 1.5}[grade])
                self.particles.append([cx, cy - 18, math.cos(ang) * sp, math.sin(ang) * sp, random.uniform(0.5, 1.1),
                                       col])
            if grade == "common":
                sfx.play("sfx_coin", 0.5)
            elif grade == "special":
                self.game.screen.shake = (2, 1)
            if grade in ("special", "legend"):
                self.game.haptics.vibrate("perfect" if grade == "special" else "double_perfect")
        elif key == "card":
            self.game.guide.event("chest_opened")   # TG-10
            r = a["reward"]
            if r["type"] == "item" and not r.get("dup"):
                sfx.play("sfx_catch", 0.7)

    def _action(self) -> None:
        if self.kind == "exchange":
            self._exchange()
        elif self.kind == "items":
            self._item_action()

    # ── 보유 아이템: 장착·사용 (src/save/item_use.py — 인벤토리와 같이 씀) ──
    def _item_state(self, it: dict) -> tuple[str, bool]:
        """(버튼 글자, 누를 수 있는지)."""
        from src.save import item_use
        return item_use.item_state(self.save, it)

    def _item_action(self) -> None:
        from src.save import item_use
        items = self._list()
        if not items:
            return
        it = items[min(self.sel, len(items) - 1)]
        label, ok = self._item_state(it)
        if not ok:
            return
        msg, col, options = item_use.use(self.game, it)
        if options:
            self._open_chooser(it["id"], options)
            return
        if msg:
            self._say(msg, col)
        self.game.sfx.play("ui_enhance", 0.8)  # 아이템 사용
        self.game.save_now()

    def _open_chooser(self, iid: str, options: list) -> None:
        self.chooser = {"item": iid}
        w = (DETAIL.w - 16 - 4 * (len(options) - 1)) // len(options)
        self.choice_btns = [ui.Button((DETAIL.x + 8 + i * (w + 4), DETAIL.bottom - 44, w, 17), label,
                                      lambda v=value: self._choose(v)) for i, (label, value) in enumerate(options)]

    def _choose(self, value) -> None:
        from src.save import item_use
        msg, col = item_use.choose(self.game, self.fishing, self.chooser["item"], value)
        self._say(msg, col)
        self.chooser = None
        self.choice_btns = []
        self.game.sfx.play("ui_enhance", 0.8)
        self.game.save_now()

    # ── 교환소 ──
    def _exchange(self) -> None:
        items = self._list()
        if not items:
            return
        it = items[min(self.sel, len(items) - 1)]
        if self.kind != "exchange":
            return
        if it["kind"] == "phantom_x":
            from src.fishing import phantom
            reason = phantom.can_exchange(self.save, it)
            if reason:
                self._say(reason, ui.BAD)
                return
            phantom.exchange(self.save, it)
            self.game.sfx.play("ui_buy")
            self._say(f"{it['name']} 교환!", ui.GOOD)
            self.game.save_now()
            return
        reason = tr.can_exchange(self.save, it["id"])
        if reason:
            self._say(reason, ui.BAD)
            return
        tr.exchange(self.save, it["id"])
        self.game.sfx.play("ui_buy")
        self._say(f"{it['name']} 교환!", ui.GOOD)
        self.game.save_now()

    def _list(self) -> list:
        if self.kind == "exchange":
            out = [i for i in tr.cfg()["items"] if not i.get("reward_only")]
            from src.fishing import phantom
            if phantom.revealed(self.save):
                # 환상 비늘 교환 (33장 P5): 외형·칭호 테두리·특별 상자 (성능 아이템 없음)
                out += [dict(x, grade="special", kind="phantom_x") for x in phantom.exchange_items()]
            return out
        if self.kind == "items":
            items = self.save.data["items"]
            out = [tr.item_info(i) for i in items["owned"]]
            out += [tr.item_info(i) for i, n in items["consumables"].items() if n > 0]
            order = {g: i for i, g in enumerate(tr.GRADES)}
            return sorted(out, key=lambda it: (order[it["grade"]], it["name"]))
        return []

    # ── 입력 ──
    def handle_action(self, act) -> None:
        if self.anim:
            if act.name in ("primary", "confirm", "back"):
                a = self.anim
                if a["t"] < CARD_AT[a["grade"]]:
                    a["t"] = CARD_AT[a["grade"]]  # 건너뛰기
                    if "open" not in a["fired"]:
                        a["fired"].add("open")
                        self._anim_event("open")
                elif a["t"] > CARD_AT[a["grade"]] + 0.3:
                    self.anim = None
            return
        if act.name == "back" or act.is_("menu", "chest"):
            self._close()
        elif act.name == "scroll":
            n = len(self._list())
            self.scroll = max(0, min(max(0, n - LIST.h // ROW_H), self.scroll - act.value))
        elif act.name == "primary":
            m = act.pos
            if self.tabs.click(m):
                self.sel, self.scroll = 0, 0
                self.chooser, self.choice_btns = None, []
                self.game.sfx.play("ui_tab")
                return
            if self.close_btn.click(m):
                return
            if self.chooser:
                for b in self.choice_btns:
                    if b.click(m):
                        return
                self.chooser, self.choice_btns = None, []
            if self.kind == "open":
                for b in self.open_btns:
                    if b.click(m):
                        return
                return
            if self.kind in ("exchange", "items") and self.action_btn.click(m):
                return
            if self.kind == "diary":
                if getattr(self, "story_row", None) is not None and self.story_row.collidepoint(m):
                    from src.story.ui import PaperScene
                    from src.story.story import load_json as _lj
                    self.game.scenes.push(PaperScene(self.game, _lj("story/letters.json")["last_page"], backdrop=self.draw))
                    return
                self.diary_page = getattr(self, "diary_page", 0) + 1  # 클릭하면 다음 장
                self.game.sfx.play("ui_click")
                return
            if self.kind == "dex":
                return
            if LIST.collidepoint(m):
                i = (m[1] - LIST.y) // ROW_H + self.scroll
                if 0 <= i < len(self._list()):
                    self.sel = i
                    self.chooser, self.choice_btns = None, []
                    self.game.sfx.play("ui_click")

    def update(self, dt: float) -> None:
        self.age += dt
        self.t += dt
        self.mouse = self.ui_pointer()
        self.msg_t = max(0.0, self.msg_t - dt)
        for p in self.particles:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[3] += 60 * dt
            p[2] *= 0.97
            p[4] -= dt
        self.particles = [p for p in self.particles if p[4] > 0]
        if self.anim:
            a = self.anim
            a["t"] += dt
            for key, at in (("open", OPEN_AT[a["grade"]]), ("card", CARD_AT[a["grade"]])):
                if a["t"] >= at and key not in a["fired"]:
                    a["fired"].add(key)
                    self._anim_event(key)
            if a["t"] > OPEN_AT[a["grade"]] + 0.25:
                self.game.screen.shake = (0, 0)

    # ── 그리기 ──
    def draw(self, canvas) -> None:
        ui.backdrop(canvas, self.fishing, int(170 * min(1.0, self.age / 0.15)), "chest_scene")
        canvas = self.ui_canvas(canvas)
        ui.panel(canvas, (8, 6, 464, 258))
        text(canvas, "보물상자", (16, 16), ui.ACCENT, 16, "midleft")
        text(canvas, f"상자 조각 {self.save.data['shards']}", (464, 16), (200, 170, 255), 11, "midright")
        self.tabs.draw(canvas, self.mouse)
        if self.kind == "open":
            self._draw_open(canvas)
        elif self.kind == "dex":
            self._draw_dex(canvas)
        elif self.kind == "diary":
            self._draw_diary(canvas)
        else:
            self._draw_list(canvas)
        if self.msg_t > 0:
            text(canvas, self.msg, (LIST.x, 252), self.msg_col, 11, "midleft")
        self.close_btn.draw(canvas, self.mouse)
        if self.anim:
            self._draw_anim(canvas)
        draw_cursor(canvas, self.mouse)

    def _draw_open(self, canvas) -> None:
        chests = self.save.data["chests"]
        for i, g in enumerate(tr.GRADES):
            info = tr.grade_info(g)
            col = tuple(info["color"])
            r = pygame.Rect(18 + i * 112, 56, 104, 150)
            ui.panel(canvas, r, border=col if chests.get(g, 0) else ui.BORDER, fill=(16, 20, 36))
            n = chests.get(g, 0)
            if n:
                draw_glow(canvas, r.centerx, r.y + 62, 38 + 3 * math.sin(self.t * 3 + i), col, 1.2 + 0.3 * i)
            draw_chest(canvas, r.centerx, r.y + 78, 2.4, col if n else (70, 72, 84), 0.0, 0.0, self.t)
            text(canvas, f"{info['name']} 상자", (r.centerx, r.y + 14), col, 11, "center")
            text(canvas, f"× {n}", (r.centerx, r.y + 100), ui.TEXT if n else ui.DIM, 16, "center")
            b = self.open_btns[i]
            b.rect.topleft = (r.x + 6, r.bottom - 24)
            b.enabled = n > 0
            b.draw(canvas, self.mouse)
        c = tr.cfg()["pity"]
        p = self.save.data["pity"]
        text(canvas, f"천장: 특별 상자까지 {max(0, c['special'] - p['special'])}개 · 전설 상자까지 "
                     f"{max(0, c['legend'] - p['legend'])}개", (240, 218), ui.DIM, 11, "center")
        text(canvas, "상자는 물고기를 잡을 때 가끔 얻어요 (S랭크면 더 잘 나와요)", (240, 232), ui.DIM, 11, "center")
        from src.tutorial import targets as T   # TG-10 강조 대상
        panels = [pygame.Rect(18 + i * 112, 56, 104, 150) for i in range(len(tr.GRADES))]
        T.mark_ui(self, "chest.grade", panels[0].unionall(panels))
        for i, g in enumerate(tr.GRADES):
            if chests.get(g, 0):
                T.mark_ui(self, "chest.box", self.open_btns[i].rect)   # '열기' 버튼
        T.mark_ui(self, "chest.pity", (60, 211, 360, 14))

    def _row_rect(self, i: int) -> pygame.Rect:
        return pygame.Rect(LIST.x + 2, LIST.y + 2 + (i - self.scroll) * ROW_H, LIST.w - 4, ROW_H - 1)

    def _draw_list(self, canvas) -> None:
        ui.panel(canvas, LIST, fill=(16, 20, 36))
        ui.panel(canvas, DETAIL, fill=(16, 20, 36))
        items = self._list()
        self.sel = max(0, min(self.sel, len(items) - 1)) if items else 0
        visible = LIST.h // ROW_H
        owned = self.save.data["items"]
        if not items:
            text(canvas, "아직 아이템이 없어요", LIST.center, ui.DIM, 11, "center")
            return
        for i in range(self.scroll, min(len(items), self.scroll + visible)):
            it = items[i]
            r = self._row_rect(i)
            if i == self.sel or r.collidepoint(self.mouse):
                canvas.fill(ui.PANEL_LIGHT, r)
            col = tuple(tr.grade_info(it["grade"])["color"])
            text(canvas, it["name"], (r.x + 4, r.centery), col, 11, "midleft")
            if self.kind == "exchange" and it["kind"] == "phantom_x":
                from src.fishing import phantom
                have = phantom.exchange_owned(self.save, it)
                status = "보유" if have else f"비늘 {it['cost']}"
                scol = ui.GOOD if have else ((200, 150, 255) if phantom.state(self.save)["scales"] >= it["cost"] else ui.DIM)
            elif self.kind == "exchange":
                have = it["kind"] != "consumable" and it["id"] in owned["owned"]
                status = "보유" if have else f"조각 {tr.exchange_cost(it['id'])}"
                scol = ui.GOOD if have else (ui.ACCENT if self.save.data["shards"] >= tr.exchange_cost(it["id"])
                                              else ui.DIM)
            else:
                n = owned["consumables"].get(it["id"], 0)
                status, scol = (f"× {n}", ui.TEXT) if it["kind"] == "consumable" else (KIND_KO[it["kind"]], ui.DIM)
            text(canvas, status, (r.right - 4, r.centery), scol, 11, "midright")
        it = items[self.sel]
        col = tuple(tr.grade_info(it["grade"])["color"])
        x, y = DETAIL.x + 8, DETAIL.y + 8
        text(canvas, it["name"], (x, y + 4), col, 11, "midleft")
        text(canvas, f"{tr.grade_info(it['grade'])['name']} · {KIND_KO[it['kind']]}", (DETAIL.right - 8, y + 4),
             ui.DIM, 11, "midright")
        yy = y + 22
        for ln in wrap_text(it["desc"], DETAIL.w - 16)[:4]:
            text(canvas, ln, (x, yy), ui.TEXT, 11, "midleft")
            yy += 13
        for key, label, c in (("cost", "대가", ui.BAD), ("limit", "제한", ui.DIM)):
            if it.get(key):
                yy += 3
                for ln in wrap_text(f"{label}: {it[key]}", DETAIL.w - 16)[:3]:
                    text(canvas, ln, (x, yy), c, 11, "midleft")
                    yy += 13
        if self.kind == "exchange" and it["kind"] == "phantom_x":
            from src.fishing import phantom
            reason = phantom.can_exchange(self.save, it)
            self.action_btn.label = f"교환 (환상 비늘 {it['cost']} / 보유 {phantom.state(self.save)['scales']})"
            self.action_btn.enabled = reason is None
            if reason and reason != "환상 비늘이 부족해요":
                self.action_btn.label = reason
            self.action_btn.draw(canvas, self.mouse)
        elif self.kind == "exchange":
            reason = tr.can_exchange(self.save, it["id"])
            self.action_btn.label = f"교환 (조각 {tr.exchange_cost(it['id'])})"
            self.action_btn.enabled = reason is None
            if reason and reason != "조각이 부족해요":
                self.action_btn.label = reason
            self.action_btn.draw(canvas, self.mouse)
        else:
            label, ok = self._item_state(it)
            self.action_btn.label, self.action_btn.enabled = label, ok
            self.action_btn.draw(canvas, self.mouse)
            for b in self.choice_btns:
                b.draw(canvas, self.mouse)
            # 부적 칸
            names = [tr.item_info(c)["name"] if c else "비어 있음" for c in self.save.charms()]
            text(canvas, "부적: " + " / ".join(names), (240, 16), (200, 170, 255), 11, "center")

    # ── 보물 도감 ──
    def _draw_dex(self, canvas) -> None:
        from src.fishing import phantom
        allit = [i for i in tr.cfg()["items"] if not i.get("reward_only") or phantom.revealed(self.save)]
        tdex = self.save.data["treasure_dex"]
        got = sum(1 for it in allit if tdex.get(it["id"]))
        text(canvas, f"수집 {got}/{len(allit)}", (240, 16), ui.ACCENT, 11, "center")
        hover = None
        for i, it in enumerate(allit):
            col_i, row = i % 4, i // 4
            r = pygame.Rect(18 + col_i * 112, 54 + row * 46, 106, 42)
            known = bool(tdex.get(it["id"]))
            col = tuple(tr.grade_info(it["grade"])["color"])
            ui.panel(canvas, r, border=col if known else ui.BORDER, fill=(16, 20, 36))
            draw_item_icon(canvas, r.x + 14, r.centery, it["kind"], col, known)
            lines = wrap_text(it["name"], r.w - 34)[:2] if known else ["???"]
            for j, ln in enumerate(lines):
                text(canvas, ln, (r.x + 28, r.y + (13 if len(lines) == 1 else 10) + j * 13), col if known else ui.DIM,
                     11, "midleft")
            text(canvas, f"×{tdex[it['id']]}" if known else tr.grade_info(it["grade"])["name"],
                 (r.right - 5, r.bottom - 8), ui.TEXT if known else ui.DIM, 11, "midright")
            if r.collidepoint(self.mouse):
                hover = (it, known)
        if hover:
            it, known = hover
            msg = it["desc"] if known else "상자에서 얻으면 기록돼요"
            text(canvas, msg[:46], (240, 241), ui.TEXT if known else ui.DIM, 11, "center")
        else:
            text(canvas, "얻은 상자 아이템이 기록돼요 (못 얻은 건 ???)", (240, 241), ui.DIM, 11, "center")

    def _draw_diary(self, canvas) -> None:
        """낡은 어부의 수첩 보관함 (도감과 별개): 찾은 장만 읽을 수 있다."""
        from src.core.config import load_json
        from src.fishing import phantom
        h = load_json("phantom_hints.json")
        got = phantom.state(self.save)["notes"]
        from src.story import story
        named = story.active(self.save) and story.flag(self.save, "grandpa_named")   # 1막 끝(C1-06) 뒤: 할아버지의 수첩
        book = "할아버지의 수첩" if named else "낡은 어부의 수첩"
        text(canvas, f"{book} · 찾은 장 {len(got)}/{len(h['diary'])}", (240, 16), (210, 160, 255), 11, "center")
        self.story_row = None
        if story.active(self.save) and story.state(self.save)["items"].get("grandpa_last_page"):
            # 이야기 칸: 해강의 마지막 장 (환상 수첩 12장 개수에 넣지 않음)
            self.story_row = pygame.Rect(16, 222, 448, 16)
            canvas.fill((40, 34, 24), self.story_row)
            pygame.draw.rect(canvas, (200, 170, 110), self.story_row, 1)
            text(canvas, "이야기 · 해강의 마지막 장 (눌러서 읽기)", (24, self.story_row.centery), (240, 220, 170), 11, "midleft")
        y = 52
        shown = [fid for fid in h["diary"] if fid in got]
        if not shown:
            text(canvas, "보물상자에서 가끔 낡은 수첩이 나온다고 한다…", (240, 140), ui.DIM, 11, "center")
            return
        spots = {s["id"]: s["name"] for s in load_json("spots.json")["spots"]}
        per = 4 if named else 6
        pages = (len(shown) + per - 1) // per
        page = getattr(self, "diary_page", 0) % pages
        for fid in shown[page * per:page * per + per]:
            sp = phantom.by_id(fid)["spot"]
            text(canvas, f"— {spots.get(sp, '')}에서", (20, y), (190, 150, 240), 11, "midleft")
            for ln in wrap_text(h["diary"][fid], 430)[:2]:
                y += 13
                text(canvas, ln, (30, y), (225, 220, 235), 11, "midleft")
            if named:   # 각 장 맨 아래 (본문은 그대로)
                y += 13
                text(canvas, "— 윤해강", (446, y), (200, 180, 150), 11, "midright")
            y += 18
        if pages > 1:
            text(canvas, f"{page + 1}/{pages}쪽 (클릭: 다음 쪽)", (20, 210 if self.story_row else 236), ui.DIM, 11, "midleft")

    # ── 개봉 연출 ──
    def _draw_anim(self, canvas) -> None:
        a = self.anim
        g, t = a["grade"], a["t"]
        col = tuple(tr.grade_info(g)["color"])
        w, h = canvas.get_size()
        cx, cy = 240, 150
        open_at, card_at = OPEN_AT[g], CARD_AT[g]
        # 배경: 어둡게 (전설은 거의 암전)
        dim = {"common": 150, "rare": 175, "special": 195, "legend": 235}[g]
        veil = pygame.Surface((w, h), pygame.SRCALPHA)
        veil.fill((4, 4, 12, int(dim * clamp(t / 0.25, 0, 1))))
        canvas.blit(veil, (0, 0))
        # 전설: 금빛 기둥이 하늘에서 내려와 상자를 감싼다
        if g == "legend" and t > 0.5:
            pk = clamp((t - 0.5) / 0.8, 0, 1)
            pw = int(lerp(3, 46, pk) + math.sin(t * 18) * 3)
            pillar = pygame.Surface((pw * 2, h), pygame.SRCALPHA)
            for i in range(pw):
                al = int(170 * (1 - i / pw))
                pygame.draw.line(pillar, (255, 220, 120, al), (pw - i, 0), (pw - i, int(h * pk)))
                pygame.draw.line(pillar, (255, 220, 120, al), (pw + i, 0), (pw + i, int(h * pk)))
            canvas.blit(pillar, (cx - pw, 0), special_flags=pygame.BLEND_RGBA_ADD)
        # 희귀 이상: 열린 뒤 빛줄기가 돈다
        opened = t >= open_at
        if opened and g != "common":
            k = clamp((t - open_at) / 0.3, 0, 1)
            n = {"rare": 10, "special": 14, "legend": 18}[g]
            for i in range(n):
                ang = t * (0.6 if g != "special" else -0.9) + i * math.tau / n
                ln = (140 + 40 * ("rare", "special", "legend").index(g)) * k
                c2 = lerp_color((20, 20, 40), col, 0.55 if i % 2 else 0.3)
                pygame.draw.polygon(canvas, c2, [(cx, cy - 18), (cx + math.cos(ang) * ln, cy - 18 + math.sin(ang) * ln),
                                                 (cx + math.cos(ang + 0.12) * ln, cy - 18 + math.sin(ang + 0.12) * ln)])
        draw_glow(canvas, cx, cy - 16, 40 + (25 if opened else 0), col, 0.8 if opened else 0.4)
        # 상자: 흔들림 → 열림
        shake = 0.0
        if not opened:
            if g == "rare":
                shake = 1.5 * clamp((t - 0.3) / 0.4, 0, 1)
            elif g == "special":
                shake = 1 + 3.5 * clamp((t - 0.3) / 0.8, 0, 1)
            elif g == "legend":
                shake = 0.8 * clamp((t - 1.0) / 0.6, 0, 1)
        lid = clamp((t - open_at) / 0.15, 0, 1)
        bob = -6 * math.sin(clamp(t / 0.4, 0, 1) * math.pi / 2) if g == "legend" else 0
        draw_chest(canvas, cx, cy + bob, 4.0, col, lid, shake, t)
        # 특별: 열리는 순간 보랏빛 폭발 고리
        if g == "special" and opened:
            kk = clamp((t - open_at) / 0.5, 0, 1)
            if kk < 1:
                pygame.draw.circle(canvas, lerp_color(col, (255, 255, 255), 1 - kk), (cx, cy - 18), int(10 + kk * 170),
                                   max(1, int(5 * (1 - kk))))
        for x, y, _, _, life, pc in self.particles:
            c = (255, 255, 255) if life > 0.6 else pc
            if g in ("special", "legend") and life > 0.5:
                draw_star(canvas, x, y, 2, c)
            else:
                canvas.fill(c, (int(x), int(y), 2, 2))
        # 섬광
        if opened and t - open_at < 0.18 and g != "common":
            fl = _opaque((w, h))
            fl.fill((255, 245, 210))
            fl.set_alpha(int(220 * (1 - (t - open_at) / 0.18) * (1.0 if g == "legend" else 0.6)))
            canvas.blit(fl, (0, 0))
        # 보상 카드
        if t >= card_at:
            self._draw_reward(canvas, a["reward"], col, t - card_at)

    def _draw_reward(self, canvas, r: dict, col, age: float) -> None:
        pop = 1.0 + 0.5 * math.exp(-age * 10) * math.cos(age * 22)
        cx = 240
        band = pygame.Surface((480, 74), pygame.SRCALPHA)
        band.fill((6, 6, 16, int(200 * min(1.0, age / 0.2))))
        canvas.blit(band, (0, 190))
        if r["type"] == "gold":
            big_text(canvas, f"+{r['amount']:,}원", (cx, 212), (255, 228, 140), 2.0 * pop, outline=True)
            sub = "골드"
        elif r["type"] == "materials":
            line = f"{MAT_KO.get(r['continent'], '소재')} +{r['n']}"
            if r.get("rare"):
                line += f" · 희귀 소재 +{r['rare']}"
            big_text(canvas, line, (cx, 212), (190, 230, 200), 1.4 * pop, outline=True)
            sub = "강화 소재"
        else:
            it = r["item"]
            icol = tuple(tr.grade_info(it["grade"])["color"])
            big_text(canvas, it["name"], (cx, 206), icol, 2.0 * pop, outline=True)
            if r.get("dup"):
                sub = f"이미 가지고 있어서 상자 조각 +{r['shards']}"
            else:
                sub = f"{tr.grade_info(it['grade'])['name']} {KIND_KO[it['kind']]} 획득!"
            text(canvas, it["desc"][:40], (cx, 240), ui.TEXT, 11, "center")
        text(canvas, sub, (cx, 228), ui.DIM if r["type"] != "item" else ui.ACCENT, 11, "center")
        if age > 0.3:
            text(canvas, "클릭: 닫기", (cx, 256), ui.DIM, 11, "center")
        big_text(canvas, f"{tr.grade_info(r['grade'])['name']} 상자", (cx, 40), col, 1.6, outline=True)
