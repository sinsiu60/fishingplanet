"""튜토리얼 대본: 대본 물고기(튜토리얼에 필요한 순간이 반드시 오게) · 단계별 특수 진행 · 끝났을 때 할 일.

data/tutorials.json 의 튜토리얼마다
  script  이름 → SCRIPTS[이름] = {"start", "stop", "tick", "on_step"} (없는 칸은 건너뜀)
  fish    대본 물고기 행동 (plan(game, 키) 로 낚시 코드가 읽는다 — 예: 입질 시각, 지침 시각, 패턴 고정)
  on_done 끝났을 때 할 일 (ACTIONS)
tick 이 True 를 돌려주면 그 프레임은 가이드가 단계 조건을 보지 않는다 (대본이 직접 진행).
"""

import pygame

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
        return False   # 뜰채: 설명 단계(퍼덕임) → 물고기가 실제로 멈추는 순간 정지 (억지로 맞추지 않음)

    @staticmethod
    def stop(game) -> None:
        fs = _fishing(game)
        if fs is not None and fs.fight is not None:
            fs.fight.script_pull = 0.0


script("tg02_fight")(_TG02)


def _close_catch(game) -> None:
    """TG-03 마지막: 포획 카드 닫기 → TG-04."""
    fs = _fishing(game)
    if fs is None:
        return
    if fs.catch_show is not None:
        fs._close_catch_show()     # 환상·전설 연출 카드 (TG-PH)
    elif fs.fight is not None and fs.fight.phase in ("caught", "lost"):
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


# ───────────────────────── 패턴 튜토리얼 (TG-P1 ~ TG-P16) ─────────────────────────
# ① 예고 순간 정지(탭) → ② '그 순간'까지는 게임이 흐르고(released) 순간이 오면 정지 · 지시한 조작 → ③ 결과 1.5초.
# 튜토리얼 중: 그 패턴 예고 2배, 다른 패턴 안 나옴(행동 목록 비움). 정확히 조작하면 판정이 성공하도록 대본이 돕는다.
OPS = {   # 콤보·이중 패턴의 한 행동: (넘어가는 조건, 조작 이름)
    "rush": ("drag_down", "{드랙내리기}"), "jump": ("lower", "{숙이기}"), "turn": ("turn", "{왼쪽}"),
    "shake": ("release", "{손떼기}"), "dive": ("up", "{위}"), "surface": ("down", "{아래}"),
    "reverse": ("mash", "{연타}"), "twist": ("circle", "{원}"), "bite": ("drag_min", "{순간최저}"),
    "hide": ("drag_down", "{드랙내리기}"), "charge": ("reel", "{감기}"), "pump": ("reel", "{감기}"),
}
MOMENT_OF = {"rush": "rush", "jump": "apex", "turn": "turn", "charge": "charge_tired"}   # 그 밖은 'action'
WAIT_LIMIT = 14.0   # 순간이 끝내 안 오면 (물고기 행동이 바뀜) 이번엔 그만


class _Pattern:
    @staticmethod
    def _f(game):
        fs = _fishing(game)
        return fs.fight if fs is not None else None

    @staticmethod
    def start(game, run) -> None:
        f = _Pattern._f(game)
        if f is None:
            return
        tut = game.guide.data[run["id"]]
        b = f.brain
        ctx = run["ctx"]
        ctx["fight"] = f
        ctx["saved"] = (dict(b.actions), b.fake_cue_p, b.fake_rush_p, b.fake_tired_p)
        b.actions = {}                      # 다른 패턴은 나오지 않음
        b.fake_cue_p = b.fake_rush_p = 0.0
        if tut["pattern"] != "fake":
            b.fake_tired_p = 0.0
        if b.state == "telegraph":          # 예고 시간 2배
            b.timer += b.cur_telegraph
            b.cur_telegraph *= 2
        if "mash_need" in tut:
            ctx["mash_need"] = tut["mash_need"]

    @staticmethod
    def on_step(game, run) -> None:
        tut = game.guide.data[run["id"]]
        steps = tut["steps"]
        i = run["i"]
        ctx = run["ctx"]
        prev = steps[i - 1] if i > 0 else None
        f = ctx.get("fight")
        if prev is not None and prev.get("at") == "turn" and f is not None:
            f.flick(ctx.get("turn_need", 1))   # 꺾기 판정 (정지 중 방향을 맞춘 것으로)
        if i < len(steps) and steps[i].get("at"):
            ctx["released"] = True           # 그 순간까지는 게임이 흐름
            ctx["wait_t"] = 0.0
            ctx["ci"] = 0

    @staticmethod
    def _arm(run, text=None, until=None) -> None:
        ctx = run["ctx"]
        ctx["released"] = False
        ctx.pop("show", None)
        ctx["passed"] = []
        for k in ("c_acc", "c_prev", "c_hist", "mash_n", "circle_k"):
            ctx.pop(k, None)
        run["t"] = 0.0
        if text:
            ctx["text"] = text
        if until:
            from src.tutorial import conds
            ctx["allow"] = conds.ALLOWED.get(until, [])
            ctx["anim"] = conds.ANIM.get(until) if until != "turn" else ("swipe_l" if ctx.get("dir", -1) < 0 else "swipe_r")

    @staticmethod
    def _moment(f, at: str, pid: str, ctx) -> bool:
        b = f.brain
        if at == "rush":
            return (b.state == "telegraph" and b.pending == "rush" and b.timer <= 0.3) or b.state == "rush"
        if at == "apex":
            return b.state == "jump" and b.time_to_apex() <= 0.0
        if at == "second":
            return b.state == "jump" and b.jump_kind == "thrash" and b.time_to_second() <= 0.0
        if at == "turn":
            off = b.turn_offset()
            if off is not None and off >= -0.02:
                ctx["turn_need"] = -b.turn_dir
                ctx["dir"] = -b.turn_dir
                return True
            return False
        if at == "action":
            return b.state == pid or (b.state == "dual" and pid == "dual")
        if at == "peek":
            return any(p.id == "hide" and p.peeking for p in f.pats)
        if at in ("gap0", "gap1"):
            j = next((p for p in f.pats if p.id == "pump"), None)
            if j is None or not j.active:
                return False
            k, ph = j._phase()
            return k == int(at[-1]) and ph >= j.interval / 2 - 0.02
        if at == "charge_tired":
            if b.state == "charge" and b.timer <= 0.05:
                _Pattern._force_tired(b)
                return True
            return b.state == "tired"
        if at == "real_tired":
            if b.state == "fake_tired":
                ctx["fake_seen"] = True
                return False
            if ctx.get("fake_seen") and b.state in ("idle", "recover", "tired"):
                if b.state != "tired":
                    _Pattern._force_tired(b)
                return True
            return False
        return False

    @staticmethod
    def _force_tired(b) -> None:
        b.rush_after_charge = False
        b.pending = None
        b._enter("tired", max(2.5, b._rand(b.tired_range)))
        b.events.append("tired")

    @staticmethod
    def _assist(f, run, pid: str, tut) -> None:
        """정확히 조작했으면 판정도 성공하도록 (대본 물고기)."""
        i = run["i"]
        f.hook = min(f.hook, 80.0)                      # 튜토리얼 중엔 놓치지 않게 (바늘·줄·걸림)
        f.line = max(f.line, f.line_max * 0.3)
        f.snag = min(f.snag, 80.0)
        resp = [k for k, s in enumerate(tut["steps"]) if s.get("at")]
        after = i > resp[0] or pid in ("shake", "chain", "dual")   # 콤보·이중은 한 단계 안에서 여러 번
        if not after:
            f.script_pull = 0.0
            return
        b = f.brain
        f.script_pull = -45.0 if b.state == "rush" else 0.0   # 돌진: 줄을 풀어 줬으니 빨간 칸까지 가지 않게
        pair = set(b.dual_pair or ()) if pid == "dual" else {pid}
        if pid == "chain":
            pair = set(b.combo_all or ())
        for j in f.pats:
            if j.id not in pair:
                continue
            if j.id == "reverse":
                j.gauge = 100.0
            elif j.id == "twist":
                f.twist.value = 0.0
            elif j.id == "pump":
                j.hits = [True] * len(j.hits)
                j.bad = [False] * len(j.bad)
            elif j.id == "bite":
                if j.t0 is not None and not j.passed():
                    j.edges.append(j.t0)
            elif j.id == "hide":
                if not j.peeking and not j.success and i <= resp[-1]:
                    j.hold_t = j.c["hold_sec"]
                elif j.peeking and not j.success and i > resp[-1]:
                    j.success, j.react_left = True, 1.0
                    b.end_pattern("hide")
            j.ok_t = j.judged_t
        if f.twist.value > 0 and "twist" in pair:
            f.twist.value = 0.0

    @staticmethod
    def tick(game, run, dt: float) -> bool:
        g = game.guide
        tut = g.data[run["id"]]
        steps = tut["steps"]
        i = run["i"]
        ctx = run["ctx"]
        f = _Pattern._f(game)
        if f is None or f is not ctx.get("fight") or f.phase not in ("fight", "net"):
            if i < len(steps) - 1:
                g.abort()     # 물고기를 놓쳤다·잡았다: 다음에 그 순간이 오면 다시
                return True
            return False
        pid = tut["pattern"]
        _Pattern._assist(f, run, pid, tut)
        if i >= len(steps):
            return False
        s = steps[i]
        at = s.get("at")
        if not at:
            return False
        if ctx.get("released"):
            ctx["wait_t"] = ctx.get("wait_t", 0.0) + dt
            if ctx["wait_t"] > WAIT_LIMIT:
                g.abort()
                return True
        # ── 머리 흔들기: 문구를 띄운 채 진행, 손을 대면 정지 ──
        if s["until"] == "hold:shake":
            return _Pattern._shake(game, run, f, tut)
        # ── 콤보: 행동마다 따로 정지 ──
        if at == "chain":
            return _Pattern._chain(game, run, f, tut)
        if s["until"] == "dual":
            return _Pattern._dual(game, run, f, tut)
        if ctx.get("released") and _Pattern._moment(f, at, pid, ctx):
            text = None
            if at == "turn" and ctx.get("dir", -1) > 0:
                text = s["text"].replace("{왼쪽}", "{오른쪽}")   # 실제 화살표 방향대로
            _Pattern._arm(run, text)
        if s["until"] == "input:mash" and not ctx.get("released"):   # 연타 횟수 0/6
            n = sum(1 for p in ctx.get("passed", []) if p in ("primary", "reel_tap"))
            ctx["badge"] = f"{min(n, ctx.get('mash_need', 6))}/{ctx.get('mash_need', 6)}"
        return False

    @staticmethod
    def _shake(game, run, f, tut) -> bool:
        ctx = run["ctx"]
        b = f.brain
        inp = game.input
        touching = inp.held("reel") or inp.held("press")
        if b.state == "shake":
            ctx["shook"] = True
            if ctx.get("released"):
                ctx["show"] = True
                ctx["badge"] = tut["hold_text"]       # 참는 중…
                if touching:                          # 손을 댔다: 멈추고 '손을 떼세요!'
                    _Pattern._arm(run, tut["again_text"] + " {손떼기}")
                    ctx["badge"] = None
            elif not touching and run["t"] > 0.3:
                ctx["released"] = True
            return True
        if ctx.get("shook"):                          # 떨림이 끝났다 = 성공
            ctx.pop("show", None)
            game.guide._next(success=True)
            return True
        return True

    @staticmethod
    def _chain(game, run, f, tut) -> bool:
        from src.tutorial import conds
        ctx = run["ctx"]
        b = f.brain
        seq = list(b.chain_seq) if getattr(b, "chain_seq", None) else list(b.combo_all or [])
        ci = ctx.get("ci", 0)
        if ci >= len(seq):
            game.guide._next(success=True)
            return True
        act = seq[ci]
        until, op = OPS.get(act, ("reel", "{감기}"))
        texts = tut.get("chain_texts", ["첫 번째!", "두 번째!", "마지막!"])
        if ctx.get("released"):
            at = MOMENT_OF.get(act, "action")
            if _Pattern._moment(f, at, act, ctx):
                if act == "turn" and ctx.get("dir", -1) > 0:
                    op = "{오른쪽}"
                label = texts[min(ci, len(texts) - 1)] if ci < len(seq) - 1 else texts[-1]
                _Pattern._arm(run, f"{label} {op}", until)
            return True
        if until == "release":
            ok = run["t"] >= conds.INPUT_DELAY and not game.input.held("reel")
        else:
            ok = conds.input_ok(game, until, run)
        if ok:
            if act == "turn":
                f.flick(ctx.get("turn_need", 1))
            game.slowmo(0.3, 0.35)
            ctx["ci"] = ci + 1
            ctx["released"] = True
            ctx["wait_t"] = 0.0
            for k in ("text", "anim", "allow", "passed"):
                ctx.pop(k, None)
        return True

    @staticmethod
    def _dual(game, run, f, tut) -> bool:
        from src.tutorial import conds
        ctx = run["ctx"]
        b = f.brain
        if ctx.get("released"):
            if b.state == "dual" and b.dual_pair:
                pair = list(b.dual_pair)
                ctx["pair"] = pair
                ops = [OPS.get(a, ("reel", "{감기}")) for a in pair]
                _Pattern._arm(run)
                ctx["allow"] = sorted({x for u, _ in ops for x in conds.ALLOWED.get(u, [])})
                ctx["anim"] = conds.ANIM.get(ops[0][0])
                # 슬롯마다 조작 이름 (왼쪽 슬롯 = 첫 패턴, 오른쪽 = 둘째)
                from src.tutorial import targets
                rs = targets.rects(game, "fight.slots", run)
                r0 = rs[0] if rs else pygame.Rect(game.screen.width // 2 - 34, 60, 68, 40)
                from src.core.fonts import get_font
                g = game.guide
                w = [get_font(11).size(g._sub(o[1]))[0] + 10 for o in ops]
                ctx["labels"] = [(ops[0][1], (r0.left - 6 - w[0] // 2, r0.centery - 10)),
                                 (ops[1][1], (r0.right + 6 + w[1] // 2, r0.centery + 10))]
            return True
        pair = ctx.get("pair", [])
        oks = []
        for a in pair:
            u = OPS.get(a, ("reel", ""))[0]
            if u == "release":
                oks.append(run["t"] >= conds.INPUT_DELAY and not game.input.held("reel"))
            else:
                oks.append(conds.input_ok(game, u, run))
        if pair and all(oks):
            ctx.pop("labels", None)
            game.guide._next(success=True)
        return True

    @staticmethod
    def stop(game) -> None:
        g = game.guide
        f = _Pattern._f(game)
        ctx = g.run["ctx"] if g.run is not None else None
        if f is None:
            return
        f.script_pull = 0.0
        saved = ctx.get("saved") if ctx else None
        if saved and ctx.get("fight") is f:
            b = f.brain
            b.actions, b.fake_cue_p, b.fake_rush_p, b.fake_tired_p = saved


script("pattern")(_Pattern)


# ───────────────────────── 다른 시스템 (TG-09 ~ TG-19, TG-PH) ─────────────────────────
class _SeasonPanel:
    """TG-15: 계절이 바뀐 뒤 마을 입장 → 계절 알림판을 열어 두고 설명."""

    @staticmethod
    def start(game, run) -> None:
        cur = game.scenes.current
        if type(cur).__name__ == "VillageScene" and cur.panel is None:
            cur.panel = {"t": 0.0}


script("season_panel")(_SeasonPanel)


class _FloatShop:
    """TG-18: 엘라 공방 '사기' — 돈이 모자라면 '물고기를 팔면 살 수 있어요…' + 판매 탭."""

    @staticmethod
    def tick(game, run, dt: float) -> bool:
        if run["i"] != 2:
            return False
        cur = game.scenes.current
        if type(cur).__name__ != "ShopScene":
            return False
        from src.core.config import load_json
        it = next((f for f in load_json("floats.json")["floats"] if f["id"] == "paralysis_float"), None)
        owned = "paralysis_float" in game.save.data.get("float", {}).get("owned", [])
        ctx = run["ctx"]
        step = game.guide.data[run["id"]]["steps"][2]
        if it is not None and not owned and game.save.money < it["price"]:
            ctx["text"] = step["short_text"]
            ctx["target"] = "shop.tab.sell" if cur.kind != "sell" else "-"   # 판매 탭에선 막지 않음
        elif cur.kind != "float":
            ctx.pop("text", None)
            ctx["target"] = "shop.tab.float"
        else:
            ctx.pop("text", None)
            ctx.pop("target", None)
        return False


script("float_shop")(_FloatShop)


class _Phantom:
    """TG-PH: 포획 카드에서 백 노인 → 카드 닫기 → 도감 [환상] 탭."""

    @staticmethod
    def start(game, run) -> None:
        from src.fishing import phantom
        if game.save is not None:
            phantom.state(game.save)["tutorial"] = True


script("phantom")(_Phantom)
