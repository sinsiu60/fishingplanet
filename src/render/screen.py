"""저해상도 캔버스에 그리고 확대해 창에 출력한다.

PC     : 480x270 캔버스를 정수 배율로 확대 (기존 그대로).
모바일 : 화면비에 맞춰 캔버스를 늘린다 — 짧은 쪽을 기준(270 또는 480)으로 고정하고 긴 쪽을 넓힌다.
         폰(18:9~21:9) = 높이 270, 폭 540~630 / 태블릿(4:3~16:10) = 폭 480, 높이 300~360.
         21:9보다 길거나 4:3보다 높으면 남는 부분만 검은 띠. 배율은 실수 (기기 해상도가 제각각이라).
메뉴 창은 캔버스 가운데의 480x270 'UI 상자'(ui_rect)에 그린다. PC에선 ui_rect = 캔버스 전체.
pygame.transform.scale은 최근접 보간이라 픽셀이 뭉개지지 않는다.
"""
import pygame

BASE_W, BASE_H = 480, 270
MAX_W, MAX_H = 630, 360  # 21:9 / 4:3
_masks = None


def opaque(size) -> pygame.Surface:
    """불투명 표면을 캔버스와 같은 픽셀 형식으로 (v0.8.11).

    pygame.Surface(size) 는 화면(창) 형식을 따르는데, 폰 창은 RGB 순서가 다르거나(ABGR) 16비트라
    반투명 그림(SRCALPHA, ARGB)을 그 위에 섞으면 픽셀마다 형식을 변환하는 느린 길로 간다 (S25 파이팅 '그리기' 200ms+).
    그래서 캔버스와 불투명 표면은 SRCALPHA 와 RGB 순서가 같은 32비트로 만든다."""
    global _masks
    if _masks is None:
        r, g, b, _a = pygame.Surface((1, 1), pygame.SRCALPHA).get_masks()
        _masks = (r, g, b, 0)
    return pygame.Surface(size, 0, 32, _masks)


def fmt_name(surf) -> str:
    m = surf.get_masks()
    order = "".join(c for _, c in sorted(zip(m[:3], "RGB"), reverse=True))
    return f"{surf.get_bitsize()}bit {order}{'A' if m[3] else ''}"


def canvas_size_for(window_w: int, window_h: int) -> tuple[int, int]:
    """창(기기 화면) 크기 → 모바일 캔버스 크기."""
    aspect = window_w / window_h
    if aspect >= BASE_W / BASE_H:
        return min(MAX_W, int(round(BASE_H * aspect / 2)) * 2), BASE_H
    return BASE_W, min(MAX_H, int(round(BASE_W / aspect / 2)) * 2)


class PixelScreen:
    def __init__(self, width: int, height: int, scale: int | None, title: str, mobile_window=None, gpu: bool = False):
        """mobile_window: None = PC, (w, h) = 모바일 미리보기 창 크기, (0, 0) = 기기 전체 화면.
        gpu: 모바일에서 확대를 GPU 에 맡김 (pygame SCALED — 캔버스 크기 그대로 올리고 기기 해상도 확대는 SDL 렌더러가.
             예전처럼 CPU 로 2400x1080 까지 키워 통째로 다시 올리지 않음, DESIGN.md 44). 실패하면 예전 방식."""
        self.mobile = mobile_window is not None
        self.gpu = False
        self.overlay = None  # 창 위에 덧그리는 함수 (모바일 미리보기: 노치·진동 표시)
        self.shake = (0, 0)  # 화면 흔들림 (캔버스 픽셀)
        try:
            from src.render.icon import icon_surface
            pygame.display.set_icon(icon_surface(32))  # set_mode 전에 해야 작업표시줄에도 적용
        except pygame.error:
            pass
        if self.mobile:
            flags = pygame.FULLSCREEN if tuple(mobile_window) == (0, 0) else 0
            if gpu:
                # 창을 처음부터 SCALED 로 만든다 (이미 만든 창을 SCALED 로 바꾸면 렌더러를 못 만드는 기기가 있음 — pygame 2.6)
                try:
                    if flags:
                        d = (pygame.display.get_desktop_sizes() or [(0, 0)])[0]
                        ww, wh = max(d), min(d)   # 가로 고정 게임
                    else:
                        ww, wh = mobile_window
                    if ww <= 0 or wh <= 0:
                        raise pygame.error("화면 크기 모름")
                    width, height = canvas_size_for(ww, wh)
                    self.window = pygame.display.set_mode((width, height), flags | pygame.SCALED)
                    self.gpu = True
                    self._gpu_dest(width, height)
                except pygame.error:
                    self.gpu = False
            if not self.gpu:
                self.window = pygame.display.set_mode(tuple(mobile_window), flags)
                ww, wh = self.window.get_size()
                width, height = canvas_size_for(ww, wh)
                self.fscale = min(ww / width, wh / height)
                self.scale = self.fscale
                dw, dh = int(width * self.fscale), int(height * self.fscale)
                self.dest = pygame.Rect((ww - dw) // 2, (wh - dh) // 2, dw, dh)
                self.device_size = (ww, wh)   # 손가락 좌표(0~1) → 기기 픽셀
        self.width = width
        self.height = height
        self.canvas = opaque((width, height))
        self.ui_rect = pygame.Rect((width - BASE_W) // 2, (height - BASE_H) // 2, BASE_W, BASE_H)
        # 좌우 안전 여백 (캔버스 px): 가로가 긴 폰은 가장자리에 카메라 구멍·둥근 모서리가 있다. PC·태블릿은 0
        self.safe_x = 0
        if self.mobile and width >= 540:
            from src.core.config import load_json
            self.safe_x = load_json("mobile_config.json")["safe_x_px"]
        if self.mobile:
            from src.platform.detect import IS_ANDROID
            if IS_ANDROID:
                # 실제 기기: 카메라 구멍 안전 여백을 물어본다 (기기 픽셀 → 캔버스 픽셀). 모를 땐 위 기본값
                from src.platform import android
                ins = android.cutout_insets()
                if ins is not None:
                    self.safe_x = max(6, -(-max(ins) // max(1, int(self.fscale))) + 2)
        if not self.mobile:
            self.scale = scale or self._best_scale()
            self.window = pygame.display.set_mode((width * self.scale, height * self.scale))
        pygame.display.set_caption(title)
        # 창 형식이 캔버스와 다르면 transform.scale 로 창에 바로 쓸 수 없다 → 작은 캔버스를 창 형식으로 한 번 옮긴 뒤 확대
        self.same_fmt = (self.window.get_bitsize() == 32 and self.window.get_masks()[:3] == self.canvas.get_masks()[:3])
        self._conv = None if self.same_fmt else pygame.Surface((width, height), 0, self.window)
        import os
        out = "GPU 확대" if self.gpu else ("CPU 확대 (안전 모드)" if os.environ.get("FP_SAFE") else "CPU 확대") if self.mobile else ""
        self.fmt_note = f"창 {fmt_name(self.window)} · 캔버스 {fmt_name(self.canvas)}" + (f" · {out}" if out else "")

    def _src(self) -> pygame.Surface:
        """창 형식의 캔버스 (같으면 캔버스 그대로)."""
        if self._conv is None:
            return self.canvas
        self._conv.blit(self.canvas, (0, 0))
        return self._conv

    def _best_scale(self) -> int:
        """모니터에 들어가는 가장 큰 정수 배율 (작업표시줄 여유 고려)."""
        sizes = pygame.display.get_desktop_sizes()
        if not sizes:
            return 3
        dw, dh = sizes[0]
        return max(1, min((dw - 80) // self.width, (dh - 120) // self.height))

    def set_scale(self, scale: int) -> None:
        if self.mobile:
            return
        self.scale = max(1, scale)
        self.window = pygame.display.set_mode((self.width * self.scale, self.height * self.scale))
        self.same_fmt = (self.window.get_bitsize() == 32 and self.window.get_masks()[:3] == self.canvas.get_masks()[:3])
        self._conv = None if self.same_fmt else pygame.Surface((self.width, self.height), 0, self.window)

    def to_canvas(self, pos: tuple[int, int]) -> tuple[int, int]:
        """창 좌표(마우스) → 캔버스 좌표. GPU 모드는 SDL 이 마우스 좌표를 이미 캔버스 크기로 바꿔 준다."""
        if self.gpu:
            return int(pos[0]), int(pos[1])
        if self.mobile:
            return (int((pos[0] - self.dest.x) / self.fscale), int((pos[1] - self.dest.y) / self.fscale))
        return pos[0] // self.scale, pos[1] // self.scale

    def _gpu_dest(self, width: int, height: int) -> None:
        """GPU 모드: 실제 창 크기와 렌더러 배율로 화면 안 캔버스 자리(손가락 좌표 변환)를 다시 잡는다."""
        ww, wh = pygame.display.get_window_size()
        sx = sy = min(ww / width, wh / height)
        try:
            from pygame._sdl2 import video
            sx, sy = video.Renderer.from_window(video.Window.from_display_module()).scale
        except Exception:
            pass
        self.device_size = (ww, wh)
        self.fscale = self.scale = sx
        dw, dh = int(width * sx), int(height * sy)
        self.dest = pygame.Rect((ww - dw) // 2, (wh - dh) // 2, dw, dh)

    def finger_to_canvas(self, nx: float, ny: float) -> tuple[int, int]:
        """손가락 이벤트 좌표(창 기준 0~1) → 캔버스 좌표."""
        if self.mobile:
            ww, wh = self.device_size
            return (int((nx * ww - self.dest.x) * self.width / self.dest.w),
                    int((ny * wh - self.dest.y) * self.height / self.dest.h))
        ww, wh = self.window.get_size()
        return self.to_canvas((nx * ww, ny * wh))

    def present(self) -> None:
        if self.gpu:
            # 캔버스 크기 그대로 창 표면에 → flip 때 SDL 렌더러가 GPU 로 기기 해상도까지 확대
            if self.shake == (0, 0):
                self.window.blit(self.canvas, (0, 0))
            else:
                self.window.fill((0, 0, 0))
                self.window.blit(self.canvas, self.shake)
            pygame.display.flip()
            return
        if self.mobile:
            # 폰은 창이 기기 해상도(예: 2400x1080)라 프레임마다 전체를 칠하고 새로 확대해 붙이면 무겁다 (v0.8.7):
            # 흔들림이 없으면 화면 안 그 자리에 바로 확대해 쓰고, 검은 띠는 흔들림이 있었을 때만 다시 칠한다.
            sx, sy = int(self.shake[0] * self.fscale), int(self.shake[1] * self.fscale)
            if (sx, sy) == (0, 0) and self.window.get_rect().contains(self.dest):
                if getattr(self, "_bars_dirty", True) or self.overlay is not None:  # 미리보기는 띠에 표시를 그린다
                    self.window.fill((0, 0, 0))
                    self._bars_dirty = False
                pygame.transform.scale(self._src(), self.dest.size, self.window.subsurface(self.dest))
            else:
                self.window.fill((0, 0, 0))
                scaled = pygame.transform.scale(self._src(), self.dest.size)
                self.window.blit(scaled, (self.dest.x + sx, self.dest.y + sy))
                self._bars_dirty = True
        elif self.shake == (0, 0):
            pygame.transform.scale(self._src(), self.window.get_size(), self.window)
        else:
            scaled = pygame.transform.scale(self._src(), self.window.get_size())
            self.window.fill((0, 0, 0))
            self.window.blit(scaled, (self.shake[0] * self.scale, self.shake[1] * self.scale))
        if self.overlay is not None:
            self.overlay(self.window)
        pygame.display.flip()
