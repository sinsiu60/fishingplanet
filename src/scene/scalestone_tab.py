"""상점 '비늘석' 탭 (SCALESTONE.md 화면 2 · 3, DESIGN.md 46장 S5). ShopScene 이 kind == "scalestone" 일 때 이 객체에 맡긴다.

배치 (UI 상자 480x270, 상점 틀 464x258 — 건물 안에서도 이 탭은 넓은 틀로 연다):
  위 왼쪽   장착 칸 4개 (낚싯대 · 릴 · 줄 · 뜰채: 장비 작은 그림 + 비늘석 32x32 / 빈 칸 그림 + +n)
  그 아래   필터 칩 (등급 · 강화 단계 · 옵션 포함 · 장착 중) + 정렬 (등급 · 강화 단계 · 최근 획득)
  왼쪽 목록 등급 색 띠 · 16x16 아이콘 · +n · 첫 옵션 · 옵션 개수 점 · 잠금 · 장착 장비 그림 (맨 아래 = 특급 배송 시스템)
  오른쪽    상세: 그림 3배(96x96) · 등급 · +n · 강화 비용 · [강화] [장착/해제] [잠금] [분해] · 부옵션 5줄
  아래      [합계 효과] [일괄 분해] · 안내 글자 · [닫기]
장착: [장착] → 칸 4개가 깜빡임 → 고른 칸에 (원래 있던 비늘석은 보관함으로), 파이팅 중엔 못 바꿈.
"""
import pygame

from src.render import gear_icon
from src.save import scalestone as ss
from src.ui import scalestone_ui as sui
from src.ui import shop_ui as su
from src.ui import widgets as ui
from src.ui.hud import text

SLOT_KO = {"rod": "낚싯대", "reel": "릴", "line": "줄", "net": "뜰채"}
LIST_W = 226
SLOT_H = 38
ROW = 16
SORTS = [("grade", "등급"), ("level", "강화 단계"), ("recent", "최근 획득")]
DELIVERY = {"id": "delivery", "name": "특급 배송 시스템", "tier": 0}


class ScalestoneTab:
    def __init__(self, shop):
        self.shop = shop
        self.game = shop.game
        self.save = shop.save
        self.f_grade: str | None = None
        self.f_level: int | None = None
        self.f_opt: str | None = None
        self.f_equipped = False
        self.sort = 0
        self.sel_uid = None           # 고른 비늘석 (목록이 다시 정렬돼도 그대로)
        self.reveal: sui.EnhanceReveal | None = None
        self.pick = False             # 장착할 칸 고르는 중 (칸 4개 깜빡임)
        self.pick_t = 0.0
        self.totals_on = False
        self.opt_menu = False         # 옵션 필터 고르기
        self.chip_rects: list = []
        self.opt_rects: list = []
        self.detail_rects: dict = {}
        self.layout()

    # ───────────────────────── 배치 ─────────────────────────
    def layout(self) -> None:
        sh = self.shop
        fr = sh.frame
        bottom = fr.bottom - 26
        top = fr.y + 42
        self.SLOTS = pygame.Rect(fr.x + 6, top, LIST_W, SLOT_H)
        self.chip_cy = self.SLOTS.bottom + 9
        ly = self.SLOTS.bottom + 17
        sh.LIST = pygame.Rect(fr.x + 6, ly, LIST_W, bottom - ly)
        sh.DETAIL = pygame.Rect(sh.LIST.right + 8, top, fr.right - 7 - (sh.LIST.right + 8), bottom - top)
        D = sh.DETAIL
        sh.action_btn = ui.Button((D.x + 6, D.bottom - 20, D.w - 12, 16), "", sh._action)   # 특급 배송 상세
        cx = D.x + 4 + 96 + 8
        cw = D.right - 5 - cx
        self.btn_enh = ui.Button((cx, D.y + 52, cw, 16), "강화", self._enhance)
        self.btn_eq = ui.Button((cx, D.y + 70, cw, 16), "장착", self._equip)
        hw = (cw - 3) // 2
        self.btn_lock = ui.Button((cx, D.y + 88, hw, 15), "잠금", self._lock)
        self.btn_sal = ui.Button((cx + hw + 3, D.y + 88, cw - hw - 3, 15), "분해", self._salvage)
        by = fr.bottom - 21
        self.btn_tot = ui.Button((sh.LIST.x, by, 68, 16), "합계 효과", self._totals)
        self.btn_batch = ui.Button((sh.LIST.x + 72, by, 68, 16), "일괄 분해", self._batch)
        n = len(ss.SLOTS)
        cw = (LIST_W - (n - 1) * 3) // n
        self.slot_rects = {s: pygame.Rect(self.SLOTS.x + i * (cw + 3), self.SLOTS.y, cw, SLOT_H) for i, s in enumerate(ss.SLOTS)}

    # ───────────────────────── 데이터 ─────────────────────────
    def _fighting(self) -> bool:
        f = getattr(self.shop.fishing, "fight", None)
        return f is not None and getattr(f, "phase", "") in ("fight", "net")

    def stones(self) -> list[dict]:
        out = []
        eq = ss.state(self.save)["equipped"]
        for s in ss.state(self.save)["items"]:
            if self.f_grade and s["grade"] != self.f_grade:
                continue
            if self.f_level is not None and s["level"] != self.f_level:
                continue
            if self.f_opt and all(o["id"] != self.f_opt for o in s["opts"]):
                continue
            if self.f_equipped and s["uid"] not in eq.values():
                continue
            out.append(s)
        order = {g: i for i, g in enumerate(reversed(ss.grades()["order"]))}   # 전설 먼저
        mode = SORTS[self.sort][0]
        if mode == "grade":
            out.sort(key=lambda s: (order[s["grade"]], -s["level"], -s.get("got", 0)))
        elif mode == "level":
            out.sort(key=lambda s: (-s["level"], order[s["grade"]], -s.get("got", 0)))
        else:
            out.sort(key=lambda s: -s.get("got", 0))
        return out

    def rows(self) -> list:
        return [("stone", s) for s in self.stones()] + [("delivery", DELIVERY)]

    def _sync_sel(self, rows) -> None:
        """고른 비늘석 uid 에 맞춰 shop.sel (정렬 · 필터 · 분해 뒤에도 같은 돌)."""
        sh = self.shop
        if self.sel_uid is not None:
            i = next((i for i, (k, x) in enumerate(rows) if k == "stone" and x["uid"] == self.sel_uid), None)
            if i is not None:
                sh.sel = i
        sh.sel = max(0, min(sh.sel, len(rows) - 1))
        k, x = rows[sh.sel]
        self.sel_uid = x["uid"] if k == "stone" else None
        self._clamp_scroll(rows)

    def current(self) -> dict | None:
        return ss.by_uid(self.save, self.sel_uid) if self.sel_uid is not None else None

    def _visible(self) -> int:
        return (self.shop.LIST.h - 4 - 14) // ROW

    def _clamp_scroll(self, rows) -> None:
        sh = self.shop
        vis = self._visible()
        if sh.sel < sh.scroll:
            sh.scroll = sh.sel
        elif sh.sel >= sh.scroll + vis:
            sh.scroll = sh.sel - vis + 1
        sh.scroll = max(0, min(sh.scroll, max(0, len(rows) - vis)))

    def _row_rect(self, i: int) -> pygame.Rect | None:
        L = self.shop.LIST
        j = i - self.shop.scroll
        if not 0 <= j < self._visible():
            return None
        return pygame.Rect(L.x + 2, L.y + 2 + j * ROW, L.w - 8, ROW - 1)

    def select(self, i: int) -> None:
        rows = self.rows()
        sh = self.shop
        sh.sel = max(0, min(i, len(rows) - 1))
        k, x = rows[sh.sel]
        self.sel_uid = x["uid"] if k == "stone" else None
        self._clamp_scroll(rows)

    def _cont(self) -> str:
        host = self.shop.host
        if host is not None and getattr(host, "cont", None) in ss.CONTS:
            return host.cont
        from src.save.save_game import spot_continent
        return spot_continent(self.save.data.get("spot", ""))

    # ───────────────────────── 동작 ─────────────────────────
    def busy(self) -> bool:
        return self.reveal is not None and self.reveal.active

    def _enhance(self) -> None:
        st = self.current()
        if st is None:
            return
        why = ss.enhance_block(self.save, st)
        if why:
            self.shop._say(why, ui.BAD)
            return
        res = ss.enhance(self.save, st["uid"])
        if res is None:
            return
        self.pick = False
        self.reveal = sui.EnhanceReveal(res, reduce=bool(self.game.settings.get("reduce_fx")), sfx=self.game.sfx)
        self.shop._react("enhance")
        self.game.save_now()

    def _equip(self) -> None:
        st = self.current()
        if st is None:
            return
        if self._fighting():
            self.shop._say("파이팅 중에는 바꿀 수 없어요", ui.BAD)
            return
        slot = ss.equipped_slot(self.save, st["uid"])
        if slot and not self.pick:
            ss.unequip(self.save, slot)
            self.game.sfx.play("ui_equip")
            self.shop._say(f"{SLOT_KO[slot]} 칸에서 뺐어요", ui.TEXT)
            self.game.save_now()
            return
        self.pick = not self.pick
        self.pick_t = 0.0
        self.game.sfx.play("ui_click")
        if self.pick:
            self.shop._say("끼울 칸을 고르세요", ui.ACCENT)

    def _pick_slot(self, slot: str) -> None:
        st = self.current()
        self.pick = False
        if st is None:
            return
        if ss.equip(self.save, st["uid"], slot, fighting=self._fighting()):
            self.game.sfx.play("ui_equip")
            self.shop._say(f"{SLOT_KO[slot]} 칸에 장착!", ui.GOOD)
            self.game.guide.event("ss_equipped")   # TG-12 비늘석 7단계
            self.game.save_now()

    def _lock(self) -> None:
        st = self.current()
        if st is None:
            return
        ss.set_locked(self.save, st["uid"], not st.get("locked"))
        self.game.sfx.play("ui_click")
        self.shop._say("잠갔어요 (분해 안 됨)" if st["locked"] else "잠금을 풀었어요", ui.TEXT)
        self.game.save_now()

    def _salvage(self) -> None:
        st = self.current()
        if st is None:
            return
        why = ss.salvage_block(self.save, st)
        if why:
            self.shop._say(why, ui.BAD)
            return
        n = ss.salvage_yield(st)
        uid = st["uid"]

        def yes():
            got = ss.salvage(self.save, uid, self._cont())
            if got is not None:
                self.game.sfx.play("ui_stamp", 0.5)
                self.shop._say(f"분해: 소재 +{got}", ui.GOOD)
                self.sel_uid = None
                self.game.save_now()
        from src.scene.confirm import ConfirmScene
        self.game.scenes.push(ConfirmScene(self.game, f"분해할까요? 소재 +{n}개", yes, yes="분해", no="취소"))

    def _batch(self) -> None:
        cands = ss.batch_candidates(self.save, {self.f_grade} if self.f_grade else None, self.f_level)
        if not cands:
            self.shop._say("분해할 비늘석이 없어요 (잠김 · 장착 중 제외)", ui.BAD)
            return

        def done(got):
            if got["count"]:
                self.shop._say(f"비늘석 {got['count']}개 분해: 소재 +{got['mat']}", ui.GOOD)
                self.game.save_now()
        from src.scene.scalestone_salvage import SalvageConfirmScene
        self.game.scenes.push(SalvageConfirmScene(self.game, cands, self._cont(), done))

    def _totals(self) -> None:
        self.totals_on = not self.totals_on
        self.game.sfx.play("ui_paper" if self.totals_on else "ui_click")

    # ───────────────────────── 입력 ─────────────────────────
    def key(self, event) -> bool:
        if event.type != pygame.KEYDOWN:
            return False
        if self.busy() or self.totals_on or self.opt_menu:
            return event.key not in (pygame.K_ESCAPE,)
        if event.key in (pygame.K_UP, pygame.K_DOWN, pygame.K_w, pygame.K_s):
            self.select(self.shop.sel + (-1 if event.key in (pygame.K_UP, pygame.K_w) else 1))
            self.shop.tut_picked = True
            self.game.sfx.play("ui_click")
            return True
        if event.key == pygame.K_l:
            self._lock()
            return True
        return False

    def enter(self) -> bool:
        """Enter: 고른 비늘석 강화 (특급 배송 줄이면 상점 기본 동작)."""
        if self.busy() or self.current() is None:
            return self.busy()
        self._enhance()
        return True

    def handle_action(self, a) -> bool:
        """처리했으면 True (상점이 탭 · 닫기 · 특급 배송을 처리)."""
        if self.busy():
            if a.name in ("primary", "confirm", "back"):
                self.reveal.tap()
            return True
        if self.totals_on:
            if a.name in ("primary", "back", "confirm"):
                self.totals_on = False
            return True
        if self.opt_menu:
            if a.name == "primary":
                for oid, r in self.opt_rects:
                    if r.collidepoint(a.pos):
                        self.f_opt = oid
                        self.shop.scroll = 0
                        self.game.sfx.play("ui_tab")
                        break
            if a.name in ("primary", "back"):
                self.opt_menu = False
            return True
        if self.pick:
            if a.name == "back":
                self.pick = False
                return True
            if a.name == "primary":
                for slot, r in self.slot_rects.items():
                    if r.collidepoint(a.pos):
                        self._pick_slot(slot)
                        return True
                self.pick = False   # 다른 곳 = 취소
            return a.name == "primary"
        if a.name == "scroll":
            rows = self.rows()
            sh = self.shop
            sh.scroll = max(0, min(max(0, len(rows) - self._visible()), sh.scroll - a.value))
            return True
        if a.name != "primary":
            return False
        m = a.pos
        for key, r in self.chip_rects:
            if r.collidepoint(m):
                self._chip(key)
                return True
        for slot, r in self.slot_rects.items():
            if r.collidepoint(m):
                uid = ss.state(self.save)["equipped"].get(slot)
                if uid is not None:
                    self.f_grade = self.f_level = self.f_opt = None
                    self.f_equipped = False
                    self.sel_uid = uid
                    self._sync_sel(self.rows())
                    self.shop.tut_picked = True
                    self.game.sfx.play("ui_click")
                return True
        for b in (self.btn_tot, self.btn_batch):
            if b.click(m):
                return True
        if self.current() is not None:
            for b in (self.btn_enh, self.btn_eq, self.btn_lock, self.btn_sal):
                if b.click(m):
                    return True
        if self.shop.LIST.collidepoint(m):
            rows = self.rows()
            for i in range(len(rows)):
                r = self._row_rect(i)
                if r is not None and r.collidepoint(m):
                    self.select(i)
                    self.shop.tut_picked = True
                    self.game.sfx.play("ui_click")
                    return True
            return True
        return False

    def _chip(self, key: str) -> None:
        order = ss.grades()["order"]
        if key == "grade":
            i = order.index(self.f_grade) + 1 if self.f_grade else 0
            self.f_grade = order[i] if i < len(order) else None
        elif key == "level":
            nxt = 0 if self.f_level is None else self.f_level + 1
            self.f_level = nxt if nxt <= ss.enhance_cfg()["max_level"] else None
        elif key == "opt":
            self.opt_menu = True
        elif key == "eq":
            self.f_equipped = not self.f_equipped
        elif key == "sort":
            self.sort = (self.sort + 1) % len(SORTS)
        self.shop.scroll = 0
        self.game.sfx.play("ui_tab")

    def update(self, dt: float) -> None:
        self.pick_t += dt
        if self.reveal is not None:
            was = self.reveal.active
            self.reveal.update(dt)
            if was and not self.reveal.active:
                r = self.reveal.res
                g = ss.grade_info(r["stone"]["grade"])["name"]
                self.shop._say(f"{g} 비늘석 +{r['level']}" + (" 완성!" if r["done"] else "") + f" · {ss.option_text(r['opt'])}", ui.GOOD)
                self.game.guide.event("ss_enhanced")   # TG-12 비늘석 5단계

    # ───────────────────────── 그리기 ─────────────────────────
    def draw(self, canvas) -> None:
        sh = self.shop
        rows = self.rows()
        self._sync_sel(rows)
        self._draw_slots(canvas)
        self._draw_chips(canvas)
        self._draw_list(canvas, rows)
        k, x = rows[sh.sel]
        if k == "delivery":
            self.detail_rects = {}
            sh._draw_delivery_detail(canvas, x)
        else:
            self._draw_detail(canvas, x)
        self._draw_bottom(canvas)
        if self.opt_menu:
            self._draw_opt_menu(canvas)
        if self.totals_on:
            self._draw_totals(canvas)

    def _draw_slots(self, canvas) -> None:
        eq = ss.equipped_stones(self.save)
        blink = self.pick and int(self.pick_t * 4) % 2 == 0
        for slot, r in self.slot_rects.items():
            st = eq[slot]
            sel = st is not None and st["uid"] == self.sel_uid
            canvas.fill(su.SEL_BG if (sel or self.pick) else su.CELL_BG, r)
            col = su.YELLOW if (blink or sel) else su.BORDER
            pygame.draw.rect(canvas, col, r, 1)
            gear_icon.draw(canvas, slot, self.save.equipped(slot), (r.x + 3, r.y + 3, 14, 14))
            canvas.blit(sui.icon(st["grade"] if st else None), (r.right - 35, r.y + 3))
            if st is not None:
                text(canvas, f"+{st['level']}", (r.x + 3, r.bottom - 9), tuple(ss.grade_info(st["grade"])["color"]), 11, "midleft")
            else:
                text(canvas, SLOT_KO[slot], (r.x + 3, r.bottom - 9), su.SUB, 11, "midleft")

    def _draw_chips(self, canvas) -> None:
        cy = self.chip_cy
        x = self.SLOTS.x
        gi = ss.grade_info(self.f_grade) if self.f_grade else None
        items = [("grade", gi["name"] if gi else "모든 등급", tuple(gi["color"]) if gi else su.GRAY, bool(gi)),
                 ("level", f"+{self.f_level}" if self.f_level is not None else "모든 단계", su.YELLOW, self.f_level is not None),
                 ("opt", su.fit(ss.options()["options"][self.f_opt]["name"], 52) if self.f_opt else "옵션", su.CYAN, bool(self.f_opt)),
                 ("eq", "장착 중", su.GREEN, self.f_equipped)]
        self.chip_rects = []
        for key, label, col, on in items:
            r = su.chip(canvas, label, x, cy, col, on)
            self.chip_rects.append((key, r))
            x = r.right + 3
        lab = SORTS[self.sort][1]   # 정렬: 작은 위아래 화살표(직접 그림 — 폰 글꼴에 ↕ 없음) + 기준
        r = pygame.Rect(0, 0, su.width(lab) + 11, 12)
        r.midright = (self.SLOTS.right, cy)
        if r.x < x:
            lab = lab[:2]
            r = pygame.Rect(0, 0, su.width(lab) + 11, 12)
            r.midright = (self.SLOTS.right, cy)
        canvas.fill(su.CELL_BG, r)
        pygame.draw.rect(canvas, su.GRAY, r, 1)
        ax = r.x + 4
        pygame.draw.polygon(canvas, su.WHITE, [(ax - 2, cy - 1), (ax + 2, cy - 1), (ax, cy - 4)])
        pygame.draw.polygon(canvas, su.WHITE, [(ax - 2, cy + 1), (ax + 2, cy + 1), (ax, cy + 4)])
        text(canvas, lab, (r.x + 9, cy), su.WHITE, 11, "midleft")
        self.chip_rects.append(("sort", r))

    def _draw_list(self, canvas, rows) -> None:
        sh = self.shop
        L = sh.LIST
        st = ss.state(self.save)
        eq = st["equipped"]
        for i, (k, x) in enumerate(rows):
            r = self._row_rect(i)
            if r is None:
                continue
            su.row_bg(canvas, r, i == sh.sel, r.collidepoint(sh.mouse))
            cy = r.centery
            if k == "delivery":
                from src.save import delivery
                dl = delivery.level(self.save)
                gear_icon.draw(canvas, "delivery", x, (r.x + 10, cy - 7, 14, 14))
                text(canvas, x["name"], (r.x + 28, cy), su.WHITE, 11, "midleft")
                text(canvas, f"Lv{dl}" if dl else "미보유", (r.right - 3, cy), su.YELLOW if dl else su.SUB, 11, "midright")
                continue
            col = tuple(ss.grade_info(x["grade"])["color"])
            canvas.fill(col, (r.x + 8, r.y + 2, 2, r.h - 4))
            canvas.blit(sui.icon(x["grade"], small=True), (r.x + 12, r.y))
            text(canvas, f"+{x['level']}", (r.x + 30, cy), su.YELLOW if x["level"] >= 4 else su.WHITE, 11, "midleft")
            right = r.right - 3
            slot = next((s for s in ss.SLOTS if eq.get(s) == x["uid"]), None)
            if slot:
                gear_icon.draw(canvas, slot, self.save.equipped(slot), (right - 14, cy - 7, 14, 14))
            right -= 16
            if x.get("locked"):
                su.lock(canvas, right - 7, cy, su.GRAY)
            right -= 10
            dx = right - 35
            sui.draw_dots(canvas, dx, cy, x, col)
            text(canvas, su.fit(ss.option_text(x["opts"][0], False), dx - (r.x + 46) - 3), (r.x + 46, cy), su.WHITE, 11, "midleft")
        n = len(rows)
        if n > self._visible():
            sh._scrollbar(canvas, n, self._visible(), L.y + 2, L.bottom - 16)
        mats = ss.materials_total(self.save)
        text(canvas, f"보관 {len(st['items'])}/{ss.enhance_cfg()['storage_max']} · 소재 {mats}개", (L.x + 6, L.bottom - 8),
             su.SUB, 11, "midleft")

    def _draw_detail(self, canvas, stone: dict) -> None:
        sh = self.shop
        D = sh.DETAIL
        rv = self.reveal if (self.reveal is not None and self.reveal.stone is stone and self.reveal.active) else None
        self.detail_rects = sui.draw_detail(canvas, D, stone, rv, buttons=True)
        cx = self.btn_enh.rect.x
        cost = ss.enhance_cost(stone)
        if cost is not None:
            short = ss.enhance_block(self.save, stone)
            gcol = su.RED if self.save.money < cost["gold"] else su.WHITE
            r = su.price(canvas, cost["gold"], (cx, D.y + 44), gcol, anchor="midleft")
            mcol = su.RED if ss.materials_total(self.save) < cost["mat"] else su.WHITE
            text(canvas, su.fit(f"· 소재 {cost['mat']}", D.right - 5 - r.right - 3), (r.right + 3, D.y + 44), mcol, 11, "midleft")
            su.button(canvas, self.btn_enh.rect, "강화", "fill" if not short and rv is None else "dim", sh.mouse)
        else:
            text(canvas, "완성 (+4)", (cx, D.y + 44), su.YELLOW, 11, "midleft")
            su.button(canvas, self.btn_enh.rect, "최대 강화", "dim", sh.mouse)
        slot = ss.equipped_slot(self.save, stone["uid"])
        lab = "칸 고르기…" if self.pick else (f"해제 ({SLOT_KO[slot]})" if slot else "장착")
        su.button(canvas, self.btn_eq.rect, lab, "dim" if self._fighting() else "outline", sh.mouse)
        su.button(canvas, self.btn_lock.rect, "잠금 해제" if stone.get("locked") else "잠금", "outline", sh.mouse)
        su.button(canvas, self.btn_sal.rect, "분해", "dim" if ss.salvage_block(self.save, stone) else "outline", sh.mouse)

    def _draw_bottom(self, canvas) -> None:
        sh = self.shop
        su.button(canvas, self.btn_tot.rect, "합계 효과", "outline", sh.mouse)
        su.button(canvas, self.btn_batch.rect, "일괄 분해", "outline", sh.mouse)
        x = self.btn_batch.rect.right + 6
        w = sh.close_btn.rect.x - x - 6
        if sh.msg_t > 0 and w > 20:
            text(canvas, su.fit(sh.msg, w), (x, self.btn_batch.rect.centery), sh.msg_col, 11, "midleft")

    def _draw_opt_menu(self, canvas) -> None:
        o = ss.options()
        ids = [None] + list(o["order"])
        cols = 2
        cw, rh = 96, 14
        nrow = (len(ids) + cols - 1) // cols
        r0 = self.chip_rects[2][1] if len(self.chip_rects) > 2 else pygame.Rect(self.SLOTS.x, self.chip_cy, 10, 10)
        box = pygame.Rect(self.SLOTS.x, r0.bottom + 2, cols * cw + 8, nrow * rh + 8)
        canvas.fill(ui.SHADOW, box.move(2, 2))
        canvas.fill(su.WIN_BG, box)
        pygame.draw.rect(canvas, su.YELLOW, box, 1)
        self.opt_rects = []
        for i, oid in enumerate(ids):
            r = pygame.Rect(box.x + 4 + (i % cols) * cw, box.y + 4 + (i // cols) * rh, cw - 2, rh - 1)
            on = oid == self.f_opt
            if on or r.collidepoint(self.shop.mouse):
                canvas.fill(su.SEL_BG, r)
            name = "모든 옵션" if oid is None else o["options"][oid]["name"]
            text(canvas, su.fit(name, cw - 6), (r.x + 3, r.centery), su.YELLOW if on else su.WHITE, 11, "midleft")
            self.opt_rects.append((oid, r))

    def _draw_totals(self, canvas) -> None:
        """합계 효과: 장착 중인 4개를 합친 옵션 표 (이름 · 합계 · 상한). 상한을 넘으면 '(상한 12% 중 12%, 1.4% 초과)' 회색."""
        fr = self.shop.frame
        tot = ss.totals(self.save)
        o = ss.options()
        ids = [oid for oid in o["order"] if oid in tot]
        h = 34 + max(1, len(ids)) * 13 + 16
        box = pygame.Rect(0, 0, 330, h)
        box.center = fr.center
        canvas.fill(ui.SHADOW, box.move(2, 2))
        canvas.fill(su.WIN_BG, box)
        pygame.draw.rect(canvas, su.YELLOW, box, 1)
        su.btext(canvas, "합계 효과 (장착 중인 비늘석 4칸)", (box.x + 8, box.y + 10), su.YELLOW, 11, "midleft")
        y = box.y + 28
        if not ids:
            text(canvas, "장착한 비늘석이 없어요", (box.centerx, y + 4), su.GRAY, 11, "center")
        for oid in ids:
            t = tot[oid]
            sp = o["options"][oid]
            text(canvas, sp["name"], (box.x + 10, y), su.WHITE, 11, "midleft")
            text(canvas, ss.value_text(oid, t["eff"]), (box.x + 150, y), su.GREEN, 11, "midright")
            if t["over"] > 0:
                s = f"(상한 {unit(oid, t['cap'])} 중 {unit(oid, t['eff'])}, {unit(oid, t['over'])} 초과)"
                text(canvas, s, (box.x + 158, y), su.GRAY, 11, "midleft")
            else:
                text(canvas, f"상한 {unit(oid, t['cap'])}", (box.x + 158, y), su.SUB, 11, "midleft")
            y += 13
        text(canvas, "같은 옵션은 합쳐지고, 상한을 넘으면 더 쌓이지 않아요", (box.centerx, box.bottom - 9), su.SUB, 11, "center")

    # ───────────────────────── 튜토리얼 ─────────────────────────
    def mark(self) -> None:
        from src.tutorial import targets as T
        sh = self.shop
        T.mark_ui(sh, "ss.slots", self.SLOTS)
        T.mark_ui(sh, "ss.list", sh.LIST)
        T.mark_ui(sh, "ss.btn.totals", self.btn_tot.rect)
        rows = self.rows()
        first = next((i for i, (k, _) in enumerate(rows) if k == "stone"), None)
        if first is not None:
            r = self._row_rect(first)
            if r is not None:
                T.mark_ui(sh, "ss.list.first", r)
        if self.current() is not None and self.detail_rects:
            rr = self.detail_rects["rows"]
            T.mark_ui(sh, "ss.detail.opts", rr[0].unionall(rr))
            st = self.current()
            n = len(st["opts"])
            T.mark_ui(sh, "ss.detail.newopt", rr[min(4, n - 1)])
            T.mark_ui(sh, "ss.btn.enhance", self.btn_enh.rect.union(pygame.Rect(self.btn_enh.rect.x, sh.DETAIL.y + 38, 4, 4)))
            T.mark_ui(sh, "ss.btn.equip", self.btn_eq.rect)

    def tut_cond(self, name: str):
        if name == "ss_sel":
            return self.shop.tut_picked and self.current() is not None
        return None


def unit(oid: str, v: float) -> str:
    """부호 없는 수치 (상한 표시): 12% · 0.15초 · 2.50%p."""
    spec = ss.options()["options"][oid]
    if spec["unit"] == "pct":
        return f"{v:.1f}".rstrip("0").rstrip(".") + "%"
    if spec["unit"] == "sec":
        return f"{v:.2f}초"
    return f"{v:.2f}%p"
