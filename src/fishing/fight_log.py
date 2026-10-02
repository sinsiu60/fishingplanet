"""파이팅 로그 (DESIGN.md 31장 C2·C4): 패턴 시작(시각·행동·부하·그때 예산)과 에피소드(쉬지 않고 이어진 행동 묶음).

Fight가 매 틱 끝에 tick()을 부른다 (메모리에만 쌓음, 가볍다). 낚시 화면은 디버그 빌드(debug_keys)일 때만
파이팅이 끝나면 save()로 `세이브 폴더/fight_logs/*.jsonl`에 저장. 분석은 tools/fight_log.py.

- 시작(starts): 물고기 두뇌가 패턴을 시작할 때 남기는 (시각, 부하, 예산, 행동) — 콤보 안의 단계는 콤보 부하(4)에 포함,
  가짜 예고(등불)는 부하 0이라 없음. 3초 부하 예산은 '3초 안에 시작한 패턴 부하 합' (혼자인 콤보·이중은 예외).
- 에피소드: 쉬는 상태(idle·recover·tired·exhausted·stiff)를 벗어난 순간 ~ 다시 쉬는 상태. 힘 모으기 → 돌진,
  연속 점프처럼 쉬지 않고 이어진 행동은 한 에피소드. 휴식 규칙은 에피소드 사이 간격 (가짜 예고만 있던 에피소드는 제외).
"""
import json
import os
import time

from src.core.config import load_json


def signals() -> dict:
    return load_json("signals.json")


class FightLog:
    def __init__(self, fish: dict, spot: str):
        self.fish_id = fish.get("id", "?")
        self.rarity = fish.get("rarity", "")
        self.spot = spot
        self.starts: list[dict] = []
        self.episodes: list[dict] = []
        self.results: list[dict] = []
        self.cur: dict | None = None
        self._ev_i = 0
        self._last_start = -1.0
        self.rest = set(signals()["rest_states"])
        self.outcome = None

    def tick(self, fight) -> None:
        b = fight.brain
        t = round(b.clock, 3)
        evs = fight.events
        if self._ev_i > len(evs):
            self._ev_i = 0
        for ev in evs[self._ev_i:]:
            self._event(t, ev)
        self._ev_i = len(evs)
        if fight.phase != "fight":
            self._close()
            return
        busy = b.state not in self.rest
        if busy and self.cur is None:
            act = b.pending if b.state == "telegraph" else b.state
            self.cur = {"t": t, "end": t, "action": act or b.state, "acts": [], "res": []}
        for s in b.starts:
            if s[0] > self._last_start:
                self.starts.append({"t": round(s[0], 3), "load": s[1], "budget": s[2], "action": s[3],
                                    "penalty": bool(s[4])})
                self._last_start = s[0]
                if self.cur is not None and s[3] not in self.cur["acts"]:
                    self.cur["acts"].append(s[3])
        if self.cur is not None:
            if busy:
                self.cur["end"] = t
            else:
                self._close()

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

    def _close(self) -> None:
        if self.cur is None:
            return
        e = self.cur
        self.cur = None
        e["load"] = sum(s["load"] for s in self.starts if e["t"] - 0.02 <= s["t"] <= e["end"] + 0.02
                        and not s["penalty"])  # 실패 결과로 이어진 행동은 뺀다
        e["fake_only"] = e["load"] == 0  # 등불 가짜 예고만 — 휴식 규칙에서 제외
        self.episodes.append(e)

    def to_dict(self) -> dict:
        return {"fish": self.fish_id, "rarity": self.rarity, "spot": self.spot, "outcome": self.outcome,
                "starts": self.starts, "episodes": self.episodes, "results": self.results}

    def save(self, folder: str) -> str | None:
        try:
            os.makedirs(folder, exist_ok=True)
            path = os.path.join(folder, time.strftime("%Y%m%d") + ".jsonl")
            with open(path, "a", encoding="utf-8") as fp:
                fp.write(json.dumps(self.to_dict(), ensure_ascii=False) + "\n")
            return path
        except OSError:
            return None


def analyze(logs: list[dict]) -> dict:
    """낚시터별 3초 부하 초과·휴식 위반·같은 고부하 연속, 패턴별 성공률."""
    sig = signals()
    rest = sig["rest"]
    win = sig["timing"]["window_sec"]
    spots: dict = {}
    pats: dict = {}
    for lg in logs:
        st = spots.setdefault(lg["spot"], {"fights": 0, "over_fights": 0, "over_windows": 0, "max3": 0,
                                          "rest_short": 0, "rest_short_heavy": 0, "same_heavy": 0, "gaps": []})
        st["fights"] += 1
        starts = [s for s in lg["starts"] if not s.get("penalty")]  # 실패의 결과로 이어진 행동은 집계에서 뺀다
        over = False
        for i, s in enumerate(starts):
            # 이 패턴을 시작하는 순간, 직전 3초 안에 시작한 패턴 부하 합 (두뇌가 고를 때와 같은 기준·그때 예산)
            inwin = [x for x in starts[: i + 1] if x["t"] > s["t"] - win]
            total = sum(x["load"] for x in inwin)
            st["max3"] = max(st["max3"], total)
            if total > s["budget"] and len(inwin) > 1:
                over = True
                st["over_windows"] += 1
        st["over_fights"] += over
        eps = [e for e in lg["episodes"] if not e.get("fake_only")]
        for a, b in zip(eps, eps[1:]):
            gap = b["t"] - a["end"]
            st["gaps"].append(round(gap, 2))
            if gap < rest["min_sec"] - 0.05:
                st["rest_short"] += 1
            if a["load"] >= rest["heavy_load"] and gap < rest["after_heavy_sec"] - 0.05:
                st["rest_short_heavy"] += 1
            if a["action"] == b["action"] and sig["actions"].get(a["action"], {}).get("load", 1) >= rest["heavy_load"]:
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
        st["rest_min"] = g[0] if g else None
    return {"spots": spots, "patterns": pats}
