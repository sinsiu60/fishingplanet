"""보물상자 아이템 장착·사용 (보물상자 화면 '보유 아이템'과 인벤토리(I)가 같이 쓴다).

item_state(save, it)            → (버튼 글자, 누를 수 있는지)
use(game, it)                   → (알림 글자, 색, 고를 것 목록 | None)  — 모래시계·소라는 고를 것이 있으면 choose() 로 마무리
choose(game, fishing, iid, v)   → (알림 글자, 색)
"""
from src.core.game_clock import PERIODS
from src.core.weather import WEATHER_KO, Weather

GOOD = (140, 240, 150)
BAD = (255, 140, 120)


def item_state(save, it: dict) -> tuple[str, bool]:
    iid, kind = it["id"], it["kind"]
    if kind in ("rod", "reel", "net"):
        return ("장착 중", False) if save.data["gear"][kind] == iid else ("장착하기", True)
    if kind == "charm":
        if save.charm_on(iid):
            return "부적 해제", True
        used = sum(1 for c in save.charms() if c)
        return f"부적 장착 ({used}/{save.charm_slots()}칸)", True
    if kind == "cosmetic":
        return ("외형 해제", True) if save.cosmetic_on(iid) else ("외형 적용", True)
    if save.consumable_count(iid) <= 0:
        return "없음", False
    buffs = save.data["buffs"]
    if iid in ("repair_spool", "calm_charm"):
        return f"파이팅 중 {'1' if iid == 'repair_spool' else '2'}키로 사용", False
    if iid == "lucky_paste" and buffs.get("lucky_casts", 0) > 0:
        return f"효과 중 ({buffs['lucky_casts']}번 남음)", False
    if iid == "fisher_lunch" and save.lunch_active():
        left = (buffs["lunch_until"] - save.data["playtime"]) / 60
        return f"효과 중 ({left:.0f}분 남음)", False
    return "사용하기", True


def use(game, it: dict):
    """누를 수 있을 때만 부른다. 돌려줌: (알림, 색, 고를 것 [(이름, 값)] 또는 None)."""
    s, iid, kind = game.save, it["id"], it["kind"]
    if kind in ("rod", "reel", "net"):
        s.equip(kind, iid)
        return f"{it['name']} 장착!", GOOD, None
    if kind == "charm":
        on = s.toggle_charm(iid) == "on"
        return f"{it['name']} {'장착' if on else '해제'}", GOOD, None
    if kind == "cosmetic":
        s.toggle_cosmetic(iid)
        return f"{it['name']} {'적용' if s.cosmetic_on(iid) else '해제'}", GOOD, None
    if iid == "hourglass":
        return "", GOOD, [(name, start) for start, _, name in PERIODS]
    if iid == "storm_conch":
        return "", GOOD, [(WEATHER_KO[w], w) for w in ("clear", "rain", "storm")]
    if iid == "lucky_paste":
        s.use_consumable(iid)
        s.data["buffs"]["lucky_casts"] = 5
        return "다음 5번 캐스팅 동안 희귀 이상 +3%p", GOOD, None
    if iid == "fisher_lunch":
        s.use_consumable(iid)
        s.data["buffs"]["lunch_until"] = s.data["playtime"] + 600
        return "10분 동안 판매가 +10%", GOOD, None
    return "", GOOD, None


def choose(game, fishing, iid: str, value) -> tuple[str, tuple]:
    s = game.save
    s.use_consumable(iid)
    if iid == "hourglass":
        fishing.clock.hour = value + 0.01
        return "시간이 흘러갔다...", GOOD
    ws = fishing.weather_sys
    now = Weather.abs_time(fishing.clock.day, fishing.clock.hour)
    ws.set_override(value, now, now + 12)  # 실제 10분 = 게임 12시간 — 그 동안 예보표 위에 덮어씀 (DESIGN 48장)
    ws.update(fishing.clock.day, fishing.clock.hour)
    ws.events.clear()
    return f"날씨가 바뀌었다: {WEATHER_KO[value]}", GOOD
