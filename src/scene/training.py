"""훈련 수조 (DESIGN.md 31장 C5): 해금한 패턴(또는 계열)을 골라 무한 반복 연습.

- 낚시 화면 위에서 도는 '훈련 모드' (FishingScene.training). 지도에서 들어간다.
- 줄 끊김·바늘 빠짐·도주 없음(게이지를 계속 채워 둠), 잡히지도 않음 → 보상·패널티·변이·의뢰·숙련도 기록 없음.
- 예고 속도: 0.5배(예고 2배 길게) / 1배(계열 최소 예고) / 실전(그 패턴 교관 물고기의 원래 예고).
- 훈련 수조 안에서만 숫자(성공률) 표시 허용.
"""
import copy

from src.core.config import load_json
from src.save.save_game import all_fish
from src.ui import signal_slots as ss
from src.ui import widgets as ui
from src.ui.hud import text

# 패턴 → 훈련용으로 빌려 쓰는 물고기 (그 패턴 교관)
BASE_FISH = {"rush": "bass", "jump": "bass", "turn": "bass", "leap": "bass", "shake": "cherry_salmon",
             "dive": "rockfish", "surface": "sea_bass", "reverse": "red_seabream", "twist": "alfonsino",
             "chain": "galaxy_trout", "hide": "marsh_eel", "pump": "stalactite_catfish", "thrash": "falls_salmon",
             "bite": "lava_grouper", "dual": "life_trout", "rush_big": "marlin"}
# rush_big = 돌진 (대형): 큰 물고기라 줄 펄스가 2번 (31-14)
ORDER = ("rush", "rush_big", "jump", "turn", "leap", "shake", "dive", "surface", "reverse", "twist", "chain", "hide", "pump",
         "thrash", "bite", "dual")
SPEEDS = (("slow", "0.5배"), ("norm", "1배"), ("real", "실전"))


def unlocked(save, tutorial) -> list[str]:
    """만나 본 패턴만 (기존 행동은 그 첫 만남 카드를 봤으면)."""
    seen = set(save.data.get("patterns_seen", []))
    out = []
    for p in ORDER:
        if p in ("rush", "rush_big", "jump", "turn", "leap"):
            q = "rush" if p == "rush_big" else p
            if tutorial.is_seen(f"telegraph:{q}") or save.data.get("pattern_mastery", {}).get(q):
                out.append(p)
        elif p in seen:
            out.append(p)
    return out


class TrainingTank:
    def __init__(self, scene):
        self.scene = scene
        pats = unlocked(scene.save, scene.tutorial) or ["rush"]
        fams = []
        for p in pats:
            f = ss.family_of(p)
            if f in ss.cfg()["families"] and f not in fams:
                fams.append(f)
        # 고를 것: 패턴 하나씩 + 계열 (그 계열의 해금 패턴을 섞어서)
        self.entries = [("pat", p) for p in pats] + [("fam", f) for f in fams]
        # 환상어 고유 패턴: 잡아 본 환상어만 (33장 P4)
        from src.fishing import phantom
        self.entries += [("ph", fid) for fid in phantom.caught_ids(scene.save)]
        self.pats = pats
        self.index = 0
        self.speed = 1
        self.ok = 0
        self.n = 0
        self.btn_prev = ui.Button((0, 0, 18, 15), "<", lambda: self._pick(-1))
        self.btn_next = ui.Button((0, 0, 18, 15), ">", lambda: self._pick(1))
        self.btn_speed = ui.Button((0, 0, 52, 15), "", self._speed)
        self.btn_exit = ui.Button((0, 0, 44, 15), "나가기", self.stop)

    # ── 고르기 ──
    def label(self) -> str:
        kind, v = self.entries[self.index]
        if kind == "fam":
            return f"계열: {ss.cfg()['families'][v]['name']}"
        if kind == "ph":
            from src.fishing.phantom import by_id
            return f"환상: {by_id(v)['sig_title']}"
        return load_json("patterns.json")["names"].get(v) or {"rush": "돌진", "rush_big": "돌진 (대형)", "jump": "점프",
                                                                 "turn": "방향 전환", "leap": "몸털기 점프"}[v]

    def actions(self) -> list[str]:
        kind, v = self.entries[self.index]
        if kind == "pat":
            return [v]
        if kind == "ph":
            from src.fishing.phantom import by_id
            f = by_id(v)
            return list(f["phases"][-1].get("actions") or f["actions"])
        return [p for p in self.pats if ss.family_of(p) == v and p != "rush_big"]

    def _pick(self, d: int) -> None:
        self.index = (self.index + d) % len(self.entries)
        self.ok = self.n = 0
        self.start()

    def _speed(self) -> None:
        self.speed = (self.speed + 1) % len(SPEEDS)
        self.ok = self.n = 0
        self.start()

    # ── 진행 ──
    def start(self) -> None:
        """훈련용 물고기로 파이팅 시작 (변이·의뢰·기믹·위협 구역 없음)."""
        sc = self.scene
        acts = self.actions()
        kind, v = self.entries[self.index]
        if kind == "ph":
            # 잡아 본 환상어의 2페이즈(고유 패턴) 그대로 — 보라 연출·보상 없음
            from src.fishing.phantom import by_id
            src = by_id(v)
            fish = copy.deepcopy({**src, **{k: x for k, x in src["phases"][-1].items() if k != "desc"}})
            fish.pop("phases", None)
            fish.pop("phase_at", None)
            fish["rarity"] = "uncommon"
            fish["id"] = "training"
            fish["stamina"] = 99999
            fish["spot"] = src["spot"]
            self._begin(fish)
            return
        base = next(f for f in all_fish() if f["id"] == BASE_FISH[acts[0]])
        fish = copy.deepcopy(base)
        fish.pop("phases", None)
        fish.pop("first_rush", None)
        fish["rarity"] = "uncommon"
        fish["actions"] = {("rush" if a == "rush_big" else a): 10 for a in acts}
        fish["fake_tired"] = 0.0
        fish["fake_cue"] = 0.0
        fish["spot"] = "world_tree" if "dual" in acts else sc.spot_id
        fish["id"] = "training"
        fish["stamina"] = 99999
        self._begin(fish)

    def _begin(self, fish: dict) -> None:
        sc = self.scene
        sc.fight = None
        sc.cast.reset()
        sc.bite.fish = fish
        sc.bite.cast_distance = 18
        sc.cast.bx, sc.cast.bz = 0.0, 18.0
        from src.fishing.casting import CastState
        sc.cast.state = CastState.HOOKED
        sc._start_fight()
        b = sc.fight.brain
        b.load_budget = 99            # 시간 규칙(최소 예고·휴식)은 그대로, 예산만 풀어 연습 횟수를 늘림
        b.mastery = b.fail_streak = None
        b.train_speed = SPEEDS[self.speed][0]
        sc.quest_run = None
        sc.card = None

    def stop(self) -> None:
        sc = self.scene
        sc.training = None
        sc.fight = None
        sc.cast.reset()
        sc.toasts.sink = None

    def update(self, dt: float) -> None:
        f = self.scene.fight
        if f is None or f.phase in ("caught", "lost", "net"):
            self.start()
            return
        # 패널티 없음: 줄·바늘·체력·거리를 계속 채워 둔다, 지치지도 않게
        f.line = max(f.line, f.line_max * 0.6)
        f.hook = min(f.hook, 50)
        f.hook_floor = 0.0
        f.snag = 0.0
        f.stamina = f.stamina_max
        f.distance = min(max(f.distance, 12.0), 24.0)
        f.escape_t = None
        f.brain.burst = max(f.brain.burst, 0.6)

    def count(self, pid: str, ok: bool) -> None:
        self.n += 1
        self.ok += 1 if ok else 0

    # ── 입력·그리기 ──
    def _layout(self, canvas) -> None:
        # 한 줄: [훈련] < 패턴 > [속도] 성공률 [나가기] — 위쪽 체력 막대 아래
        w = canvas.get_width()
        x = w // 2 - 170
        y = 34
        self.btn_prev.rect.topleft = (x + 34, y)
        self.btn_next.rect.topleft = (x + 142, y)
        self.btn_speed.rect.topleft = (x + 164, y)
        self.btn_exit.rect.topleft = (x + 294, y)
        self.bar = (x, y - 4, 340, 23)

    def handle(self, a) -> bool:
        if a.name in ("back", "menu"):
            self.stop()
            return True
        if a.name != "primary":
            return False
        for b in (self.btn_prev, self.btn_next, self.btn_speed, self.btn_exit):
            if b.click(a.pos):
                self.scene.sfx.play("ui_click")
                return True
        return False

    def draw(self, canvas, mouse) -> None:
        self._layout(canvas)
        import pygame
        x, y, w, h = self.bar
        back = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(back, (12, 16, 30, 200), back.get_rect(), border_radius=6)
        canvas.blit(back, (x, y))
        text(canvas, "훈련", (x + 6, y + 11), (255, 214, 90), 11, "midleft")
        text(canvas, self.label(), (self.btn_prev.rect.right + 52, y + 11), (240, 244, 252), 11, "center")
        self.btn_speed.label = f"속도 {SPEEDS[self.speed][1]}"
        for b in (self.btn_prev, self.btn_next, self.btn_speed, self.btn_exit):
            b.draw(canvas, mouse)
        rate = f"{self.ok}/{self.n} {self.ok * 100 // self.n}%" if self.n else "-"
        text(canvas, rate, (self.btn_speed.rect.right + 39, y + 11), (130, 255, 180), 11, "center")
