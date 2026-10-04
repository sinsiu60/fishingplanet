"""NPC 대사 시스템 (DESIGN.md 35-3·35-12, CONTENT_EXPANSION.md B-3): data/dialogue.json.

조건(cond)을 모두 만족하는 대사 중에서 고른다. 우선순위: 새 달성 반응(prio 3, 대개 1회성) → 계절·이벤트(2) → 일반 잡담(1, 무작위, 최근 3개 피함).
1회성(once) 대사는 들은 기록(save.data["dialogue"]["heard"])에 남겨 다시 안 나온다. 말풍선 하나 = 최대 2줄.
환상 튜토리얼 전에는 'phantom_tutorial: false' 대사(흐릿한 소문)만 — '환상' 단어는 튜토리얼 뒤 대사에만.
"""
import random

from src.core import season as seasons
from src.core.config import load_json

_RNG = random.Random()


def lines() -> list[dict]:
    return load_json("dialogue.json")["lines"]


def state(save) -> dict:
    d = save.data.setdefault("dialogue", {})
    d.setdefault("heard", [])
    d.setdefault("recent", {})
    d.setdefault("flags", {})
    return d


def note(save, key: str, delta: int | None = None, value=None) -> None:
    """대사용 진행 기록 (연속 놓침·의뢰 연속 실패 등)."""
    f = state(save)["flags"]
    if value is not None:
        f[key] = value
    elif delta is not None:
        f[key] = f.get(key, 0) + delta


def context(game, cont: str | None = None, overrides: dict | None = None) -> dict:
    fishing = next((s for s in game.scenes.stack if hasattr(s, "clock") and hasattr(s, "weather_sys")), None)
    ctx = {"season": seasons.current(game.settings), "period": fishing.clock.period()[0] if fishing else "day",
           "weather": fishing.weather if fishing else "clear", "event": None, "cont": cont}
    try:
        from src.fishing import weather_events
        ev = weather_events.active(game.save)
        ctx["event"] = ev["id"] if ev else None
    except ImportError:
        pass
    if overrides:
        ctx.update({k: v for k, v in overrides.items() if v is not None or k == "event"})
    return ctx


def cond_ok(cond: dict, save, ctx: dict) -> bool:
    from src.save import dexbook
    from src.fishing import phantom
    d = save.data
    flags = state(save)["flags"]
    for k, v in cond.items():
        if k == "spot_unlocked":
            ok = v in d.get("unlocked_spots", [])
        elif k == "continent_unlocked":
            ok = v in d.get("unlocked_continents", [])
        elif k == "legend_caught":
            legends = [f["id"] for f in load_json("fish.json")["fish"] if f["rarity"] == "legend"]
            ok = any(save.caught(x) for x in legends) if v == "any" else save.caught(v)
        elif k == "legend_caught_eld":
            from src.save.save_game import spot_continent
            ok = any(save.caught(f["id"]) for f in load_json("fish.json")["fish"]
                     if f["rarity"] == "legend" and spot_continent(f["spot"]) == "eldrasion") == v
        elif k == "gear_tier_ge":
            ok = save.gear_tier(v[0]) >= v[1]
        elif k == "mastery_ge":
            ok = any(dexbook.mastery(save, f) >= v for f in dexbook.all_species() if dexbook.entry(save, f))
        elif k == "dex_stars_ge":
            ok = dexbook.points(save) >= v
        elif k == "prints_ge":
            ok = len(d.get("prints", {})) >= v
        elif k == "prints_lt":
            ok = len(d.get("prints", {})) < v
        elif k in ("gold_print", "legend_print", "phantom_print"):
            kind = {"gold_print": "gold_leaf", "legend_print": "legend", "phantom_print": "phantom"}[k]
            ok = any(p.get("kind") == kind for p in d.get("prints", {}).values()) == v
        elif k == "lost_streak_ge":
            ok = flags.get("lost_streak", 0) >= v
        elif k == "quest_fail_streak_ge":
            ok = flags.get("quest_fail_streak", 0) >= v
        elif k == "quests_done_ge":
            ok = d.get("quests", {}).get("done", 0) >= v
        elif k == "catches_ge":
            ok = d["stats"].get("catches", 0) >= v
        elif k == "keepnet_ge":
            ok = len(d.get("keepnet", [])) >= v
        elif k == "period":
            ok = ctx["period"] in v
        elif k == "weather":
            ok = ctx["weather"] in v
        elif k == "season":
            ok = ctx["season"] in v
        elif k == "event":
            ok = ctx.get("event") == v
        elif k == "phantom_tutorial":
            have = ctx["phantom_tutorial"] if ctx.get("phantom_tutorial") is not None else bool(phantom.state(save)["tutorial"])
            ok = have == v
        else:
            ok = False
        if not ok:
            return False
    return True


def candidates(save, npc_id: str, ctx: dict) -> list[dict]:
    heard = set(state(save)["heard"])
    return [ln for ln in lines() if ln["npc"] == npc_id and not (ln["once"] and ln["id"] in heard)
            and cond_ok(ln["cond"], save, ctx)]


def choose(save, npc_id: str, ctx: dict, prefer_season: bool = False, rnd=_RNG, commit: bool = True) -> dict | None:
    cands = candidates(save, npc_id, ctx)
    if not cands:
        return None
    st = state(save)
    recent = st["recent"].get(npc_id, [])
    top = [c for c in cands if c["prio"] >= 3]
    mid = [c for c in cands if c["prio"] == 2]
    low = [c for c in cands if c["prio"] <= 1]
    if top:
        pick = top[0]
    elif mid and (prefer_season or rnd.random() < 0.4 or not low):
        pick = rnd.choice([c for c in mid if c["id"] not in recent] or mid)
    else:
        pick = rnd.choice([c for c in low if c["id"] not in recent] or low)
    if commit:
        if pick["once"]:
            st["heard"].append(pick["id"])
        st["recent"][npc_id] = (recent + [pick["id"]])[-3:]
    return pick


def pick(game, npc_id: str, cont: str, prefer_season: bool = False) -> list[str]:
    ln = choose(game.save, npc_id, context(game, cont), prefer_season)
    if ln is None:
        n = load_json("villages.json")[cont]["npcs"].get(npc_id, {})
        return [random.choice(n.get("lines", ["…"]))]
    return [ln["text"]]


def gallery_comment(save, fish: dict) -> str:
    """갈매기 박사: 어탁마다 한마디 (종류·희귀도에 따라)."""
    rec = save.data.get("prints", {}).get(fish["id"], {})
    name = fish["name"].split(" '")[0]
    kind = rec.get("kind")
    if kind == "phantom":
        return f"이 보라빛 {name}… 종이가 아직도 떨리고 있는 것 같습니다!"
    if kind == "legend":
        return f"{name}! 금빛 먹으로 찍은 전설. 이 벽의 왕좌입니다, 끼룩!"
    if kind == "gold_leaf":
        return f"금박 테두리의 {name}… 숙련의 손길이 느껴지는군요."
    pool = [f"{name}의 비늘 결이 살아 있군요! {rec.get('size', 0):.1f}cm라니, 훌륭합니다.",
            f"오호, {name}! 제 연구 노트에도 그림이 있지요. 이쪽이 더 낫군요.",
            f"{rec.get('spot', '')} 도장이 선명하군요. {name}이(가) 웃고 있습니다!"]
    return random.Random(fish["id"]).choice(pool)
