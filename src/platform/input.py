"""입력 추상화 (DESIGN.md 26-5). 씬은 마우스·키보드·터치를 직접 읽지 않고 '행동'만 받는다.

이벤트형 행동 (Action, 씬의 handle_action 으로 전달)
  primary / primary_up   주 입력 누름·뗌 (캐스팅·챔질·뜰채·버튼)     PC: 좌클릭       모바일: 탭
  secondary              보조 입력 (파이팅=숙이기, 대기=회수)          PC: 우클릭       모바일: 버튼
  click_other            그 밖의 마우스 버튼 (도움말·카드 닫기용)      PC: 가운데·휠 버튼
  scroll (value=±n)      목록 스크롤 / 낚시 중엔 드랙                  PC: 휠           모바일: 드래그
  drag (value=±1)        드랙 올리기·내리기                           PC: E / Q        모바일: ▲▼
  item (value=1|2)       소모품                                      PC: 1 / 2        모바일: 🧪
  menu (value=shop|dex|map|chest)                                    PC: B/Tab/M/C    모바일: 🎒
  back                   뒤로·일시정지                                PC: ESC          모바일: 뒤로 가기
  confirm                연출 넘기기                                  PC: Space/Enter  모바일: 탭
  help / time_fast / debug(value=F1~F6)                              PC: H / T / F1~F6
상태형 (매 틱 읽기)
  pointer       캔버스 좌표 (화면 밖이면 가장자리로)   pointer_raw  자르지 않은 좌표
  held("reel")  릴 감기 유지                         PC: 좌클릭 유지
  held("press") 주 입력 누르고 있음 (루어 감기)        PC: 좌클릭 유지  모바일: 수면·패드 누르기
  held("drag_min") 드랙 순간 최저                     PC: Shift        모바일: ▼ 길게 누르기
  rod_pitch()   낚싯대 상하 -1~1 (None = 중립)        PC: 마우스 위아래 모바일: 릴 패드 노브 위아래
  circle_sample(min_px) 원 그리기 표본 (pos, 중심|None, 최소 반경)
  연타          PC: 파이팅 중 primary 하나하나        모바일: reel_tap (릴 패드 누를 때마다)
  (상태 → 이벤트 변환은 src/platform/gesture.py)
"""
from dataclasses import dataclass

import pygame

KEY_ACTIONS = {
    pygame.K_ESCAPE: ("back", 0),
    pygame.K_b: ("menu", "shop"),
    pygame.K_TAB: ("menu", "dex"),
    pygame.K_m: ("menu", "map"),
    pygame.K_c: ("menu", "chest"),
    pygame.K_i: ("menu", "inventory"),
    pygame.K_j: ("menu", "quests"),
    pygame.K_h: ("help", 0),
    pygame.K_t: ("time_fast", 0),
    pygame.K_q: ("drag", -1),
    pygame.K_e: ("drag", +1),
    pygame.K_1: ("item", 1),
    pygame.K_2: ("item", 2),
    pygame.K_SPACE: ("confirm", 0),
    pygame.K_RETURN: ("confirm", 0),
    pygame.K_F1: ("debug", "F1"),
    pygame.K_F2: ("debug", "F2"),
    pygame.K_F3: ("debug", "F3"),
    pygame.K_F4: ("debug", "F4"),
    pygame.K_F5: ("debug", "F5"),
    pygame.K_F6: ("debug", "F6"),
    pygame.K_F7: ("debug", "F7"),
    pygame.K_F8: ("debug", "F8"),
    pygame.K_F9: ("debug", "F9"),
    pygame.K_F10: ("debug", "F10"),
    pygame.K_F11: ("debug", "F11"),
}


@dataclass
class Action:
    name: str
    value: object = 0
    pos: tuple[int, int] | None = None  # 캔버스 좌표 (포인터 행동만)

    def is_(self, name: str, value=None) -> bool:
        return self.name == name and (value is None or self.value == value)

    @property
    def any_press(self) -> bool:
        """아무 버튼이나 누름 (카드·도움말 닫기)."""
        return self.name in ("primary", "secondary", "click_other")


class PcInput:
    """PC: 지금까지의 마우스·키보드 조작 그대로."""
    kind = "pc"

    def __init__(self, game):
        self.game = game

    def translate(self, event) -> Action | None:
        et = event.type
        if et == pygame.MOUSEBUTTONDOWN:
            pos = self.game.to_canvas(event.pos)
            name = {1: "primary", 3: "secondary"}.get(event.button, "click_other")
            return Action(name, event.button, pos)
        if et == pygame.MOUSEBUTTONUP and event.button == 1:
            return Action("primary_up", 1, self.game.to_canvas(event.pos))
        if et == pygame.MOUSEWHEEL:
            return Action("scroll", event.y)
        if et == pygame.KEYDOWN and event.key in KEY_ACTIONS:
            name, value = KEY_ACTIONS[event.key]
            return Action(name, value)
        return None

    @property
    def pointer(self) -> tuple[int, int]:
        return self.game.to_canvas(pygame.mouse.get_pos())

    @property
    def pointer_raw(self) -> tuple[int, int]:
        return self.game.screen.to_canvas(pygame.mouse.get_pos())

    def held(self, name: str) -> bool:
        if name in ("reel", "press"):
            return bool(pygame.mouse.get_pressed()[0])
        if name == "drag_min":
            return bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)
        return False

    def rod_pitch(self) -> float | None:
        """화면 가운데보다 위 = 올림 (+), 아래 = 내림 (-)."""
        h = self.game.screen.height
        return (h / 2 - self.pointer[1]) / (h * controls_cfg()["pc_pitch_range"])

    def circle_sample(self, min_px: float):
        return self.pointer, None, min_px  # 중심은 최근 마우스 위치들의 평균

    def aim_override(self, fighting: bool):
        return None  # PC: 조준은 마우스 위치

    def consume_look(self) -> float:
        return 0.0  # PC: 둘러보기는 화면 끝에 마우스


# 미리보기에서 키보드로 누르는 터치 버튼 (platform/preview.py 설명)
VIRTUAL_KEYS = {pygame.K_SPACE: "dip", pygame.K_UP: "drag_up", pygame.K_DOWN: "drag_down", pygame.K_f: "pad",
                pygame.K_r: "retrieve"}


class TouchInput(PcInput):
    """모바일 터치 (DESIGN.md 26-10). 미리보기 모드에선 마우스 왼쪽 버튼이 손가락 하나.

    메뉴 씬   : 손가락을 떼는 순간 primary (조금이라도 끌면 탭이 아니라 스크롤), 끌기 = scroll, 길게 누르기 = 툴팁 유지.
    낚시 씬   : touch_ui 버튼 + 화면 영역.
      수면 누르기  = primary (던지기 충전·챔질·뜰채·넘기기), 손가락 위치 = 조준, 떼기 = primary_up
      하늘 끌기    = 둘러보기 (대기 중)
      릴 패드      = 누르는 동안 감기, 노브 좌우 = 낚싯대 방향, 빠르게 튕기기 = 꺾기(flick)
      숙이기/회수  = secondary, ▲▼ = drag, 도구 = item, 일시정지 = back, 가방 = menu(bag)
    여러 손가락을 동시에 따로 추적한다 (릴 패드 누른 채 숙이기 등).
    """
    kind = "touch"

    def __init__(self, game):
        super().__init__(game)
        self.fingers: dict = {}
        self._pointer = (-100, -100)
        self.look_dx = 0.0
        self.aim = 0.0
        self.items_open = False
        self.flick_ready_ms = 0
        self.pitch = 0.0
        self.controls: list = []

    # ── 원시 이벤트 → 손가락 ──
    def translate(self, event):
        et = event.type
        if et in (pygame.KEYDOWN, pygame.KEYUP) and event.key in VIRTUAL_KEYS:
            # 키보드 = 두 번째 손가락 (미리보기·키보드 달린 기기): 낚시 화면의 그 버튼을 누른 것과 같다
            fid = ("key", event.key)
            if et == pygame.KEYUP:
                return self._up(fid, self.fingers[fid]["pos"], pygame.time.get_ticks()) if fid in self.fingers else None
            ctx = self._scene_ctx()
            if ctx is not None and fid not in self.fingers:
                from src.platform import touch_ui
                ctrls = touch_ui.layout(self.game.screen.width, self.game.screen.height, ctx, self.game.settings,
                                        self.items_open)
                c = next((c for c in ctrls if c.id == VIRTUAL_KEYS[event.key]), None)
                if c is not None:
                    return self._down(fid, c.center, pygame.time.get_ticks())
        if et == pygame.KEYDOWN:
            if event.key == pygame.K_AC_BACK:
                return Action("back")
            return super().translate(event)  # 미리보기에서 키보드도 그대로
        if et in (pygame.FINGERDOWN, pygame.FINGERMOTION, pygame.FINGERUP):
            ww, wh = self.game.screen.window.get_size()
            pos = self.game.screen.to_canvas((event.x * ww, event.y * wh))
            fid = event.finger_id
            kind = {pygame.FINGERDOWN: "down", pygame.FINGERMOTION: "move", pygame.FINGERUP: "up"}[et]
        elif et in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION):
            if getattr(event, "touch", False):
                return None  # 터치가 만든 가짜 마우스 이벤트 (손가락 이벤트로 이미 처리)
            if et == pygame.MOUSEMOTION:
                if not event.buttons[0]:
                    return None
                kind = "move"
            elif event.button != 1:
                return None
            else:
                kind = "down" if et == pygame.MOUSEBUTTONDOWN else "up"
            pos, fid = self.game.screen.to_canvas(event.pos), "mouse"
        elif et == pygame.MOUSEWHEEL and not getattr(event, "touch", False):
            return Action("scroll", event.y)
        else:
            return None
        w, h = self.game.screen.width, self.game.screen.height
        pos = (max(0, min(w - 1, pos[0])), max(0, min(h - 1, pos[1])))
        now = pygame.time.get_ticks()
        if kind == "down":
            if fid in self.fingers:
                return None
            return self._down(fid, pos, now)
        if fid not in self.fingers:
            return None
        if kind == "move":
            return self._move(fid, pos, now)
        return self._up(fid, pos, now)

    def _scene_ctx(self):
        sc = self.game.scenes.current
        return sc.touch_context() if hasattr(sc, "touch_context") else None

    def _down(self, fid, pos, now):
        ctx = self._scene_ctx()
        f = {"start": pos, "pos": pos, "t0": now, "moved": False, "sy": pos[1], "role": "menu", "hist": [(now, pos[0])]}
        self.fingers[fid] = f
        if len(self.fingers) >= 5 and cfg().get("debug_build"):
            # 디버그 빌드만: 다섯 손가락 탭 = 수치 표시(F1). 릴리스 APK에선 꺼져 있다 (MOBILE.md 4번)
            for g in self.fingers.values():
                g["role"] = "ignored"
            return Action("debug", "F1")
        if ctx is None:
            self._pointer = pos
            return None
        from src.platform import touch_ui
        self.controls = touch_ui.layout(self.game.screen.width, self.game.screen.height, ctx, self.game.settings,
                                        self.items_open)
        hit = next((c for c in self.controls if c.hit(pos)), None)
        if hit is None:
            self.items_open = False
            if ctx.get("can_look") and pos[1] < ctx["horizon"]:
                f["role"] = "look"
                return None
            f["role"] = "water"
            self._pointer = pos
            return Action("primary", 1, pos)
        f["role"] = hit.id
        if hit.id != "item" and not hit.id.startswith("item"):
            self.items_open = False
        if hit.id == "pad":
            self._pad_aim(hit, pos)
            return Action("reel_tap")
        if hit.id == "item":
            self.items_open = not self.items_open
            return None
        if hit.id.startswith("item"):
            self.items_open = False
            return Action("item", int(hit.id[4:]))
        return {"pause": Action("back"), "bag": Action("menu", "bag"), "dip": Action("secondary", 3, pos),
                "retrieve": Action("secondary", 3, pos), "drag_up": Action("drag", +1),
                "drag_down": Action("drag", -1)}.get(hit.id)

    def _move(self, fid, pos, now):
        f = self.fingers[fid]
        c = cfg()
        prev = f["pos"]
        f["pos"] = pos
        if abs(pos[0] - f["start"][0]) + abs(pos[1] - f["start"][1]) > c["tap_slop_px"]:
            f["moved"] = True
        role = f["role"]
        if role == "menu":
            self._pointer = pos
            out = []
            dy = pos[1] - f["sy"]
            step = c["scroll_step_px"]
            while f["moved"] and abs(dy) >= step:
                d = 1 if dy > 0 else -1
                out.append(Action("scroll", d))
                f["sy"] += d * step
                dy = pos[1] - f["sy"]
            return out or None
        if role == "water":
            self._pointer = pos
        elif role == "look":
            self.look_dx += pos[0] - prev[0]
        elif role == "pad":
            pad = next((ct for ct in self.controls if ct.id == "pad"), None)
            if pad:
                self._pad_aim(pad, pos)
            f["hist"].append((now, pos[0]))
            # 시간 창 안의 기록 + 그 직전 위치(손가락이 멈춰 있던 곳)를 시작점으로
            old = [(t, x) for t, x in f["hist"] if now - t > c["flick_ms"]]
            f["hist"] = ([(now - c["flick_ms"], old[-1][1])] if old else []) + \
                [(t, x) for t, x in f["hist"] if now - t <= c["flick_ms"]]
            dx = f["hist"][-1][1] - f["hist"][0][1]
            if abs(dx) >= c["flick_px"] and now >= self.flick_ready_ms:
                self.flick_ready_ms = now + c["flick_cooldown_ms"]
                f["hist"] = [(now, pos[0])]
                return Action("flick", 1 if dx > 0 else -1)
        return None

    def _up(self, fid, pos, now):
        f = self.fingers.pop(fid)
        role = f["role"]
        if role == "menu":
            long_press = now - f["t0"] >= cfg()["long_press_ms"]
            # 길게 누르면 그 자리에 포인터를 남겨 툴팁이 계속 보이게, 탭이면 숨김 (버튼 강조가 남지 않게)
            self._pointer = pos if long_press else (-100, -100)
            if f["moved"]:
                return None
            return [Action("primary", 1, pos), Action("primary_up", 1, pos)]
        if role == "water":
            return Action("primary_up", 1, pos)
        return None

    def _pad_aim(self, pad, pos) -> None:
        self.aim = max(-1.0, min(1.0, (pos[0] - pad.center[0]) / max(1, pad.r)))
        self.pitch = max(-1.0, min(1.0, (pad.center[1] - pos[1]) / max(1, pad.r * cfg()["pad_pitch_range"])))

    # ── 상태 ──
    @property
    def pointer(self) -> tuple[int, int]:
        return self._pointer

    @property
    def pointer_raw(self) -> tuple[int, int]:
        return self._pointer

    def held(self, name: str) -> bool:
        roles = [f["role"] for f in self.fingers.values()]
        if name == "reel":
            return "pad" in roles
        if name == "press":
            return "pad" in roles or "water" in roles
        if name == "drag_min":
            now = pygame.time.get_ticks()
            return any(f["role"] == "drag_down" and now - f["t0"] >= cfg()["drag_min_hold_ms"]
                       for f in self.fingers.values())
        return False

    def _pad_finger(self):
        return next((f for f in self.fingers.values() if f["role"] == "pad"), None)

    def rod_pitch(self) -> float | None:
        return self.pitch if self._pad_finger() is not None else None  # 손을 떼면 중립

    def circle_sample(self, min_px: float):
        f = self._pad_finger()
        pad = next((c for c in self.controls if c.id == "pad"), None)
        if f is None or pad is None:
            return None
        return f["pos"], pad.center, pad.r * cfg()["circle_min_frac"]  # 패드 가운데 둘레로 돌리기

    def pressed_controls(self) -> set:
        return {f["role"] for f in self.fingers.values()}

    def aim_override(self, fighting: bool):
        return self.aim if fighting else None

    def consume_look(self) -> float:
        d, self.look_dx = self.look_dx, 0.0
        return d


def cfg() -> dict:
    from src.core.config import load_json
    return load_json("mobile_config.json")


def controls_cfg() -> dict:
    from src.core.config import load_json
    return load_json("fishing_config.json")["controls"]


def create_input(game):
    from src.platform.detect import IS_MOBILE
    return TouchInput(game) if IS_MOBILE else PcInput(game)
