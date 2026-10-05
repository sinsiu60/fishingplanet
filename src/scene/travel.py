"""이동 컷신 (DESIGN.md 35-3, CONTENT_EXPANSION.md B-4): 화면이 뚝 바뀌는 대신 '그곳에 가는' 짧은 장면.

종류: first(첫 방문 ≈7초: 이동 → 낚시터 전경이 펼쳐짐 → 이름 + 부제) / revisit(≈2초) / return(낚시터 → 마을 ≈2초)
     / voyage(대륙 이동 ≈4초: 범선 항해 → 도착 항구 + 마을 이름, 이어서 낚시터 컷신). 대륙 첫 항해는 기존 VoyageScene.
설정 '이동 컷신: 전체 / 짧게(첫 방문도 재방문 버전) / 끄기(0.5초 페이드)'. 화면 효과 줄이기 = 흔들림·출렁임 없음.
재생 중 도착할 화면을 한 번 미리 그려 둔다 (그림 캐시 = 도착 순간 멈칫하지 않게). 건너뛰기: 클릭 (첫 방문은 1초 뒤).
"""
import math

import pygame

from src.core import season as seasons
from src.core.config import load_json
from src.core.mathutil import clamp, smoothstep
from src.render.travel import TravelView
from src.render.weather_fx import themed_palette
from src.scene.base import Scene
from src.ui.hud import text

STEP_SOUND = {"step": "amb_step#", "wood_step": "amb_wood_step#", "snow_step": "amb_snow_step#", "oar": "amb_oar#"}


def cfg() -> dict:
    return load_json("travel_cutscenes.json")


def mode(settings) -> str:
    return settings.get("travel_cutscene") or "full"


def start_trip(game, fishing, spot_id: str, prev_cont: str) -> None:
    """지도에서 낚시터로 (fishing.travel 이 이미 끝난 뒤). 대륙이 바뀌면 항해부터."""
    save = game.save
    m = mode(game.settings)
    visited = save.data.setdefault("visited", [])
    if m == "off":
        first = spot_id not in visited
        _mark(save, spot_id)
        game.fade_in(0.5)
        if first:
            from src.story import runner
            runner.after_travel(game, fishing, spot_id)
        return
    first = spot_id not in visited and m == "full"
    kind = "first" if first else "revisit"
    spot = next(s for s in load_json("spots.json")["spots"] if s["id"] == spot_id)
    cont = spot.get("continent", "sharmion")
    if cont != prev_cont:
        game.scenes.push(TravelScene(game, fishing, "voyage", cont=cont, then=(kind, spot_id)))
    else:
        game.scenes.push(TravelScene(game, fishing, kind, spot_id=spot_id))


def start_return(game, fishing, cont: str) -> None:
    """낚시터 → 마을 (다른 대륙의 마을이면 항해)."""
    if mode(game.settings) == "off":
        from src.scene.village import VillageScene
        game.scenes.push(VillageScene(game, fishing, cont))
        game.fade_in(0.5)
        return
    here = fishing.spot.get("continent", "sharmion")
    game.scenes.push(TravelScene(game, fishing, "return" if cont == here else "voyage", cont=cont))


def _mark(save, spot_id: str) -> None:
    v = save.data.setdefault("visited", [])
    if spot_id not in v:
        v.append(spot_id)


class TravelScene(Scene):
    def __init__(self, game, fishing, kind: str, spot_id: str | None = None, cont: str | None = None, then=None,
                 on_done=None):
        super().__init__(game)
        self.on_done = on_done   # 테스트 룸: 기록·화면 전환 없이 이것만 부름
        self.fishing = fishing
        self.kind = kind
        self.spot_id = spot_id
        self.then = then
        c = cfg()
        self.c = c
        if kind in ("first", "revisit"):
            self.scene = c["spots"][spot_id]
            self.spot = next(s for s in load_json("spots.json")["spots"] if s["id"] == spot_id)
            self.cont = self.spot.get("continent", "sharmion")
            self.name = self.spot["name"]
            self.subtitle = self.scene.get("subtitle", "")
        else:
            self.cont = cont or "sharmion"
            self.scene = c["return"][self.cont] if kind == "return" else c["voyage"]
            self.spot = None
            vc = load_json("villages.json")[self.cont]
            self.name, self.subtitle = vc["name"], vc.get("subtitle", "")
        d = c["durations"][kind]
        self.t_travel, self.t_reveal = d["travel"], d["reveal"]
        self.total = self.t_travel + self.t_reveal
        w, h = game.screen.canvas.get_size()
        self.season = seasons.current(game.settings)
        self.view = TravelView(self.scene, w, h, self.season, bool(game.settings.get("reduce_fx")),
                               seed=hash((spot_id, kind)) & 0xffff)
        from src.render.season_fx import SeasonParticles
        from src.render.event_fx import EventFx
        self.particles = SeasonParticles()
        self.efx = EventFx()
        self.t = 0.0
        self.step_t = 0.0
        self.preloaded = False
        self.village = None
        if kind in ("return", "voyage"):
            from src.scene.village import VillageScene
            self.village = VillageScene(game, fishing, self.cont)   # 도착할 마을 (그림 미리)
            if kind == "voyage" and then:
                fishing.backdrop = None   # 항해 뒤 낚시터로 이어짐
        game.sfx.play("ui_click", 0.0)

    # ── 진행 ──
    def _finish(self) -> None:
        g = self.game
        if self in g.scenes.stack:
            g.scenes.stack.remove(self)
        if self.on_done is not None:
            self.on_done()
            return
        if self.kind in ("first", "revisit"):
            first = self.spot_id not in g.save.data.get("visited", [])
            _mark(g.save, self.spot_id)
            self.fishing.backdrop = None
            g.save_now()
            if first:   # 스토리: 용문 폭포·세계수 뿌리 샘 첫 방문 컷신(타이틀까지) 바로 뒤 (C3-02 · C5-04)
                from src.story import runner
                if runner.after_travel(g, self.fishing, self.spot_id):
                    return
        elif self.kind == "return":
            g.scenes.push(self.village)
        elif self.kind == "voyage" and self.then:
            kind, sid = self.then
            g.scenes.push(TravelScene(g, self.fishing, kind, spot_id=sid))
            return
        elif self.kind == "voyage":   # 다른 대륙의 마을로 바로
            g.scenes.push(self.village)
        g.fade_in(0.25)

    def handle_action(self, a) -> None:
        if a.name in ("primary", "back", "confirm"):
            if self.kind == "first" and self.t < self.c["skip_after_first"]:
                return
            self.t = max(self.t, self.total)

    def update(self, dt: float) -> None:
        self.t += dt
        sp = 1.0 if self.t < self.t_travel else max(0.0, 1 - (self.t - self.t_travel) / 0.6)
        self.view.update(dt, sp)
        self.particles.update(dt, self.season, self.cont, *self.game.screen.canvas.get_size(), self.fishing.clock.period()[0],
                              self.fishing.weather, mobile=self.game.input.kind == "touch",
                              enabled=not self.scene.get("cave"))
        f = self.fishing
        dest = self.spot_id if self.spot is not None else f"village_{self.cont}"
        f.ambience.update(dt, dest, f.clock.period()[0], f.weather)   # 도착지 환경음 (이동 중 점점)
        # 발소리·노 젓는 소리
        snd = STEP_SOUND.get(self.scene.get("sound"))
        if snd and self.t < self.t_travel:
            self.step_t -= dt
            if self.step_t <= 0:
                walk = self.scene.get("move") in ("walk", "bridge")
                self.step_t = (0.44 if walk else 1.1) / self.scene.get("speed", 1.0)
                n = sum(1 for k in self.game.sfx.sounds if k.startswith(snd[:-1]))
                name = f"{snd[:-1]}{int(self.t * 7) % max(1, n)}"
                self.game.sfx.play(name, 0.35 if walk else 0.5, pan=(-0.25 if int(self.t / 0.44) % 2 else 0.25) if walk else 0.4)
        if not self.preloaded and self.t > 0.15:
            self.preloaded = True
            tmp = pygame.Surface(self.game.screen.canvas.get_size())
            self._draw_target(tmp)   # 도착 화면 그림 캐시를 미리 채움
        if self.t >= self.total:
            self._finish()

    # ── 그리기 ──
    def _pal(self) -> dict:
        f = self.fishing
        from src.render.season_fx import season_palette
        from src.render.event_fx import event_palette
        from src.fishing import weather_events
        theme = self.spot["theme"] if self.spot else {}
        ev = weather_events.active(self.game.save)
        pal = season_palette(themed_palette(f.palette.sample(f.clock.hour), theme, f.weather), self.season, self.cont)
        return event_palette(pal, ev["id"] if ev else None, self.cont)

    def _draw_target(self, surf) -> None:
        if self.village is not None:
            if self.kind == "voyage":
                self.village.ox = 0
            self.village.draw_world(surf)
        else:
            f = self.fishing
            back = f.backdrop
            f.backdrop = None
            f.scenic = True
            try:
                f.draw(surf)
            finally:
                f.scenic = False
                f.backdrop = back

    def draw(self, canvas) -> None:
        from src.render.village import _night
        w, h = canvas.get_size()
        pal = self._pal()
        night = _night(self.fishing.clock.hour)
        self.view.draw(canvas, pal, night, self.fishing.weather)
        from src.fishing import weather_events
        ev = weather_events.active(self.game.save)
        if ev and not self.scene.get("cave"):   # 이벤트 하늘도 그대로 (유성우 밤이면 컷신 하늘에도 유성)
            self.efx.update(1 / 60, ev["id"], w, 118, False)
            clip = canvas.get_clip()
            canvas.set_clip(pygame.Rect(0, 0, w, 118))
            self.efx.draw_sky(canvas, ev["id"], self.cont, 118, False)
            canvas.set_clip(clip)
            self.efx.draw_low(canvas, ev["id"], self.cont, 118, False)
        self.particles.draw(canvas)
        if self.t > self.t_travel:
            k = smoothstep(clamp((self.t - self.t_travel) / (self.t_reveal * 0.6), 0, 1))
            tgt = pygame.Surface((w, h))
            self._draw_target(tgt)
            if self.kind == "first":   # 전경이 펼쳐짐: 시선이 천천히 들림
                tgt = pygame.transform.smoothscale(tgt, (int(w * (1.06 - 0.06 * k)), int(h * (1.06 - 0.06 * k))))
                off = ((w - tgt.get_width()) // 2, int((h - tgt.get_height()) // 2 + 18 * (1 - k)))
            else:
                off = (0, 0)
            tgt.set_alpha(int(255 * k))
            canvas.blit(tgt, off)
        self._title(canvas, w, h)
        if self.kind == "first" and self.t > self.c["skip_after_first"] or self.kind != "first":
            text(canvas, "클릭: 건너뛰기", (w - 6, h - 8), (200, 200, 210), 11, "midright")

    def _title(self, canvas, w, h) -> None:
        """화면 아래쪽 가운데: 이름(크게) + 부제(작게), 천천히 나타났다 사라짐."""
        if self.kind == "first":
            t0, t1 = self.t_travel + 0.2, self.total + 0.3
            big = True
        else:
            t0 = self.t_travel if self.kind == "voyage" else self.t_travel * 0.5   # 항해: 항구가 보일 때
            t1, big = self.total + 0.2, False
        if not t0 < self.t < t1:
            return
        a = min(1.0, (self.t - t0) / 0.5, (t1 - self.t) / 0.5)
        y = h - 52 if big else h - 34
        band = pygame.Surface((w, 46 if big else 22), pygame.SRCALPHA)
        for i in range(band.get_height()):
            band.fill((8, 10, 20, int(150 * a * math.sin(math.pi * i / band.get_height()))), (0, i, w, 1))
        canvas.blit(band, (0, y - (14 if big else 11)))
        col = tuple(int(v * a + 20 * (1 - a)) for v in (255, 244, 220))
        if big:
            from src.ui.fight_fx import big_text
            big_text(canvas, self.name, (w // 2, y), col, 1.6)
            text(canvas, self.subtitle, (w // 2, y + 20), tuple(int(v * a) for v in (220, 215, 200)), 11, "center", shadow=True)
        else:
            text(canvas, self.name, (w // 2, y), col, 16, "center")
