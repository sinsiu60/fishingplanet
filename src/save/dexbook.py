"""도감 별 · 숙련 · 도감 포인트 (DESIGN.md 35-2, CONTENT_EXPANSION.md A-1·A-2).

저장 필드를 새로 만들지 않고 기존 포획 기록(dex · mutation_dex · phantom.caught)에서 매번 계산한다 → 옛 세이브도 자동 소급.
세이브에 남기는 것은 받은 도감 보상(claimed)·표지(cover)·알림 기준(seen) 뿐 (save.data["dex_book"]).

  별 ★1 첫 포획 / ★2 S랭크 / ★3 대물(크기 범위 상위 10%) / ★4 변이 3종(일반·고급·희귀·한정) · 3회(전설·환상) / ★5 숙련 5
  숙련 단계 = 누적 포획 수 기준 (일반·고급·희귀 1·5·15·30·50 · 전설 1·2·3·5·8 · 환상 1·2·3·4·5 · 계절·이벤트 1·3·6·10·15)
"""
from src.core.config import load_json

MASTERY = {"normal": (1, 5, 15, 30, 50), "legend": (1, 2, 3, 5, 8), "phantom": (1, 2, 3, 4, 5), "limited": (1, 3, 6, 10, 15)}
STAR_LABEL = {1: "첫 포획", 2: "S랭크", 3: "대물", 4: "변이 3종", 5: "숙련 5"}


def cfg() -> dict:
    return load_json("dex_rewards.json")


def book(save) -> dict:
    b = save.data.setdefault("dex_book", {})
    b.setdefault("claimed", [])
    b.setdefault("cover", None)
    b.setdefault("seen", None)
    return b


# ── 물고기 목록 ──
def limited_fish() -> list[dict]:
    """계절 한정 + 날씨 이벤트 물고기 (fish.json 밖 → 도감 %·해금 집계 제외)."""
    out = []
    try:
        out += load_json("seasonal_fish.json")["fish"]
    except (OSError, KeyError, ValueError):
        pass
    try:
        out += [e["fish"] for e in load_json("weather_events.json")["events"] if e.get("fish")]
    except (OSError, KeyError, ValueError):
        pass
    return out


def all_species() -> list[dict]:
    from src.fishing.phantom import all_phantoms
    return load_json("fish.json")["fish"] + all_phantoms() + limited_fish()


def kind_of(fish: dict) -> str:
    if fish.get("rarity") == "phantom":
        return "phantom"
    if fish.get("limited"):
        return "limited"
    if fish.get("rarity") == "legend":
        return "legend"
    return "normal"


def entry(save, fish: dict) -> dict | None:
    if fish.get("rarity") == "phantom":
        e = save.data.get("phantom", {}).get("caught", {}).get(fish["id"])
    else:
        e = save.data["dex"].get(fish["id"])
    return e if e and e.get("count", 0) > 0 else None


# ── 숙련 · 별 ──
def mastery(save, fish: dict) -> int:
    e = entry(save, fish)
    n = e["count"] if e else 0
    return sum(1 for need in MASTERY[kind_of(fish)] if n >= need)


def next_mastery(save, fish: dict) -> tuple[int, int] | None:
    """(지금 포획 수, 다음 단계 필요 수) — 5단계면 None."""
    e = entry(save, fish)
    n = e["count"] if e else 0
    for need in MASTERY[kind_of(fish)]:
        if n < need:
            return n, need
    return None


def big_size(fish: dict) -> float:
    lo, hi = fish["size_cm"]
    return lo + 0.9 * (hi - lo)


def stars(save, fish: dict) -> list[bool]:
    e = entry(save, fish)
    if e is None:
        return [False] * 5
    k = kind_of(fish)
    s1 = True
    s2 = e.get("best_rank") == "S"
    s3 = e.get("max_size", 0) >= big_size(fish)
    if k in ("legend", "phantom"):
        s4 = e["count"] >= 3
    else:   # 변이는 전설·환상 말고 모든 종에 붙는다 (mutation.roll)
        s4 = len(save.data.get("mutation_dex", {}).get(fish["id"], [])) >= 3
    s5 = mastery(save, fish) >= 5
    return [s1, s2, s3, s4, s5]


def star_count(save, fish: dict) -> int:
    return sum(stars(save, fish))


def points(save) -> int:
    return sum(star_count(save, f) for f in all_species())


def max_points() -> int:
    return 5 * len(all_species())


def spot_stars(save, spot: str) -> tuple[int, int]:
    """그 낚시터 (fish.json) 별 합계 / 최대."""
    fish = [f for f in load_json("fish.json")["fish"] if f["spot"] == spot]
    return sum(star_count(save, f) for f in fish), 5 * len(fish)


def mastery_hint(fish: dict) -> str | None:
    """숙련 3: 선호 루어 리듬 힌트."""
    from src.fishing.lure import profile_of, cfg as lure_cfg
    p = profile_of(fish)
    names = lure_cfg().get("profile_names", {})
    return names.get(p, p) if p else None


# ── 칭호 · 보상 ──
def master_title_id(fish: dict) -> str:
    return f"master_{fish['id']}"


def cosmetic_item(item_id: str) -> dict | None:
    """도감 보상·달인 칭호를 quests.shop_item 과 같은 모양으로."""
    if item_id.startswith("master_"):
        fid = item_id[len("master_"):]
        f = next((x for x in all_species() if x["id"] == fid), None)
        if f:
            return {"id": item_id, "kind": "title", "name": f"{f['name']}의 달인"}
        return None
    for rw in cfg()["rewards"]:
        if rw.get("id") == item_id and rw["kind"] != "cover":
            return {k: v for k, v in rw.items() if k != "points"}
    return None


def covers() -> list[dict]:
    return [rw for rw in cfg()["rewards"] if rw["kind"] == "cover"]


def cover_of(save) -> dict | None:
    cid = book(save)["cover"]
    return next((c for c in covers() if c["id"] == cid), None)


def _grant(save, rw: dict) -> str:
    from src.save import quests
    if rw["kind"] == "cover":
        b = book(save)
        if b["cover"] is None:
            b["cover"] = rw["id"]   # 첫 표지는 바로 씌움
        return f"도감 표지 '{rw['name']}'"
    slot = quests.KIND_SLOT[rw["kind"]][0]
    lst = quests.cosmetics(save)[slot]
    if rw["id"] not in lst:
        lst.append(rw["id"])
    return {"title": "칭호", "float_skin": "찌 외형", "rod_skin": "낚싯대 외형", "net_skin": "뜰채 외형"}[rw["kind"]] + \
        f" '{rw['name']}'"


def claim_rewards(save) -> list[str]:
    """도감 포인트 보상 + 숙련 5 달인 칭호를 지급하고 이름 목록을 돌려준다 (이미 받은 건 다시 안 줌)."""
    from src.save import quests
    b = book(save)
    pts = points(save)
    got = []
    for rw in cfg()["rewards"]:
        key = f"{rw['kind']}:{rw['id']}"
        if pts >= rw["points"] and key not in b["claimed"]:
            b["claimed"].append(key)
            got.append(_grant(save, rw))
    titles = quests.cosmetics(save)["titles"]
    for f in all_species():
        if mastery(save, f) >= 5 and master_title_id(f) not in titles:
            titles.append(master_title_id(f))
            got.append(f"칭호 '{f['name']}의 달인'")
    return got


def snapshot(save) -> dict:
    """알림 기준: 종별 (별 비트, 숙련)."""
    out = {}
    for f in all_species():
        e = entry(save, f)
        if e is None:
            continue
        s = stars(save, f)
        out[f["id"]] = [sum(1 << i for i, v in enumerate(s) if v), mastery(save, f)]
    return out


def ensure_seen(save) -> None:
    """옛 세이브를 처음 불러올 때: 지금 상태를 '이미 본 것'으로 (알림 폭탄 방지) + 소급 보상 지급."""
    b = book(save)
    if b["seen"] is None:
        b["seen"] = snapshot(save)
        claim_rewards(save)


def on_catch(save, fish: dict) -> dict:
    """포획 뒤 (기록 저장 다음): 새 별·숙련 상승·도감 보상. 결과 화면 배지용."""
    ensure_seen(save)
    b = book(save)
    old_bits, old_m = b["seen"].get(fish["id"], [0, 0])
    s = stars(save, fish)
    bits = sum(1 << i for i, v in enumerate(s) if v)
    m = mastery(save, fish)
    b["seen"][fish["id"]] = [bits, m]
    new_stars = [i + 1 for i in range(5) if bits & (1 << i) and not old_bits & (1 << i)]
    out = {}
    if new_stars:
        out["dex_stars"] = new_stars
        out["dex_star_total"] = sum(s)
    if m > old_m and m >= 2:
        out["mastery_up"] = m
    rw = claim_rewards(save)
    if rw:
        out["dex_rewards"] = rw
    return out
