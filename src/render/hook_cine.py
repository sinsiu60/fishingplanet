"""고등급 입질 연출 엔진 (DETAILS.md B, DESIGN.md 45장 DT4~DT6). 수치는 data/details/hook_cinematics.json.

두 단계:
  ① 입질 예고 (pre)  진짜 입질('쑥')이 시작되는 순간 · 0.3초 이내 · 찌를 가리지 않음 (찌 · 줄보다 먼저 그림)
                     · 챔질 판정(bite.py BITE 창)은 건드리지 않는다 — 그림과 소리만.
  ② 챔질 연출 (post) 챔질 성공 직후 — FishingScene 이 Fight 를 아직 만들지 않고 기다림(물고기가 당기지 않음) · 입력 무시
                     · skip_after_sec 이후 탭하면 건너뛰기 → 끝나면 파이팅 시작.
반복: 첫 만남(seen_hook_cinematic 에 없는 종) = 전체 / 재회 = 전설 · 환상 짧은 버전, 희귀는 ① 만 / 일반 · 고급 = 없음.

②의 사건(events)은 데이터로 적고 장면이 실행한다: slowmo · bend · sfx · haptic · line_drops · pull (DT5 · DT6 에서 종류를 더함).
시간은 실제 초 — 슬로모션 중에도 연출 길이는 같다.
"""
import math

import pygame

from src.core.config import load_json


def cfg() -> dict:
    return load_json("details/hook_cinematics.json")


def seen_list(save) -> list:
    return save.data.setdefault("details", {}).setdefault("seen_hook_cinematic", [])


def plan(save, fish: dict | None, force_full: bool = False) -> dict:
    """이 물고기의 입질 연출 계획 {"pre": bool, "post": "full" | "short" | None, "rarity": str}."""
    if not fish:
        return {"pre": False, "post": None, "rarity": None}
    rar = "phantom" if fish.get("rarity") == "phantom" or fish.get("phantom") else fish.get("rarity")
    C = cfg()
    if rar not in C["rules"]["full_for"] or rar not in C or not C[rar].get("post", True):
        return {"pre": False, "post": None, "rarity": rar}
    first = force_full or fish["id"] not in seen_list(save)
    if first:
        post = "full"
    elif rar in C["rules"]["short_for"]:
        post = "short"
    else:
        post = None          # 희귀 재회: ① 예고만 (45-D 확정 9)
    return {"pre": True, "post": post, "rarity": rar}


class HookCine:
    def __init__(self):
        self.pre = None    # {"rarity", "t", "sec", "x", "z"}
        self.post = None   # {"rarity", "fish", "mode", "t", "sec", "events", "done_i", "bend", "pull"}

    # ── ① 입질 예고 ──
    def start_pre(self, rarity: str, x: float, z: float, sfx=None) -> None:
        c = cfg().get(rarity, {}).get("pre")
        if not isinstance(c, dict):
            return
        sec = min(c["sec"], cfg()["rules"]["pre_max_sec"])
        self.pre = {"rarity": rarity, "t": 0.0, "sec": sec, "x": x, "z": z, "c": c}
        if sfx is not None:
            hap = c.get("haptic")
            for i, (name, vol) in enumerate(c.get("sfx", [])):
                if hap and i == 0:
                    sfx.play(name, vol, haptic=hap[0])
                else:
                    sfx.play(name, vol, haptic="bite" if name == "sfx_bite_real" else None)

    # ── ② 챔질 연출 ──
    def start_post(self, rarity: str, fish: dict, mode: str) -> bool:
        rc = cfg().get(rarity, {})
        c = rc.get("post_short") if mode == "short" and rc.get("post_short") else rc.get("post")
        if not isinstance(c, dict) or mode is None:
            return False
        self.post = {"rarity": rarity, "fish": fish, "mode": mode, "t": 0.0, "sec": c["sec"],
                     "events": sorted(c.get("events", []), key=lambda e: e["at"]), "done_i": 0,
                     "bend": None, "pull": None}
        return True

    @property
    def active(self) -> bool:
        return self.post is not None

    def can_skip(self) -> bool:
        return self.post is not None and self.post["t"] >= cfg()["rules"]["skip_after_sec"]

    def update(self, dt_real: float, run) -> bool:
        """run(event) = 장면이 사건을 실행. 돌려주는 값: ②가 이번에 끝났나."""
        if self.pre is not None:
            self.pre["t"] += dt_real
            if self.pre["t"] >= self.pre["sec"]:
                self.pre = None
        p = self.post
        if p is None:
            return False
        p["t"] += dt_real
        while p["done_i"] < len(p["events"]) and p["events"][p["done_i"]]["at"] <= p["t"]:
            ev = p["events"][p["done_i"]]
            p["done_i"] += 1
            if ev["do"] == "bend":
                p["bend"] = ev
            elif ev["do"] == "pull":
                p["pull"] = dict(ev, t0=p["t"])
            else:
                run(ev)
        if p["t"] >= p["sec"]:
            self.post = None
            return True
        return False

    def finish(self) -> None:
        """건너뛰기: 남은 그림 사건은 버리고 바로 끝 (소리 · 슬로모션은 다시 내지 않음)."""
        self.post = None

    # ── 장면이 읽는 값 ──
    def bend_extra(self) -> float:
        """②: 낚싯대가 크게 휨 (px) — 처음 0.08초에 올라 끝까지 유지, 마지막 0.1초에 풀림."""
        p = self.post
        if p is None or p["bend"] is None:
            return 0.0
        b = p["bend"]
        up = min(1.0, (p["t"] - b["at"]) / 0.08)
        down = min(1.0, max(0.0, (b.get("until", p["sec"]) - p["t"]) / 0.1))
        return b["px"] * up * down

    def pull_offset(self, toward) -> tuple[int, int]:
        """②: 화면이 물(찌) 쪽으로 px 끌려갔다 돌아옴. toward = 화면 가운데 → 찌 방향 (단위 벡터)."""
        p = self.post
        if p is None or p["pull"] is None:
            return (0, 0)
        u = (p["t"] - p["pull"]["t0"]) / max(0.01, p["pull"]["sec"])
        if u >= 1.0:
            return (0, 0)
        k = math.sin(math.pi * u) * p["pull"]["px"]
        return (int(round(toward[0] * k)), int(round(toward[1] * k)))

    def bobber_offset(self) -> tuple[float, float]:
        """① 전설: 찌가 거칠게 끌려 들어감 (좌우 흔들 + 아래로)."""
        pr = self.pre
        if pr is None or pr["rarity"] != "legend":
            return (0.0, 0.0)
        k = min(1.0, pr["t"] / pr["sec"])
        d = pr["c"].get("drag_px", 3)
        return (math.sin(pr["t"] * 70) * d * 0.6, d * k)

    def draw_pre(self, canvas, cam, pal=None) -> None:
        pr0 = self.pre
        if pr0 is not None and pr0["rarity"] == "legend" and pal is not None:
            p = cam.project(pr0["x"], pr0["z"])
            if p is not None:
                from src.render.legend_hook_fx import bulge
                k = math.sin(math.pi * 0.5 * min(1.0, pr0["t"] / pr0["sec"]))
                bulge(canvas, pal, p[0], p[1] + 1, k, int(pr0["c"].get("bulge_px", 14) * max(0.6, p[2] / 20)))
            return
        """① 희귀: 찌가 들어가는 자리 물속 파란 빛 한 번 번쩍 — 찌 · 줄보다 먼저 그려서 찌를 가리지 않음."""
        pr = self.pre
        if pr is None or pr["rarity"] != "rare":
            return
        p = cam.project(pr["x"], pr["z"])
        if p is None:
            return
        k = math.sin(math.pi * min(1.0, pr["t"] / pr["sec"]))
        c = pr["c"]
        r = max(4, int(c["flash_radius"] * max(0.5, p[2] / 20)))
        col = tuple(int(v * k * 0.85) for v in c["flash_color"])
        g = pygame.Surface((r * 2 + 1, r + 1))
        pygame.draw.ellipse(g, tuple(v // 3 for v in col), (0, 0, r * 2 + 1, r + 1))
        pygame.draw.ellipse(g, col, (r // 2, r // 4, r + 1, r // 2 + 1))
        canvas.blit(g, (int(p[0]) - r, int(p[1]) + 1), special_flags=pygame.BLEND_RGB_ADD)   # 수면 아래쪽 (찌 바로 밑)
