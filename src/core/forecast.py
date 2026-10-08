"""달력 계산 (CORE_UPDATE.md CU1, DESIGN.md 52-0): 14일 예보 · 날짜 요약 · 시간대 묶음 · 전설 조건 칸 · 특별 날씨 계획.

모두 예보표 씨앗(weather_at, TIME_REST 🅰)으로 계산 — 저장 없이 과거 · 미래 어느 칸이든 같은 값.
칸 = 3시간 (block = floor(절대 시각 / 3)). 하루 d 의 칸 = 8d … 8d+7 (00 · 03 · … · 21시).
시간대 줄 (CU1-2 '3시간 칸 8개를 시간대별로 묶어 4줄'): 칸 시작 시각으로 나눔 —
  아침 06 · 09 / 낮 12 · 15 / 저녁 18 / 밤 21 + 다음 날 00 · 03 (그날 밤은 다음 날 새벽까지).
"""
import random

from src.core.config import load_json
from src.core.game_clock import PERIODS
from src.core.weather import CHANGE_EVERY

ROWS = (("morning", "아침", 6, 10, (6, 9)), ("day", "낮", 10, 17, (12, 15)), ("evening", "저녁", 17, 20, (18,)),
        ("night", "밤", 20, 30, (21, 24, 27)))   # (id, 이름, 시작 시, 끝 시, 칸 시작 시각들 — 24 이상 = 다음 날)


def cfg() -> dict:
    return load_json("core.json")["calendar"]


def period_of(hour: float) -> str:
    h = hour % 24
    pid = PERIODS[-1][1]
    for start, p, _ in PERIODS:
        if h >= start:
            pid = p
    return pid


def block_periods(block: int) -> set:
    """칸(3시간)이 걸치는 시간대들."""
    return {period_of(block * CHANGE_EVERY + k * 0.5) for k in range(int(CHANGE_EVERY * 2))}


def rows_of(day: int) -> list[dict]:
    """그날의 시간대 4줄: [{id, name, t0 (절대 시각 = 그 시간대 시작), blocks: [칸 번호…]}]."""
    out = []
    for pid, name, h0, _, starts in ROWS:
        out.append({"id": pid, "name": name, "t0": day * 24.0 + h0,
                    "blocks": [int((day * 24 + s) // CHANGE_EVERY) for s in starts]})
    return out


def _rep(ws: list[str]) -> str:
    """대표 날씨: 폭풍이 하나라도 있으면 폭풍, 아니면 가장 많은 것 (같으면 앞쪽 칸)."""
    if "storm" in ws:
        return "storm"
    return max(dict.fromkeys(ws), key=ws.count)


def day_summary(wsys, spot: dict, day: int) -> dict:
    """{rep: 대표 날씨, rows: [{id, name, t0, blocks, weathers, rep}], blocks: {칸: 날씨}}."""
    rows = rows_of(day)
    blocks = {}
    for r in rows:
        r["weathers"] = [wsys.at_block(b, spot["id"], spot["weather"]) for b in r["blocks"]]
        r["rep"] = _rep(r["weathers"])
        blocks.update(zip(r["blocks"], r["weathers"]))
    own = [wsys.at_block(b, spot["id"], spot["weather"]) for b in range(day * 8, day * 8 + 8)]
    return {"rep": _rep(own), "rows": rows, "blocks": blocks}


def legends_with_bait(save, spot: dict, all_fish) -> list[dict]:
    """그 낚시터 전설 중 전용 미끼를 가진 것 (없으면 표시 안 함 — 스포일러 방지)."""
    return [fi for fi in all_fish if fi["spot"] == spot["id"] and fi.get("rarity") == "legend"
            and fi.get("bait") and save.owns("bait", fi["bait"])]


def legend_hits(legends: list[dict], block: int, weather: str) -> list[dict]:
    """그 칸에서 만날 수 있는 전설 (시간대 + 날씨)."""
    per = block_periods(block)
    return [fi for fi in legends if weather in fi.get("weathers", []) and per & set(fi.get("times", []))]


def event_plan(save, wsys, spot: dict, day: int) -> dict | None:
    """그날 특별한 날씨 이벤트 계획 (weather_events.tick 과 같은 씨앗) — 이 낚시터 예보로 조건이 맞을 때만.
    돌려줌: {id, name, start} 또는 None."""
    from src.core.weather import ensure_seed
    from src.fishing import weather_events as we
    rnd = random.Random(f"{ensure_seed(save.data)}:event:{day}")
    r = rnd.random()
    acc = 0.0
    plan = None
    for e in we.cfg()["events"]:
        acc += e["day_chance"]
        if r < acc:
            plan = e
            break
    if plan is None:
        return None
    t0 = day * 24.0 + plan["start"]
    need = plan.get("need", {})
    w = wsys.at_time(t0, spot["id"], spot["weather"])
    if w not in need.get("weather", [w]):
        return None
    if need.get("rained_today"):
        rained = any(wsys.at_time(day * 24.0 + h, spot["id"], spot["weather"]) in ("rain", "storm")
                     for h in range(6, int(plan["start"]) + 1, 3))
        if not rained:
            return None
    return {"id": plan["id"], "name": plan["name"], "start": plan["start"]}


def day_word(day: int, today: int) -> str:
    return {0: "오늘", 1: "내일", 2: "모레"}.get(day - today, f"{day - today}일 뒤")


def until_label(t: float, today: int) -> str:
    """'내일 21:00' — 절대 시각."""
    day = int(t // 24)
    h = t - day * 24
    return f"{day_word(day, today)} {int(h):02d}:{int(round((h - int(h)) * 60)) % 60:02d}"
