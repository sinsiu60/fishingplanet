"""플레이 기록 (JOURNEY.md 📏, DESIGN 54-5): 최근 50세션 + 낚시터별 머문 시간. 기기 밖으로 자동 전송 없음 — [기록 복사]로만.

세션 하나 = 세이브를 불러와 다른 세이브 · 타이틀로 나갈 때까지. game.py 프레임마다 tick (설정 'play_log' 끄면 기록 안 함).
저장: save.data["play_log"] = {"sessions": [{start, end, min, spot0, spot1, catch, legend, exam, last}], "spot_sec": {낚시터: 초}}.
"""
import time

MAX_SESSIONS = 50


def state(save) -> dict:
    st = save.data.setdefault("play_log", {})
    st.setdefault("sessions", [])
    st.setdefault("spot_sec", {})
    return st


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M")


def _counts(save) -> tuple[int, int, int]:
    from src.core.config import load_json
    from src.save import exam
    legends = {f["id"] for f in load_json("fish.json")["fish"] if f["rarity"] == "legend"}
    leg = sum(1 for fid in legends if save.caught(fid))
    return int(save.data.get("stats", {}).get("catches", 0)), leg, exam.passed(save)


def scene_label(game) -> tuple[str, str | None]:
    """(마지막 화면 이름, 낚시 중이면 낚시터 id)."""
    sc = game.scenes.current
    name = type(sc).__name__ if sc is not None else ""
    from src.scene.fishing_scene import FishingScene
    fishing = next((s for s in game.scenes.stack if isinstance(s, FishingScene)), None)
    if isinstance(sc, FishingScene):
        if sc.backdrop is not None:
            return "마을", None
        from src.save.journey import spot_short
        return f"낚시 · {spot_short(sc.spot_id)}", sc.spot_id
    labels = {"VillageScene": "마을", "InteriorScene": "건물 안", "HomeScene": "집", "MapScene": "지도", "ShopScene": "상점",
              "DexScene": "도감", "DexDetailScene": "도감", "ExamScene": "백 노인의 시험", "CalendarScene": "달력",
              "CampfireScene": "모닥불", "SettingsScene": "설정", "PauseScene": "일시 정지", "InventoryScene": "가방",
              "ChestScene": "보물상자", "QuestBoardScene": "의뢰 게시판", "CutsceneScene": "이야기 장면",
              "TravelScene": "이동", "VoyageScene": "항해", "EndingScene": "엔딩", "TrainingScene": "훈련 수조",
              "AchievementsScene": "업적", "TitleScene": "타이틀", "PlayLogScene": "플레이 기록", "JournalScene": "낚시 일지",
              "MemoriesScene": "추억", "PhotoScene": "사진", "PrintGalleryScene": "어탁", "EpilogueScene": "에필로그",
              "RemainingScene": "남은 이야기"}
    lab = labels.get(name, name or "?")
    return lab, (fishing.spot_id if fishing is not None and lab == "?" else None)


def tick(game, dt: float) -> None:
    save = game.save
    if save is None or not game.settings.get("play_log"):
        return
    st = state(save)
    if getattr(game, "_plog_save", None) is not save:   # 새 세션 (세이브를 불러옴)
        game._plog_save = save
        game._plog_acc = 0.0
        c, lg, ex = _counts(save)
        lab, spot = scene_label(game)
        st["sessions"].append({"start": _now(), "end": _now(), "min": 0.0, "spot0": spot or save.data.get("spot"),
                               "spot1": spot or save.data.get("spot"), "c0": c, "l0": lg, "e0": ex,
                               "catch": 0, "legend": 0, "exam": [], "last": lab})
        del st["sessions"][:-MAX_SESSIONS]
    s = st["sessions"][-1]
    s["min"] = s.get("min", 0.0) + dt / 60.0
    lab, spot = scene_label(game)
    if spot is not None:
        st["spot_sec"][spot] = st["spot_sec"].get(spot, 0.0) + dt
        s["spot1"] = spot
        if not s.get("spot0"):
            s["spot0"] = spot
    game._plog_acc = getattr(game, "_plog_acc", 0.0) + dt
    if game._plog_acc >= 5.0:   # 5초마다 끝 시각 · 포획 · 시험 (꺼져도 마지막 기록이 남게)
        game._plog_acc = 0.0
        c, lg, ex = _counts(save)
        s["end"] = _now()
        s["catch"] = c - s.get("c0", c)
        s["legend"] = lg - s.get("l0", lg)
        s["exam"] = [t for t in range(s.get("e0", ex) + 1, ex + 1)]
        s["last"] = lab


def text(save) -> str:
    """[기록 복사] 텍스트 — 사람이 읽고 개발자에게 보낼 수 있게."""
    from src.save.journey import spot_short
    st = state(save)
    lines = ["미니 피싱 플레이 기록", f"총 플레이 {int(save.data.get('playtime', 0) // 60)}분 · 세션 {len(st['sessions'])}개", ""]
    for s in st["sessions"]:
        sp = f"{_name(s.get('spot0'))}→{_name(s.get('spot1'))}"
        ex = (" · 시험 " + ",".join(f"T{t}" for t in s.get("exam", []))) if s.get("exam") else ""
        lines.append(f"{s['start']}~{s['end'][-5:]} {round(s.get('min', 0))}분 · {sp} · {s.get('catch', 0)}마리 · "
                     f"전설 {s.get('legend', 0)}{ex} · 마지막: {s.get('last', '?')}")
    lines.append("")
    lines.append("낚시터별 머문 시간")
    for sp, sec in sorted(st["spot_sec"].items(), key=lambda kv: -kv[1]):
        lines.append(f"  {spot_short(sp)} {round(sec / 60)}분")
    return "\n".join(lines)


def _name(sp) -> str:
    if not sp:
        return "?"
    try:
        from src.save.journey import spot_short
        return spot_short(sp)
    except StopIteration:
        return str(sp)
