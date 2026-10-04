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
