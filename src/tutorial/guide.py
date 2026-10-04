"""가이드 튜토리얼 엔진 (TUTORIAL.md, DESIGN.md 40). game.guide — 매 프레임 update, 장면 위에 draw.

단계 종류 (data/tutorials.json, tools/tutorial_build.py 가 TUTORIAL.md 에서 만듦)
  spotlight 강조   화면 검정 70% + 대상만 밝게 + 노란 테두리 천천히 깜빡임. 대상 밖 입력은 막힘 → 대상을 누르면(조건) 다음
  info      설명   강조 그대로 + 안내 상자 '▼'. 아무 곳이나 탭 → 다음 (낚시 화면이면 시간도 멈춤)
  freeze    정지   낚시·파이팅 시간이 완전히 멈춤. 지시한 조작만 통과 → 정확히 하면 0.3초 슬로모션 + '좋아요!' 1초
                   틀린 조작은 아무 일도 없고 조작 그림을 한 번 더 강조 (실패 처리 없음, 제한 시간 없음)
  wait      대기   안내 상자만 위쪽에 작게, 게임은 그대로 → 정해진 일이 일어나면 다음
공통: 한 번에 하나(나머지는 대기열) · 스토리 장면 중엔 시작 안 함 · 오른쪽 위 '건너뛰기'(확인 창) ·
      설정 '튜토리얼 안내' 끄기 / '튜토리얼 다시 보기' · 완료·건너뛴 것은 다시 자동으로 안 나옴 (세이브 tutorial.done).
"""
import re

import pygame

from src.core.config import load_json
from src.tutorial import conds, targets

OK_SEC = 1.0
SLOW_SEC, SLOW_SCALE = 0.3, 0.35


class Guide:
    def __init__(self, game):
        self.game = game
        self.data = load_json("tutorials.json")["tutorials"]
        self.inputs = load_json("tutorial_inputs.json")["inputs"]
        self.run: dict | None = None        # {"id", "i", "t", "events", "tapped", "nudge", "ctx"}
        self.queue: list[str] = []
        self.modal = False                  # 건너뛰기 확인 창
        self.ok_t = 0.0                     # '좋아요!' 남은 시간
        self.ok_text = "좋아요!"
        self.result: dict | None = None     # 패턴 ③ 결과 (대기 단계로 표시)
        self.t = 0.0
        self.force_debug = False

    # ── 세이브 ──
    def st(self) -> dict:
        save = self.game.save
        if save is None:
            return {"done": [], "active": None, "enabled": True, "replay": []}
        s = save.data.setdefault("tutorial", {})
        s.setdefault("done", [])
        s.setdefault("active", None)
        s.setdefault("enabled", True)
        s.setdefault("replay", [])
        return s

    def enabled(self) -> bool:
        return bool(self.st()["enabled"])

    def done(self, tid: str) -> bool:
        return tid in self.st()["done"]

    def _finish(self, skipped: bool = False) -> None:
        r = self.run
        if r is None:
            return
        tid = r["id"]
        st = self.st()
        if tid not in st["done"]:
            st["done"].append(tid)
        if tid in st["replay"]:
            st["replay"].remove(tid)
        st["active"] = None
        tut = self.data[tid]
        self.run = None
        self.modal = False
        from src.tutorial import scripts
        scripts.stop(self.game, tid)
        if not skipped and tut.get("on_done"):
            scripts.action(self.game, tut["on_done"])
        if self.game.save is not None:
            self.game.save_now()
        self.event(f"tg_done:{tid}")
        nxt = tut.get("next")
        if skipped and nxt:   # 건너뛰면 이어지는 튜토리얼도 (TG-01 → 02 → 03…) 함께 건너뜀
            for t2 in self._chain(nxt):
                if t2 not in st["done"]:
                    st["done"].append(t2)

    def abort(self) -> None:
        """끝내지 못하고 멈춤 (물고기를 놓쳤다 등) — 완료로 치지 않아 다음에 그 순간이 오면 다시."""
        r = self.run
        if r is None:
            return
        self.run = None
        self.modal = False
        self.st()["active"] = None
        from src.tutorial import scripts
        scripts.stop(self.game, r["id"])

    def _chain(self, tid: str) -> list[str]:
        out = []
        while tid and tid not in out:
            out.append(tid)
            tid = self.data.get(tid, {}).get("next")
        return out

    # ── 시작 ──
    def can_start(self, tid: str) -> bool:
        tut = self.data.get(tid)
        if tut is None or self.game.save is None:
            return False
        st = self.st()
        replay = tid in st["replay"]
        if tid in st["done"] and not replay:
            return False
        if not st["enabled"] and not replay and not self.force_debug:
            return False
        if not replay:
            cur = self.run["id"] if self.run is not None else None
            if any(a not in st["done"] and a != cur for a in tut.get("after", [])):   # 진행 중인 앞 튜토리얼은 곧 끝남
                return False
        if tut.get("need_cond") and not conds.check(self.game, tut["need_cond"], None) and not replay:
            return False
        return True

    def request(self, tid: str) -> None:
        if tid not in self.queue and (self.run is None or self.run["id"] != tid) and self.can_start(tid):
            self.queue.append(tid)

    def start_now(self, tid: str) -> None:
        """디버그·다시 보기: 지금 바로 (조건 무시)."""
        self.queue = [q for q in self.queue if q != tid]
        if self.run is not None:
            self.run = None
        self._begin(tid)

    def _begin(self, tid: str) -> None:
        self.run = {"id": tid, "i": 0, "t": 0.0, "events": set(), "tapped": False, "nudge": 0.0, "ctx": {},
                    "sub": 0}
        self.st()["active"] = {"id": tid, "step": 0}
        from src.tutorial import scripts
        scripts.start(self.game, tid, self.run)

    def event(self, name: str, **info) -> None:
        """게임이 알려 주는 일: 진행 중 단계의 조건 + 다른 튜토리얼의 시작 조건."""
        if self.run is not None:
            self.run["events"].add(name)
            self.run["ctx"].setdefault("ev_info", {})[name] = info
        replay = self.st()["replay"] if self.game.save is not None else []
        for tid, tut in self.data.items():
            st = tut.get("start", "")
            if st == f"event:{name}" and tut.get("pattern"):
                # 패턴 튜토리얼: 예고 '그 순간'에만 (대기열에 넣지 않고 바로, 다른 튜토리얼 중이면 이번엔 넘김)
                if self.run is None and self.can_start(tid) and not conds.aside(self.game):
                    self._begin(tid)
            elif st == f"event:{name}":
                self.request(tid)
            elif tid in replay and name.startswith("spot_enter:") and st.startswith("event:spot_enter:"):
                self.request(tid)   # 다시 보기: 낚시 튜토리얼은 다음 낚시 때 (어느 낚시터든)

    # ── 진행 ──
    @property
    def step(self) -> dict | None:
        if self.run is None:
            return None
        steps = self.data[self.run["id"]]["steps"]
        return steps[self.run["i"]] if self.run["i"] < len(steps) else None

    def frozen(self) -> bool:
        """낚시 화면 시간 정지: 정지 지시·설명(그 화면에 있을 때)·건너뛰기 확인 창."""
        s = self.step
        if s is None:
            return False
        if self.modal:
            return True
        return s["kind"] in ("freeze", "info") and not self.run["ctx"].get("released")

    def released(self) -> bool:
        """정지 지시가 '그 순간'을 기다리는 중 (게임은 그대로 흐르고 안내도 숨김)."""
        return bool(self.run is not None and self.run["ctx"].get("released"))

    def _next(self, success: bool = False) -> None:
        r = self.run
        s = self.step
        if s and s.get("on_done"):
            from src.tutorial import scripts
            scripts.action(self.game, s["on_done"])
        if success and s and s["kind"] == "freeze" and s["until"] != "tap" and not self.data[r["id"]].get("no_ok"):
            self.ok_t = OK_SEC
            self.game.slowmo(SLOW_SEC, SLOW_SCALE)
        if self.run is not r:   # on_done 이 튜토리얼을 끝냈으면
            return
        r["i"] += 1
        r["t"] = 0.0
        r["events"] = set()
        r["tapped"] = False
        r["nudge"] = 0.0
        r["sub"] = 0
        for k in ("released", "start_ptr", "passed", "c_acc", "c_prev", "c_hist", "mash_n", "circle_k", "text", "anim",
                  "allow", "badge", "show", "dir"):
            r["ctx"].pop(k, None)
        self.st()["active"] = {"id": r["id"], "step": r["i"]}
        if self.step is None:
            self._finish()
        else:
            from src.tutorial import scripts
            scripts.on_step(self.game, r["id"], r)

    def update(self, dt: float) -> None:
        self.t += dt
        self.ok_t = max(0.0, self.ok_t - dt)
        if self.game.save is None:
            self.run, self.queue = None, []
            return
        if conds.aside(self.game):
            return   # 일시정지·설정·스토리 장면 중: 가이드도 멈춤
        if self.run is None:
            if self.queue and not conds.story_busy(self.game):
                tid = self.queue.pop(0)
                if self.can_start(tid):
                    self._begin(tid)
            return
        r = self.run
        r["t"] += dt
        r["nudge"] = max(0.0, r["nudge"] - dt)
        if self.modal:
            return
        from src.tutorial import scripts
        if scripts.tick(self.game, r["id"], r, dt):
            return   # 스크립트가 단계를 직접 진행 (패턴 튜토리얼 등)
        s = self.step
        if s is None:
            self._finish()
            return
        if self._satisfied(s):
            self._next(success=True)

    def _satisfied(self, s: dict) -> bool:
        r = self.run
        u = s["until"]
        if r["ctx"].get("released"):
            return False
        kind, _, arg = u.partition(":")
        if u == "tap":
            return r["tapped"]
        if kind == "event":
            return arg in r["events"]
        if kind == "scene":
            cur = self.game.scenes.current
            return cur is not None and type(cur).__name__ == arg
        if kind == "closed":
            return not any(type(sc).__name__ == arg for sc in self.game.scenes.stack)
        if kind == "auto":
            return r["t"] >= float(arg)
        if kind == "input":
            return conds.input_ok(self.game, arg, r)
        if kind == "cond":
            return conds.check(self.game, arg, r)
        return False

    # ── 입력 ──
    def skip_rect(self) -> pygame.Rect:
        """오른쪽 위 작게. 강조 대상이나 상점 소지금과 겹치면 왼쪽 위 → 왼쪽 아래로 비켜 남."""
        w, h = self.game.screen.canvas.get_size()
        x = w - 62
        if self.game.input.kind == "touch":   # 모바일: 오른쪽 위 가방 버튼 왼쪽
            from src.core.config import load_json
            x -= load_json("mobile_config.json")["hud_inset_px"] + self.game.screen.safe_x
        s = self.step
        avoid = targets.rects(self.game, "shop.money")
        if s is not None and s.get("target"):
            avoid += targets.rects(self.game, s["target"], self.run)
        for r in (pygame.Rect(x, 4, 58, 15), pygame.Rect(4 + self.game.screen.safe_x, 4, 58, 15),
                  pygame.Rect(4 + self.game.screen.safe_x, h - 19, 58, 15)):
            if not any(r.colliderect(a) for a in avoid):
                return r
        return pygame.Rect(x, 4, 58, 15)

    def _modal_rects(self):
        c = self.game.screen.canvas
        box = pygame.Rect(0, 0, 220, 64)
        box.center = (c.get_width() // 2, c.get_height() // 2)
        return box, pygame.Rect(box.x + 14, box.bottom - 24, 90, 17), pygame.Rect(box.right - 104, box.bottom - 24, 90, 17)

    def active(self) -> bool:
        """지금 화면에 가이드가 떠 있나 (끼어든 화면·스토리 중이면 숨김)."""
        return self.run is not None and self.step is not None and not conds.aside(self.game)

    def pass_event(self, event) -> bool:
        """원시 이벤트 단계: 건너뛰기·확인 창. False = 장면에 안 넘김."""
        if not self.active():
            return True
        if event.type in (pygame.MOUSEBUTTONDOWN, pygame.FINGERDOWN):
            pos = self._event_pos(event)
            if pos is not None:
                if self.modal:
                    box, b_skip, b_cont = self._modal_rects()
                    if b_skip.collidepoint(pos):
                        self.game.sfx.play("ui_click")
                        self._finish(skipped=True)
                    elif b_cont.collidepoint(pos):
                        self.game.sfx.play("ui_click")
                        self.modal = False
                    return False
                if self.skip_rect().collidepoint(pos):
                    self.modal = True
                    self.game.sfx.play("ui_click")
                    return False
        if self.modal:
            return event.type not in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN, pygame.FINGERDOWN)
        if event.type == pygame.KEYDOWN and self.step["kind"] != "wait":
            # 행동으로 바뀌지 않는 장면 전용 키(상점 ↑↓·L 등)는 가이드 중엔 막음
            from src.platform.input import KEY_ACTIONS, VIRTUAL_KEYS
            if event.key not in KEY_ACTIONS and event.key not in VIRTUAL_KEYS:
                return False
        return True

    def _event_pos(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            return self.game.to_canvas(event.pos)
        if event.type == pygame.FINGERDOWN:
            ww, wh = self.game.screen.window.get_size()
            return self.game.to_canvas((event.x * ww, event.y * wh))
        return None

    def allow_action(self, scene, a) -> bool:
        """행동 단계 (Scene.handle_event): 단계 종류별로 통과시킬지. 화면 좌표(a.pos)는 캔버스 기준."""
        if not self.active():
            return True
        s = self.step
        r = self.run
        k = s["kind"]
        if a.name in ("primary_up",):
            return True
        if a.name == "debug" or r["ctx"].get("released"):
            return True
        if k == "wait":
            return True
        if k == "info" or (k == "freeze" and s["until"] == "tap"):
            if (a.any_press or a.name in ("confirm", "reel_tap", "drag")) and r["t"] > 0.3:   # 모바일: 릴 패드·버튼을 눌러도 넘어감
                r["tapped"] = True
            return False
        if k == "spotlight":
            rects = targets.rects(self.game, s["target"], r)
            if not rects:
                return True   # 대상이 화면에 없으면 막지 않음 (갇히지 않게)
            keys = s.get("allow_keys", []) + targets.actions(self.game, s["target"])
            if f"{a.name}:{a.value}" in keys or a.name in keys:
                return True
            if a.pos is not None:
                if any(rc.collidepoint(a.pos) for rc in rects) or s.get("allow") == "anywhere":
                    return True
                r["nudge"] = 0.6
            return False
        if k == "freeze":
            ok = conds.allowed_actions(s["until"], r)
            if a.name in ok or f"{a.name}:{a.value}" in ok:
                if r["t"] >= conds.INPUT_DELAY:
                    r["ctx"].setdefault("passed", []).extend([a.name, f"{a.name}:{a.value}"])
                    return True
                return False
            if a.name in ("primary", "secondary", "drag", "scroll", "confirm"):
                r["nudge"] = 0.8   # 틀린 조작: 아무 일도 없고 조작 그림을 한 번 더 강조
            return False
        return True

    # ── 그리기 ──
    def text_of(self, s: dict) -> str:
        """문구: {이름} → 기기별 조작 이름, **굵게** → 노랑 (색 태그)."""
        txt = s["text"]
        alt = conds.dynamic_text(self.game, s, self.run)
        if alt:
            txt = alt
        touch = self.game.input.kind == "touch"

        def sub(m):
            v = self.inputs.get(m.group(1))
            return (v["mobile"] if touch else v["pc"]) if v else m.group(0)
        txt = re.sub(r"\{([^}/]+)\}", sub, txt)
        return re.sub(r"\*\*(.+?)\*\*", r"{gold}\1{/}", txt)

    def _sub(self, txt: str) -> str:
        touch = self.game.input.kind == "touch"
        return re.sub(r"\{([^}/]+)\}", lambda m: (self.inputs[m.group(1)]["mobile" if touch else "pc"]
                                                    if m.group(1) in self.inputs else m.group(0)), txt)

    def who(self) -> str:
        return self.data[self.run["id"]].get("who", "haru") if self.run else "haru"

    def draw(self, canvas) -> None:
        from src.tutorial import overlay
        if self.ok_t > 0:
            overlay.ok_banner(canvas, self.ok_text, self.ok_t / OK_SEC)
        if not self.active():
            return
        s = self.step
        r = self.run
        rects = targets.rects(self.game, s["target"], r) if s.get("target") else []
        k = s["kind"]
        if r["ctx"].get("released"):
            if r["ctx"].get("show"):   # 머리 흔들기: 문구를 띄운 채 진행
                overlay.box(canvas, self.text_of(s), self.who(), s.get("expr") or "neutral", rects, "wait", self.t,
                            small=True)
                if r["ctx"].get("badge") and rects:
                    overlay.badge(canvas, r["ctx"]["badge"], (rects[0].centerx, rects[0].bottom + 10))
            overlay.skip_button(canvas, self.skip_rect(), self.game.input.pointer)
            return
        if k != "wait" and (rects or k != "spotlight"):
            overlay.dim(canvas, rects, self.t)
        expr = s.get("expr") or {"haru": "happy", "ella": "neutral", "baek": "neutral"}.get(self.who(), "neutral")
        overlay.box(canvas, self.text_of(s), self.who(), expr, rects, k, self.t, small=k == "wait",
                    more=k == "info" or (k == "freeze" and s["until"] == "tap"))
        if k == "freeze" and s["until"] != "tap":
            how = conds.anim_of(self.game, s["until"], r)
            if how:
                pos = conds.anim_pos(self.game, s, r, rects)
                overlay.input_anim(canvas, how, pos, self.t, self.game.input.kind == "touch", r["nudge"])
                if r["ctx"].get("circle_k") is not None and how == "circle":
                    overlay.progress_ring(canvas, pos, r["ctx"]["circle_k"])
            if r["ctx"].get("badge"):
                bp = (rects[0].centerx, rects[0].bottom + 10) if rects else (canvas.get_width() // 2, 90)
                overlay.badge(canvas, r["ctx"]["badge"], bp)
            for txt, pos in r["ctx"].get("labels", []):   # 이중 패턴: 슬롯마다 조작 이름
                overlay.badge(canvas, self._sub(txt), pos)
        overlay.skip_button(canvas, self.skip_rect(), self.game.input.pointer)
        if self.modal:
            overlay.modal(canvas, *self._modal_rects())
        from src.ui import hud
        if self.game.input.kind != "touch":
            hud.draw_cursor(canvas, self.game.input.pointer)   # 어둡게 한 막 위로 커서
