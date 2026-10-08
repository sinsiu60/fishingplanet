"""기다려지는 것 (CORE_UPDATE CU12): 계절 축제 · 떠돌이 상인 · 오렌의 도전장 · 주간 대회. 수치 · 문구는 data/events_calendar.json.

확률 · 판매에 영향 없는 것(외형 · 칭호 · 대사) 위주 — 떠돌이 상인 특별 주문(하루 한 종 3마리 ×2)만 소액.
축제 · 주간 대회 = 기기 실제 날짜 (date_events.today — 테스트에서 바꿀 수 있음), 상인 · 오렌 = 게임 날짜.
세이브: data["events_cal"] = {"fest": {"2026-autumn": True}, "merchant": {...}, "oren": {...}, "weekly": {...}, "trophies": [...]}
"""
import datetime
import random

from src.core.config import load_json


def cfg() -> dict:
    return load_json("events_calendar.json")


def st(save) -> dict:
    s = save.data.setdefault("events_cal", {})
    s.setdefault("fest", {})
    s.setdefault("trophies", [])
    return s


def _today() -> datetime.date:
    from src.render import date_events
    return date_events.today()


def _grant(save, title: str | None = None, skin: str | None = None) -> None:
    cos = save.data.setdefault("cosmetics", {"titles": [], "float_skins": [], "rod_skins": []})
    if title and title not in cos.setdefault("titles", []):
        cos["titles"].append(title)
    if skin and skin not in cos.setdefault("float_skins", []):
        cos["float_skins"].append(skin)


def title_name(tid: str) -> str:
    return load_json("quests.json").get("titles_extra", {}).get(tid, tid)


def skin_name(sid: str) -> str:
    return load_json("quests.json").get("skins_extra", {}).get(sid, {}).get("name", sid)


# ───────────────────────── 계절 축제 ─────────────────────────
def _in_range(md: str, a: str, b: str) -> bool:
    return a <= md <= b if a <= b else (md >= a or md <= b)


def festival(d: datetime.date | None = None) -> tuple[str, dict] | None:
    """지금(실제 날짜) 열리는 축제 (키, 정보) 또는 None."""
    d = d or _today()
    md = d.strftime("%m-%d")
    for k, f in cfg()["festivals"].items():
        if k.startswith("_"):
            continue
        if _in_range(md, f["from"], f["to"]):
            return k, f
    return None


def next_festival(days: int = 14, d: datetime.date | None = None) -> tuple[str, dict, datetime.date] | None:
    """오늘부터 days 일 안에 열리는(또는 열린) 축제 — 달력 위 축제 띠."""
    d = d or _today()
    for i in range(days):
        x = d + datetime.timedelta(days=i)
        f = festival(x)
        if f:
            return f[0], f[1], x
    return None


def festival_visit(save) -> tuple[str, dict] | None:
    """축제 주간 마을 첫 입장: 그해 처음이면 축제 찌 + 칭호 (외형만). 받았으면 (키, 정보)."""
    f = festival()
    if f is None:
        return None
    key = f"{_today().year}-{f[0]}"
    s = st(save)
    if s["fest"].get(key):
        return None
    s["fest"][key] = True
    _grant(save, f[1]["title"], f[1]["skin"])
    return f


# ───────────────────────── 떠돌이 상인 ─────────────────────────
def merchant_here(day: int) -> bool:
    m = cfg()["merchant"]
    return day % m["every_days"] == m["offset"]


def merchant(save, day: int) -> dict | None:
    """그날 상인 상태 {day, fish, sold, skin, bought} (상인이 없는 날은 None). 같은 날엔 같은 값 (날짜 씨앗)."""
    if not merchant_here(day):
        return None
    s = st(save)
    m = s.get("merchant")
    if m is None or m.get("day") != day:
        c = cfg()["merchant"]
        rnd = random.Random(day * 7919 + 13)
        from src.save.save_game import all_fish
        spots = {sp["id"]: sp for sp in load_json("spots.json")["spots"]}
        pool = [f for f in all_fish() if f["rarity"] in ("common", "uncommon")
                and spots.get(f["spot"], {}).get("continent", "sharmion") == "sharmion"]
        have = set(save.data.get("cosmetics", {}).get("float_skins", []))
        skins = [k for k in c["skins"] if k not in have]
        m = {"day": day, "fish": rnd.choice(pool)["id"], "sold": 0,
             "skin": rnd.choice(skins) if skins else None, "bought": False}
        s["merchant"] = m
    return m


def order_left(save, day: int, fid: str) -> int:
    m = merchant(save, day)
    if m is None or m["fish"] != fid:
        return 0
    return max(0, cfg()["merchant"]["order_max"] - m["sold"])


def order_sold(save, day: int, n: int = 1) -> None:
    m = merchant(save, day)
    if m is not None:
        m["sold"] += n


def buy_skin(save, day: int) -> str:
    """상인 외형 사기: 'ok' · 'money' · 'none'."""
    m = merchant(save, day)
    if m is None or not m["skin"] or m["bought"]:
        return "none"
    price = cfg()["merchant"]["skin_price"]
    if save.data["money"] < price:
        return "money"
    save.data["money"] -= price
    m["bought"] = True
    _grant(save, skin=m["skin"])
    return "ok"


# ───────────────────────── 오렌의 도전장 ─────────────────────────
def oren(save) -> dict | None:
    return st(save).get("oren")


def oren_offer(save, day: int, rnd=random) -> dict | None:
    """엘드라시온 마을에 들어올 때 (게임 날짜당 한 번 굴림): 새 도전장 (이미 진행 중이면 그대로)."""
    s = st(save)
    o = s.get("oren")
    if o is not None and not o.get("done"):
        return o
    if s.get("oren_roll_day") == day:
        return None
    s["oren_roll_day"] = day
    c = cfg()["oren"]
    if rnd.random() >= c["chance"]:
        return None
    from src.save.save_game import all_fish
    spots = {sp["id"]: sp for sp in load_json("spots.json")["spots"]}
    pool = [f for f in all_fish() if f["rarity"] in ("common", "uncommon", "rare") and save.caught(f["id"])
            and spots.get(f["spot"], {}).get("continent") == "eldrasion"]
    if not pool:
        return None
    f = rnd.choice(pool)
    size = round(f["size_cm"][1] * rnd.uniform(*c["size_k"]), 1)
    s["oren"] = {"fish": f["id"], "size": size, "day": day, "done": False, "react": False}
    return s["oren"]


def oren_line(save, key: str) -> str | None:
    o = oren(save)
    if o is None:
        return None
    from src.save.save_game import fish_by_id
    c = cfg()["oren"]
    line = c[key] if key != "react" else random.choice(c["react"])
    return line.format(fish=fish_by_id(o["fish"])["name"], size=f"{o.get('beat', o['size']):g}")


# ───────────────────────── 주간 대회 ─────────────────────────
def week_key(d: datetime.date | None = None) -> str:
    y, w, _ = (d or _today()).isocalendar()
    return f"{y}-W{w:02d}"


def weekly_fish(d: datetime.date | None = None) -> dict:
    from src.save.save_game import all_fish
    c = cfg()["weekly"]
    pool = [f for f in all_fish() if f["spot"] in c["pool_spots"] and f["rarity"] in ("common", "uncommon")]
    y, w, _ = (d or _today()).isocalendar()
    return pool[(y * 53 + w) % len(pool)]


def weekly_board(save) -> tuple[dict, list[tuple[str, float, bool]]]:
    """(그 주의 종, [(이름, 크기, 나?)] 큰 순)."""
    f = weekly_fish()
    c = cfg()["weekly"]
    rows = [(n, round(f["size_cm"][1] * k, 1), False) for n, k in c["npcs"]]
    w = st(save).get("weekly") or {}
    if w.get("week") == week_key() and w.get("best"):
        rows.append(("나", w["best"], True))
    rows.sort(key=lambda r: -r[1])
    return f, rows


def weekly_rank(save) -> int | None:
    _, rows = weekly_board(save)
    return next((i + 1 for i, r in enumerate(rows) if r[2]), None)


def weekly_settle(save) -> list[str]:
    """지난 주 대회 결과: 1~3등이면 칭호 + 집에 거는 트로피 (한 번). 돌려주는 값 = 알림 문장들."""
    s = st(save)
    w = s.get("weekly")
    if not w or w.get("week") == week_key() or w.get("settled") or not w.get("best"):
        return []
    w["settled"] = True
    f = next((x for x in load_json("fish.json")["fish"] if x["id"] == w["fish"]), None)
    if f is None:
        return []
    c = cfg()["weekly"]
    npc = sorted((round(f["size_cm"][1] * k, 1) for _, k in c["npcs"]), reverse=True)
    rank = 1 + sum(1 for v in npc if v > w["best"])
    if rank > 3:
        return [f"지난주 대회 ({f['name']}): {rank}등 — 다음 주에 다시!"]
    tid = c["titles"][rank - 1]
    _grant(save, tid)
    s["trophies"].append({"week": w["week"], "fish": f["id"], "rank": rank, "size": w["best"]})
    return [f"지난주 대회 {rank}등! ({f['name']} {w['best']:g}cm) 칭호 '{title_name(tid)}' · 집에 트로피"]


# ───────────────────────── 잡았을 때 ─────────────────────────
def on_catch(save, fish: dict, size: float, news: dict) -> None:
    """save_game.record_catch 가 부름: 오렌의 도전장 · 주간 대회 기록."""
    o = oren(save)
    if o is not None and not o.get("done") and fish["id"] == o["fish"] and size > o["size"]:
        o["done"], o["react"], o["beat"] = True, True, round(size, 1)
        first = cfg()["oren"]["title"] not in save.data.get("cosmetics", {}).get("titles", [])
        _grant(save, cfg()["oren"]["title"])
        news["oren"] = {"size": round(size, 1), "first": first}
    s = st(save)
    wk = week_key()
    w = s.get("weekly")
    if w is None or w.get("week") != wk:
        if w is not None and not w.get("settled"):
            s["pending_settle"] = weekly_settle(save)
        w = s["weekly"] = {"week": wk, "fish": weekly_fish()["id"], "best": 0.0}
    if fish["id"] == w["fish"] and size > w.get("best", 0.0):
        w["best"] = round(size, 1)
        news["weekly"] = {"size": w["best"], "rank": weekly_rank(save)}
