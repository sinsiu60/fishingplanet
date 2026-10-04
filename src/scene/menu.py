"""시작 메뉴와 슬롯 선택."""
import datetime

import pygame

from src.core.config import game_config, load_json
from src.render import world
from src.render.camera import Camera
from src.render.palette import Palette
from src.save.save_game import SLOTS, SaveGame
from src.scene.base import Scene
from src.ui import widgets as ui
from src.ui.fight_fx import big_text
from src.ui.hud import draw_cursor, text
from src.version import VERSION

SPOT_NAMES = {s["id"]: s["name"] for s in load_json("spots.json")["spots"]}


class MenuBackdrop:
    """메뉴 배경: 해 질 녘 저수지가 천천히 흐른다."""

    def __init__(self, w: int, h: int):
        self.cam = Camera(w, h, game_config()["camera"])
        self.palette = Palette()
        self.stars = world.StarField(self.cam)
        self.clouds = world.Clouds(self.cam)
        self.water = world.Water(self.cam)
        self.reeds = world.Reeds(self.cam)
        self.t = 0.0
        self.hour = 18.2

    def update(self, dt: float) -> None:
        self.t += dt
        self.hour = 18.2 + (self.t * 0.02) % 4.0
        self.cam.yaw = 0.12 * __import__("math").sin(self.t * 0.05)
        self.clouds.update(dt)

    def draw(self, canvas) -> None:
        pal = self.palette.sample(self.hour)
        world.draw_sky(canvas, pal, self.cam)
        self.stars.draw(canvas, pal, self.cam, self.t)
        world.draw_celestial(canvas, pal, self.cam, self.hour, self.t)
        self.clouds.draw(canvas, pal, self.cam)
        world.draw_mountains(canvas, pal, self.cam)
        self.water.draw(canvas, pal, self.t, self.hour)
        self.reeds.draw(canvas, pal, self.t)


def start_game(game, save: SaveGame) -> None:
    from src.scene.fishing_scene import FishingScene
    game.save = save
    from src.save import dexbook
    dexbook.ensure_seen(save)   # 옛 세이브: 지금 별·숙련을 기준으로 (알림 폭탄 없이) + 소급 보상·달인 칭호
    game.save.save()
    game.scenes.stack.clear()
    game.scenes.push(FishingScene(game))
    game.fade_in(0.7)


class TitleScene(Scene):
    UI_FRAME = True

    def __init__(self, game):
        super().__init__(game)
        self.bg = MenuBackdrop(game.screen.width, game.screen.height)
        w = game.screen.ui_rect.w
        self.mouse = (0, 0)
        self.latest = SaveGame.latest_slot()
        info = SaveGame.summary(self.latest) if self.latest is not None else None
        self.latest_title = info.get("title") if info else None
        bx, bw = w // 2 - 60, 120
        y0 = 132
        items = [("이어하기", self._continue, self.latest is not None),
                 ("새 게임", lambda: self._push(SlotScene(game, "new")), True),
                 ("불러오기", lambda: self._push(SlotScene(game, "load")), self.latest is not None),
                 ("설정", self._settings, True),
                 ("종료", game.quit, True)]
        self.buttons = [ui.Button((bx, y0 + i * 23, bw, 19), label, act, en)
                        for i, (label, act, en) in enumerate(items)]

    def _push(self, scene) -> None:
        self.game.scenes.push(scene)

    def _continue(self) -> None:
        sg = SaveGame.load(self.latest)
        if sg:
            start_game(self.game, sg)

    def _settings(self) -> None:
        from src.scene.settings_scene import SettingsScene
        self._push(SettingsScene(self.game))

    def on_resume(self) -> None:
        self.latest = SaveGame.latest_slot()
        self.buttons[0].enabled = self.buttons[2].enabled = self.latest is not None

    def handle_action(self, a) -> None:
        from src.platform.detect import IS_MOBILE
        if a.name == "back" and IS_MOBILE:
            # 안드로이드 뒤로 가기: 타이틀에선 바로 끄지 않고 물어본다
            from src.scene.confirm import ConfirmScene
            self.game.scenes.push(ConfirmScene(self.game, "게임을 종료할까요?", self.game.quit, "종료", "계속하기"))
            return
        if a.name == "primary":
            for b in self.buttons:
                if b.click(a.pos):
                    self.game.sfx.play("ui_click")
                    break

    def update(self, dt: float) -> None:
        self.bg.update(dt)
        self.mouse = self.ui_pointer()
        self.game.music.play("title")
        self.game.adaptive.set_context("sharmion", None)  # 대륙 테마 (32장 S6)
        self.game.adaptive.set("menu")

    def draw(self, canvas) -> None:
        self.bg.draw(canvas)
        canvas = self.ui_canvas(canvas)
        w = canvas.get_width()
        big_text(canvas, game_config()["title"], (w // 2, 58), (255, 228, 150), 3.0, outline=True)
        text(canvas, "MINI  FISHING", (w // 2, 84), (255, 214, 140), 11, "center")
        text(canvas, "어렵지만 공정한 1인칭 낚시", (w // 2, 98), (235, 225, 240), 11, "center")
        if self.latest_title:
            text(canvas, f"「{self.latest_title}」", (w // 2, 114), (255, 214, 90), 11, "center")  # 장착한 칭호
        for b in self.buttons:
            b.draw(canvas, self.mouse)
        text(canvas, f"v{VERSION}", (w - 6, canvas.get_height() - 8), (150, 150, 165), 11, "midright")
        draw_cursor(canvas, self.mouse)


class SlotScene(Scene):
    """mode='new': 새 게임을 시작할 슬롯 / mode='load': 불러올 슬롯."""
    UI_FRAME = True


    def __init__(self, game, mode: str):
        super().__init__(game)
        self.mode = mode
        self.mouse = (0, 0)
        self.confirm: int | None = None
        self.infos = {s: SaveGame.summary(s) for s in range(1, SLOTS + 1)}
        w = game.screen.ui_rect.w
        self.cards = {s: pygame.Rect(w // 2 - 150, 54 + (s - 1) * 58, 300, 52) for s in range(1, SLOTS + 1)}
        self.back = ui.Button((w // 2 - 40, 234, 80, 18), "뒤로", self._back)

    def _back(self) -> None:
        self.game.scenes.pop()
        top = self.game.scenes.current
        if hasattr(top, "on_resume"):
            top.on_resume()

    def _pick(self, slot: int) -> None:
        info = self.infos[slot]
        if self.mode == "load":
            if info:
                sg = SaveGame.load(slot)
                if sg:
                    start_game(self.game, sg)
            return
        if info and self.confirm != slot:
            self.confirm = slot  # 덮어쓰기 확인
            return
        start_game(self.game, SaveGame(slot))

    def handle_action(self, a) -> None:
        if a.name == "back":
            self._back()
        elif a.name == "primary":
            m = a.pos
            if self.back.click(m):
                self.game.sfx.play("ui_click")
                return
            for s, r in self.cards.items():
                if r.collidepoint(m):
                    self.game.sfx.play("ui_click")
                    self._pick(s)
                    return
            self.confirm = None

    def update(self, dt: float) -> None:
        self.mouse = self.ui_pointer()
        under = self.game.scenes.stack[0]
        if hasattr(under, "bg"):
            under.bg.update(dt)

    def draw(self, canvas) -> None:
        under = self.game.scenes.stack[0]
        if hasattr(under, "bg"):
            under.bg.draw(canvas)
        ui.dim(canvas, 120)
        canvas = self.ui_canvas(canvas)
        w = canvas.get_width()
        title = "새 게임 — 슬롯 선택" if self.mode == "new" else "불러오기"
        text(canvas, title, (w // 2, 30), ui.ACCENT, 16, "center")
        for s, r in self.cards.items():
            info = self.infos[s]
            hov = r.collidepoint(self.mouse)
            usable = self.mode == "new" or info is not None
            border = ui.ACCENT if hov and usable else ui.BORDER
            if self.confirm == s:
                border = ui.BAD
            ui.panel(canvas, r, border, ui.PANEL_LIGHT if hov and usable else ui.PANEL)
            text(canvas, f"슬롯 {s}", (r.x + 10, r.y + 12), ui.ACCENT if usable else ui.DIM, 16, "midleft")
            if info is None:
                text(canvas, "비어 있음", (r.x + 80, r.y + 26), ui.DIM, 11, "midleft")
            else:
                when = datetime.datetime.fromtimestamp(info["updated"]).strftime("%m/%d %H:%M")
                text(canvas, f"{ui.money_text(info['money'])}   도감 {info['dex']}/{info['dex_total']}",
                     (r.x + 80, r.y + 16), ui.TEXT, 11, "midleft")
                if info.get("title"):
                    text(canvas, f"「{info['title']}」", (r.right - 8, r.y + 12), (255, 214, 90), 11, "midright")
                text(canvas, f"{SPOT_NAMES.get(info['spot'], '')} · {ui.time_text(info['playtime'])} · {when}",
                     (r.x + 80, r.y + 34), ui.DIM, 11, "midleft")
            if self.confirm == s:
                text(canvas, "덮어쓸까요? 한 번 더 클릭", (r.right - 8, r.y + 12), ui.BAD, 11, "midright")
        self.back.draw(canvas, self.mouse)
        draw_cursor(canvas, self.mouse)
