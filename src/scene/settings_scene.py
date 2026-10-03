"""설정.

PC     : 탭 세 개 — [화면] 화면 연출, 화면 배율, 튜토리얼 다시 보기, 소리 자막, 세이브 옮기기
                    [소리] 전체·음악·효과음·환경음 볼륨, 신호 강조, 오디오 지연 보정, 사운드 테스트 룸 (32장 S3)
                    [접근성] 예고 시간 배율, 첫 만남 카드, 신호 크기, 색약 모드, 소리 신호 (31장 C6)
모바일 : 탭 네 개 — [화면] 화면 연출, 소리 자막, 튜토리얼 / [소리] PC와 같음
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
            self.tabs = ui.Tabs(self.w // 2 - 136, 56, ["화면", "소리", "터치·기기", "접근성"], width=66)
        else:
            self.tabs = ui.Tabs(self.w // 2 - 110, 56, ["화면", "소리", "접근성"], width=72)
        self._build()

    # ── 줄 정의: (이름, 종류, 값 글자 함수, 동작들) ──
    def _rows(self) -> list[tuple]:
        s = self.s
        sound = [
            ("화면 연출 (흔들림·줌)", "toggle", lambda: s.get("screen_shake"), self._toggle_fx),
            ("찌 확대 창 (말풍선)", "toggle", lambda: s.get("bobber_zoom"), lambda: s.set("bobber_zoom", not s.get("bobber_zoom"))),
        ]
        tutorial = ("튜토리얼", "button", lambda: "처음부터 다시 보기", self._reset_tutorial)
        captions = ("소리 자막 (예고음 글자로)", "toggle", lambda: s.get("sound_captions"), self._toggle_captions)
        transfer = ("세이브 옮기기 (PC·모바일)", "button", lambda: "열기", self._open_transfer)
        tab = self.tabs.labels[self.tabs.index]
        if tab == "접근성":
            return self._access_rows()
        if tab == "소리":
            return self._sound_rows()
        if not IS_MOBILE:
            scale = ("화면 배율", "step", lambda: f"{self.game.screen.scale}배 (최대 {self._max_scale()})",
                     (lambda: self._scale(-1), lambda: self._scale(1)))
            return sound + [scale, tutorial, captions, transfer]
        if tab == "화면":
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
        perf = ("성능 표시 (FPS·처리 시간)", "toggle", lambda: s.get("perf_overlay"),
                lambda: s.set("perf_overlay", not s.get("perf_overlay")))
        return [size, alpha, left, vib, fps, perf, transfer]

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

    def _sound_rows(self) -> list[tuple]:
        """소리 (32장 S3): 버스 볼륨 4개, 신호음 모드(N2), 성공 효과음·파이팅 음악(32-16), 신호 때 배경 줄이기, 오디오 지연 보정, 사운드 테스트 룸."""
        s = self.s

        def vol(label, key):
            return (label, "volume", lambda: key, (lambda: self._vol(key, -0.1), lambda: self._vol(key, 0.1)))
        mode = ("신호음", "step", lambda: ("자연음", "보조음", "강조")[s.get("signal_mode")],
                (lambda: self._step("signal_mode", -1, 2), lambda: self._step("signal_mode", 1, 2)))
        zing = ("성공 효과음 (지이이잉)", "toggle", lambda: s.get("success_sfx"),
                lambda: s.set("success_sfx", not s.get("success_sfx")))
        fmus = ("파이팅 음악", "toggle", lambda: s.get("fight_music"),
                lambda: s.set("fight_music", not s.get("fight_music")))
        boost = ("신호 때 배경 줄이기", "toggle", lambda: s.get("signal_boost"), self._toggle_boost)
        offset = ("오디오 지연 보정", "step", lambda: f"{s.get('audio_offset_ms'):+d}ms",
                  (lambda: self._offset(-10), lambda: self._offset(10)))
        test = ("사운드 테스트 룸", "button", lambda: "열기", self._open_sound_test)
        return [vol("전체 음량", "volume"), vol("음악", "vol_music"), vol("효과음", "vol_sfx"), vol("환경음", "vol_amb"),
                mode, zing, fmus, boost, offset, test]

    def _vol(self, key: str, d: float) -> None:
        self.s.set(key, round(min(1.0, max(0.0, self.s.get(key) + d)), 1))
        self.game.apply_audio_settings()
        self.game.sfx.play("sfx_hook_success" if key == "vol_sfx" else "ui_click", 0.6)

    def _toggle_boost(self) -> None:
        self.s.set("signal_boost", not self.s.get("signal_boost"))
        self.game.apply_audio_settings()

    def _offset(self, d: int) -> None:
        from src.core.config import load_json
        lo, hi = load_json("audio_config.json")["audio_offset_range_ms"]
        self.s.set("audio_offset_ms", max(lo, min(hi, self.s.get("audio_offset_ms") + d)))

    def _open_sound_test(self) -> None:
        from src.scene.sound_test import SoundTestScene
        self.game.scenes.push(SoundTestScene(self.game))

    def _build(self) -> None:
        x = self.x0 + ROW_X
        self.rows = self._rows()
        y0, back_y = 86, 226
        step = 24 if len(self.rows) <= 6 else 19 if len(self.rows) <= 7 else 18 if len(self.rows) <= 8 else 16
        bh = 16
        if len(self.rows) > 9:   # 소리 탭 10줄: 조금 위에서 촘촘히
            y0, step, bh = 82, 15, 14
        self.rows_y = [y0 + i * step for i in range(len(self.rows))]
        self.buttons = []
        for (label, kind, value, act), y in zip(self.rows, self.rows_y):
            if kind in ("volume", "step"):
                self.buttons.append(ui.Button((x, y - bh // 2, 18, bh), "-", act[0]))
                self.buttons.append(ui.Button((x + 104, y - bh // 2, 18, bh), "+", act[1]))
            else:
                self.buttons.append(ui.Button((x, y - bh // 2, 122, bh), "", act))
        self.back_btn = ui.Button((self.w // 2 - 40, back_y, 80, 18), "뒤로", self._back)
        self.buttons.append(self.back_btn)

    @property
    def s(self):
        return self.game.settings


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
                self.game.sfx.play("ui_tab")
                self._build()
                return
            for b in self.buttons:
                if b.click(m):
                    self.game.sfx.play("ui_click")
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
                ui.bar(canvas, (x + 22, y - 4, 78, 8), self.s.get(value()), (140, 200, 255))
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
