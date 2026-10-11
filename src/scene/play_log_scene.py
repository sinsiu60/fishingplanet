"""플레이 기록 화면 (설정 → 접근성 → 플레이 기록 보기, JOURNEY.md 📏, DESIGN 54-5).

왼쪽: 최근 세션 목록 (새 것부터) · 오른쪽: 낚시터별 머문 시간 막대 · [기록 복사] (클립보드 + 파일, 안드로이드는 공유 창).
기기 밖으로 자동 전송 없음.
"""
import pygame

from src.platform.detect import IS_ANDROID
from src.save import play_log
from src.save.journey import ORDER, spot_short
from src.scene.base import Scene
from src.ui import widgets as ui
from src.ui.hud import draw_cursor, text
from src.ui.shop_ui import fit


class PlayLogScene(Scene):
    UI_FRAME = True
    ROW = 13

    def __init__(self, game):
        super().__init__(game)
        self.mouse = (0, 0)
        self.scroll = 0
        self.msg, self.msg_col = "", ui.TEXT
        self.list_r = pygame.Rect(30, 48, 262, 182)
        self.buttons = [ui.Button((306, 230, 70, 18), "기록 복사", self._copy),
                        ui.Button((382, 230, 60, 18), "닫기", self._close)]

    def _sessions(self) -> list:
        return list(reversed(play_log.state(self.game.save)["sessions"]))

    def _copy(self) -> None:
        from src.core.paths import save_dir
        from src.save import transfer
        body = play_log.text(self.game.save)
        parts = []
        if transfer.clipboard_put(body):
            parts.append("복사했어요")
        try:
            path = save_dir() / "play_log.txt"
            path.write_text(body, encoding="utf-8")
            parts.append(f"파일: {path.name}")
        except OSError:
            pass
        if IS_ANDROID:
            from src.platform import android
            if android.share_text(body, "미니 피싱 플레이 기록"):
                parts.append("공유 창에서 보내기")
        self.msg = " · ".join(parts) or "복사하지 못했어요"
        self.msg_col = ui.GOOD if parts else ui.BAD

    def _close(self) -> None:
        if self in self.game.scenes.stack:
            self.game.scenes.stack.remove(self)

    def handle_action(self, a) -> None:
        if a.name == "back":
            self._close()
        elif a.name == "scroll":
            n = len(self._sessions()) * 2
            self.scroll = max(0, min(max(0, n - self.list_r.h // self.ROW), self.scroll - a.value))
        elif a.name == "primary":
            for b in self.buttons:
                if b.click(a.pos):
                    self.game.sfx.play("ui_click")
                    return

    def update(self, dt: float) -> None:
        self.mouse = self.ui_pointer()

    def draw(self, canvas) -> None:
        under = self.scene_below()
        if under is not None:
            under.draw(canvas)
        ui.dim(canvas, 180)
        canvas = self.ui_canvas(canvas)
        ui.panel(canvas, (20, 18, 440, 238))
        text(canvas, "플레이 기록", (30, 32), ui.ACCENT, 16, "midleft")
        save = self.game.save
        st = play_log.state(save)
        text(canvas, f"총 {int(save.data.get('playtime', 0) // 60)}분 · 세션 {len(st['sessions'])}개 (최근 {play_log.MAX_SESSIONS})",
             (450, 32), ui.DIM, 11, "midright")
        lines = []
        for s in self._sessions():
            ex = (" · 시험 " + ",".join(f"T{t}" for t in s.get("exam", []))) if s.get("exam") else ""
            lines.append((f"{s['start'][5:]}  {round(s.get('min', 0))}분 · {s.get('catch', 0)}마리 · 전설 {s.get('legend', 0)}{ex}", ui.TEXT))
            lines.append((f"   {play_log._name(s.get('spot0'))} → {play_log._name(s.get('spot1'))} · 마지막: {s.get('last', '?')}", ui.DIM))
        per = self.list_r.h // self.ROW
        for i, (ln, col) in enumerate(lines[self.scroll:self.scroll + per]):
            text(canvas, fit(ln, self.list_r.w), (self.list_r.x, self.list_r.y + i * self.ROW + 6), col, 11, "midleft")
        if not lines:
            text(canvas, "아직 기록이 없어요.", self.list_r.center, ui.DIM, 11, "center")
        # 낚시터별 머문 시간
        x0, y0 = 306, 50
        text(canvas, "낚시터별 머문 시간", (x0, y0), (255, 214, 120), 11, "midleft")
        sec = st["spot_sec"]
        top = max(sec.values(), default=1.0) or 1.0
        for i, sp in enumerate(ORDER):
            y = y0 + 14 + i * 13
            m = sec.get(sp, 0.0) / 60
            text(canvas, spot_short(sp), (x0, y), ui.TEXT if m else ui.DIM, 11, "midleft")
            w = int(70 * sec.get(sp, 0.0) / top)
            if w:
                canvas.fill((120, 180, 230), (x0 + 50, y - 3, w, 6))
            text(canvas, f"{round(m)}분", (x0 + 146, y), ui.DIM, 11, "midright")
        text(canvas, fit(self.msg or "기기 밖으로 자동으로 보내지 않아요 — [기록 복사]로만", 270), (30, 239),
             self.msg_col if self.msg else ui.DIM, 11, "midleft")
        for b in self.buttons:
            b.draw(canvas, self.mouse)
        draw_cursor(canvas, self.mouse)
