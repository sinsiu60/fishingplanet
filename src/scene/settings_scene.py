"""설정.

PC     : 탭 두 개 — [화면·소리] 음량, 화면 연출, 화면 배율, 튜토리얼 다시 보기, 소리 자막, 세이브 옮기기
                    [접근성] 예고 시간 배율, 첫 만남 카드, 신호 크기, 색약 모드, 소리 신호 (31장 C6)
모바일 : 탭 세 개 — [화면·소리] 음량, 화면 연출, 소리 자막, 튜토리얼
                    [터치·기기] 터치 버튼 크기·진하기, 왼손잡이, 진동(끔/약/중/강), 화면 갱신(30/60), 세이브 옮기기
                    [접근성] PC와 같음
"""
from src.platform.detect import IS_MOBILE
from src.platform.haptics import LEVEL_NAMES
from src.save.settings import TELE_MULTS
from src.scene.base import Scene
from src.ui import widgets as ui
from src.ui.hud import draw_cursor, text

ROW_X = 150  # 줄 이름 오른쪽에 조절 버튼


class SettingsScene(Scene):
    UI_FRAME = True

    def __init__(self, game):
        super().__init__(game)
        self.mouse = (0, 0)
        self.msg = ""
        self.msg_t = 0.0
        self.w = game.screen.ui_rect.w
        self.x0 = self.w // 2 - 140
        if IS_MOBILE:
            self.tabs = ui.Tabs(self.w // 2 - 137, 56, ["화면·소리", "터치·기기", "접근성"], width=90)
        else:
            self.tabs = ui.Tabs(self.w // 2 - 102, 56, ["화면·소리", "접근성"], width=100)
        self._build()

    # ── 줄 정의: (이름, 종류, 값 글자 함수, 동작들) ──
    def _rows(self) -> list[tuple]:
        s = self.s
        sound = [
            ("음량", "volume", None, (lambda: self._volume(-0.1), lambda: self._volume(0.1))),
            ("화면 연출 (흔들림·줌)", "toggle", lambda: s.get("screen_shake"), self._toggle_fx),
        ]
        tutorial = ("튜토리얼", "button", lambda: "처음부터 다시 보기", self._reset_tutorial)
        captions = ("소리 자막 (예고음 글자로)", "toggle", lambda: s.get("sound_captions"), self._toggle_captions)
        transfer = ("세이브 옮기기 (PC·모바일)", "button", lambda: "열기", self._open_transfer)
        if self.tabs.labels[self.tabs.index] == "접근성":
            return self._access_rows()
        if not IS_MOBILE:
            scale = ("화면 배율", "step", lambda: f"{self.game.screen.scale}배 (최대 {self._max_scale()})",
                     (lambda: self._scale(-1), lambda: self._scale(1)))
            return sound + [scale, tutorial, captions, transfer]
        if self.tabs.index == 0:
            return sound + [captions, tutorial]
        size = ("터치 버튼 크기", "step", lambda: ("작게", "보통", "크게")[s.get("touch_size")],
                (lambda: self._step("touch_size", -1, 2), lambda: self._step("touch_size", 1, 2)))
        alpha = ("터치 버튼 진하기", "step", lambda: ("흐리게", "보통", "진하게")[s.get("touch_alpha")],
                 (lambda: self._step("touch_alpha", -1, 2), lambda: self._step("touch_alpha", 1, 2)))
        left = ("왼손잡이 (버튼 좌우 반전)", "toggle", lambda: s.get("touch_left"),
                lambda: s.set("touch_left", not s.get("touch_left")))
        vib = ("진동", "step", lambda: LEVEL_NAMES[s.get("vibration")],
               (lambda: self._step("vibration", -1, 3), lambda: self._vib_step()))
        fps = ("화면 갱신 (배터리)", "button", lambda: f"초당 {s.get('fps')}번",
               lambda: s.set("fps", 30 if s.get("fps") == 60 else 60))
        return [size, alpha, left, vib, fps, transfer]

    def _access_rows(self) -> list[tuple]:
        """접근성 (31장 C6). 예고 배율은 랭크 판정에 영향 없음 — 결과 화면에 작게 표시."""
        s = self.s
        tele = ("예고 시간 배율", "step", lambda: f"{TELE_MULTS[s.get('tele_mult')]}배",
                (lambda: self._step("tele_mult", -1, 2), lambda: self._step("tele_mult", 1, 2)))
        cards = ("첫 만남 신호 카드", "toggle", lambda: s.get("signal_cards"),
                 lambda: s.set("signal_cards", not s.get("signal_cards")))
        slot = ("신호 크기", "step", lambda: ("작게", "보통", "크게")[s.get("slot_size")],
                (lambda: self._step("slot_size", -1, 2), lambda: self._step("slot_size", 1, 2)))
        cb = ("색약 모드 (고대비 신호색)", "toggle", lambda: s.get("colorblind"),
              lambda: s.set("colorblind", not s.get("colorblind")))
        snd = ("소리 신호 (끄면 그림 강조)", "toggle", lambda: s.get("signal_sound"),
               lambda: s.set("signal_sound", not s.get("signal_sound")))
        return [tele, cards, slot, cb, snd]

    def _build(self) -> None:
        x = self.x0 + ROW_X
        y0, step, back_y = 86, 24, 226
        self.rows = self._rows()
        self.rows_y = [y0 + i * step for i in range(len(self.rows))]
        self.buttons = []
        for (label, kind, value, act), y in zip(self.rows, self.rows_y):
            if kind in ("volume", "step"):
                self.buttons.append(ui.Button((x, y - 8, 18, 16), "-", act[0]))
                self.buttons.append(ui.Button((x + 104, y - 8, 18, 16), "+", act[1]))
            else:
                self.buttons.append(ui.Button((x, y - 8, 122, 16), "", act))
        self.back_btn = ui.Button((self.w // 2 - 40, back_y, 80, 18), "뒤로", self._back)
        self.buttons.append(self.back_btn)

    @property
    def s(self):
        return self.game.settings

    def _volume(self, d: float) -> None:
        v = round(min(1.0, max(0.0, self.s.get("volume") + d)), 1)
        self.s.set("volume", v)
        self.game.sfx.volume = v

    def _step(self, key: str, d: int, top: int) -> None:
        self.s.set(key, max(0, min(top, self.s.get(key) + d)))

    def _vib_step(self) -> None:
        self._step("vibration", 1, 3)
        self.game.haptics.vibrate("bite")  # 세기 맛보기

    def _toggle_fx(self) -> None:
        self.s.set("screen_shake", not self.s.get("screen_shake"))
        for scene in self.game.scenes.stack:
            if hasattr(scene, "apply_settings"):
                scene.apply_settings()

    def _toggle_captions(self) -> None:
        self.s.set("sound_captions", not self.s.get("sound_captions"))

    def _max_scale(self) -> int:
        return max(1, self.game.screen._best_scale())

    def _scale(self, d: int) -> None:
        cur = self.game.screen.scale
        new = min(self._max_scale(), max(1, cur + d))
        if new != cur:
            self.game.screen.set_scale(new)
            self.s.set("scale", new)

    def _reset_tutorial(self) -> None:
        self.s.set("tutorial_seen", [])
        for scene in self.game.scenes.stack:
            if hasattr(scene, "tutorial"):
                scene.tutorial.seen.clear()
        self.msg, self.msg_t = "튜토리얼을 처음부터 다시 보여드려요", 2.0

    def _open_transfer(self) -> None:
        from src.scene.save_transfer import SaveTransferScene
        self.game.scenes.push(SaveTransferScene(self.game))

    def _back(self) -> None:
        self.game.scenes.pop()

    def handle_action(self, a) -> None:
        if a.name == "back":
            self._back()
        elif a.name == "primary":
            m = a.pos
            if self.tabs.click(m):
                self.game.sfx.play("click")
                self._build()
                return
            for b in self.buttons:
                if b.click(m):
                    self.game.sfx.play("click")
                    break

    def update(self, dt: float) -> None:
        self.mouse = self.ui_pointer()
        self.msg_t = max(0.0, self.msg_t - dt)
        under = self.game.scenes.stack[0]
        if hasattr(under, "bg"):
            under.bg.update(dt)

    def draw(self, canvas) -> None:
        under = self.scene_below()
        if under is not None:
            under.draw(canvas)
        ui.dim(canvas, 170)
        canvas = self.ui_canvas(canvas)
        w = canvas.get_width()
        ui.panel(canvas, (self.x0 - 10, 30, 300, 218))
        text(canvas, "설정", (w // 2, 44), ui.ACCENT, 16, "center")
        self.tabs.draw(canvas, self.mouse)
        x = self.x0 + ROW_X
        bi = 0
        for (label, kind, value, act), y in zip(self.rows, self.rows_y):
            text(canvas, label, (self.x0, y), ui.TEXT, 11, "midleft")
            if kind == "volume":
                ui.bar(canvas, (x + 22, y - 4, 78, 8), self.s.get("volume"), (140, 200, 255))
                bi += 2
            elif kind == "step":
                text(canvas, value(), (x + 61, y), ui.TEXT, 11, "center")
                bi += 2
            else:
                v = value()
                self.buttons[bi].label = ("켬" if v else "끔") if kind == "toggle" else v
                bi += 1
        for b in self.buttons:
            b.draw(canvas, self.mouse)
        if self.msg_t > 0:
            text(canvas, self.msg, (w // 2, 240), ui.GOOD, 11, "center")
        draw_cursor(canvas, self.mouse)
