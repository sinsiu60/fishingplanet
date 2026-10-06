"""사진 모드 (DETAILS.md H-5, DESIGN.md 45장 DT11).

일시정지 메뉴 → "사진 찍기" (낚시터 · 마을, 파이팅 · 컷신 중 불가). 멈춘 풍경을 UI 없이 보여 주고 아래에 필터 4개:
기본 / 필름(살짝 노랗고 거친 입자) / 흑백 / 따뜻하게. 찍기 = 셔터 소리 + 아주 약한 흰 번쩍임 0.1초 (화면 효과 줄이기면 없음).
저장: PC = 내 사진/<게임 이름>/ PNG (내부 해상도 × 3배, 최근접) / 안드로이드 = 앱 전용 외부 폴더/photos + [공유].
[일지에 붙이기] → 주인공의 집 낚시 일지에 날짜와 함께 사진 칸 (최대 30장, 넘으면 가장 오래된 것을 바꿀지 물어봄).
일지용 작은 사진은 세이브 폴더 photos/ 에 따로 둠 (원본을 지우거나 옮겨도 일지는 그대로).
"""
import datetime

import numpy as np
import pygame

from src.platform.detect import IS_MOBILE
from src.scene.base import Scene
from src.ui import widgets as ui
from src.ui.hud import draw_cursor, text

FILTERS = (("plain", "기본"), ("film", "필름"), ("mono", "흑백"), ("warm", "따뜻하게"))
MAX_PHOTOS = 30
SCALE = 3
THUMB = (96, 54)
FLASH_SEC = 0.1


def can_open(fishing) -> bool:
    """파이팅 · 컷신 · 포획 연출 중엔 열지 않음."""
    if fishing is None:
        return False
    if fishing.backdrop is not None:   # 마을: 아스테라 도착 자막 같은 장면 중이 아니면
        v = getattr(fishing.backdrop, "__self__", None)
        return getattr(v, "story_seq", None) is None
    if fishing.fight is not None or getattr(fishing, "scenic", False) or fishing.training is not None:
        return False
    for attr in ("catch_show", "landing", "board", "release_scene", "cutscene"):
        if getattr(fishing, attr, None) is not None:
            return False
    return not fishing.hook_cine.active and not fishing.phantom_fx.locked()


def apply_filter(surf: pygame.Surface, kind: str, seed: int = 7) -> pygame.Surface:
    if kind == "plain":
        return surf.copy()
    a = pygame.surfarray.array3d(surf).astype(np.float32)
    if kind == "mono":
        g = a[..., 0] * 0.299 + a[..., 1] * 0.587 + a[..., 2] * 0.114
        a = np.repeat(g[..., None], 3, axis=2)
    elif kind == "warm":
        a = a * np.array([1.08, 1.0, 0.84]) + np.array([10, 4, -6])
    elif kind == "film":   # 살짝 노랗게 + 바랜 검정 + 거친 입자
        a = a * np.array([1.04, 1.0, 0.82]) + np.array([14, 10, 4])
        a = 18 + a * (1 - 18 / 255)
        rng = np.random.default_rng(seed)
        a = a + rng.normal(0, 9, a.shape[:2])[..., None]
    out = pygame.Surface(surf.get_size())
    pygame.surfarray.blit_array(out, np.clip(a, 0, 255).astype(np.uint8))
    return out


class PhotoScene(Scene):
    def __init__(self, game, fishing):
        super().__init__(game)
        self.fishing = fishing
        self.mouse = (0, 0)
        self.t = 0.0
        self.filter = 0
        self.flash = 0.0
        self.result = None      # {"path", "thumb"} 찍은 뒤
        self.ask_replace = False
        self.msg, self.msg_t = "", 0.0
        self.world = self._capture()
        self._cache: dict = {}
        self.buttons: list = []

    # ── 풍경 ──
    def _capture(self) -> pygame.Surface:
        c = self.game.screen.canvas
        surf = pygame.Surface(c.get_size())
        f = self.fishing
        prev = getattr(f, "scenic", False)
        f.scenic = True   # 낚싯대 · 풍경까지만 (HUD · 카드 없음) — 마을이면 backdrop(마을 풍경)
        try:
            f.draw(surf)
        finally:
            f.scenic = prev
        return surf

    def image(self) -> pygame.Surface:
        kind = FILTERS[self.filter][0]
        img = self._cache.get(kind)
        if img is None:
            img = self._cache[kind] = apply_filter(self.world, kind)
        return img

    # ── 동작 ──
    def _shoot(self) -> None:
        self.game.sfx.play("ui_shutter", 0.7)
        if not self.game.settings.get("reduce_fx"):
            self.flash = FLASH_SEC
        img = self.image()
        big = pygame.transform.scale(img, (img.get_width() * SCALE, img.get_height() * SCALE))   # 최근접 (픽셀 그대로)
        from src.core.config import game_config
        from src.platform.paths import pictures_dir
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        name = f"photo_{stamp}_{FILTERS[self.filter][0]}.png"
        path = None
        for d in (pictures_dir(game_config()["title"]), self._save_photos_dir()):
            try:
                d.mkdir(parents=True, exist_ok=True)
                pygame.image.save(big, str(d / name))
                path = d / name
                break
            except (OSError, pygame.error):
                continue
        self.result = {"path": str(path) if path else None, "img": img, "name": name}
        self._say("저장했어요" if path else "저장하지 못했어요 (폴더 권한)")

    def _save_photos_dir(self):
        from src.core.paths import save_dir
        return save_dir() / "photos"

    def _attach(self, replace: bool = False) -> None:
        """일지에 붙이기: 작은 사진을 세이브 폴더에 두고 일지 칸 추가 (최대 30장)."""
        from src.story import story
        st = story.state(self.game.save)
        det = self.game.save.data.setdefault("details", {})
        photos = det.setdefault("photos", [])
        if len(photos) >= MAX_PHOTOS and not replace:
            self.ask_replace = True
            return
        self.ask_replace = False
        if len(photos) >= MAX_PHOTOS:   # 가장 오래된 것부터 바꿈
            old = photos.pop(0)
            st["journal"] = [e for e in st["journal"] if e.get("photo") != old]
        d = self._save_photos_dir()
        try:
            d.mkdir(parents=True, exist_ok=True)
            thumb = pygame.transform.smoothscale(self.result["img"], THUMB)
            tp = d / ("j_" + self.result["name"])
            pygame.image.save(thumb, str(tp))
        except (OSError, pygame.error):
            self._say("일지에 붙이지 못했어요")
            return
        photos.append(str(tp))
        f = self.fishing
        st["journal"].append({"id": "photo_" + self.result["name"], "photo": str(tp),
                              "day": int(f.clock.day), "season": f.season,
                              "date": datetime.date.today().isoformat()})
        self.result["attached"] = True
        self.game.sfx.play("st_paper", 0.5)
        self._say(f"낚시 일지에 붙였어요 ({len(photos)}/{MAX_PHOTOS})")
        self.game.save_now()

    def _share(self) -> None:
        from src.platform import android
        if self.result and self.result.get("path") and android.share_image(self.result["path"], "미니 피싱 사진"):
            return
        self._say("공유하지 못했어요")

    def _say(self, s: str) -> None:
        self.msg, self.msg_t = s, 2.5

    def _close(self) -> None:
        if self in self.game.scenes.stack:
            self.game.scenes.stack.remove(self)

    # ── 입력 ──
    def handle_action(self, a) -> None:
        if a.name == "back":
            if self.ask_replace:
                self.ask_replace = False
            elif self.result is not None:
                self.result = None
            else:
                self._close()
            return
        if a.name == "primary":
            for b in self.buttons:
                if b.click(a.pos):
                    return
        elif a.name == "confirm" and self.result is None:
            self._shoot()

    def update(self, dt: float) -> None:
        self.t += dt
        self.mouse = self.game.input.pointer
        self.flash = max(0.0, self.flash - dt)
        self.msg_t = max(0.0, self.msg_t - dt)

    # ── 그리기 ──
    def _layout(self, w: int, h: int) -> list:
        bh = 22 if IS_MOBILE else 16
        y = h - bh - 6
        bs = []
        if self.ask_replace:
            bs.append(ui.Button((w // 2 - 104, h // 2 + 6, 100, bh), "바꾸기", lambda: self._attach(replace=True)))
            bs.append(ui.Button((w // 2 + 4, h // 2 + 6, 100, bh), "취소", lambda: setattr(self, "ask_replace", False)))
            return bs
        if self.result is not None:
            items = []
            if not self.result.get("attached"):
                items.append(("일지에 붙이기", self._attach))
            if IS_MOBILE and self.result.get("path"):
                items.append(("공유", self._share))
            items.append(("계속 찍기", lambda: setattr(self, "result", None)))
            items.append(("닫기", self._close))
            bw = 86
            x0 = w // 2 - (len(items) * (bw + 4) - 4) // 2
            return [ui.Button((x0 + i * (bw + 4), y, bw, bh), lab, act) for i, (lab, act) in enumerate(items)]
        bw = 56
        x0 = w // 2 - (len(FILTERS) * (bw + 4) + 70 + 54) // 2
        for i, (_, lab) in enumerate(FILTERS):
            bs.append(ui.Button((x0 + i * (bw + 4), y, bw, bh), lab, lambda k=i: self._set_filter(k)))
        x = x0 + len(FILTERS) * (bw + 4) + 6
        bs.append(ui.Button((x, y, 62, bh), "찍기", self._shoot, accent=(255, 240, 200)))
        bs.append(ui.Button((x + 66, y, 48, bh), "닫기", self._close))
        return bs

    def _set_filter(self, k: int) -> None:
        self.filter = k
        self.game.sfx.play("ui_tab", 0.6)

    def draw(self, canvas) -> None:
        w, h = canvas.get_size()
        canvas.blit(self.image(), (0, 0))
        if self.flash > 0:   # 아주 약한 흰 번쩍임 0.1초
            veil = pygame.Surface((w, h))
            veil.fill((255, 255, 255))
            veil.set_alpha(int(90 * self.flash / FLASH_SEC))
            canvas.blit(veil, (0, 0))
        self.buttons = self._layout(w, h)
        bar = pygame.Surface((w, self.buttons[0].rect.h + 12 if self.buttons else 28), pygame.SRCALPHA)
        bar.fill((8, 10, 20, 150))
        if not self.ask_replace:
            canvas.blit(bar, (0, h - bar.get_height()))
        for i, b in enumerate(self.buttons):
            b.draw(canvas, self.mouse, selected=self.result is None and not self.ask_replace and i == self.filter)
        if self.result is None and not self.ask_replace:
            text(canvas, "사진 모드 — 필터를 고르고 찍기", (w // 2, 12), (240, 236, 220), 11, "center", shadow=True)
        elif self.result is not None and not self.ask_replace:
            r = pygame.Rect(w // 2 - 110, 30, 220, 62 + 52)
            ui.panel(canvas, r)
            canvas.blit(pygame.transform.smoothscale(self.result["img"], (176, 99)), (r.centerx - 88, r.y + 6))
            p = self.result.get("path") or ""
            text(canvas, ("…" + p[-34:]) if len(p) > 35 else p, (r.centerx, r.bottom - 7), ui.DIM, 11, "center")
        if self.ask_replace:
            r = pygame.Rect(w // 2 - 130, h // 2 - 30, 260, 64)
            ui.panel(canvas, r)
            text(canvas, f"일지 사진이 {MAX_PHOTOS}장 꽉 찼어요.", (r.centerx, r.y + 12), ui.TEXT, 11, "center")
            text(canvas, "가장 오래된 사진을 바꿀까요?", (r.centerx, r.y + 26), ui.ACCENT, 11, "center")
            for b in self.buttons:
                b.draw(canvas, self.mouse)
        if self.msg_t > 0:
            text(canvas, self.msg, (w // 2, 28 if self.result is None else 22), ui.GOOD, 11, "center", shadow=True)
        draw_cursor(canvas, self.mouse)
