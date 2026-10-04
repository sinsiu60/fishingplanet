"""실내 전용 소리 레시피 만들기 (AUDIO_ZONES.md 3번, DESIGN.md 39) → data/sfx_recipes.json 의 room_* · door_* 항목.

빗방울·장작 타닥처럼 작은 소리를 많이 흩뿌리는 레시피는 손으로 쓰기 어려워 여기서 정해진 씨앗(seed)으로 펼쳐 쓴다.
다시 만들기: python tools/gen_room_recipes.py → python tools/bake_sfx.py (바뀐 것만 굽기)
"""
import json
import os
import random

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "data", "sfx_recipes.json")


def tick(start, f, gain, length=0.012, q=3.0, pan=0.0):
    return {"wave": "noise", "start": round(start, 4), "len": length, "filter": {"type": "bp", "f": f, "q": q, "track": False},
            "env": {"a": 0.0008, "d": length * 0.6, "s": 0, "r": length * 0.4}, "gain": round(gain, 3), "pan": round(pan, 2)}


def scatter(rnd, n, total, f_lo, f_hi, g_lo, g_hi, length=0.012, q=3.0, pan=0.7, edge=0.02):
    return [tick(rnd.uniform(edge, total - edge - length), rnd.uniform(f_lo, f_hi), rnd.uniform(g_lo, g_hi), length, q,
                 rnd.uniform(-pan, pan)) for _ in range(n)]


def recipes() -> dict:
    r = random.Random(39)
    out = {}
    # ── 공통 ──
    out["room_air"] = {"_소리": "실내: 방 공기 (거의 안 들림, 정적이 비어 보이지 않게)", "loop": True, "xfade": 1.0, "len": 8.0,
                       "peak_db": -18.0, "layers": [
                           {"wave": "pink", "len": 8.0, "filter": {"type": "lp", "f": 260, "track": False},
                            "env": {"a": 0.5, "d": 1, "s": 1, "r": 0.5}, "gain": 0.6, "trem": [0.07, 0.25]},
                           {"wave": "sine", "freq": 58, "len": 8.0, "env": {"a": 0.5, "d": 1, "s": 1, "r": 0.5}, "gain": 0.05}]}
    out["room_rain_roof_light"] = {"_소리": "실내: 지붕·창문 빗소리 '톡톡톡' (비)", "loop": True, "xfade": 0.3, "len": 6.0,
                                   "peak_db": -9.0, "reverb": {"mix": 0.18, "time": 0.25},
                                   "layers": scatter(r, 70, 6.0, 1800, 4200, 0.25, 0.9) + scatter(r, 30, 6.0, 600, 1200, 0.2, 0.5,
                                                                                                    length=0.02, q=2.0) + [
                                       {"wave": "pink", "len": 6.0, "filter": {"type": "bp", "f": 900, "q": 0.7, "track": False},
                                        "env": {"a": 0.3, "d": 1, "s": 1, "r": 0.3}, "gain": 0.06}]}
    out["room_rain_roof_heavy"] = {"_소리": "실내: 지붕·창문 빗소리 (폭풍 — 더 촘촘하고 크게)", "loop": True, "xfade": 0.3, "len": 6.0,
                                   "peak_db": -6.0, "reverb": {"mix": 0.2, "time": 0.25},
                                   "layers": scatter(r, 190, 6.0, 1500, 4500, 0.3, 1.0) + scatter(r, 80, 6.0, 500, 1100, 0.25, 0.6,
                                                                                                    length=0.022, q=2.0) + [
                                       {"wave": "pink", "len": 6.0, "filter": {"type": "bp", "f": 800, "q": 0.6, "track": False},
                                        "env": {"a": 0.3, "d": 1, "s": 1, "r": 0.3}, "gain": 0.16, "trem": [0.4, 0.3]}]}
    out["room_window_rattle"] = {"_소리": "실내: 천둥에 창문 '덜컥' (아주 작게)", "len": 0.55, "peak_db": -10.0,
                                 "layers": [tick(0.0 + i * 0.045 + r.uniform(0, 0.012), r.uniform(380, 700), 0.9 - i * 0.12,
                                                 0.03, 4.0) for i in range(6)] + [
                                     {"wave": "sine", "freq": [90, 60], "len": 0.35, "env": {"a": 0.005, "d": 0.2, "s": 0, "r": 0.1},
                                      "gain": 0.3}]}
    out["room_window_wind"] = {"_소리": "실내: 창문 틈 바람 '우우—' (폭풍, 간헐적)", "loop": True, "xfade": 1.5, "len": 10.0,
                               "peak_db": -10.0, "layers": [
                                   {"wave": "pink", "len": 10.0, "filter": {"type": "bp", "f": [260, 420], "q": 3.0, "track": False},
                                    "env": {"a": 1.0, "d": 1, "s": 1, "r": 1.0}, "gain": 0.8, "trem": [0.13, 0.85]},
                                   {"wave": "sine", "freq": [310, 360], "vib": [0.3, 0.02], "len": 10.0,
                                    "env": {"a": 2.0, "d": 1, "s": 1, "r": 2.0}, "gain": 0.08, "trem": [0.17, 0.95]}]}
    # ── 장소별 ──
    out["room_clock"] = {"_소리": "집: 벽시계 째깍 (작게, 반복)", "loop": True, "xfade": 0.005, "len": 2.0, "peak_db": -14.0,
                         "reverb": {"mix": 0.15, "time": 0.2},
                         "layers": [tick(0.05, 3200, 1.0, 0.008, 6.0), tick(1.05, 2500, 0.8, 0.008, 6.0)]}
    out["room_floor_creak"] = {"_소리": "집: 나무 바닥 삐걱 (가끔)", "len": 0.7, "peak_db": -12.0, "layers": [
        {"wave": "saw", "freq": [210, 150], "len": 0.5, "filter": {"type": "bp", "f": [700, 520], "q": 6.0, "track": False},
         "env": {"a": 0.06, "d": 0.2, "s": 0.4, "r": 0.15}, "gain": 0.3, "vib": [13, 0.04]}]}
    out["room_reel_rattle"] = {"_소리": "낚시점: 선반의 릴이 달그락 (가끔)", "len": 0.5, "peak_db": -13.0, "reverb": {"mix": 0.15, "time": 0.25},
                               "layers": [tick(i * 0.06 + r.uniform(0, 0.02), r.uniform(2200, 3400), 0.8 - i * 0.15, 0.015, 8.0)
                                          for i in range(4)] + [
                                   {"wave": "sine", "freq": 2650, "start": 0.02, "len": 0.25, "harm": [[2.7, 0.3]],
                                    "env": {"a": 0.001, "d": 0.12, "s": 0, "r": 0.08}, "gain": 0.15}]}
    out["room_fire"] = {"_소리": "오두막: 화로 불 바탕 (낮은 웅웅 + 잔 타닥)", "loop": True, "xfade": 0.5, "len": 8.0, "peak_db": -9.0,
                        "layers": [{"wave": "pink", "len": 8.0, "filter": {"type": "lp", "f": 380, "track": False},
                                    "env": {"a": 0.4, "d": 1, "s": 1, "r": 0.4}, "gain": 0.7, "trem": [0.5, 0.35]}]
                        + scatter(r, 45, 8.0, 1200, 3600, 0.15, 0.55, length=0.01, q=2.5, pan=0.3)}
    for i in range(3):   # 굵은 '타닥' 3종 (간격·크기 랜덤으로 끼워 넣음)
        n = 2 + i
        out[f"room_fire_pop{i}"] = {"_소리": f"오두막: 장작 타닥 ({i + 1}/3)", "len": 0.35, "peak_db": -10.0,
                                    "layers": [tick(k * r.uniform(0.03, 0.07), r.uniform(1400, 3000), r.uniform(0.6, 1.0), 0.014, 2.0,
                                                    r.uniform(-0.3, 0.3)) for k in range(n)]}
    out["room_net_sway"] = {"_소리": "오두막: 걸어 둔 그물이 흔들림 (사락)", "len": 1.4, "peak_db": -14.0, "layers": [
        {"wave": "noise", "len": 1.3, "filter": {"type": "bp", "f": [1800, 1200], "q": 1.2, "track": False},
         "env": {"a": 0.4, "d": 0.4, "s": 0.3, "r": 0.4}, "gain": 0.4, "trem": [6, 0.5]}]}
    out["room_crystal_ting"] = {"_소리": "공방: 수정이 맑게 '팅' (6~12초 랜덤)", "len": 2.4, "peak_db": -12.0,
                                "reverb": {"mix": 0.4, "time": 1.6}, "layers": [
                                    {"wave": "sine", "freq": 2637, "len": 2.0, "harm": [[2.0, 0.2], [3.01, 0.08]],
                                     "env": {"a": 0.003, "d": 1.2, "s": 0.05, "r": 0.7}, "gain": 0.35},
                                    {"wave": "sine", "freq": 3951, "start": 0.04, "len": 1.4, "env": {"a": 0.003, "d": 0.9, "s": 0, "r": 0.4},
                                     "gain": 0.12}]}
    out["room_page"] = {"_소리": "서재: 책장 넘기는 소리", "len": 0.5, "peak_db": -14.0, "layers": [
        {"wave": "noise", "len": 0.32, "filter": {"type": "bp", "f": [2600, 1400], "q": 1.0, "track": False},
         "env": {"a": 0.03, "d": 0.15, "s": 0.2, "r": 0.1}, "gain": 0.5},
        tick(0.33, 1800, 0.4, 0.02, 2.0)]}
    out["room_candle"] = {"_소리": "서재: 촛불 일렁 (아주 작게)", "len": 0.9, "peak_db": -20.0, "layers": [
        {"wave": "pink", "len": 0.8, "filter": {"type": "bp", "f": 500, "q": 1.5, "track": False},
         "env": {"a": 0.2, "d": 0.3, "s": 0.3, "r": 0.3}, "gain": 0.6, "trem": [9, 0.7]}]}
    # 서재: 3분마다 아주 작은 오르골풍 짧은 선율
    notes = [(0.0, 76), (0.35, 79), (0.7, 83), (1.05, 81), (1.4, 79), (1.75, 76), (2.3, 74), (2.65, 76), (3.2, 72)]
    out["room_orgel"] = {"_소리": "서재: 오르골풍 짧은 선율 (3분마다, 아주 작게)", "len": 5.0, "peak_db": -12.0,
                         "reverb": {"mix": 0.35, "time": 1.2},
                         "layers": [{"wave": "sine", "freq": round(440 * 2 ** ((m - 69) / 12), 2), "start": s, "len": 1.2,
                                     "harm": [[2.0, 0.3], [4.1, 0.08]], "env": {"a": 0.002, "d": 0.6, "s": 0.0, "r": 0.4},
                                     "gain": 0.3} for s, m in notes]}
    # ── 문 (바깥 버전 또렷 / 실내 버전 먹먹) ──
    for kind, base, ring in (("wood", 300, 950), ("heavy", 190, 620)):
        creak = {"wave": "saw", "freq": [base, base * 0.8], "len": 0.34, "filter": {"type": "bp", "f": [ring, ring * 0.75], "q": 3.0,
                                                                                          "track": False},
                 "env": {"a": 0.03, "d": 0.2, "s": 0.3, "r": 0.1}, "gain": 0.22}
        latch = tick(0.0, 1900 if kind == "wood" else 1300, 0.6, 0.02, 3.0)
        out[f"door_{kind}_open"] = {"_소리": f"문 여는 소리 ({kind}, 바깥 — 또렷하게)", "len": 0.5, "peak_db": -10.0,
                                    "layers": [latch, dict(creak, start=0.05)]}
        out[f"door_{kind}_open_in"] = {"_소리": f"문 여는 소리 ({kind}, 실내 쪽)", "len": 0.5, "peak_db": -11.0,
                                       "reverb": {"mix": 0.2, "time": 0.2},
                                       "layers": [latch, dict(creak, start=0.05, filter=dict(creak["filter"], f=[ring * 0.8, ring * 0.6]))]}
        out[f"door_{kind}_close_in"] = {"_소리": f"문 닫는 소리 ({kind}, 실내 — '툭')", "len": 0.35, "peak_db": -10.0,
                                        "reverb": {"mix": 0.18, "time": 0.15}, "layers": [
                                            {"wave": "noise", "len": 0.1, "filter": {"type": "lp", "f": [420, 200], "q": 0.8, "track": False},
                                             "env": {"a": 0.002, "d": 0.05, "s": 0.1, "r": 0.04}, "gain": 0.6},
                                            {"wave": "sine", "freq": [110 if kind == "wood" else 80, 60], "len": 0.16,
                                             "env": {"a": 0.002, "d": 0.1, "s": 0, "r": 0.05}, "gain": 0.5}]}
    return out


def main() -> None:
    """data/sfx_recipes.json 의 다른 항목은 글자 그대로 두고, room_*·door_* 줄만 (지우고) 끝에 다시 붙인다."""
    text = open(PATH, encoding="utf-8").read()
    keep = [ln for ln in text.rstrip().split("\n") if not ln.startswith((' "room_', ' "door_'))]
    assert keep[-1].strip() == "}", "마지막 줄이 } 이어야 함"
    body = keep[:-1]
    if not body[-1].rstrip().endswith(","):
        body[-1] = body[-1].rstrip() + ","
    new = recipes()
    add = [f" {json.dumps(k, ensure_ascii=False)}: {json.dumps(v, ensure_ascii=False)}," for k, v in new.items()]
    add[-1] = add[-1].rstrip(",")
    open(PATH, "w", encoding="utf-8").write("\n".join(body + add + ["}"]) + "\n")
    json.load(open(PATH, encoding="utf-8"))
    print("room/door 레시피", len(new))


if __name__ == "__main__":
    main()
