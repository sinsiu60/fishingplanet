"""환상의 물고기 (DESIGN.md 33장, PHANTOM_FISH.md): 데이터·등장 판정·천장·세이브 기록.

data/phantom.json 에 따로 두므로 fish.json 을 도는 도감 %·해금·의뢰·변이 집계에 들어가지 않는다.
등장 판정은 찌가 착수하는 순간 (낚시 씬 _splash) — 판정되면 그 캐스팅은 가짜 입질 없이 환상어 진짜 입질.
"""
import random

from src.core.config import load_json

COLOR = (190, 120, 255)        # 환상 보라 (테두리·카드·탭)
COLOR_LIGHT = (225, 180, 255)  # 연보라 (대사·강조)
LINE = "물결이 숨을 죽인다"
LOST_LINE = "보라빛 잔상이 깊은 곳으로 사라졌다"


def cfg() -> dict:
    return load_json("phantom.json")


def spawn_cfg() -> dict:
    return cfg()["spawn"]


def all_phantoms() -> list[dict]:
    return cfg()["fish"]


def by_id(fid: str) -> dict | None:
    return next((f for f in all_phantoms() if f["id"] == fid), None)


def for_spot(spot: str) -> dict | None:
    return next((f for f in all_phantoms() if f["spot"] == spot), None)


def is_phantom(fish: dict | None) -> bool:
    return bool(fish) and fish.get("rarity") == "phantom"


def state(save) -> dict:
    """세이브 data['phantom'] (옛 세이브는 _deep_merge 가 기본값으로 채움)."""
    ph = save.data.setdefault("phantom", {})
    for k, v in (("casts", {}), ("caught", {}), ("tutorial", False), ("notes", []), ("scales", 0), ("rewards", []),
                 ("title_frame", False), ("phase2_seen", [])):   # phase2_seen: 2페이즈 컷신 전체 버전을 본 환상어
        ph.setdefault(k, v if not isinstance(v, (dict, list)) else type(v)())
    return ph


def reset_records(save) -> None:
    """테스트용: 환상어 낚은 기록을 지운다 (환상 도감·수집 보상 진행·첫 포획 튜토리얼·착수 천장).
    이미 받은 칭호·외형·부적·환상 비늘·돈은 그대로 — 다시 달성해도 겹쳐 주지 않음 (첫 포획 골드 보너스만 다시 받음)."""
    ph = state(save)
    ph["caught"] = {}
    ph["rewards"] = []
    ph["tutorial"] = False
    ph["casts"] = {}


def legend_caught(save, spot: str) -> bool:
    return any(f["spot"] == spot and f["rarity"] == "legend" and save.caught(f["id"])
               for f in load_json("fish.json")["fish"])


def chance(save, spot: str) -> float:
    """이번 착수의 환상 확률: 기본 0.5% / 그 낚시터 전설을 잡았으면 2%, 천장 이후 착수마다 +0.05%p (최대 5%)."""
    c = spawn_cfg()
    leg = legend_caught(save, spot)
    p = c["legend_chance"] if leg else c["base_chance"]
    n = state(save)["casts"].get(spot, 0)
    after = c["pity_after_legend"] if leg else c["pity_after"]
    if n > after:
        p = min(c["pity_max"], p + c["pity_step"] * (n - after))
    return p


def pity_frac(save, spot: str) -> float:
    """천장 진행도 0~1 (환상의 눈 눈금·먼 수면 보라 물결 빈도). 천장 시작까지 0→0.5, 최대 확률까지 0.5→1."""
    c = spawn_cfg()
    leg = legend_caught(save, spot)
    after = c["pity_after_legend"] if leg else c["pity_after"]
    n = state(save)["casts"].get(spot, 0)
    if n <= after:
        return 0.5 * n / after
    base = c["legend_chance"] if leg else c["base_chance"]
    full = (c["pity_max"] - base) / c["pity_step"]
    return min(1.0, 0.5 + 0.5 * (n - after) / max(1.0, full))


def roll(save, spot: str, rnd=random, force: bool = False) -> dict | None:
    """착수 순간 판정. 나오면 그 환상어, 아니면 None (착수 수 +1)."""
    fish = for_spot(spot)
    if fish is None:
        return None
    if force or rnd.random() < chance(save, spot):
        return fish
    casts = state(save)["casts"]
    casts[spot] = casts.get(spot, 0) + 1
    return None


def reset_pity(save, spot: str) -> None:
    """환상어와 파이팅까지 갔다 (잡든 놓치든) → 그 낚시터 천장 카운트 0."""
    state(save)["casts"][spot] = 0


def caught_ids(save) -> list[str]:
    return [fid for fid, e in state(save)["caught"].items() if e.get("count", 0) > 0]


def caught(save, fid: str) -> bool:
    return state(save)["caught"].get(fid, {}).get("count", 0) > 0


def record(save, result: dict) -> dict:
    """포획 기록 (환상 도감). 돌려줌: {'new': 그 종 첫 포획, 'first_ever': 환상어 첫 포획}."""
    ph = state(save)
    fid = result["fish"]["id"]
    first_ever = not caught_ids(save)
    e = ph["caught"].setdefault(fid, {"count": 0, "max_size": 0.0, "best_rank": "C"})
    new = e["count"] == 0
    e["count"] += 1
    e["max_size"] = max(e["max_size"], result["size"])
    order = "CBAS"
    if order.index(result["rank"]) > order.index(e["best_rank"]) or new:
        e["best_rank"] = result["rank"] if new or order.index(result["rank"]) > order.index(e["best_rank"]) else e["best_rank"]
    return {"new": new, "first_ever": first_ever}


def continent_of(spot: str) -> str:
    sp = next((s for s in load_json("spots.json")["spots"] if s["id"] == spot), {})
    return sp.get("continent", "sharmion")


# ───────────────────────── 보상 (P5) ─────────────────────────

def reward_cfg() -> dict:
    return cfg()["reward"]


def blessing_left(save) -> float:
    """물결의 축복 남은 초 (플레이 시간 기준)."""
    return max(0.0, save.data["buffs"].get("blessing_until", 0.0) - save.data["playtime"])


def blessing_active(save) -> bool:
    return blessing_left(save) > 0


def _next_gear_price(save) -> int:
    """'그 시점 상점 장비 하나 가격': 아직 안 산 장비 중 가장 싼 것 (다 샀으면 가장 비싼 것)."""
    from src.save.save_game import equipment
    eq = equipment()
    prices = [g["price"] for k in ("rod", "reel", "line", "net") for g in eq[k]
              if g.get("price", 0) > 0 and not save.owns(k, g["id"])]
    if not prices:
        prices = [max(g.get("price", 0) for k in ("rod", "reel", "line", "net") for g in eq[k])]
    return min(prices)


def collected(save, cont: str | None) -> int:
    ids = caught_ids(save)
    if cont is None:
        return len(ids)
    return sum(1 for fid in ids if continent_of(by_id(fid)["spot"]) == cont)


def on_catch(save, fish: dict, first_species: bool) -> dict:
    """포획 보상 (상자는 treasure.roll_drop 이 따로). 돌려줌: 결과 화면 배지용 정보."""
    rc = reward_cfg()
    ph = state(save)
    out = {}
    n = rc["scales_first"] if first_species else rc["scales"]
    ph["scales"] += n
    out["phantom_scales"] = n
    # 물결의 축복: 10분 (버프 중 또 잡으면 시간만 10분으로 초기화 — 효과 중첩 없음)
    save.data["buffs"]["blessing_until"] = save.data["playtime"] + rc["blessing_sec"]
    out["blessing"] = True
    if first_species:
        gold = int(round(_next_gear_price(save) * rc["gold_bonus_frac"], -1))
        save.data["money"] += gold
        save.data["stats"]["earned"] += gold
        out["phantom_gold"] = gold
    out["phantom_rewards"] = check_collection(save)
    return out


def check_collection(save) -> list[str]:
    """수집 보상: 새로 달성한 것을 주고 이름 목록을 돌려준다."""
    from src.save import quests
    ph = state(save)
    got = []
    for r in reward_cfg()["collect"]:
        if r["id"] in ph["rewards"] or collected(save, r["cont"]) < r["n"]:
            continue
        ph["rewards"].append(r["id"])
        cos = quests.cosmetics(save)
        if r.get("title"):
            if r["title"] not in cos["titles"]:
                cos["titles"].append(r["title"])
            got.append(f"칭호 「{quests.shop_item(r['title'])['name']}」")
        if r.get("skin"):
            it = quests.shop_item(r["skin"])
            slot = quests.KIND_SLOT[it["kind"]][0]
            if r["skin"] not in cos[slot]:
                cos[slot].append(r["skin"])
            got.append(f"외형 {it['name']}")
        if r.get("charm"):
            owned = save.data["items"]["owned"]
            if r["charm"] not in owned:
                owned.append(r["charm"])
            from src.save.treasure import item_info
            got.append(f"부적 {item_info(r['charm'])['name']}")
    return got


def exchange_items() -> list[dict]:
    return reward_cfg()["exchange"]


def exchange_owned(save, it: dict) -> bool:
    from src.save import quests
    if it.get("skin"):
        sk = quests.shop_item(it["skin"])
        return it["skin"] in quests.cosmetics(save)[quests.KIND_SLOT[sk["kind"]][0]]
    if it.get("frame"):
        return state(save)["title_frame"]
    return False


def can_exchange(save, it: dict) -> str | None:
    if exchange_owned(save, it):
        return "이미 가지고 있어요"
    if state(save)["scales"] < it["cost"]:
        return "환상 비늘이 부족해요"
    return None


def exchange(save, it: dict) -> bool:
    from src.save import quests
    if can_exchange(save, it):
        return False
    ph = state(save)
    ph["scales"] -= it["cost"]
    if it.get("skin"):
        sk = quests.shop_item(it["skin"])
        quests.cosmetics(save)[quests.KIND_SLOT[sk["kind"]][0]].append(it["skin"])
    elif it.get("frame"):
        ph["title_frame"] = True
    elif it.get("chest"):
        from src.save.treasure import give_chest
        give_chest(save, it["chest"])
    return True


def revealed(save) -> bool:
    """환상 관련 목록(도감 탭·업적·칭호·교환소)이 보이는지 — 첫 포획 튜토리얼 이후."""
    return state(save)["tutorial"] or bool(caught_ids(save))


# ───────────────────────── 존재 힌트 (P6) ─────────────────────────

def hints() -> dict:
    return load_json("phantom_hints.json")


def rumor(rnd=random) -> str | None:
    """로딩·이동 화면 소문 (가끔)."""
    h = hints()
    return rnd.choice(h["rumors"]) if rnd.random() < h["rumor_chance"] else None


def roll_diary(save, rnd=random) -> dict | None:
    """보물상자를 열 때 낮은 확률로 '낡은 어부의 수첩' 한 장. 이미 가진 장이면 환상 비늘 1개로."""
    h = hints()
    if rnd.random() >= h["diary_chance"]:
        return None
    fid = rnd.choice(list(h["diary"]))
    ph = state(save)
    if fid in ph["notes"]:
        ph["scales"] += 1
        return {"dup": True}
    ph["notes"].append(fid)
    return {"id": fid, "dup": False}


def glint_rate(save, spot: str) -> float:
    """대기 중 먼 수면 보라빛 물결이 한 번 반짝일 초당 확률 (천장에 가까울수록·전설 포획 낚시터일수록 자주)."""
    g = hints()["glint"]
    k = g["base_per_sec"] * (1 + g["pity_mult"] * pity_frac(save, spot))
    if legend_caught(save, spot):
        k *= g["legend_mult"]
    return k
