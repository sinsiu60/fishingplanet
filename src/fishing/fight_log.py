"""파이팅 로그 (DESIGN.md 31장 C2): 패턴 에피소드(예고 시작 ~ 행동 끝)의 시각·종류·계열·부하·결과.

Fight가 매 틱 끝에 tick()을 부른다 (메모리에만 쌓음, 가볍다). 낚시 화면은 디버그 빌드(debug_keys)일 때만
파이팅이 끝나면 save()로 `세이브 폴더/fight_logs/*.jsonl`에 저장. 분석은 tools/fight_log.py.

에피소드: 물고기 상태가 쉬는 상태(idle·recover·tired·exhausted·stiff)를 벗어난 순간 시작, 다시 쉬는 상태가 되면 끝.
연쇄 콤보는 한 에피소드(부하 4), 이중 패턴은 두 패턴 부하의 합.
"""
import json
import os
import time

from src.core.config import load_json


def signals() -> dict:
    return load_json("signals.json")


def action_load(action: str) -> int:
    return signals()["actions"].get(action, {}).get("load", 1)


def action_family(action: str) -> str:
    return signals()["actions"].get(action, {}).get("family", "-")


class FightLog:
    def __init__(self, fish: dict, spot: str):
        self.fish_id = fish.get("id", "?")
        self.rarity = fish.get("rarity", "")
        self.spot = spot
        self.episodes: list[dict] = []
        self.results: list[dict] = []   # 판정 결과 (시각, 이벤트)
        self.cur: dict | None = None
        self._ev_i = 0
        self.rest = set(signals()["rest_states"])
        self.outcome = None

    # ── 기록 ──
    def tick(self, fight) -> None:
        b = fight.brain
        t = round(fight.elapsed, 3)
        evs = fight.events
        if self._ev_i > len(evs):
            self._ev_i = 0  # 화면이 이벤트 목록을 비웠다
        for ev in evs[self._ev_i:]:
            self._event(t, ev)
        self._ev_i = len(evs)
        if fight.phase != "fight":
            self._close(t)
            return
        busy = b.state not in self.rest
        prev, self._prev = getattr(self, "_prev", None), b.state
        if (busy and self.cur is not None and b.state == "telegraph" and prev not in (None, "telegraph")
                and not getattr(b, "combo_on", False) and self.cur["action"] != "chain" and "dual" not in self.cur["acts"]):
            self._close(t)  # 앞 행동이 끝나자마자 새 예고 (예: 힘 모으기 → 돌진) = 새 에피소드, 휴식 0초
        if busy and self.cur is None:
            act = b.pending if b.state == "telegraph" else b.state
            if b.state == "jump" and getattr(b, "jump_kind", None) == "thrash":
                act = "thrash"
            self.cur = {"t": t, "end": t, "action": act or b.state, "acts": [], "tele": None, "res": []}
            if b.state == "telegraph":
                self.cur["tele"] = round(getattr(b, "cur_telegraph", 0.0) or b.timer, 3)
        if self.cur is not None:
            if busy:
                self.cur["end"] = t
                names = [b.pending] if b.state == "telegraph" and b.pending else [b.state]
                names += [p.id for p in fight.pats]
                for n in names:
                    if n and n not in ("telegraph", "idle") and n not in self.cur["acts"]:
                        self.cur["acts"].append(n)
            else:
                self._close(t)

    def _event(self, t: float, ev: str) -> None:
        if ev.startswith(("pattern_ok:", "pattern_fail:", "pattern_neutral:")) or ev in (
                "perfect", "good", "miss_early", "miss_late", "miss_none", "flick_perfect", "flick_good", "flick_miss",
                "combo_ok", "combo_fail", "dual_ok", "pump_hit", "pump_miss") or ev.startswith("lost:"):
            self.results.append({"t": t, "ev": ev})
            if self.cur is not None:
                self.cur["res"].append(ev)
        if ev.startswith("lost:"):
            self.outcome = ev
        elif ev == "caught":
            self.outcome = "caught"

    def _close(self, t: float) -> None:
        if self.cur is None:
            return
        e = self.cur
        self.cur = None
        acts = e["acts"]
        if "chain" in acts or e["action"] == "chain":
            e["load"] = action_load("chain")
            e["family"] = "combo"
        elif "dual" in acts:
            parts = [a for a in acts if a != "dual"]
            e["load"] = sum(action_load(a) for a in parts)
            e["family"] = "+".join(sorted({action_family(a) for a in parts}))
        else:
            e["load"] = action_load(e["action"])
            e["family"] = action_family(e["action"])
        self.episodes.append(e)

    # ── 저장 ──
    def to_dict(self) -> dict:
        return {"fish": self.fish_id, "rarity": self.rarity, "spot": self.spot, "outcome": self.outcome,
                "episodes": self.episodes, "results": self.results}

    def save(self, folder: str) -> str | None:
        try:
            os.makedirs(folder, exist_ok=True)
            path = os.path.join(folder, time.strftime("%Y%m%d") + ".jsonl")
            with open(path, "a", encoding="utf-8") as fp:
                fp.write(json.dumps(self.to_dict(), ensure_ascii=False) + "\n")
            return path
        except OSError:
            return None


# ── 분석 (tools/fight_log.py 와 C7 검증이 쓴다) ──
def analyze(logs: list[dict]) -> dict:
    """로그 여러 개 → 낚시터별 3초 부하 초과·휴식 위반·같은 고부하 연속, 패턴별 성공률."""
    sig = signals()
    rest = sig["rest"]
    spots: dict = {}
    pats: dict = {}
    for lg in logs:
        eps = lg["episodes"]
        st = spots.setdefault(lg["spot"], {"fights": 0, "over_fights": 0, "over_windows": 0, "max3": 0,
                                          "rest_short": 0, "rest_short_heavy": 0, "same_heavy": 0, "gaps": []})
        st["fights"] += 1
        budget = sig["budget_3s"].get(lg["spot"], 3) + (sig["legend_extra"] if lg.get("rarity") == "legend" else 0)
        end = max((e["end"] for e in eps), default=0.0)
        over, t0 = False, 0.0
        while t0 <= end:
            s = sum(e["load"] for e in eps if e["t"] < t0 + 3 and e["end"] > t0)
            st["max3"] = max(st["max3"], s)
            if s > budget:
                over = True
                st["over_windows"] += 1
            t0 += 0.1
        st["over_fights"] += over
        for a, b in zip(eps, eps[1:]):
            gap = b["t"] - a["end"]
            st["gaps"].append(round(gap, 2))
            if gap < rest["min_sec"]:
                st["rest_short"] += 1
            if a["load"] >= rest["heavy_load"] and gap < rest["after_heavy_sec"]:
                st["rest_short_heavy"] += 1
            if a["load"] >= rest["heavy_load"] and a["action"] == b["action"]:
                st["same_heavy"] += 1
        for e in eps:
            p = pats.setdefault(e["action"], {"n": 0, "ok": 0, "fail": 0})
            p["n"] += 1
            if any(r.startswith("pattern_ok") or r in ("perfect", "good", "flick_perfect", "flick_good", "combo_ok", "dual_ok")
                   for r in e["res"]):
                p["ok"] += 1
            elif any(r.startswith(("pattern_fail", "miss", "lost:")) or r in ("flick_miss", "combo_fail") for r in e["res"]):
                p["fail"] += 1
    for st in spots.values():
        g = sorted(st.pop("gaps"))
        st["rest_median"] = g[len(g) // 2] if g else None
    return {"spots": spots, "patterns": pats}
