"""세이브 옮기기 화면 (설정 → 세이브 옮기기). 내용은 src/save/transfer.py."""
import pygame

from src.platform.detect import IS_ANDROID
from src.save import transfer
from src.save.save_game import SLOTS, SaveGame
from src.scene.base import Scene
from src.ui import widgets as ui
from src.ui.hud import draw_cursor, text, wrap_text


class SaveTransferScene(Scene):
    UI_FRAME = True

    def __init__(self, game):
        super().__init__(game)
        self.mouse = (0, 0)
        self.sel = game.save.slot if game.save is not None else 1
        self.confirm = False
        self.msg, self.msg_col = "", ui.TEXT
        self.rows = {s: pygame.Rect(56, 56 + (s - 1) * 28, 368, 24) for s in range(1, SLOTS + 1)}
        self.buttons = [ui.Button((64, 146, 170, 22), "내보내기", self._export),
                        ui.Button((246, 146, 170, 22), "가져오기", self._import),
                        ui.Button((200, 222, 80, 18), "닫기", self._close)]
        self._refresh()

    def _refresh(self) -> None:
        if self.game.save is not None:
            self.game.save_now()
        self.infos = {s: SaveGame.summary(s) for s in range(1, SLOTS + 1)}

    def _say(self, msg: str, col=ui.TEXT) -> None:
        self.msg, self.msg_col = msg, col

    def _export(self) -> None:
        self.confirm = False
        self._refresh()
        code = transfer.export_code(self.sel)
        if code is None:
            self._say(f"슬롯 {self.sel}이 비어 있어요", ui.BAD)
            return
        path = transfer.write_export_file(self.sel, code)
        copied = transfer.clipboard_put(code)
        parts = []
        if copied:
            parts.append("코드를 복사했어요")
        if path is not None:
            parts.append(f"파일: {path.parent.name}/{path.name} ({'Android/data' if IS_ANDROID else '내 문서/FishingPlanet'} 안)")
        if IS_ANDROID:
            from src.platform import android
            if android.share_text(code, "낚시 게임 세이브"):
                parts.append("공유 창에서 나에게 보내기(카톡·메일)를 고르세요")
        self._say(" · ".join(parts) or "내보내기에 실패했어요", ui.GOOD if parts else ui.BAD)

    def _import(self) -> None:
        code, where = transfer.find_import_code()
        if code is None:
            self._say(f"가져올 코드가 없어요. 코드를 복사하거나 '{transfer.export_dir().name}' 폴더에 import.txt 로 넣어 주세요",
                      ui.BAD)
            self.confirm = False
            return
        try:
            data = transfer.decode(code)
        except ValueError as e:
            self._say(str(e), ui.BAD)
            self.confirm = False
            return
        if not self.confirm and self.infos.get(self.sel):
            self.confirm = True
            self._say(f"{where}의 세이브(돈 {data['money']:,}원)로 슬롯 {self.sel}을 덮어쓸까요? "
                      f"'가져오기'를 한 번 더 누르세요 (지금 것은 자동 백업)", ui.ACCENT)
            return
        self.confirm = False
        active = self.game.save is not None and self.game.save.slot == self.sel
        bak = transfer.import_to_slot(self.sel, data)
        msg = f"슬롯 {self.sel}에 가져왔어요" + (f" · 백업: {bak.name}" if bak else "")
        if active:
            # 지금 하던 슬롯이면 새 세이브로 다시 시작 (안 그러면 자동 저장이 덮어씀)
            from src.scene.menu import start_game
            sg = SaveGame.load(self.sel)
            if sg is not None:
                self.game.save = None
                start_game(self.game, sg)
                self.game.scenes.current.toasts.show(msg, ui.GOOD, 3.0, 11)
                return
        self._refresh()
        self._say(msg, ui.GOOD)

    def _close(self) -> None:
        self.game.scenes.pop()
        top = self.game.scenes.current
        if hasattr(top, "on_resume"):
            top.on_resume()

    def handle_action(self, a) -> None:
        if a.name == "back":
            self._close()
        elif a.name == "primary":
            for b in self.buttons:
                if b.click(a.pos):
                    self.game.sfx.play("click")
                    return
            for s, r in self.rows.items():
                if r.collidepoint(a.pos):
                    self.sel, self.confirm = s, False
                    self.game.sfx.play("click")

    def update(self, dt: float) -> None:
        self.mouse = self.ui_pointer()

    def draw(self, canvas) -> None:
        under = self.scene_below()
        if under is not None:
            under.draw(canvas)
        ui.dim(canvas, 170)
        canvas = self.ui_canvas(canvas)
        ui.panel(canvas, (40, 24, 400, 222))
        text(canvas, "세이브 옮기기 (PC·모바일)", (240, 38), ui.ACCENT, 16, "center")
        for s, r in self.rows.items():
            info = self.infos.get(s)
            sel = s == self.sel
            canvas.fill(ui.PANEL_LIGHT if sel else ui.PANEL, r)
            pygame.draw.rect(canvas, ui.ACCENT if sel else ui.BORDER, r, 1)
            label = f"슬롯 {s}  ·  " + (f"{info['money']:,}원 · 도감 {info['dex']}/{info['dex_total']}" if info else "비어 있음")
            text(canvas, label, (r.x + 8, r.centery), ui.TEXT if info else ui.DIM, 11, "midleft")
        for b in self.buttons:
            b.draw(canvas, self.mouse)
        msg = self.msg or "내보내기: 코드를 복사하고 파일로도 저장해요. 가져오기: 복사한 코드(또는 import.txt)로 고른 슬롯을 덮어써요."
        y = 180
        for ln in wrap_text(msg, 380)[:3]:
            text(canvas, ln, (240, y), self.msg_col if self.msg else ui.DIM, 11, "center")
            y += 13
        draw_cursor(canvas, self.mouse)
