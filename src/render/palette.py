"""시간대별 팔레트 보간. 모든 그리기는 여기서 나온 색 변수를 쓴다."""
from src.core.config import load_json
from src.core.mathutil import lerp, lerp_color


class Palette:
    def __init__(self):
        frames = load_json("palettes.json")["keyframes"]
        self.frames = []
        for f in sorted(frames, key=lambda f: f["hour"]):
            colors = {}
            for k, v in f.items():
                if k in ("hour", "name"):
                    continue
                colors[k] = tuple(v) if isinstance(v, list) else float(v)
            self.frames.append((f["hour"], colors))

    def sample(self, hour: float) -> dict:
        hour %= 24.0
        frames = self.frames
        a = frames[-1]
        b = frames[0]
        for i, fr in enumerate(frames):
            if fr[0] > hour:
                b = fr
                a = frames[i - 1]
                break
        else:
            a, b = frames[-1], frames[0]
        ha, hb = a[0], b[0]
        if hb <= ha:
            hb += 24.0
        h = hour if hour >= ha else hour + 24.0
        t = (h - ha) / (hb - ha) if hb > ha else 0.0
        out = {}
        for k, va in a[1].items():
            vb = b[1][k]
            out[k] = lerp(va, vb, t) if isinstance(va, float) else lerp_color(va, vb, t)
        return out
