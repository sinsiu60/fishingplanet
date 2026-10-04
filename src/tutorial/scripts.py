"""튜토리얼 대본: 대본 물고기(튜토리얼에 필요한 순간이 반드시 오게) · 단계별 특수 진행 · 끝났을 때 할 일.

data/tutorials.json 의 튜토리얼마다
  script  이름 → SCRIPTS[이름] = {"start", "stop", "tick", "on_step"} (없는 칸은 건너뜀)
  fish    대본 물고기 행동 (plan(game, 키) 로 낚시 코드가 읽는다 — 예: 입질 시각, 지침 시각, 패턴 고정)
  on_done 끝났을 때 할 일 (ACTIONS)
tick 이 True 를 돌려주면 그 프레임은 가이드가 단계 조건을 보지 않는다 (대본이 직접 진행).
"""

SCRIPTS: dict[str, dict] = {}
ACTIONS: dict = {}


def script(name: str):
    """@script("tg01_bite") class ... 또는 dict 등록."""
    def deco(obj):
        SCRIPTS[name] = {k: getattr(obj, k) for k in ("start", "stop", "tick", "on_step") if hasattr(obj, k)}
        return obj
    return deco


def action(game, name: str) -> None:
    fn = ACTIONS.get(name)
    if fn is not None:
        fn(game)


def _hook(game, tid: str, which: str, *args):
    tut = game.guide.data.get(tid, {})
    sc = SCRIPTS.get(tut.get("script") or "")
    fn = sc.get(which) if sc else None
    return fn(game, *args) if fn else None


def start(game, tid: str, run) -> None:
    _hook(game, tid, "start", run)
    _hook(game, tid, "on_step", run)


def stop(game, tid: str) -> None:
    _hook(game, tid, "stop")


def tick(game, tid: str, run, dt: float) -> bool:
    return bool(_hook(game, tid, "tick", run, dt))


def on_step(game, tid: str, run) -> None:
    _hook(game, tid, "on_step", run)


def plan(game, key: str):
    """진행 중인 튜토리얼의 대본 물고기 값 (없으면 None) — 낚시 코드가 '지금 대본대로 할까?'를 물을 때."""
    g = getattr(game, "guide", None)
    if g is None or g.run is None:
        return None
    return g.data[g.run["id"]].get("fish", {}).get(key)


def step_is(game, tid: str, i: int | None = None) -> bool:
    g = getattr(game, "guide", None)
    return g is not None and g.run is not None and g.run["id"] == tid and (i is None or g.run["i"] == i)


# ───────────────────────── 낚시 기본 (TG-01 ~ TG-03) ─────────────────────────
def _fishing(game):
    for sc in reversed(game.scenes.stack):
        if type(sc).__name__ == "FishingScene":
            return sc
    return None


class _TG02:
    """첫 파이팅 대본 (붕어): 패턴 없음 → 감는 동안 장력이 빨간 칸까지 → 손을 떼고 초록으로 돌아오면 지침 → 거리 0 → 뜰채."""

    @staticmethod
    def _plan(game):
        return game.guide.data["TG-02"].get("fish", {}).get("fight", {})

    @staticmethod
    def start(game, run) -> None:
        fs = _fishing(game)
        f = fs.fight if fs is not None else None
        if f is None:
            return
        b = f.brain
        b.actions = {}                       # 패턴 없이
        b.fake_cue_p = b.fake_rush_p = b.fake_tired_p = 0.0
        b.first_rush_done, b.first_rush_on = True, False
        b.chain_left = 0
        if b.state in ("telegraph", "charge", "rush"):
            b._enter("idle", 1.0)
        b.phases = []

    @staticmethod
    def tick(game, run, dt: float) -> bool:
        fs = _fishing(game)
        f = fs.fight if fs is not None else None
        if f is None:
            return False
        p = _TG02._plan(game)
        i = run["i"]
        # 튜토리얼 중엔 지지 않게 (줄·바늘이 끝까지 가지 않음)
        f.line = max(f.line, f.line_max * 0.35)
        f.hook = min(f.hook, 60.0)
        f.snag = min(f.snag, 60.0)
        if f.phase == "fight":
            b = f.brain
            if i <= 2:
                f.script_pull = 0.0
            elif i == 3:   # 계속 감아요 → 장력이 빨간 칸까지
                f.script_pull = min(p.get("red_pull_max", 45), f.script_pull + p.get("red_pull_rate", 18) * dt)
            else:
                f.script_pull = 0.0
            if i == 5 and b.state not in ("tired", "exhausted"):
                ctx = run["ctx"]
                ctx["green_t"] = ctx.get("green_t", 0.0) + dt if f.zone() == "green" or not f.reeling else 0.0
                if ctx["green_t"] >= p.get("tired_after_green", 1.5) and run["t"] > 1.0:
                    b._enter("tired", 999.0)   # 지침 (뜰채까지 계속)
                    need = f.cfg["net_min_stamina"]
                    f.stamina = min(f.stamina, f.stamina_max * need * 0.8)
                    b.events.append("tired")
            if i >= 6 and b.state not in ("tired", "exhausted"):
                b._enter("tired", 999.0)
        elif f.phase == "net" and i == 8 and not run["ctx"].get("net_set"):
            run["ctx"]["net_set"] = True
            f.net_t = f.net_period + 0.02   # 물고기가 멈춘 순간 (지금 누르면 건져짐)
        return False

    @staticmethod
    def stop(game) -> None:
        fs = _fishing(game)
        if fs is not None and fs.fight is not None:
            fs.fight.script_pull = 0.0


script("tg02_fight")(_TG02)


def _close_catch(game) -> None:
    """TG-03 마지막: 포획 카드 닫기 → TG-04."""
    fs = _fishing(game)
    if fs is not None and fs.fight is not None and fs.fight.phase in ("caught", "lost"):
        fs._end_fight()


ACTIONS["close_catch"] = _close_catch


# ───────────────────────── 도감 · 상점 (TG-04 ~ TG-07) ─────────────────────────
def _save_only(game) -> None:
    """다음 목표는 story.goal() 이 튜토리얼 완료 기록으로 고른다 — 여기선 저장만."""
    if game.save is not None:
        game.save_now()


ACTIONS["goal_sell"] = _save_only   # TG-04 끝: '하루네 낚시점에서 물고기를 팔아 보자'
ACTIONS["goal_baek"] = _save_only   # TG-07 끝: '마을 오두막의 노인을 만나 보자'


def _shop_to_buy(game) -> None:
    """TG-06 끝 → TG-07: 팔기 패널을 판매 + 장비 탭이 같이 있는 패널로 바꿔 '낚싯대' 탭을 누르게."""
    cur = game.scenes.current
    if type(cur).__name__ != "ShopScene" or cur.host is None:
        return
    host = cur.host
    game.scenes.pop()
    host.shop = None
    tabs = ["sell"] + host.c["shop_tabs"]["buy"]
    host._open_shop("buy", tabs=tabs, tab="sell")


ACTIONS["shop_to_buy"] = _shop_to_buy
