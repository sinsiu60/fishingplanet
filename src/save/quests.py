"""챌린지 의뢰 (DESIGN.md 27-5, Phase U6). 수치·템플릿·포인트 상점은 data/quests.json.

세이브 data["quests"] = {"points": 의뢰 포인트, "done": 완료 수, "boards": {대륙: 게시판}}
게시판 = {"daily": [의뢰 3개], "weekly": 의뢰, "date": "2026-10-02", "week": "2026-W40", "refresh_used": 0}
의뢰 = {"id", "conds": [{"t": 템플릿, ...수치}], "fish": 대상 물고기 id|None, "spot": 낚시터|None, "need": 필요 횟수,
        "have": 지금 횟수, "stars": 1~5, "reward": {...}, "done": bool, "weekly": bool}
  single 템플릿 = 특정 물고기 한 마리를 조건대로 잡기 (need 1) / multi = 여러 번 쌓기 (패턴 성공·변이·환경)
갱신: 기기 시간 자정(일일) / 월요일 0시(주간). 생성 난수는 날짜·대륙·새로고침 횟수로 정해져 같은 날엔 같은 의뢰.
파이팅 중 진행·위반은 QuestRun (낚시 씬이 파이팅마다 하나 만든다).
"""
import datetime
import random

from src.core.config import load_json

RARITY_KO = {"common": "일반", "uncommon": "고급", "rare": "희귀", "legend": "전설"}
WEATHER_KO = {"clear": "맑은 날", "rain": "비 오는 날", "storm": "폭풍 치는 날"}
PERIOD_KO = {"morning": "아침", "day": "낮", "evening": "저녁", "night": "밤"}


def cfg() -> dict:
    return load_json("quests.json")


def _spots() -> dict:
    return {s["id"]: s for s in load_json("spots.json")["spots"]}


def spot_cont(spot_id: str) -> str:
    return _spots().get(spot_id, {}).get("continent", "sharmion")


def today_key(now: datetime.datetime | None = None) -> str:
    return (now or datetime.datetime.now()).strftime("%Y-%m-%d")


def week_key(now: datetime.datetime | None = None) -> str:
    y, w, _ = (now or datetime.datetime.now()).isocalendar()
    return f"{y}-W{w:02d}"


def root(save) -> dict:
    q = save.data.setdefault("quests", {})
    q.setdefault("points", 0)
    q.setdefault("done", 0)
    q.setdefault("boards", {})
    return q


def board(save, cont: str, now: datetime.datetime | None = None) -> dict:
    """그 대륙 게시판 (날짜·주가 바뀌었으면 새로 만든다)."""
    q = root(save)
    b = q["boards"].setdefault(cont, {"daily": [], "weekly": None, "date": "", "week": "", "refresh_used": 0})
    d, w = today_key(now), week_key(now)
    if b["date"] != d:
        b["date"], b["refresh_used"] = d, 0
        b["daily"] = _make_daily(save, cont, f"{d}:{cont}:0")
    if b["week"] != w:
        b["week"] = w
        b["weekly"] = generate(save, cont, random.Random(f"{w}:{cont}"), weekly=True)
    if b["weekly"] is None:
        b["week"] = ""  # 아직 만들 게 없었다 — 다음에 다시
    return b


def refresh(save, cont: str) -> bool:
    """일일 의뢰 새로고침 (하루 refresh_per_day번, 끝낸 의뢰는 남긴다)."""
    b = board(save, cont)
    if b["refresh_used"] >= cfg()["refresh_per_day"]:
        return False
    b["refresh_used"] += 1
    kept = [x for x in b["daily"] if x["done"]]
    fresh = _make_daily(save, cont, f"{b['date']}:{cont}:{b['refresh_used']}")
    b["daily"] = kept + fresh[: cfg()["daily_count"] - len(kept)]
    return True


def force_new_day(save, cont: str) -> None:
    """[테스트] 의뢰 즉시 갱신: 날짜를 지운 것처럼 다시 만든다 (새로고침 횟수도 초기화)."""
    b = board(save, cont)
    b["refresh_used"] = 0
    n = b.get("debug_n", 0) + 1
    b["debug_n"] = n
    b["daily"] = _make_daily(save, cont, f"{b['date']}:{cont}:debug{n}")
    b["weekly"] = generate(save, cont, random.Random(f"{b['week']}:{cont}:debug{n}"), weekly=True)


def _make_daily(save, cont: str, seed: str) -> list[dict]:
    rnd = random.Random(seed)
    out, used = [], set()
    for _ in range(cfg()["daily_count"] * 4):
        q = generate(save, cont, rnd)
        if q is None:
            continue
        key = title(q)
        if key not in used:
            used.add(key)
            out.append(q)
        if len(out) >= cfg()["daily_count"]:
            break
    return out


# ───────────────────────── 생성 ─────────────────────────

def _context(save, cont: str) -> dict:
    from src.fishing.patterns import fish_patterns
    from src.save.save_game import all_fish
    spots = [s for s in save.data["unlocked_spots"] if spot_cont(s) == cont]
    fishes = [f for f in all_fish() if f["spot"] in spots and f["rarity"] != "legend"]
    caught = [f for f in fishes if save.caught(f["id"])]
    seen = set(save.data.get("patterns_seen", []))
    pats = sorted({p for f in fishes for p in fish_patterns(f)} & seen - {"chain", "dual", "fake"})
    muts = sorted({m for v in save.data.get("mutation_dex", {}).values() for m in v})
    return {"spots": spots, "caught": caught, "patterns": pats, "mutations": muts}


def _single_cond(save, t: str, fish: dict, rnd) -> dict | None:
    """특정 물고기 조건 하나 (만들 수 없으면 None)."""
    from src.fishing.fight import fish_gear_tier
    c = cfg()["templates"][t]
    if t == "gear_limit":
        n = save.gear_tier("rod") - 1
        if n < 1 or fish_gear_tier(fish) > n:
            return None
        return {"t": t, "n": n}
    if t == "drag_fixed":
        steps = save.fight_gear()["drag_steps"]
        return {"t": t, "k": (steps + 1) // 2}  # 파이팅 시작 단계 그대로 = 드랙을 건드리지 않기
    if t == "perfects":
        if not set(fish["actions"]) & {"jump", "leap", "thrash", "turn"}:
            return None
        return {"t": t, "k": rnd.randint(*c["k"])}
    if t == "double_perfect":
        if "thrash" not in fish["actions"] or c["needs_pattern"] not in save.data.get("patterns_seen", []):
            return None
        return {"t": t}
    if t == "line_keep":
        return {"t": t, "p": rnd.choice(range(c["p"][0], c["p"][1] + 1, 5))}
    if t == "time":
        est = fish.get("stamina", 100) * cfg()["fight_sec_per_stamina"] + 8
        return {"t": t, "sec": max(c["min_sec"], int(round(est * c["time_mult"] / 5.0)) * 5)}
    if t == "size":
        lo, hi = fish["size_cm"]
        return {"t": t, "cm": round(lo + (hi - lo) * (1 - c["top_frac"]))}
    return None


def generate(save, cont: str, rnd, weekly: bool = False) -> dict | None:
    """의뢰 하나. 해금된 것만 쓴다 (잡아 본 물고기·만나 본 패턴·잡아 본 변이)."""
    c = cfg()
    ctx = _context(save, cont)
    if not ctx["spots"]:
        return None  # 아직 못 간 대륙
    singles = [t for t, v in c["templates"].items() if v["kind"] == "single"]
    for _ in range(40):
        multi_ok = ["env"] + (["pattern"] if ctx["patterns"] else []) + (["mutation"] if ctx["mutations"] else [])
        use_single = bool(ctx["caught"]) and (weekly or rnd.random() < 0.65)
        if use_single:
            pool = ctx["caught"]
            if weekly:
                pool = sorted(pool, key=lambda f: ("common", "uncommon", "rare").index(f["rarity"]))[-max(1, len(pool) // 3):]
            fish = rnd.choice(pool)
            t1 = rnd.choice(singles)
            c1 = _single_cond(save, t1, fish, rnd)
            if c1 is None:
                continue
            conds = [c1]
            if weekly or rnd.random() < c["combo_chance"]:
                t2 = rnd.choice([t for t in singles if t != t1])
                c2 = _single_cond(save, t2, fish, rnd)
                if c2 is None:
                    continue
                conds.append(c2)
            rs = c["rarity_star"][fish["rarity"]]
            if len(conds) == 1:
                stars = min(3, c["templates"][t1]["star"] + rs)
            else:
                stars = 5 if weekly or rs >= 1 else 4
            q = {"conds": conds, "fish": fish["id"], "spot": fish["spot"], "need": 1}
        else:
            t = rnd.choice(multi_ok)
            tc = c["templates"][t]
            k = rnd.randint(*tc["k"]) * (2 if weekly else 1) if "k" in tc else 1
            if t == "env":
                spot = rnd.choice(ctx["spots"])
                cond = {"t": t, "weather": rnd.choice(["clear", "rain"]), "period": rnd.choice(list(PERIOD_KO)), "spot": spot}
            elif t == "pattern":
                cond = {"t": t, "pattern": rnd.choice(ctx["patterns"])}
                spot = None
            else:
                # 잘 나오는 변이 하나 1마리, 또는 아무 변이 2~3마리
                kinds = [m for m in tc["kinds"] if m in ctx["mutations"]]
                if kinds and rnd.random() < 0.5:
                    cond, k = {"t": t, "mutation": rnd.choice(kinds)}, tc["k_kind"] * (2 if weekly else 1)
                else:
                    cond, k = {"t": t, "mutation": "any"}, rnd.randint(*tc["k_any"]) * (2 if weekly else 1)
                spot = None
            stars = 5 if weekly else tc["star"]
            q = {"conds": [cond], "fish": None, "spot": spot, "need": k}
        q.update(stars=stars, have=0, done=False, weekly=weekly)
        q["id"] = f"{cont}:{rnd.randrange(1 << 30):x}"
        q["reward"] = _reward(cont, q, ctx)
        return q
    return None


def _avg_price(spots: list[str]) -> float:
    from src.save.save_game import all_fish
    prices = [f["base_price"] for f in all_fish() if f["spot"] in spots and f["rarity"] != "legend"]
    return sum(prices) / len(prices) if prices else 50.0


def _reward(cont: str, q: dict, ctx: dict) -> dict:
    r = cfg()["reward"]
    s = q["stars"]
    spots = [q["spot"]] if q.get("spot") else ctx["spots"]
    out = {"gold": int(round(_avg_price(spots) * (r["gold_base"] + r["gold_per_star"] * s) / 10.0)) * 10,
           "materials": {cont: s * r["materials_per_star"]},
           "points": s * r["points_per_star"]}
    chest = r["chest_by_star"].get(str(s))
    if chest:
        out["chest"] = chest
    if q["weekly"]:
        out["chest"] = [r["weekly_chest"]]
        out["points"] += r["weekly_points"]
        out["title"] = r["weekly_title"]
    return out


# ───────────────────────── 글 ─────────────────────────

def cond_text(cond: dict) -> str:
    from src.fishing.mutation import cfg as mcfg
    t = cond["t"]
    tmpl = cfg()["templates"][t]["text"]
    if t == "pattern":
        return tmpl.format(pattern=load_json("patterns.json")["names"].get(cond["pattern"], cond["pattern"]), k="{k}")
    if t == "mutation":
        name = "아무" if cond["mutation"] == "any" else mcfg()["kinds"][cond["mutation"]]["name"]
        return tmpl.format(mutation=name, k="{k}")
    if t == "env":
        return tmpl.format(weather=WEATHER_KO.get(cond["weather"], cond["weather"]), period=PERIOD_KO[cond["period"]],
                           spot=_spots()[cond["spot"]]["name"], k="{k}")
    return tmpl.format(n=cond.get("n"), k=cond.get("k"), p=cond.get("p"), t=cond.get("sec"), s=cond.get("cm"))


def title(q: dict) -> str:
    """의뢰 한 줄: '퍼펙트 3회 이상으로 · 30초 안에 배스 잡기'."""
    from src.save.save_game import fish_by_id
    parts = [cond_text(c) for c in q["conds"]]
    if q.get("fish"):
        return " · ".join(parts) + f" {fish_by_id(q['fish'])['name']} 잡기"
    return parts[0].replace("{k}", str(q["need"]))


def progress_text(q: dict) -> str:
    if q["done"]:
        return "완료"
    return f"{q['have']}/{q['need']}" if q["need"] > 1 else "도전 중"


def reward_text(rw: dict) -> str:
    from src.ui.widgets import money_text
    parts = [money_text(rw["gold"]), f"소재 {sum(rw['materials'].values())}", f"포인트 {rw['points']}"]
    if rw.get("chest"):
        parts.append("상자")
    if rw.get("title"):
        parts.append("칭호")
    return " · ".join(parts)


# ───────────────────────── 완료 · 보상 ─────────────────────────

def complete(save, q: dict, rnd=random) -> dict:
    """의뢰 완료 + 보상 지급. 지급한 것을 돌려준다."""
    if q["done"]:
        return {}
    q["done"] = True
    q["have"] = q["need"]
    rw = q["reward"]
    d = save.data
    d["money"] += rw["gold"]
    d["stats"]["earned"] += rw["gold"]
    for k, v in rw["materials"].items():
        d["materials"][k] = d["materials"].get(k, 0) + v
    r = root(save)
    r["points"] += rw["points"]
    r["done"] += 1
    d["stats"]["quests_done"] = d["stats"].get("quests_done", 0) + 1
    got = dict(rw)
    if rw.get("chest"):
        from src.save import treasure
        grade = rnd.choice(rw["chest"])
        treasure.give_chest(save, grade)
        got["chest_grade"] = grade
    if rw.get("title"):
        cos = cosmetics(save)
        if rw["title"] not in cos["titles"]:
            cos["titles"].append(rw["title"])
    return got


def active(save, cont: str) -> list[dict]:
    b = board(save, cont)
    return [q for q in b["daily"] + ([b["weekly"]] if b["weekly"] else []) if q and not q["done"]]


# ───────────────────────── 파이팅 중 진행 ─────────────────────────

class QuestRun:
    """파이팅 하나 동안의 의뢰 진행. state: ok(지키는 중) / fail(위반 — 이번 파이팅은 실패, 의뢰는 남음) / done."""

    def __init__(self, save, fight, fish_id: str, spot: str, weather: str, period: str):
        self.save = save
        self.cont = spot_cont(spot)
        self.fish_id = fish_id
        self.ctx = {"spot": spot, "weather": weather, "period": period}
        self.items = []  # [quest, state, note]
        for q in active(save, self.cont):
            if q.get("fish") == fish_id:
                self.items.append([q, "ok", ""])
            elif q.get("fish") is None:
                c = q["conds"][0]
                if c["t"] == "env" and (c["spot"] != spot or c["weather"] != weather or c["period"] != period):
                    continue  # 지금 조건이 아니면 이 파이팅과 상관없음
                self.items.append([q, "ok", ""])
        self.start_checked = False
        self.events: list[str] = []

    def _fail(self, it, note: str) -> None:
        if it[1] == "ok":
            it[1], it[2] = "fail", note
            self.events.append("quest_fail")

    def update(self, fight) -> None:
        for it in self.items:
            q = it[0]
            if it[1] != "ok" or not q.get("fish"):
                continue
            for c in q["conds"]:
                t = c["t"]
                if t == "gear_limit" and not self.start_checked and self.save.gear_tier("rod") > c["n"]:
                    self._fail(it, f"낚싯대가 T{c['n']}보다 좋다")
                elif t == "drag_fixed" and fight.drag != c["k"]:
                    self._fail(it, "드랙을 바꿨다")
                elif t == "line_keep" and fight.line / fight.line_max * 100 < c["p"]:
                    self._fail(it, f"줄 {c['p']}% 아래")
                elif t == "time" and fight.elapsed > c["sec"]:
                    self._fail(it, "시간 초과")
        self.start_checked = True

    def on_event(self, ev: str) -> None:
        kind, _, pid = ev.partition(":")
        if kind != "pattern_ok":
            return
        for it in self.items:
            q = it[0]
            c = q["conds"][0]
            if not q.get("fish") and c["t"] == "pattern" and c["pattern"] == pid and not q["done"]:
                q["have"] = min(q["need"], q["have"] + 1)
                self.events.append("quest_progress")
                if q["have"] >= q["need"]:
                    self._finish(it)

    def on_caught(self, fight, result: dict) -> None:
        for it in self.items:
            q = it[0]
            if it[1] != "ok" or q["done"]:
                continue
            if q.get("fish"):
                ok, note = True, ""
                for c in q["conds"]:
                    t = c["t"]
                    if t == "perfects" and fight.perfects < c["k"]:
                        ok, note = False, f"퍼펙트 {fight.perfects}/{c['k']}"
                    elif t == "double_perfect" and fight.double_perfects < 1:
                        ok, note = False, "더블 퍼펙트 없음"
                    elif t == "size" and result["size"] < c["cm"]:
                        ok, note = False, f"{result['size']:.0f}cm < {c['cm']}cm"
                if ok:
                    q["have"] = 1
                    self._finish(it)
                else:
                    self._fail(it, note)
                continue
            c = q["conds"][0]
            muts = result.get("mutations") or []
            if c["t"] == "env" or (c["t"] == "mutation" and muts and (c["mutation"] == "any" or c["mutation"] in muts)):
                q["have"] = min(q["need"], q["have"] + 1)
                self.events.append("quest_progress")
                if q["have"] >= q["need"]:
                    self._finish(it)

    def _finish(self, it) -> None:
        it[1] = "done"
        it.append(complete(self.save, it[0]))
        self.events.append("quest_done")

    def hud_lines(self) -> list[tuple[str, str]]:
        """(글, 상태) — 오른쪽 위 작은 표시용."""
        out = []
        for it in self.items[:3]:
            q, state, note = it[0], it[1], it[2]
            label = f"{'★' * q['stars']} {title(q)}"
            if state == "fail":
                label += f" — 실패({note})"
            elif q["need"] > 1:
                label += f" {q['have']}/{q['need']}"
            out.append((label, state))
        return out


# ───────────────────────── 외형 · 칭호 ─────────────────────────

def cosmetics(save) -> dict:
    cos = save.data.setdefault("cosmetics", {})
    for k in ("titles", "float_skins", "rod_skins"):
        cos.setdefault(k, [])
    return cos


def equipped(save) -> dict:
    eq = save.data.setdefault("equipped_cosmetic", {})
    for k in ("title", "float_skin", "rod_skin"):
        eq.setdefault(k, None)
    return eq


KIND_SLOT = {"title": ("titles", "title"), "float_skin": ("float_skins", "float_skin"), "rod_skin": ("rod_skins", "rod_skin")}


def shop_item(item_id: str) -> dict | None:
    c = cfg()
    it = next((x for x in c["shop"] if x["id"] == item_id), None)
    if it:
        return it
    if item_id in c["titles_extra"]:
        return {"id": item_id, "kind": "title", "name": c["titles_extra"][item_id]}
    if item_id in c["skins_extra"]:
        return {"id": item_id, **c["skins_extra"][item_id]}
    return None


def owns(save, item: dict) -> bool:
    return item["id"] in cosmetics(save)[KIND_SLOT[item["kind"]][0]]


def buy(save, item_id: str) -> str:
    """'ok' / 'owned' / 'points'."""
    it = shop_item(item_id)
    if owns(save, it):
        return "owned"
    r = root(save)
    if r["points"] < it["price"]:
        return "points"
    r["points"] -= it["price"]
    cosmetics(save)[KIND_SLOT[it["kind"]][0]].append(it["id"])
    return "ok"


def toggle_equip(save, item_id: str) -> None:
    it = shop_item(item_id)
    slot = KIND_SLOT[it["kind"]][1]
    eq = equipped(save)
    eq[slot] = None if eq[slot] == item_id else item_id


def title_name(save) -> str | None:
    tid = equipped(save)["title"]
    it = shop_item(tid) if tid else None
    return it["name"] if it else None


def skin_colors(save, kind: str):
    sid = equipped(save)[kind]
    it = shop_item(sid) if sid else None
    return [tuple(c) for c in it["colors"]] if it else None
