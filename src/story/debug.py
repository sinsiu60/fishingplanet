"""스토리 디버그 (DESIGN.md 36, ST2): 장면 ID로 바로 재생 · 막 강제 변경 · 스토리 플래그 보기. 릴리스(debug_keys·debug_build 꺼짐)에선 안 보임."""
import json

from src.core.config import load_json
from src.scene.base import Scene
from src.story import story
from src.ui import widgets as ui
from src.ui.hud import draw_cursor, text


def enabled() -> bool:
    return bool(load_json("fishing_config.json").get("debug_keys") or load_json("mobile_config.json").get("debug_build"))


class StoryDebugScene(Scene):
    UI_FRAME = True

    def __init__(self, game, fishing):
        super().__init__(game)
        self.fishing = fishing
        self.mouse = (0, 0)
        ids = [k for k in story.scenes() if not k.startswith("_")]
        self.btns = []
        for i, sid in enumerate(ids):
            r = (14 + (i % 6) * 76, 40 + (i // 6) * 20, 72, 16)
            self.btns.append(ui.Button(r, sid, lambda s=sid: self._play(s)))
        self.chap_btn = ui.Button((14, 160, 140, 16), "", self._chapter)
        self.close_btn = ui.Button((404, 248, 60, 15), "닫기", lambda: self.game.scenes.pop())

    def _play(self, sid: str) -> None:
        from src.story import runner
        runner.replay(self.game, self.fishing, sid)

    def _chapter(self) -> None:
        st = story.state(self.game.save)
        st["flags"]["force_chapter"] = (st["flags"].get("force_chapter", -1) + 2) % 8 - 1   # -1(끔) → 0 … 6
        if st["flags"]["force_chapter"] < 0:
            st["flags"].pop("force_chapter")

    def handle_action(self, a) -> None:
        if a.name == "back":
            self.game.scenes.pop()
        elif a.name == "primary":
            for b in self.btns + [self.chap_btn, self.close_btn]:
                if b.click(a.pos):
                    return

    def update(self, dt: float) -> None:
        self.mouse = self.ui_pointer()

    def draw(self, canvas) -> None:
        canvas.fill((0, 0, 0))
        c = self.ui_canvas(canvas)
        ui.panel(c, (6, 6, 468, 260))
        text(c, "스토리 디버그 — 장면 바로 재생 (기록은 안 바뀜)", (14, 18), ui.ACCENT, 11, "midleft")
        for b in self.btns:
            b.draw(c, self.mouse)
        st = story.state(self.game.save)
        fc = st["flags"].get("force_chapter")
        self.chap_btn.label = f"막 강제: {fc if fc is not None else '끔'} (지금 {story.chapter(self.game.save)})"
        self.chap_btn.draw(c, self.mouse)
        info = {k: st[k] for k in ("player_name", "pending_scenes", "phone_pending", "true_end_choice", "items", "flags")}
        y = 184
        for ln in json.dumps(info, ensure_ascii=False).split(", \""):
            text(c, ln[:78], (14, y), ui.DIM, 11, "midleft")
            y += 12
            if y > 240:
                break
        text(c, "본 장면 " + " ".join(st["seen_scenes"])[:70], (14, 176), ui.TEXT, 11, "midleft")
        self.close_btn.draw(c, self.mouse)
        draw_cursor(c, self.mouse)
