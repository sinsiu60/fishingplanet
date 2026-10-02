"""1인칭 가짜 3D 투영.

월드 좌표: x = 좌우(m), z = 앞쪽 거리(m), h = 수면 위 높이(m).
수평선은 화면에 고정, 카메라는 좌우로만 회전(yaw)한다.
"""
import math


class Camera:
    def __init__(self, width: int, height: int, cfg: dict):
        self.width = width
        self.height = height
        self.cx = width / 2
        self.horizon = int(height * cfg["horizon_ratio"])
        # 초점거리는 16:9 기준 폭으로: 폰(더 넓음)은 좌우가 더 보이고, 태블릿(더 높음)은 위아래가 더 보인다 (PC는 그대로)
        ref_w = min(width, height * 16 / 9)
        self.f = (ref_w / 2) / math.tan(math.radians(cfg["fov_deg"]) / 2)
        self.cam_h = cfg["cam_height"]
        self.max_yaw = math.radians(cfg["max_yaw_deg"])
        self.yaw = 0.0

    def project(self, x: float, z: float, h: float = 0.0):
        """월드 → (화면 x, 화면 y, 배율 px/m). 카메라 뒤면 None."""
        cy, sy = math.cos(self.yaw), math.sin(self.yaw)
        xr = x * cy - z * sy
        zr = x * sy + z * cy
        if zr < 0.2:
            return None
        s = self.f / zr
        return self.cx + xr * s, self.horizon + (self.cam_h - h) * s, s

    def row_for_distance(self, z: float) -> float:
        return self.horizon + self.cam_h * self.f / z

    def distance_for_row(self, y: float) -> float:
        return self.cam_h * self.f / max(0.5, y - self.horizon)

    def angle_to_x(self, angle: float):
        rel = angle - self.yaw
        if abs(rel) >= math.pi / 2 - 0.05:
            return None
        return self.cx + math.tan(rel) * self.f

    def parallax(self, factor: float) -> float:
        """배경 레이어 스크롤 픽셀 (멀리 있는 레이어일수록 factor 작게)."""
        return self.yaw * self.f * factor
