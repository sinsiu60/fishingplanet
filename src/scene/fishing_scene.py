"""1인칭 낚시 장면 (Phase 1: 장면 + 캐스팅)."""
import math

import pygame

from src.core.config import game_config
from src.core.game_clock import GameClock
from src.core.mathutil import clamp, lerp, smoothstep
from src.fishing.casting import CastController, CastState
from src.render import world
from src.render.camera import Camera
from src.render.effects import Droplets, Ripples, draw_bobber, draw_line, landing_marker, rod_tip_drop
from src.render.palette import Palette
from src.render.rod import draw_rod, rod_geometry
from src.scene.base import Scene
from src.ui import hud

HINTS = {
    CastState.READY: "좌클릭 유지: 파워 충전   마우스: 방향   화면 끝: 둘러보기   T: 시간 가속",
    CastState.CHARGING: "놓으면 던지기   우클릭: 취소",
    CastState.SWING: "",
    CastState.FLIGHT: "",
    CastState.LANDED: "우클릭: 줄 회수   화면 끝: 둘러보기",
    CastState.RETRIEVE: "줄 감는 중...",
}
LOOK_STATES = (CastState.READY, CastState.LANDED)


class FishingScene(Scene):
    def __init__(self, game):
        super().__init__(game)
        cfg = game_config()
        self.cam_cfg = cfg["camera"]
        canvas = game.screen.canvas
        self.cam = Camera(canvas.get_width(), canvas.get_height(), self.cam_cfg)
        self.clock = GameClock()
        self.palette = Palette()
        self.stars = world.StarField(self.cam)
        self.clouds = world.Clouds(self.cam)
        self.water = world.Water(self.cam)
        self.reeds = world.Reeds(self.cam)
        self.cast = CastController()
        self.ripples = Ripples()
        self.droplets = Droplets()
        self.t = 0.0
        self.mouse = (canvas.get_width() // 2, canvas.get_height() // 2)
        self.look_left = self.look_right = False
        self.idle_ripple_t = 0.0
        self.wake_t = 0.0
        pygame.mouse.set_visible(False)

    # ── 입력 ──
    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_t:
            self.clock.fast = not self.clock.fast
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                self.cast.press()
            elif event.button == 3:
                self.cast.cancel_or_retrieve()
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.cast.release(self.cam.yaw)

    # ── 로직 (60틱 고정) ──
    def update(self, dt: float) -> None:
        self.t += dt
        self.clock.update(dt)
        self.clouds.update(dt)
        self.ripples.update(dt)
        self.droplets.update(dt)

        mx, my = self.game.screen.to_canvas(pygame.mouse.get_pos())
        w = self.cam.width
        self.mouse = (int(clamp(mx, 0, w - 1)), int(clamp(my, 0, self.cam.height - 1)))

        # 둘러보기: 대기 중에만, 화면 좌우 끝에 마우스
        edge = self.cam_cfg["edge_px"]
        can_look = self.cast.state in LOOK_STATES
        self.look_left = can_look and mx < edge and self.cam.yaw > -self.cam.max_yaw
        self.look_right = can_look and mx > w - edge and self.cam.yaw < self.cam.max_yaw
        speed = math.radians(self.cam_cfg["look_speed_deg"]) * dt
        if self.look_left:
            self.cam.yaw = max(-self.cam.max_yaw, self.cam.yaw - speed)
        if self.look_right:
            self.cam.yaw = min(self.cam.max_yaw, self.cam.yaw + speed)

        aim = clamp((mx - self.cam.cx) / (self.cam.cx - edge), -1.0, 1.0)
        self.cast.update(dt, aim)

        for ev in self.cast.events:
            if ev == "splash":
                self._splash()
        self.cast.events.clear()

        if self.cast.state == CastState.LANDED:
            self.idle_ripple_t += dt
            if self.idle_ripple_t > 2.2:
                self.idle_ripple_t = 0.0
                self.ripples.spawn(self.cast.bx, self.cast.bz, size=0.5, life=1.8)
        elif self.cast.state == CastState.RETRIEVE:
            self.wake_t += dt
            if self.wake_t > 0.12:
                self.wake_t = 0.0
                self.ripples.spawn(self.cast.bx, self.cast.bz, size=0.35, life=0.9)

    def _splash(self) -> None:
        c = self.cast
        self.ripples.spawn(c.bx, c.bz, size=1.0, life=1.8, rings=3)
        p = self.cam.project(c.bx, c.bz)
        if p:
            self.droplets.burst(p[0], p[1], p[2] / 20, count=12)
        self.idle_ripple_t = 0.0

    # ── 그리기 ──
    def draw(self, canvas: pygame.Surface) -> None:
        hour = self.clock.hour
        pal = self.palette.sample(hour)
        cam, c, t = self.cam, self.cast, self.t

        world.draw_sky(canvas, pal, cam)
        self.stars.draw(canvas, pal, cam, t)
        world.draw_celestial(canvas, pal, cam, hour, t)
        self.clouds.draw(canvas, pal, cam)
        world.draw_mountains(canvas, pal, cam)
        self.water.draw(canvas, pal, t, hour)
        self.ripples.draw(canvas, pal, cam)

        geo = rod_geometry(c.aim, c.swing_deg, c.bend, c.rod_hand_offset())
        tip = geo["tip"]

        if c.state == CastState.CHARGING:
            ang = c.aim_angle(cam.yaw)
            d = c.distance_for_power(c.power)
            landing_marker(canvas, pal, cam, math.sin(ang) * d, math.cos(ang) * d, t)

        hanging = c.state in (CastState.READY, CastState.CHARGING, CastState.SWING)
        if not hanging:
            self._draw_line_and_bobber(canvas, pal, tip)

        self.reeds.draw(canvas, pal, t)
        draw_rod(canvas, pal, geo, c.reel_angle)

        if hanging:
            bx, by = rod_tip_drop(tip, t)
            draw_line(canvas, pal, tip, (bx, by - 3), 0)
            draw_bobber(canvas, pal, bx, by, 7, floating=False)
        self.droplets.draw(canvas, pal)

        # HUD
        hud.draw_clock(canvas, pal, self.clock.label(), self.clock.fast, self.clock.fast_mult)
        if c.state == CastState.CHARGING:
            hud.draw_power_gauge(canvas, pal, c.power, c.distance_for_power(c.power))
        if c.state == CastState.LANDED:
            hud.text(canvas, f"찌 거리 {c.current_distance():.0f}m", (cam.width - 6, 4), pal["text"],
                     anchor="topright")
        hint = HINTS[c.state]
        if hint:
            hud.draw_hint(canvas, pal, hint)
        hud.draw_look_arrows(canvas, pal, self.look_left, self.look_right, t)
        hud.draw_cursor(canvas, self.mouse)

    def _draw_line_and_bobber(self, canvas, pal, tip) -> None:
        c, cam = self.cast, self.cam
        p = cam.project(c.bx, c.bz, c.bh)
        if p is None:
            return
        sx, sy, s = p
        size = max(3.5, 0.36 * s)
        if c.state == CastState.FLIGHT:
            # 낚싯대 끝에서 출발하는 느낌이 나게 처음엔 화면 좌표를 섞는다
            k = smoothstep(c.flight_s / 0.3)
            start = rod_tip_drop(tip, self.t)
            sx = lerp(start[0], sx, k)
            sy = lerp(start[1], sy, k)
            size = lerp(7, size, k)
            draw_line(canvas, pal, tip, (sx, sy), 3 * (1 - c.flight_s))
            draw_bobber(canvas, pal, sx, sy, size, floating=False)
            return
        bob = 0.0
        if c.state == CastState.LANDED:
            bob = math.sin(self.t * 2.0) * max(0.5, s * 0.012)
        sag = 4 if c.state == CastState.RETRIEVE else 10 + abs(tip[0] - sx) * 0.04
        draw_line(canvas, pal, tip, (sx, sy + bob - size * 0.5), sag, bias=0.6)
        draw_bobber(canvas, pal, sx, sy + bob, size, floating=True)
