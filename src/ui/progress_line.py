"""진행 막대 (CORE_UPDATE.md CU8-②): 화면 왼쪽 위 작은 한 줄
"다음: 시험 자격 2/3 · 장비까지 12,400원 (약 25분)" — 남은 돈 ÷ 최근 30분 시간당 수입 (T7+ 는 모자란 비늘도). 누르면 자격 · 장비 목록이 잠깐 펼쳐짐.
설정 '진행 막대' (progress_line, 기본 켬) 으로 끔.
"""
import collections

from src.core.config import load_json

WINDOW_SEC = 30 * 60      # 최근 30분
SAMPLE_SEC = 15.0
MIN_SEC = 3 * 60          # 이보다 짧으면 아직 계산 중


class EarnRate:
    """최근 30분 시간당 수입 (실제 플레이 초 기준)."""

    def __init__(self):
        self.log: collections.deque = collections.deque()
        self.next_t = 0.0

    def update(self, save) -> None:
        t = save.data.get("playtime", 0.0)
        if t < self.next_t:
            return
        self.next_t = t + SAMPLE_SEC
        self.log.append((t, save.data["stats"].get("earned", 0)))
        while self.log and t - self.log[0][0] > WINDOW_SEC:
            self.log.popleft()

    def per_hour(self) -> float | None:
        if len(self.log) < 2 or self.log[-1][0] - self.log[0][0] < MIN_SEC:
            return None
        (t0, e0), (t1, e1) = self.log[0], self.log[-1]
        return max(0.0, (e1 - e0) / (t1 - t0) * 3600)


def gear_goal(save) -> tuple[int, list[dict]]:
    """다음 시험 티어(다 합격했으면 지금 티어) 장비 4종 중 아직 없는 것 — (값 합, 목록)."""
    from src.save import exam
    tier = exam.next_tier(save) or exam.passed(save)
    eq = load_json("equipment.json")
    cont = set(save.data.get("unlocked_continents", []))
    need = []
    for kind in ("rod", "reel", "line", "net"):
        if save.gear_tier(kind) >= tier:
            continue
        g = next((g for g in eq[kind] if g["tier"] == tier and g.get("continent", "sharmion") in cont | {"sharmion"}), None)
        if g and not save.owns(kind, g["id"]):
            need.append(g)
    return sum(g["price"] for g in need), need


def summary(save, rate: float | None) -> tuple[str, list[str]] | None:
    """(한 줄, 펼친 줄들). 볼 것이 없으면 None."""
    from src.save import exam
    q = exam.quals(save)
    cost, gear = gear_goal(save)
    if not q and not gear:
        return None
    parts, more = [], []
    if q:
        parts.append(f"시험 자격 {sum(1 for x in q if x['ok'])}/{len(q)}")
        more += [f"{x['label']} {x['have']}/{x['need']}" + (" 완료" if x["ok"] else (f" ({x['alt']})" if x.get("alt") else ""))
                 for x in q]
    if gear:
        left = max(0, cost - save.data["money"])
        scales = max(0, sum(g.get("scales", 0) for g in gear) - save.data.get("scales", 0))
        if scales:
            parts.append(f"전설 비늘 {scales}개 더")   # 엘드라시온 T7+ 장비: 돈과 함께 비늘도 (전설 첫 포획 5개)
        if left <= 0:
            parts.append("장비 살 돈 모임")
        elif rate:
            parts.append(f"장비까지 {left:,}원 (약 {max(1, round(left / rate * 60))}분)")
        else:
            parts.append(f"장비까지 {left:,}원")
        more.append("장비: " + " · ".join(g["name"] for g in gear))
    return "다음: " + " · ".join(parts), more
